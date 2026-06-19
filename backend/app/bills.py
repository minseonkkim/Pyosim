"""법안 상세 허브 — Phase 1-3 (그물망 '법안' 축).

기획 2.1: 법안=발의·표결 정보 허브. 대표발의자·정당별 찬반·표결 의원이 모여
사람 축으로 다시 뻗는다(사람→법안→표결 의원→다시 사람, 그물망 닫힘).

🟡 중립성(기획 1.3): 공식 기록(의안정보시스템·열린국회정보)만, 출처 동반, 판정 배제.

엔드포인트:
  GET /api/bills/{id}   법안 상세(대표발의·처리 funnel·본회의 집계·정당별 찬반·표결 의원)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bill, Party, Person, Vote, VoteChoice, VoteRecord
from app.persons import PartyBrief

router = APIRouter(prefix="/api/bills", tags=["bills"])

NOTICE = (
    "법안 정보와 표결 기록은 국회 의안정보시스템·열린국회정보의 공식 데이터입니다. "
    "사실만 표시하며 가치 판단을 담지 않습니다."
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
    proposer: ProposerBrief | None
    vote: VoteAggregate | None  # 본회의 집계(있는 경우)
    party_breakdown: list[PartyVote]  # 정당별 찬반(의원별 기록 있을 때)
    voters: list[Voter]  # 표결 의원 → 프로필 연결(그물망)
    funnel: list[FunnelStep]
    notice: str


@router.get("/{bid}", response_model=BillDetail)
def get_bill(bid: int, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.get(Bill, bid)
    if bill is None:
        raise HTTPException(status_code=404, detail="해당 법안을 찾을 수 없습니다.")

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

    return BillDetail(
        id=bill.id, bill_no=bill.bill_no, title=bill.title,
        committee=bill.committee, status=bill.status,
        proposed_date=bill.proposed_date, likms_url=bill.likms_url,
        proposer=proposer, vote=vote_out,
        party_breakdown=party_breakdown, voters=voters, funnel=funnel,
        notice=NOTICE,
    )
