"""예산 분야 → 상임위원회 → 법안·의원 그물망 — 기획서 4.6 핵심.

세금 계산기(/tax)에서 "내 세금이 사회복지에 219조" 를 본 사람을, 그 분야를
실제로 심의·감독하는 **국회 상임위원회**와 그 소관 **법안·소속 의원**으로 잇는다.
세금 → 분야(예산) → 위원회 → 법안·의원, 그물망이 닫힌다.

🟡 정직성(기획 1.3):
  - 예산 '항목'과 법안을 1:1로 연결한 게 아니다(원 단위 추적 불가). 분야 예산을
    주로 다루는 **소관 상임위원회를 다리로** 이은 사실 연결이다.
  - 분야→위원회 매핑(FIELD_COMMITTEES)은 가치판단 없는 결정론적 표이며 코드로 공개된다.
  - 2025 위원회 개편으로 법안의 committee 값에 신·구 명칭이 섞여 있어(예: 환경노동위원회
    → 기후에너지환경노동위원회), 법안 조회 시 구명 동의어(COMMITTEE_SYNONYMS)까지 포함한다.

엔드포인트:
  GET /api/budget/{field_code}/network   분야 소관 위원회 + 최근 법안 + 소속 의원
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Bill, Committee, CommitteeMembership, Party, Person
from app.persons import PartyBrief

router = APIRouter(prefix="/api/budget", tags=["budget"])

# 16대 분야코드 → 분야명 (열린재정 FLD_CD, frontend/lib/budget-data.json 과 동일).
FIELD_NAMES: dict[str, str] = {
    "010": "일반·지방행정",
    "020": "공공질서및안전",
    "030": "통일·외교",
    "040": "국방",
    "050": "교육",
    "060": "문화및관광",
    "070": "환경",
    "080": "사회복지",
    "090": "보건",
    "100": "농림수산",
    "110": "산업·중소기업및에너지",
    "120": "교통및물류",
    "130": "통신",
    "140": "국토및지역개발",
    "150": "과학기술",
    "160": "예비비",
}

# 분야 → 소관 상임위원회(현행 엔티티명, 대표 위원회 먼저). 🟡 결정론적·공개.
# 근거: 각 분야 예산을 심의·감독하는 국회 상임위원회(제22대, 2025 개편 반영).
#   한 분야가 여러 위원회에 걸치면 핵심 위원회만 보수적으로 담는다(과다 연결 방지).
#   예비비(160)는 특정 소관위가 없어 매핑하지 않는다.
FIELD_COMMITTEES: dict[str, list[str]] = {
    "010": ["행정안전위원회"],                          # 일반·지방행정(지방교부세·정부 운영)
    "020": ["행정안전위원회", "법제사법위원회"],         # 공공질서및안전(경찰·소방 + 법무·검찰)
    "030": ["외교통일위원회"],                          # 통일·외교
    "040": ["국방위원회"],                              # 국방
    "050": ["교육위원회"],                              # 교육
    "060": ["문화체육관광위원회"],                      # 문화및관광
    "070": ["기후에너지환경노동위원회"],                # 환경(구 환경노동위원회)
    "080": ["보건복지위원회"],                          # 사회복지(기초연금·복지·고용서비스)
    "090": ["보건복지위원회"],                          # 보건(건강보험 지원·의료)
    "100": ["농림축산식품해양수산위원회"],              # 농림수산
    "110": ["산업통상자원중소벤처기업위원회"],          # 산업·중소기업및에너지
    "120": ["국토교통위원회"],                          # 교통및물류
    "130": ["과학기술정보방송통신위원회"],              # 통신
    "140": ["국토교통위원회"],                          # 국토및지역개발
    "150": ["과학기술정보방송통신위원회"],              # 과학기술
    "160": [],                                          # 예비비(소관위 없음)
}

# 현행 위원회명 → 법안 committee 에 남아있는 구명(2025 개편 전). 🟡 법안 조회 시 합집합.
COMMITTEE_SYNONYMS: dict[str, list[str]] = {
    "기후에너지환경노동위원회": ["환경노동위원회"],
    "재정경제기획위원회": ["기획재정위원회"],
    "성평등가족위원회": ["여성가족위원회"],
}

NOTICE = (
    "이 분야 예산을 주로 심의·감독하는 국회 상임위원회와 그 소관 법안·소속 의원입니다. "
    "예산 항목과 법안을 1:1로 연결한 것이 아니라, 소관 위원회를 다리로 이은 사실 연결입니다. "
    "분야↔위원회 매핑 기준은 코드로 공개됩니다."
)


# ───────────────────────── 스키마 ─────────────────────────
class NetworkCommittee(BaseModel):
    name: str
    type_name: str | None  # 상임위원회/상설특별위원회
    member_count: int  # 이 위원회 소속 의원 수(제22대 경력 기준)


class NetworkBill(BaseModel):
    """그물망 법안 카드 — 탭하면 법안 상세(/bills/{id})로."""
    id: int
    title: str
    committee: str | None
    category: str | None  # 생활 카테고리(있으면)
    proposed_date: date | None
    status: str | None


class NetworkMember(BaseModel):
    """그물망 의원 카드 — 탭하면 프로필(/persons/{id})로."""
    id: int
    name: str
    party: PartyBrief | None
    district: str | None
    photo_url: str | None
    role: str | None  # 위원장/간사/위원 (소스에 없으면 null)


class BudgetNetwork(BaseModel):
    field_code: str
    field_name: str
    committees: list[NetworkCommittee]
    bills: list[NetworkBill]
    bill_total: int  # 소관 위원회 법안 총건수(표시 N건 외 전체)
    members: list[NetworkMember]
    member_total: int  # 소속 의원 총수(표시 N명 외 전체)
    notice: str


# 위원장·간사를 위로(소스에 role 이 있으면). 나머지는 이름순.
_ROLE_ORDER = {"위원장": 0, "간사": 1}


def _role_key(role: str | None) -> int:
    return _ROLE_ORDER.get(role or "", 9)


@router.get("/{field_code}/network", response_model=BudgetNetwork)
def field_network(
    field_code: str,
    bill_limit: int = 6,
    member_limit: int = 12,
    db: Session = Depends(get_db),
) -> BudgetNetwork:
    """예산 분야 → 소관 상임위원회 → 최근 법안 + 소속 의원 (그물망)."""
    field_name = FIELD_NAMES.get(field_code)
    if field_name is None:
        raise HTTPException(status_code=404, detail="해당 예산 분야를 찾을 수 없습니다.")

    canon = FIELD_COMMITTEES.get(field_code, [])

    # ── 소관 위원회 엔티티(현행명) + 소속 의원 수 ──
    committees: list[NetworkCommittee] = []
    committee_ids: list[int] = []
    if canon:
        rows = db.execute(
            select(
                Committee.id, Committee.name, Committee.type_name,
                func.count(CommitteeMembership.id),
            )
            .outerjoin(CommitteeMembership, CommitteeMembership.committee_id == Committee.id)
            .where(Committee.name.in_(canon))
            .group_by(Committee.id)
        ).all()
        # FIELD_COMMITTEES 순서(대표 먼저) 유지
        order = {n: i for i, n in enumerate(canon)}
        rows.sort(key=lambda r: order.get(r[1], 99))
        for cid, name, type_name, cnt in rows:
            committee_ids.append(cid)
            committees.append(
                NetworkCommittee(name=name, type_name=type_name, member_count=cnt)
            )

    # ── 소관 위원회 법안(신·구 명칭 합집합) — 최근 발의순 ──
    bills: list[NetworkBill] = []
    bill_total = 0
    if canon:
        bill_names: set[str] = set()
        for c in canon:
            bill_names.add(c)
            bill_names.update(COMMITTEE_SYNONYMS.get(c, []))
        base = select(Bill).where(Bill.committee.in_(bill_names))
        bill_total = db.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        bill_rows = db.scalars(
            base.order_by(Bill.proposed_date.desc().nullslast(), Bill.id.desc())
            .limit(bill_limit)
        ).all()
        bills = [
            NetworkBill(
                id=b.id, title=b.title, committee=b.committee,
                category=b.category, proposed_date=b.proposed_date, status=b.status,
            )
            for b in bill_rows
        ]

    # ── 소속 의원(제22대 위원회 경력) — 위원장·간사 먼저, 이름순 ──
    members: list[NetworkMember] = []
    member_total = 0
    if committee_ids:
        m_rows = db.execute(
            select(Person, Party, CommitteeMembership.role)
            .join(CommitteeMembership, CommitteeMembership.person_id == Person.id)
            .outerjoin(Party, Party.id == Person.party_id)
            .where(CommitteeMembership.committee_id.in_(committee_ids))
        ).all()
        # 같은 의원이 매핑 위원회 둘에 겹치면 한 번만(대표 role 보존)
        seen: dict[int, tuple[Person, Party | None, str | None]] = {}
        for person, party, role in m_rows:
            cur = seen.get(person.id)
            if cur is None or _role_key(role) < _role_key(cur[2]):
                seen[person.id] = (person, party, role)
        member_total = len(seen)
        ordered = sorted(
            seen.values(), key=lambda t: (_role_key(t[2]), t[0].name)
        )
        for person, party, role in ordered[:member_limit]:
            members.append(
                NetworkMember(
                    id=person.id, name=person.name,
                    party=PartyBrief(name=party.name, color_hex=party.color_hex)
                    if party else None,
                    district=person.district, photo_url=person.photo_url, role=role,
                )
            )

    return BudgetNetwork(
        field_code=field_code, field_name=field_name,
        committees=committees, bills=bills, bill_total=bill_total,
        members=members, member_total=member_total, notice=NOTICE,
    )
