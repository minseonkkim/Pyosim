"""감시견 알림 — Phase 2 리텐션 핵심 (기획 4 "감시견 알림").

시민이 청원·법안·의원을 '감시'(구독)하면, 그 대상의 진행이 바뀔 때 알린다.
이 앱은 계정·이메일·푸시 등록이 없는 익명 세션이라, OS 푸시 대신
**앱 내 '변화 알림' 받은함**(재방문 시 pull)으로 전달한다.

동작(스냅샷 diff):
  - 구독 시 대상의 '상태 서명'(snapshot, JSON)을 저장 → 기준선.
  - GET /api/watch 가 현재 상태를 다시 계산해 snapshot 과 비교 → 바뀐 것만 알림으로.
  - 사용자가 확인하면(POST seen) snapshot 을 현재로 갱신(읽음 처리).

🟡 중립성(기획 1.3):
  - 알림 문구는 단계 이동·경과일 같은 공식 사실만(판정·평가 없음).
  - 세션ID 외 개인정보 미저장(Event 와 동일 원칙).

엔드포인트:
  POST /api/watch/subscribe     대상 구독(현재 상태 스냅샷)
  POST /api/watch/unsubscribe   구독 해제
  GET  /api/watch/check         특정 대상 구독 여부(상세 페이지 토글 초기값)
  GET  /api/watch               내 구독 목록 + 변화 알림(받은함) + 안 읽은 수
  POST /api/watch/seen          알림 읽음 처리(스냅샷을 현재로 갱신)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bill, Person, Petition, Subscription, VoteRecord

router = APIRouter(prefix="/api/watch", tags=["watch"])

KINDS = ("petition", "bill", "person")

NOTICE = (
    "감시 알림은 국회 공식 기록(의안정보시스템·열린국회정보)의 단계 변화만 사실 그대로 전합니다. "
    "가치 판단을 담지 않으며, 세션 외 개인정보는 저장하지 않습니다."
)


# ───────────────────────── 상태 서명·변화 계산 ─────────────────────────
def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def _petition_state(p: Petition) -> dict:
    return {
        "proc_result": p.proc_result,
        "committee": p.committee,
        "referred": p.committee_date is not None,
    }


def _bill_state(b: Bill) -> dict:
    return {
        "status": b.status,
        "committee_proc": _iso(b.committee_proc_date),
        "law_proc": _iso(b.law_proc_date),
        "plenary_proc": _iso(b.plenary_proc_date),
        "announce": _iso(b.announce_date),
    }


def _person_state(db: Session, person_id: int) -> dict:
    proposed = db.scalar(
        select(func.count()).select_from(Bill).where(Bill.proposer_id == person_id)
    ) or 0
    votes = db.scalar(
        select(func.count()).select_from(VoteRecord).where(VoteRecord.person_id == person_id)
    ) or 0
    return {"proposed_count": proposed, "vote_count": votes}


# 법안 단계 키 → 사람이 읽는 단계명
_BILL_STAGE_LABEL = {
    "committee_proc": "소관위 의결",
    "law_proc": "법사위(체계·자구) 의결",
    "plenary_proc": "본회의 의결",
    "announce": "공포",
}


def _petition_changes(old: dict, new: dict) -> list[str]:
    out: list[str] = []
    if not old.get("proc_result") and new.get("proc_result"):
        out.append(f"처리됐어요 — 결과: {new['proc_result']}")
    if not old.get("referred") and new.get("referred"):
        cmte = new.get("committee") or "소관 위원회"
        out.append(f"{cmte}에 회부됐어요")
    elif old.get("committee") and new.get("committee") and old["committee"] != new["committee"]:
        out.append(f"소관 위원회가 {new['committee']}(으)로 바뀌었어요")
    return out


def _bill_changes(old: dict, new: dict) -> list[str]:
    out: list[str] = []
    for key, label in _BILL_STAGE_LABEL.items():
        if not old.get(key) and new.get(key):
            out.append(f"{label} 단계를 통과했어요 ({new[key]})")
    if old.get("status") and new.get("status") and old["status"] != new["status"]:
        out.append(f"처리 상태가 '{new['status']}'(으)로 바뀌었어요")
    return out


def _person_changes(old: dict, new: dict) -> list[str]:
    out: list[str] = []
    dp = (new.get("proposed_count") or 0) - (old.get("proposed_count") or 0)
    if dp > 0:
        out.append(f"새 대표발의 {dp}건이 추가됐어요")
    dv = (new.get("vote_count") or 0) - (old.get("vote_count") or 0)
    if dv > 0:
        out.append(f"새 표결 참여 {dv}건이 기록됐어요")
    return out


def _current_state(db: Session, kind: str, ref_id: int) -> tuple[dict, str] | None:
    """대상의 현재 상태 dict + 표시 제목. 대상이 없으면 None."""
    if kind == "petition":
        p = db.get(Petition, ref_id)
        return (_petition_state(p), p.title) if p else None
    if kind == "bill":
        b = db.get(Bill, ref_id)
        return (_bill_state(b), b.title) if b else None
    if kind == "person":
        p = db.get(Person, ref_id)
        return (_person_state(db, ref_id), p.name) if p else None
    return None


def _diff(kind: str, old: dict, new: dict) -> list[str]:
    if kind == "petition":
        return _petition_changes(old, new)
    if kind == "bill":
        return _bill_changes(old, new)
    if kind == "person":
        return _person_changes(old, new)
    return []


def _href(kind: str, ref_id: int) -> str:
    return {"petition": "/petition", "bill": "/bill", "person": "/person"}[kind] + f"/{ref_id}"


# ───────────────────────── 스키마 ─────────────────────────
class WatchTarget(BaseModel):
    session_id: str
    kind: str  # petition / bill / person
    ref_id: int


class WatchToggleResult(BaseModel):
    subscribed: bool


class WatchItem(BaseModel):
    kind: str
    ref_id: int
    title: str
    href: str
    changes: list[str]  # 변화 알림(있으면 '안 읽음') — 🟡 사실 문구만
    has_update: bool
    created_at: datetime


class WatchFeed(BaseModel):
    items: list[WatchItem]
    unread: int  # 변화가 있는 구독 수(뱃지)
    total: int  # 구독 총수
    notice: str


# ───────────────────────── 엔드포인트 ─────────────────────────
def _validate_kind(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 구독 종류입니다: {kind}")


@router.post("/subscribe", response_model=WatchToggleResult)
def subscribe(body: WatchTarget, db: Session = Depends(get_db)) -> WatchToggleResult:
    """대상을 감시 목록에 추가하고 현재 상태를 스냅샷으로 저장(이후 변화의 기준선)."""
    _validate_kind(body.kind)
    cur = _current_state(db, body.kind, body.ref_id)
    if cur is None:
        raise HTTPException(status_code=404, detail="감시할 대상을 찾을 수 없습니다.")
    state, _title = cur

    existing = db.scalar(
        select(Subscription).where(
            Subscription.session_id == body.session_id,
            Subscription.kind == body.kind,
            Subscription.ref_id == body.ref_id,
        )
    )
    now = datetime.now(timezone.utc)
    if existing is None:
        db.add(
            Subscription(
                session_id=body.session_id,
                kind=body.kind,
                ref_id=body.ref_id,
                snapshot=json.dumps(state, sort_keys=True, ensure_ascii=False),
                last_seen_at=now,
            )
        )
        db.commit()
    return WatchToggleResult(subscribed=True)


@router.post("/unsubscribe", response_model=WatchToggleResult)
def unsubscribe(body: WatchTarget, db: Session = Depends(get_db)) -> WatchToggleResult:
    _validate_kind(body.kind)
    existing = db.scalar(
        select(Subscription).where(
            Subscription.session_id == body.session_id,
            Subscription.kind == body.kind,
            Subscription.ref_id == body.ref_id,
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
    return WatchToggleResult(subscribed=False)


@router.get("/check", response_model=WatchToggleResult)
def check(
    session_id: str,
    kind: str,
    ref_id: int,
    db: Session = Depends(get_db),
) -> WatchToggleResult:
    """상세 페이지 '감시하기' 토글 초기값."""
    _validate_kind(kind)
    existing = db.scalar(
        select(Subscription).where(
            Subscription.session_id == session_id,
            Subscription.kind == kind,
            Subscription.ref_id == ref_id,
        )
    )
    return WatchToggleResult(subscribed=existing is not None)


@router.get("", response_model=WatchFeed)
def list_watch(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
) -> WatchFeed:
    """내 구독 목록 + 변화 알림(받은함). 변화 있는 구독을 위로, 안 읽은 수를 뱃지로."""
    subs = db.scalars(
        select(Subscription)
        .where(Subscription.session_id == session_id)
        .order_by(Subscription.created_at.desc())
    ).all()

    items: list[WatchItem] = []
    unread = 0
    for s in subs:
        cur = _current_state(db, s.kind, s.ref_id)
        if cur is None:
            continue  # 대상이 사라졌으면 조용히 건너뜀
        state, title = cur
        try:
            old = json.loads(s.snapshot) if s.snapshot else {}
        except (TypeError, ValueError):
            old = {}
        changes = _diff(s.kind, old, state)
        if changes:
            unread += 1
        items.append(
            WatchItem(
                kind=s.kind,
                ref_id=s.ref_id,
                title=title,
                href=_href(s.kind, s.ref_id),
                changes=changes,
                has_update=bool(changes),
                created_at=s.created_at,
            )
        )

    # 변화 있는 것 먼저, 그다음 최신 구독순(items 는 이미 구독 최신순)
    items.sort(key=lambda it: (not it.has_update,))
    return WatchFeed(items=items, unread=unread, total=len(items), notice=NOTICE)


class SeenBody(BaseModel):
    session_id: str
    kind: str | None = None  # 특정 대상만 읽음. 없으면 전체.
    ref_id: int | None = None


@router.post("/seen")
def mark_seen(body: SeenBody, db: Session = Depends(get_db)) -> dict[str, int]:
    """알림 읽음 처리 — 해당 구독의 snapshot 을 현재 상태로 갱신(다음 diff 기준선 이동)."""
    stmt = select(Subscription).where(Subscription.session_id == body.session_id)
    if body.kind and body.ref_id is not None:
        _validate_kind(body.kind)
        stmt = stmt.where(Subscription.kind == body.kind, Subscription.ref_id == body.ref_id)
    subs = db.scalars(stmt).all()

    now = datetime.now(timezone.utc)
    updated = 0
    for s in subs:
        cur = _current_state(db, s.kind, s.ref_id)
        if cur is None:
            continue
        state, _title = cur
        s.snapshot = json.dumps(state, sort_keys=True, ensure_ascii=False)
        s.last_seen_at = now
        updated += 1
    db.commit()
    return {"updated": updated}
