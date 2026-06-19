"""프로토타입 데모 시드 — 앵커 법안 8건 + 가상 정치인 4명 (로컬 구동용).

본 환경엔 Postgres·실데이터가 없으므로, 화면이 렌더되도록 최소 데모 데이터를 적재한다.
  - 법안: seed_questions.DRAFTS 의 앵커 의안(문항↔법안 매핑·출처 노출용).
  - 정치인: 🟡 **명백한 가상 인물(`[데모]`)** 만. 실제 인물에 허위 정보(전과 등)를 붙이지
    않기 위함(기획 1.3 명예훼손 방지). 실데이터는 ETL(members/bills/vote_records)로 적재.

실행: python -m app.seed_demo  (seed → seed_demo → seed_questions 순서 권장, 멱등)
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Bill, CriminalRecord, Party, Person
from app.seed_questions import DRAFTS


def _title(source: str) -> str:
    """source 메모에서 법안명 추출: '<법안명> · 의안 ...' → '<법안명>'."""
    return source.split(" · 의안")[0].strip()


# 🟡 가상 정치인 (이름, 정당, 지역구, 출석률) — 데모 렌더링 전용. 실제 인물 아님.
DEMO_PERSONS: list[tuple[str, str, str, float]] = [
    ("[데모] 김하나", "더불어민주당", "서울 가나구갑", 0.96),
    ("[데모] 이두리", "국민의힘", "부산 다라구", 0.91),
    ("[데모] 박세찬", "개혁신당", "비례대표", 0.88),
    ("[데모] 최아람", "진보당", "광주 마바구", 0.99),
]
# 🟡 가상 전과 1건(데모) — '[데모] 이두리' 에 부착. 동일 양식·출처 표기 흐름 확인용.
DEMO_CRIMINAL = ("(데모) 도로교통법 위반", "벌금 100만원(가상)", date(2019, 5, 3), True)


def run() -> None:
    db = SessionLocal()
    try:
        # ── 앵커 법안 ──
        existing_bills = {b.bill_no for b in db.scalars(select(Bill)).all()}
        n_bill = 0
        for d in DRAFTS:
            if d.bill_no in existing_bills:
                continue
            db.add(Bill(bill_no=d.bill_no, title=_title(d.source)))
            existing_bills.add(d.bill_no)
            n_bill += 1
        db.flush()

        # ── 가상 정치인 ──
        parties = {p.name: p for p in db.scalars(select(Party)).all()}
        existing_persons = {p.name for p in db.scalars(select(Person)).all()}
        n_person = 0
        demo_people: list[Person] = []
        for i, (name, party_name, district, attendance) in enumerate(DEMO_PERSONS):
            person = db.scalar(select(Person).where(Person.name == name))
            if person is None:
                person = Person(
                    name=name,
                    assembly_member_code=f"DEMO-{i+1:03d}",
                    party=parties.get(party_name),
                    district=district,
                    attendance_rate=attendance,
                    profile_source_url=None,  # 데모: 출처 미연동(실데이터는 ETL)
                    last_verified=datetime.now(timezone.utc),
                )
                db.add(person)
                n_person += 1
            demo_people.append(person)
        db.flush()

        # ── 발의 법안 연결(그물망): 앞쪽 법안 2건의 대표발의를 데모 1·2번에 ──
        bills = list(db.scalars(select(Bill).order_by(Bill.id)).all())
        for person, bill in zip(demo_people[:2], bills[:2]):
            if bill.proposer_id is None:
                bill.proposer_id = person.id
                if bill.proposed_date is None:
                    bill.proposed_date = date(2025, 3, 1)

        # ── 가상 전과(데모) ──
        target = next((p for p in demo_people if p.name == "[데모] 이두리"), None)
        if target is not None and not target.criminal_records:
            charge, sentence, dt, final = DEMO_CRIMINAL
            db.add(
                CriminalRecord(
                    person_id=target.id, charge=charge, sentence=sentence,
                    date_sentenced=dt, is_final=final, source_url=None,
                )
            )

        db.commit()
        print(
            f"데모 시드: 법안 신규 {n_bill}/{len(DRAFTS)}, 가상 정치인 신규 {n_person}/"
            f"{len(DEMO_PERSONS)} (멱등)"
        )
    finally:
        db.close()


if __name__ == "__main__":
    run()
