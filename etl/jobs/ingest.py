"""수집 잡 — 열린국회정보 → DB 적재 (Phase 1-1~1-2).

잡:
  members       현직 22대 의원 300명        nwvrqwxyaytdsfvhu  → Party, Person
  bills         본회의 표결된 의안 + 집계     ncocpgfiaoituanbr  → Bill, Vote
  vote_records  의안별 의원 찬/반/기권        nojepdqqaweusdfbi  → VoteRecord
  proposers     발의법률안 + 대표발의자 연결   nzmimeepazxkubdpn  → Bill(+proposer_id)
  proposer_kinds 제안자 구분(정부·위원장)        TVBPMBILL11        → Bill(+proposer_kind/text)

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
SVC_PROPOSED = "nzmimeepazxkubdpn"  # 발의법률안 (대표발의자 RST_MONA_CD)
SVC_BILL_SEARCH = "TVBPMBILL11"  # 의안검색 — 제안자 구분(PROPOSER_KIND: 의원/정부/위원장)
SVC_ALLMEMBER = "ALLNAMEMBER"  # 역대 의원 통합 — 사진(NAAS_PIC). NAAS_CD == MONA_CD
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
        birth_date = _parse_date(row.get("BTH_DATE"))
        gender = (row.get("SEX_GBN_NM") or "").strip() or None
        term_label = (row.get("REELE_GBN_NM") or "").strip() or None
        position = (row.get("JOB_RES_NM") or "").strip() or None

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
        person.birth_date = birth_date
        person.gender = gender
        person.term_label = term_label
        person.position = position
        person.profile_source_url = MEMBER_SOURCE
        person.last_verified = _now()

    if not dry_run:
        session.commit()
    return {"new_party": n_new_party, "new_person": n_new, "updated_person": n_upd}


# ───────────────────────── photos ─────────────────────────
def run_photos(
    session: Session, client: AssemblyClient, *,
    age: str = DEFAULT_AGE, dry_run: bool = False, limit: int | None = None,
) -> dict:
    """의원 사진(NAAS_PIC) 적재 — `ALLNAMEMBER`(역대 통합).

    현직 API(`nwvrqwxyaytdsfvhu`)엔 사진 필드가 없어 통합 API 로 보강한다.
    `NAAS_CD` 가 현직 `MONA_CD`(=`assembly_member_code`)와 동일 체계라 코드로 직접 매칭
    (이름 매칭 불필요 → 동명이인 오류 없음). 우리 명단(300명)에 있는 코드만 갱신.
    """
    persons = {
        p.assembly_member_code: p
        for p in session.scalars(select(Person)).all()
        if p.assembly_member_code
    }
    if not persons:
        return {"error": "의원 데이터 없음 — members 잡 먼저 실행"}

    n_set = n_seen = 0
    for row in client.iter_rows(SVC_ALLMEMBER, max_rows=limit):
        n_seen += 1
        code = (row.get("NAAS_CD") or "").strip()
        person = persons.get(code)
        if person is None:
            continue
        pic = (row.get("NAAS_PIC") or "").strip()
        if not pic:
            continue
        person.photo_url = pic
        person.last_verified = _now()
        n_set += 1

    if not dry_run:
        session.commit()
    return {"scanned": n_seen, "photos_set": n_set, "of_members": len(persons)}


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


# ───────────────────────── proposers (발의자 연결) ─────────────────────────
def run_proposers(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    """발의법률안 적재 + 대표발의자 연결 (Phase 1-1).

    - Bill 을 의안번호로 upsert(표결 안 된 계류 의안 포함 → 의원 '대표발의' 목록을 채움).
    - 대표발의자는 `RST_MONA_CD`(의원코드) → `Person.assembly_member_code` 로 직접 연결.
      (이름 매칭 불필요 → 동명이인 오류 없음.)
    - 우리 명단에 없는 발의자(전직·정부발의 등)는 proposer 미연결로 둠(임의 생성 X).
    🟡 기존 값(표결 잡이 채운 committee/status/likms 등)은 덮어쓰지 않음(`or` 보존).
    """
    persons = {
        p.assembly_member_code: p
        for p in session.scalars(select(Person)).all()
        if p.assembly_member_code
    }
    if not persons:
        return {"error": "의원 데이터 없음 — members 잡 먼저 실행"}

    bills = {b.bill_no: b for b in session.scalars(select(Bill)).all()}
    n_new = n_upd = n_linked = n_nolink = 0

    for row in client.iter_rows(SVC_PROPOSED, params={"AGE": age}, max_rows=limit):
        bill_no = (row.get("BILL_NO") or "").strip()
        if not bill_no:
            continue
        link = row.get("DETAIL_LINK")
        bill = bills.get(bill_no)
        if bill is None:
            bill = Bill(bill_no=bill_no, title=row.get("BILL_NAME") or "")
            bills[bill_no] = bill
            n_new += 1
            if not dry_run:
                session.add(bill)
        else:
            n_upd += 1
        # 기존 값 보존(표결 잡이 더 정확). 비어 있을 때만 채움.
        bill.title = bill.title or (row.get("BILL_NAME") or "")
        bill.assembly_bill_id = bill.assembly_bill_id or row.get("BILL_ID")
        bill.committee = bill.committee or (row.get("COMMITTEE") or None)
        bill.status = bill.status or (row.get("PROC_RESULT") or None)
        bill.proposed_date = bill.proposed_date or _parse_date(row.get("PROPOSE_DT"))
        bill.likms_url = bill.likms_url or link
        bill.source_url = bill.source_url or link
        bill.last_verified = _now()

        code = (row.get("RST_MONA_CD") or "").strip()
        proposer = persons.get(code)
        if proposer is not None:
            bill.proposer_id = proposer.id  # 대표발의자 연결(항상 갱신)
            n_linked += 1
        else:
            n_nolink += 1

    if not dry_run:
        session.commit()
    return {
        "new_bill": n_new, "updated_bill": n_upd,
        "linked": n_linked, "no_person": n_nolink,
    }


# ───────────────────────── proposer_kinds (제안자 구분) ─────────────────────────
def run_proposer_kinds(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    """의안 제안자 구분(정부·위원장·의원) 보강 — 의안검색(TVBPMBILL11).

    발의법률안 API(nzmimeepazxkubdpn)는 의원발의만 담아 정부·위원장 제출안은
    대표발의자가 비어 보인다. 의안검색 API 는 PROPOSER_KIND(의원/정부/위원장)와
    PROPOSER 텍스트("정부", "정무위원장", "홍길동의원 등 10인")를 모든 의안에 제공한다.
    우리 DB 에 이미 있는 의안(표결·발의로 적재)만 의안번호로 매칭해 채운다(신규 생성 X).

    🟡 의원 대표발의는 proposer_id(프로필 링크)가 우선 — 여기 텍스트는 그 외 케이스 표시용.
    🟡 정부안 소관부처(○○부)는 API 에 없어 PROPOSER 는 "정부" 까지만 담긴다(멱등 upsert).
    """
    bills = {b.bill_no: b for b in session.scalars(select(Bill)).all()}
    if not bills:
        return {"error": "법안 데이터 없음 — bills/proposers 잡 먼저 실행"}

    n_match = n_set = 0
    for row in client.iter_rows(SVC_BILL_SEARCH, params={"AGE": age}, max_rows=limit):
        bill_no = (row.get("BILL_NO") or "").strip()
        bill = bills.get(bill_no)
        if bill is None:
            continue
        n_match += 1
        kind = (row.get("PROPOSER_KIND") or "").strip() or None
        text = (row.get("PROPOSER") or "").strip() or None
        if not kind and not text:
            continue
        bill.proposer_kind = kind
        bill.proposer_text = text
        bill.last_verified = _now()
        n_set += 1

    if not dry_run:
        session.commit()
    return {"matched": n_match, "set": n_set, "of_bills": len(bills)}
