"""정치인 프로필 허브 — Phase 1-2 (그물망 '사람' 축).

기획 2.1: 사람=프로필 허브. 정당·지역구·발의/표결 법안·전과가 한 곳에 모이고,
각 항목이 법안·지역 축으로 뻗는 그물망의 입구가 된다.

🟡 중립성(기획 1.3):
  - 모든 정치인을 **같은 스키마·같은 양식**으로 반환(특정인 부각 금지).
  - 전과·출석률 등 민감 항목은 **공식 기록 + 출처 링크**에 근거해 사실만. 가치판단 배제.
  - 순위/점수 없이 나열. 판정은 사용자 몫.

엔드포인트:
  GET /api/persons           정치인 목록(정당·지역 필터/이름 검색)
  GET /api/persons/{id}      프로필 상세(발의 법안·표결 요약·전과·출처)
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bill, Party, Person, VoteChoice, VoteRecord

router = APIRouter(prefix="/api/persons", tags=["persons"])

# 🟡 모든 프로필에 동봉되는 중립 고지(동일 양식·사실만).
NOTICE = (
    "모든 정치인을 같은 양식으로, 공식 기록과 출처 링크에 근거해 표시합니다. "
    "가치 판단이나 순위를 담지 않습니다."
)


# ───────────────────────── 스키마 ─────────────────────────
class PartyBrief(BaseModel):
    name: str
    color_hex: str | None


class PersonListItem(BaseModel):
    id: int
    name: str
    party: PartyBrief | None
    district: str | None
    photo_url: str | None


class BillBrief(BaseModel):
    id: int
    bill_no: str
    title: str
    status: str | None
    likms_url: str | None


class CriminalOut(BaseModel):
    charge: str  # 죄명
    sentence: str | None  # 형량
    date_sentenced: date | None
    is_final: bool | None  # 확정 여부
    source_url: str | None  # 🟡 출처


class VoteSummary(BaseModel):
    yes: int
    no: int
    abstain: int
    absent: int
    total: int


class PersonProfile(BaseModel):
    id: int
    name: str
    party: PartyBrief | None
    district: str | None
    photo_url: str | None
    attendance_rate: float | None
    profile_source_url: str | None
    last_verified: datetime | None
    proposed_bills: list[BillBrief]  # 대표발의 법안 → 법안 페이지로 연결(그물망)
    vote_summary: VoteSummary  # 본회의 표결 참여 집계
    criminal_records: list[CriminalOut]
    notice: str


def _party_brief(p: Party | None) -> PartyBrief | None:
    return PartyBrief(name=p.name, color_hex=p.color_hex) if p else None


# ───────────────────────── 엔드포인트 ─────────────────────────
@router.get("", response_model=list[PersonListItem])
def list_persons(
    party: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
) -> list[PersonListItem]:
    stmt = select(Person)
    if party:
        stmt = stmt.join(Party, Party.id == Person.party_id).where(Party.name == party)
    if q:
        stmt = stmt.where(Person.name.contains(q))
    stmt = stmt.order_by(Person.name)
    return [
        PersonListItem(
            id=p.id,
            name=p.name,
            party=_party_brief(p.party),
            district=p.district,
            photo_url=p.photo_url,
        )
        for p in db.scalars(stmt).all()
    ]


@router.get("/{pid}", response_model=PersonProfile)
def get_person(pid: int, db: Session = Depends(get_db)) -> PersonProfile:
    person = db.get(Person, pid)
    if person is None:
        raise HTTPException(status_code=404, detail="해당 정치인을 찾을 수 없습니다.")

    proposed = db.scalars(
        select(Bill)
        .where(Bill.proposer_id == pid)
        .order_by(Bill.proposed_date.desc().nullslast(), Bill.id.desc())
    ).all()

    counts: Counter = Counter()
    for (choice,) in db.execute(
        select(VoteRecord.choice).where(VoteRecord.person_id == pid)
    ).all():
        counts[choice] += 1
    vote_summary = VoteSummary(
        yes=counts[VoteChoice.찬성],
        no=counts[VoteChoice.반대],
        abstain=counts[VoteChoice.기권],
        absent=counts[VoteChoice.불참],
        total=sum(counts.values()),
    )

    return PersonProfile(
        id=person.id,
        name=person.name,
        party=_party_brief(person.party),
        district=person.district,
        photo_url=person.photo_url,
        attendance_rate=person.attendance_rate,
        profile_source_url=person.profile_source_url,
        last_verified=person.last_verified,
        proposed_bills=[
            BillBrief(
                id=b.id, bill_no=b.bill_no, title=b.title,
                status=b.status, likms_url=b.likms_url,
            )
            for b in proposed
        ],
        vote_summary=vote_summary,
        criminal_records=[
            CriminalOut(
                charge=c.charge, sentence=c.sentence,
                date_sentenced=c.date_sentenced, is_final=c.is_final,
                source_url=c.source_url,
            )
            for c in person.criminal_records
        ],
        notice=NOTICE,
    )
