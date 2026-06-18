"""수집 잡 — 열린국회정보 → DB 적재 (Phase 1-2).

잡:
  members       현직 22대 의원 300명        nwvrqwxyaytdsfvhu  → Party, Person
  bills         본회의 표결된 의안 + 집계     ncocpgfiaoituanbr  → Bill, Vote
  vote_records  의안별 의원 찬/반/기권        nojepdqqaweusdfbi  → VoteRecord

원칙(🟡): 수집 레코드에 1차 출처(likms LINK_URL) 자동 부착, last_verified 기록.
모든 잡 멱등(upsert). dry_run 시 DB 미기록(조회·변환만).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from clients.assembly import AssemblyClient
from jobs.db import Bill, Party, Person, Vote, VoteChoice, VoteRecord

# 확정 서비스 코드 (etl/scripts/explore_*.py 로 검증)
SVC_MEMBERS = "nwvrqwxyaytdsfvhu"  # 현직 의원
SVC_BILLS = "ncocpgfiaoituanbr"  # 의안별 표결현황(집계)
SVC_VOTE_RECORDS = "nojepdqqaweusdfbi"  # 의원별 본회의 표결정보
DEFAULT_AGE = "22"

MEMBER_SOURCE = "https://open.assembly.go.kr/portal/assm/search/memberSchPage.do"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _to_int(v) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ───────────────────────── members ─────────────────────────
def run_members(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    parties = {p.name: p for p in session.scalars(select(Party)).all()}
    persons = {
        p.assembly_member_code: p
        for p in session.scalars(select(Person)).all()
        if p.assembly_member_code
    }
    n_new_party = n_new = n_upd = 0

    for row in client.iter_rows(SVC_MEMBERS, params={"AGE": age}, max_rows=limit):
        code = (row.get("MONA_CD") or "").strip()
        name = (row.get("HG_NM") or "").strip()
        if not code or not name:
            continue
        party_name = (row.get("POLY_NM") or "").strip() or None
        district = (row.get("ORIG_NM") or "").strip() or None

        party = parties.get(party_name) if party_name else None
        if party_name and party is None:
            party = Party(name=party_name)  # color_hex 는 seed 가 채움
            parties[party_name] = party
            n_new_party += 1
            if not dry_run:
                session.add(party)
                session.flush()

        person = persons.get(code)
        if person is None:
            person = Person(name=name, assembly_member_code=code)
            persons[code] = person
            n_new += 1
            if not dry_run:
                session.add(person)
        else:
            n_upd += 1
        person.name = name
        person.district = district
        person.party = party
        person.profile_source_url = MEMBER_SOURCE
        person.last_verified = _now()

    if not dry_run:
        session.commit()
    return {"new_party": n_new_party, "new_person": n_new, "updated_person": n_upd}


# ───────────────────────── bills ─────────────────────────
def run_bills(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    bills = {b.bill_no: b for b in session.scalars(select(Bill)).all()}
    votes = {v.bill_id: v for v in session.scalars(select(Vote)).all()}
    n_new = n_upd = n_vote = 0

    for row in client.iter_rows(SVC_BILLS, params={"AGE": age}, max_rows=limit):
        bill_no = (row.get("BILL_NO") or "").strip()
        if not bill_no:
            continue
        link = row.get("LINK_URL")
        bill = bills.get(bill_no)
        if bill is None:
            bill = Bill(bill_no=bill_no, title=row.get("BILL_NAME") or "")
            bills[bill_no] = bill
            n_new += 1
            if not dry_run:
                session.add(bill)
        else:
            n_upd += 1
        bill.title = row.get("BILL_NAME") or bill.title
        bill.assembly_bill_id = row.get("BILL_ID")
        bill.committee = (row.get("CURR_COMMITTEE") or None)
        bill.status = row.get("PROC_RESULT_CD")
        bill.likms_url = link
        bill.source_url = link
        bill.last_verified = _now()
        if not dry_run:
            session.flush()  # bill.id 확보

        # 본회의 표결 집계(의안당 1건)
        if not dry_run:
            vote = votes.get(bill.id)
            if vote is None:
                vote = Vote(bill_id=bill.id)
                votes[bill.id] = vote
                session.add(vote)
                n_vote += 1
            vote.session_date = _parse_date(row.get("PROC_DT"))
            vote.member_total = _to_int(row.get("MEMBER_TCNT"))
            vote.vote_total = _to_int(row.get("VOTE_TCNT"))
            vote.yes_total = _to_int(row.get("YES_TCNT"))
            vote.no_total = _to_int(row.get("NO_TCNT"))
            vote.blank_total = _to_int(row.get("BLANK_TCNT"))
            vote.source_url = link
            vote.last_verified = _now()
        else:
            n_vote += 1

    if not dry_run:
        session.commit()
    return {"new_bill": n_new, "updated_bill": n_upd, "votes": n_vote}


# ───────────────────────── vote_records ─────────────────────────
def run_vote_records(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None, skip_done: bool = True,
) -> dict:
    """표결된 의안의 의원별 찬/반/기권 적재.

    limit: 처리할 의안 수 상한(rate limit 대응). skip_done: 이미 기록 있는 의안 건너뜀.
    """
    persons = {
        p.assembly_member_code: p
        for p in session.scalars(select(Person)).all()
        if p.assembly_member_code
    }
    if not persons:
        return {"error": "의원 데이터 없음 — members 잡 먼저 실행"}

    # 표결(Vote) 있는 의안만 대상
    q = (
        select(Bill, Vote)
        .join(Vote, Vote.bill_id == Bill.id)
        .where(Bill.assembly_bill_id.isnot(None))
        .order_by(Vote.session_date.desc().nullslast())
    )
    targets = session.execute(q).all()

    n_bill = n_rec = n_skip_member = n_skip_choice = 0
    for bill, vote in targets:
        if limit is not None and n_bill >= limit:
            break
        existing = {
            r.person_id
            for r in session.scalars(
                select(VoteRecord).where(VoteRecord.vote_id == vote.id)
            ).all()
        }
        if skip_done and existing:
            continue
        n_bill += 1
        for row in client.iter_rows(
            SVC_VOTE_RECORDS, params={"AGE": age, "BILL_ID": bill.assembly_bill_id}
        ):
            code = (row.get("MONA_CD") or "").strip()
            person = persons.get(code)
            if person is None:
                n_skip_member += 1
                continue
            raw = (row.get("RESULT_VOTE_MOD") or "").strip()
            try:
                choice = VoteChoice(raw)
            except ValueError:
                n_skip_choice += 1
                continue
            if person.id in existing:
                continue
            n_rec += 1
            if not dry_run:
                session.add(
                    VoteRecord(vote_id=vote.id, person_id=person.id, choice=choice)
                )
            existing.add(person.id)
        if not dry_run:
            session.commit()

    return {
        "bills_processed": n_bill,
        "records": n_rec,
        "skipped_member": n_skip_member,
        "skipped_choice": n_skip_choice,
    }
