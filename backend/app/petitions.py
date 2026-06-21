"""청원 추적 허브 — Phase 2 기능 A (민심 레이어 '시민 발화' 축).

기획 4.1(기능 A): 시민이 올린 청원이 접수→소관위 회부→심사→처리 중
'지금 어느 단계에 멈춰 있는지'를 공식 일자로 드러낸다("그 청원 지금 어디?").
민심(청원)과 국회(처리)의 거리를 사실로 보여주는 첫 축.

🟡 중립성(기획 1.3):
  - 발안자 개인정보 최소화 — 공개 기록(likms) 값만, 동의 인원수를 헤드라인으로.
  - 처리결과는 공식 코드 원문 그대로(판정·가치 평가 없음).
  - 모든 청원을 같은 양식으로 나열(순위·추천 없음).

엔드포인트:
  GET /api/petitions        청원 목록(상태 필터·검색) — '지금 어디' 카드
  GET /api/petitions/{id}   청원 상세(처리 단계 타임라인·출처)
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Petition

router = APIRouter(prefix="/api/petitions", tags=["petitions"])

NOTICE = (
    "청원 정보는 국회 의안정보시스템·열린국회정보의 공식 기록입니다. "
    "발안자 개인정보는 최소화하고, 처리결과는 공식 표기 그대로 표시하며 가치 판단을 담지 않습니다."
)


# ───────────────────────── 스키마 ─────────────────────────
class PetitionStage(BaseModel):
    label: str
    date: date | None  # 단계 공식 일자(있으면) — 🟡 그대로
    done: bool


class PetitionCard(BaseModel):
    id: int
    title: str
    committee: str | None  # 소관 위원회(현재 위치)
    is_national_consent: bool  # 국민동의청원 여부
    signature_count: int | None  # 동의 인원(헤드라인)
    proposed_date: date | None
    status: str  # 계류 / 처리완료
    proc_result: str | None  # 처리결과(공식 코드) — 처리완료일 때
    days_pending: int | None  # 계류 중일 때 접수 후 경과일(= '얼마나 멈췄나' 사실)


class PetitionDetail(BaseModel):
    id: int
    bill_no: str
    title: str
    proposer: str | None  # 청원인(원문) — 🟡 최소화 위해 화면은 인원수 강조
    introducer: str | None  # 소개(국민동의청원/○○의원)
    is_national_consent: bool
    signature_count: int | None
    committee: str | None
    proposed_date: date | None
    committee_date: date | None
    status: str
    proc_result: str | None
    days_pending: int | None
    referred_days: int | None  # 소관위 회부 후 경과일(= '위원회에서 얼마나 멈췄나')
    stall_line: str | None  # 멈춘 단계 한 줄(예: "법사위 회부 448일째 — 위원회 미상정")
    stall_note: str | None  # 왜 계류되는지 구조적 설명(계류일 때만) — 🟡 분노가 아닌 이해
    stages: list[PetitionStage]  # 접수→회부→처리 타임라인
    likms_url: str | None
    last_verified: datetime | None
    notice: str


class PetitionFeed(BaseModel):
    items: list[PetitionCard]
    pending: int  # 계류 중 건수
    done: int  # 처리완료 건수
    notice: str


def _status(p: Petition) -> str:
    return "처리완료" if p.proc_result else "계류"


STALL_NOTE = (
    "국회 청원은 법안과 달리 처리 시한이 없어서, 소관 위원회가 안건으로 상정하지 않으면 "
    "계속 계류됩니다. 22대 임기(2028년 5월)가 끝날 때까지 처리되지 않으면 자동 폐기돼요. "
    "거부 결정이 아니라, 시간이 지나며 무산되는 경로입니다."
)


def _referred_days(p: Petition) -> int | None:
    """소관위 회부 후 경과일 — 계류 청원이 '위원회 심사 단계에서' 얼마나 멈췄나(사실)."""
    if p.proc_result or p.committee_date is None:
        return None
    return (date.today() - p.committee_date).days


def _stall_line(p: Petition) -> str | None:
    """멈춘 지점 한 줄 — 🟡 사실만(회부 N일째·미상정 / 회부 전). 계류일 때만."""
    if p.proc_result:
        return None
    rd = _referred_days(p)
    if rd is not None:
        cmte = p.committee or "소관 위원회"
        return f"{cmte} 회부 {rd}일째 — 아직 위원회 심사에 상정되지 않았어요."
    return "접수됐지만 아직 소관 위원회 회부 전이에요."


def _days_pending(p: Petition) -> int | None:
    """계류 중인 청원의 접수 후 경과일 — '얼마나 오래 멈췄나'를 사실로."""
    if p.proc_result or p.proposed_date is None:
        return None
    return (date.today() - p.proposed_date).days


def _stages(p: Petition) -> list[PetitionStage]:
    """청원 처리 단계 타임라인 — 공식 일자 있는 단계만 done(🟡 미도달은 '여기서 멈춤').

    API 가 주는 확정 일자는 접수일·회부일뿐. 처리완료(proc_result)면 마지막 단계 done.
    없는 단계 날짜는 단정하지 않고 null 로 둔다(판정 배제).
    """
    referred = p.committee_date is not None or p.committee is not None
    done = bool(p.proc_result)
    cmt_label = f"{p.committee} 회부" if p.committee else "소관위 회부"
    return [
        PetitionStage(label="접수", date=p.proposed_date, done=p.proposed_date is not None),
        PetitionStage(label=cmt_label, date=p.committee_date, done=referred),
        PetitionStage(label="위원회 심사", date=None, done=done),
        PetitionStage(label="처리", date=None, done=done),
    ]


# ───────────────────────── 엔드포인트 ─────────────────────────
@router.get("", response_model=PetitionFeed)
def list_petitions(
    status: str | None = None,  # 계류 / 처리완료
    q: str | None = None,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> PetitionFeed:
    """청원 목록 — 최근 접수순. status(계류/처리완료)·q(제목 검색)로 좁힌다.

    🟡 추천·순위 없이 같은 양식으로 나열. 기본은 접수일 최신순(진행 중 청원이 위로 오도록).
    """
    stmt = select(Petition)
    if q:
        stmt = stmt.where(Petition.title.contains(q))
    if status == "계류":
        stmt = stmt.where(Petition.proc_result.is_(None))
    elif status == "처리완료":
        stmt = stmt.where(Petition.proc_result.isnot(None))
    stmt = stmt.order_by(Petition.proposed_date.desc().nullslast(), Petition.id.desc()).limit(limit)
    rows = db.scalars(stmt).all()

    # 전체 집계(필터와 무관하게 칩에 쓰도록 별도 카운트)
    pending = db.scalar(
        select(func.count()).select_from(Petition).where(Petition.proc_result.is_(None))
    ) or 0
    total = db.scalar(select(func.count()).select_from(Petition)) or 0

    items = [
        PetitionCard(
            id=p.id, title=p.title, committee=p.committee,
            is_national_consent=p.is_national_consent,
            signature_count=p.signature_count,
            proposed_date=p.proposed_date,
            status=_status(p), proc_result=p.proc_result,
            days_pending=_days_pending(p),
        )
        for p in rows
    ]
    return PetitionFeed(
        items=items, pending=pending, done=total - pending, notice=NOTICE,
    )


@router.get("/{pid}", response_model=PetitionDetail)
def get_petition(pid: int, db: Session = Depends(get_db)) -> PetitionDetail:
    p = db.get(Petition, pid)
    if p is None:
        raise HTTPException(status_code=404, detail="해당 청원을 찾을 수 없습니다.")
    return PetitionDetail(
        id=p.id, bill_no=p.bill_no, title=p.title,
        proposer=p.proposer, introducer=p.introducer,
        is_national_consent=p.is_national_consent, signature_count=p.signature_count,
        committee=p.committee, proposed_date=p.proposed_date,
        committee_date=p.committee_date, status=_status(p), proc_result=p.proc_result,
        days_pending=_days_pending(p),
        referred_days=_referred_days(p), stall_line=_stall_line(p),
        stall_note=(None if p.proc_result else STALL_NOTE),
        stages=_stages(p),
        likms_url=p.source_url, last_verified=p.last_verified, notice=NOTICE,
    )
