"""민심과 다른 국회 — Phase 2 핵심 명제 (민심 vs 국회 불일치 통합 뷰).

시민이 표출한 민심(입법예고 의견·청원 동의)과 국회의 응답(표결·처리)이 갈린 사안을
법안·청원 가리지 않고 한 화면에 모은다. 두 종류:
  - 법안: 입법예고에 시민 다수가 반대(또는 찬성)했는데 본회의 표결이 반대로 감.
  - 청원: 시민이 동의(국민동의청원 등)했는데 국회가 거부(불부의·폐기)하거나 방치(계류).

🟡 중립성(기획 1.3): 주제로 거르지 않는다(정쟁 필터 없음). 탄핵·정당 청원도 정책 청원과
  '같은 기준·같은 양식'으로 나열한다 — 어떤 민심은 세고 어떤 건 빼는 게 오히려 편집이므로.
  사실(의견·동의 수, 공식 처리결과)만 병치하고 옳고 그름을 판단하지 않는다.
  단, 입법예고 의견은 자발적 참여라 반대 쪽으로 기우는 경향이 있어 '여론 전체'는 아니다(고지).

엔드포인트:
  GET /api/mismatch   법안·청원 통합, 민심 규모(의견/동의 수) 큰 순.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bill, LawNotice, Petition, Vote

router = APIRouter(prefix="/api/mismatch", tags=["mismatch"])

# 청원 포함 문턱 — 국민동의청원 회부 기준(5만). 이만큼 모인 '검증된 강한 민심'만 다룬다.
# (의원소개 등 소수 동의 청원이 불부의된 건 '민심 무시'로 보기 어려워 제외 — 거부·방치 공통.)
MIN_SIGN = 50_000
# 법안 입법예고 의견 문턱 — 의견 1~2건짜리는 '민심'으로 보기 어려워 제외(참여가 있었던 것만).
MIN_OPINION = 100

NOTICE = (
    "시민이 입법예고에 의견을 내거나(주로 반대) 청원에 동의한 수와, 국회의 표결·처리 결과가 "
    "다르게 간 사안입니다. 주제로 거르지 않고 모든 사안을 같은 기준(의견·동의 수, 공식 처리결과)으로 "
    "사실 그대로 나열합니다. 입법예고 의견은 자발적 참여라 반대 쪽으로 기우는 경향이 있어 "
    "'여론 전체'가 아니라 '의견을 낸 시민들의 분포'입니다."
)


class MismatchItem(BaseModel):
    kind: str  # "bill" | "petition"
    ref_id: int
    href: str  # /bill/{id} or /petition/{id}
    title: str
    committee: str | None
    category: str | None  # 법안만(청원은 None)
    # 민심 쪽
    voice_count: int  # 입법예고 반대(또는 찬성) 의견 수 / 청원 동의 인원
    voice_label: str  # "반대" / "찬성" / "동의"
    voice_source: str  # "입법예고 의견" / "국민동의청원" / "청원"
    # 국회 응답 쪽
    response_label: str  # "가결" / "부결" / "본회의 불부의" / "계류" 등(공식 표기)
    response_kind: str  # "passed" | "rejected" | "pending"
    detail: str | None  # 표결 "찬 174 · 반 0" / 청원 "접수 320일째"


class MismatchFeed(BaseModel):
    items: list[MismatchItem]
    notice: str


def _bill_items(db: Session, limit: int) -> list[MismatchItem]:
    """법안: 입법예고 시민 다수 입장 ≠ 본회의 표결 결과. (정쟁 필터 없음 — 사실 그대로)"""
    q = (
        select(Bill, LawNotice, Vote)
        .join(LawNotice, LawNotice.bill_no == Bill.bill_no)
        .join(Vote, Vote.bill_id == Bill.id)
        .where(
            LawNotice.opinion_total.isnot(None), LawNotice.opinion_total >= MIN_OPINION,
            LawNotice.agree_count.isnot(None), LawNotice.oppose_count.isnot(None),
            Vote.yes_total.isnot(None), Vote.no_total.isnot(None),
            or_(
                and_(LawNotice.oppose_count > LawNotice.agree_count, Vote.yes_total > Vote.no_total),
                and_(LawNotice.agree_count > LawNotice.oppose_count, Vote.no_total > Vote.yes_total),
            ),
        )
        .order_by(LawNotice.opinion_total.desc())
        .limit(limit)
    )
    items: list[MismatchItem] = []
    for bill, ln, v in db.execute(q).all():
        oppose_lead = (ln.oppose_count or 0) > (ln.agree_count or 0)
        passed = (v.yes_total or 0) > (v.no_total or 0)
        items.append(MismatchItem(
            kind="bill", ref_id=bill.id, href=f"/bill/{bill.id}", title=bill.title,
            committee=bill.committee, category=bill.category,
            voice_count=max(ln.oppose_count or 0, ln.agree_count or 0),
            voice_label="반대" if oppose_lead else "찬성", voice_source="입법예고 의견",
            response_label="가결" if passed else "부결",
            response_kind="passed" if passed else "rejected",
            detail=f"찬 {v.yes_total} · 반 {v.no_total}",
        ))
    return items


def _petition_items(db: Session, limit: int) -> list[MismatchItem]:
    """청원: 동의했는데 거부(불부의·폐기) 또는 고동의인데 방치(계류). (모든 주제 동일 기준)"""
    today = date.today()

    def _src(p: Petition) -> str:
        return "국민동의청원" if p.is_national_consent else "청원"

    items: list[MismatchItem] = []
    # 거부 — 처리결과가 있는(=처리완료) 청원. 공식 표기 그대로. 5만+ 동의만.
    rejected = db.scalars(
        select(Petition).where(
            Petition.proc_result.isnot(None),
            Petition.signature_count.isnot(None),
            Petition.signature_count >= MIN_SIGN,
        )
    ).all()
    for p in rejected:
        items.append(MismatchItem(
            kind="petition", ref_id=p.id, href=f"/petition/{p.id}", title=p.title,
            committee=p.committee, category=None,
            voice_count=p.signature_count or 0, voice_label="동의", voice_source=_src(p),
            response_label=p.proc_result or "처리완료", response_kind="rejected", detail=None,
        ))
    # 방치 — 고동의(5만+)인데 아직 계류.
    neglected = db.scalars(
        select(Petition).where(
            Petition.proc_result.is_(None),
            Petition.signature_count.isnot(None),
            Petition.signature_count >= MIN_SIGN,
        )
    ).all()
    for p in neglected:
        days = (today - p.proposed_date).days if p.proposed_date else None
        items.append(MismatchItem(
            kind="petition", ref_id=p.id, href=f"/petition/{p.id}", title=p.title,
            committee=p.committee, category=None,
            voice_count=p.signature_count or 0, voice_label="동의", voice_source=_src(p),
            response_label="계류", response_kind="pending",
            detail=(f"접수 {days}일째" if days is not None else None),
        ))
    return items


@router.get("", response_model=MismatchFeed)
def list_mismatch(limit: int = 300, db: Session = Depends(get_db)) -> MismatchFeed:
    """법안·청원 통합 — 민심 규모(의견/동의 수) 큰 순. 🟡 주제 무관 동일 기준."""
    items = _bill_items(db, limit) + _petition_items(db, limit)
    items.sort(key=lambda x: x.voice_count, reverse=True)
    return MismatchFeed(items=items[:limit], notice=NOTICE)
