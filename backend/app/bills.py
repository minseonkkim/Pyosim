"""법안 상세 허브 — Phase 1-3 (그물망 '법안' 축).

기획 2.1: 법안=발의·표결 정보 허브. 대표발의자·정당별 찬반·표결 의원이 모여
사람 축으로 다시 뻗는다(사람→법안→표결 의원→다시 사람, 그물망 닫힘).

🟡 중립성(기획 1.3): 공식 기록(의안정보시스템·열린국회정보)만, 출처 동반, 판정 배제.

엔드포인트:
  GET /api/bills/{id}   법안 상세(대표발의·처리 funnel·본회의 집계·정당별 찬반·표결 의원)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bill_content import fetch_bill_content
from app.bill_summary import summarize_bill
from app.config import settings
from app.db import get_db
from app.models import Bill, Party, Person, Vote, VoteChoice, VoteRecord
from app.persons import PartyBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bills", tags=["bills"])

NOTICE = (
    "법안 정보와 표결 기록은 국회 의안정보시스템·열린국회정보의 공식 데이터입니다. "
    "사실만 표시하며 가치 판단을 담지 않습니다."
)

SUMMARY_NOTICE = (
    "아래 좋은점·문제점은 공식 원문이 아니라 AI({model})가 제안이유·주요내용을 바탕으로 "
    "양쪽을 대칭되게 정리한 참고용 요약입니다. 찬반 판단은 담지 않으며, 판단은 원문을 보고 "
    "직접 하시길 권합니다."
)


# ───────────────────────── 스키마 ─────────────────────────
class ProposerBrief(BaseModel):
    id: int
    name: str
    party: PartyBrief | None


class VoteAggregate(BaseModel):
    session_date: date | None
    member_total: int | None
    vote_total: int | None
    yes: int | None
    no: int | None
    blank: int | None


class PartyVote(BaseModel):
    party: str
    color_hex: str | None
    yes: int
    no: int
    abstain: int
    absent: int


class Voter(BaseModel):
    id: int
    name: str
    party: str | None
    choice: str


class FunnelStep(BaseModel):
    label: str
    done: bool


class BillDetail(BaseModel):
    id: int
    bill_no: str
    title: str
    committee: str | None
    status: str | None
    proposed_date: date | None
    likms_url: str | None
    proposal_reason: str | None  # 제안이유(또는 제안이유 및 주요내용) — 의안원문 공식 텍스트
    main_content: str | None  # 주요내용(분리형일 때)
    summary_pros: list[str]  # AI 참고 요약 — 좋은점(대칭)
    summary_cons: list[str]  # AI 참고 요약 — 문제점(대칭)
    summary_notice: str | None  # AI 요약이 있을 때만 동봉하는 🟡 고지
    proposer: ProposerBrief | None
    vote: VoteAggregate | None  # 본회의 집계(있는 경우)
    party_breakdown: list[PartyVote]  # 정당별 찬반(의원별 기록 있을 때)
    voters: list[Voter]  # 표결 의원 → 프로필 연결(그물망)
    funnel: list[FunnelStep]
    notice: str


def _ensure_content(db: Session, bill: Bill) -> None:
    """본문 미수집 의안이면 likms 의안원문을 그 자리에서 받아 캐싱(on-demand).

    클릭한 법안은 (likms 에 원문이 있는 한) 항상 본문이 보이도록 보장한다.
    🟡 원문 그대로 저장(요약·판정 없음). 출처 = likms billDetail.
    네트워크/파싱 실패는 페이지를 막지 않도록 삼키고, content_fetched 를 남기지 않아
    다음 열람 때 재시도한다.
    """
    if bill.content_fetched is not None or not bill.assembly_bill_id:
        return
    try:
        reason, main = fetch_bill_content(bill.assembly_bill_id)
    except Exception:  # noqa: BLE001 — 본문 수집 실패가 법안 페이지를 막지 않도록
        logger.warning("법안 본문 on-demand 수집 실패 bill=%s", bill.id, exc_info=True)
        return
    bill.proposal_reason = reason
    bill.main_content = main
    bill.content_fetched = datetime.now(timezone.utc)
    db.commit()


def _ensure_summary(db: Session, bill: Bill) -> None:
    """본문이 있으나 AI 요약이 없으면 그 자리에서 생성해 캐싱(on-demand).

    🟡 원문은 건드리지 않고 좋은점/문제점만 별도 필드에 저장. 양쪽 대칭이 아니면(한쪽 공백)
    summarize_bill 이 (None, None) 을 돌려주며, 그 경우 summary_fetched 를 남기지 않아
    다음 열람 때 재시도한다. 키 없음/본문 없음/실패는 페이지를 막지 않는다.
    """
    if bill.summary_fetched is not None:
        return
    if not settings.gemini_api_key or not (bill.proposal_reason or bill.main_content):
        return
    try:
        pros, cons = summarize_bill(
            bill.title, bill.proposal_reason, bill.main_content,
            api_key=settings.gemini_api_key, model=settings.gemini_model,
        )
    except Exception:  # noqa: BLE001 — 요약 실패가 법안 페이지를 막지 않도록
        logger.warning("법안 AI 요약 on-demand 생성 실패 bill=%s", bill.id, exc_info=True)
        return
    if not pros or not cons:  # 대칭 깨짐 → 저장 안 하고 다음에 재시도
        return
    bill.summary_pros = pros
    bill.summary_cons = cons
    bill.summary_model = settings.gemini_model
    bill.summary_fetched = datetime.now(timezone.utc)
    db.commit()


@router.get("/{bid}", response_model=BillDetail)
def get_bill(bid: int, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.get(Bill, bid)
    if bill is None:
        raise HTTPException(status_code=404, detail="해당 법안을 찾을 수 없습니다.")

    # 본문 미수집이면 그 자리에서 받아 캐싱(on-demand) → 본문 위에 AI 요약도 보강
    _ensure_content(db, bill)
    _ensure_summary(db, bill)

    # 대표발의자
    proposer = None
    if bill.proposer_id:
        p = db.get(Person, bill.proposer_id)
        if p is not None:
            proposer = ProposerBrief(
                id=p.id, name=p.name,
                party=PartyBrief(name=p.party.name, color_hex=p.party.color_hex)
                if p.party else None,
            )

    # 본회의 집계(의안당 0~1건)
    vote = db.scalars(
        select(Vote).where(Vote.bill_id == bid).order_by(Vote.session_date.desc().nullslast())
    ).first()
    vote_out = None
    party_breakdown: list[PartyVote] = []
    voters: list[Voter] = []
    if vote is not None:
        vote_out = VoteAggregate(
            session_date=vote.session_date,
            member_total=vote.member_total, vote_total=vote.vote_total,
            yes=vote.yes_total, no=vote.no_total, blank=vote.blank_total,
        )
        # 의원별 기록(있으면 정당별 분해 + 표결 의원 명단)
        rows = db.execute(
            select(Person.id, Person.name, Party.name, Party.color_hex, VoteRecord.choice)
            .join(Person, Person.id == VoteRecord.person_id)
            .outerjoin(Party, Party.id == Person.party_id)
            .where(VoteRecord.vote_id == vote.id)
            .order_by(Party.name, Person.name)
        ).all()
        agg: dict[str, dict] = defaultdict(
            lambda: {"color": None, "yes": 0, "no": 0, "abstain": 0, "absent": 0}
        )
        key = {
            VoteChoice.찬성: "yes", VoteChoice.반대: "no",
            VoteChoice.기권: "abstain", VoteChoice.불참: "absent",
        }
        for pid, pname, party_name, color, choice in rows:
            pn = party_name or "무소속"
            agg[pn]["color"] = color
            agg[pn][key[choice]] += 1
            voters.append(Voter(id=pid, name=pname, party=party_name, choice=choice.value))
        party_breakdown = [
            PartyVote(
                party=pn, color_hex=v["color"],
                yes=v["yes"], no=v["no"], abstain=v["abstain"], absent=v["absent"],
            )
            for pn, v in sorted(agg.items(), key=lambda kv: -sum(
                x for k, x in kv[1].items() if k != "color"
            ))
        ]

    funnel = [
        FunnelStep(label="발의", done=bill.proposed_date is not None),
        FunnelStep(label="위원회", done=bill.committee is not None),
        FunnelStep(label="본회의", done=vote is not None),
        FunnelStep(label="처리", done=bool(bill.status)),
    ]

    pros = bill.summary_pros.split("\n") if bill.summary_pros else []
    cons = bill.summary_cons.split("\n") if bill.summary_cons else []
    summary_notice = (
        SUMMARY_NOTICE.format(model=bill.summary_model or "생성 모델")
        if (pros and cons) else None
    )

    return BillDetail(
        id=bill.id, bill_no=bill.bill_no, title=bill.title,
        committee=bill.committee, status=bill.status,
        proposed_date=bill.proposed_date, likms_url=bill.likms_url,
        proposal_reason=bill.proposal_reason, main_content=bill.main_content,
        summary_pros=pros, summary_cons=cons, summary_notice=summary_notice,
        proposer=proposer, vote=vote_out,
        party_breakdown=party_breakdown, voters=voters, funnel=funnel,
        notice=NOTICE,
    )
