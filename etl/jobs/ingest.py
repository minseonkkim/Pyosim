"""수집 잡 — 열린국회정보 → DB 적재 (Phase 1-1~1-2).

잡:
  members       현직 22대 의원 300명        nwvrqwxyaytdsfvhu  → Party, Person
  bills         본회의 표결된 의안 + 집계     ncocpgfiaoituanbr  → Bill, Vote
  vote_records  의안별 의원 찬/반/기권        nojepdqqaweusdfbi  → VoteRecord
  proposers     발의법률안 + 대표발의자 연결   nzmimeepazxkubdpn  → Bill(+proposer_id)
  proposer_kinds 제안자 구분(정부·위원장)        TVBPMBILL11        → Bill(+proposer_kind/text)
  committees    위원회 + 의원 위원회경력(제22대) nxrvzonlafugpqjuh+nyzrglyvagmrypezq → Committee, CommitteeMembership
  bill_stages   본회의 처리 단계별 의결일        nwbpacrgavhjryiph  → Bill(단계 일자)
  petitions     청원 계류·처리현황(기능 A)        nvqbafvaajdiqhehi+ncryefyuaflxnqbqo → Petition

원칙(🟡): 수집 레코드에 1차 출처(likms LINK_URL) 자동 부착, last_verified 기록.
모든 잡 멱등(upsert). dry_run 시 DB 미기록(조회·변환만).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from clients.assembly import AssemblyClient
from jobs.db import (
    Bill,
    Committee,
    CommitteeMembership,
    Party,
    Person,
    Petition,
    Vote,
    VoteChoice,
    VoteRecord,
)

# 확정 서비스 코드 (etl/scripts/explore_*.py 로 검증)
SVC_MEMBERS = "nwvrqwxyaytdsfvhu"  # 현직 의원
SVC_BILLS = "ncocpgfiaoituanbr"  # 의안별 표결현황(집계)
SVC_VOTE_RECORDS = "nojepdqqaweusdfbi"  # 의원별 본회의 표결정보
SVC_PROPOSED = "nzmimeepazxkubdpn"  # 발의법률안 (대표발의자 RST_MONA_CD)
SVC_BILL_SEARCH = "TVBPMBILL11"  # 의안검색 — 제안자 구분(PROPOSER_KIND: 의원/정부/위원장)
SVC_ALLMEMBER = "ALLNAMEMBER"  # 역대 의원 통합 — 사진(NAAS_PIC). NAAS_CD == MONA_CD
SVC_CMT_STATUS = "nxrvzonlafugpqjuh"  # 위원회 현황(엔티티: 상임/특위, 정원)
SVC_CMT_CAREER = "nyzrglyvagmrypezq"  # 국회의원 위원회 경력(MONA_CD↔위원회명, 활동기간)
SVC_PLENARY_BILLS = "nwbpacrgavhjryiph"  # 본회의 처리안건(법률안) — 단계별 의결일
SVC_PETITION_PENDING = "nvqbafvaajdiqhehi"  # 청원 계류현황(처리결과 없음)
SVC_PETITION_DONE = "ncryefyuaflxnqbqo"  # 청원 처리현황(PROC_RESULT_CD 포함)
DEFAULT_AGE = "22"

MEMBER_SOURCE = "https://open.assembly.go.kr/portal/assm/search/memberSchPage.do"
CMT_SOURCE = "https://open.assembly.go.kr/portal/assm/assmPrpl/committeeMemberList.do"

# 국민동의청원 소개 표기(APPROVER) — 5만 동의로 자동 회부된 청원
NATIONAL_CONSENT = "국민동의청원"
_SIGN_COUNT = re.compile(r"외\s*([\d,]+)\s*인")  # PROPOSER "○○외 50,922인" → 50922


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


# ───────────────────────── committees (위원회 + 경력) ─────────────────────────
# 정규화 대상: 현행 상임위 + 상설특위(예결위). 임시·국정조사 특위는 잡음이라 제외.
_CMT_TYPES = ("상임위원회", "상설특별위원회")
_AGE22_PREFIX = re.compile(r"^제22대\s*")


def run_committees(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    """위원회 엔티티 + 의원 위원회 경력(제22대) 매핑 (Phase 1-1).

    1) 위원회 현황(`nxrvzonlafugpqjuh`) → 상임/상설특위만 Committee upsert(dept_code 키).
    2) 위원회 경력(`nyzrglyvagmrypezq`) 제22대 행 → 위원회명이 (1)의 엔티티와 일치하면
       CommitteeMembership upsert(MONA_CD→Person, term_label=FRTO_DATE 원문).
    🟡 '현재 소속' 단정 대신 공식 '위원회 경력' + 활동기간 보존. 신·구 개편 명칭은
       현행 엔티티명 매칭으로 자연 필터(구명칭·특위는 미매칭→제외). UniqueConstraint 로 멱등.
    """
    # ── 1) 위원회 엔티티 ──
    committees = {c.dept_code: c for c in session.scalars(select(Committee)).all()}
    by_name: dict[str, Committee] = {}
    n_new_cmt = n_upd_cmt = 0
    for row in client.iter_rows(SVC_CMT_STATUS):
        if (row.get("CMT_DIV_NM") or "").strip() not in _CMT_TYPES:
            continue
        code = (row.get("HR_DEPT_CD") or "").strip()
        name = (row.get("COMMITTEE_NAME") or "").strip()
        if not code or not name:
            continue
        cmt = committees.get(code)
        if cmt is None:
            cmt = Committee(dept_code=code, name=name)
            committees[code] = cmt
            n_new_cmt += 1
            if not dry_run:
                session.add(cmt)
        else:
            n_upd_cmt += 1
        cmt.name = name
        cmt.type_name = (row.get("CMT_DIV_NM") or "").strip() or None
        cmt.member_limit = _to_int(row.get("LIMIT_CNT"))
        cmt.source_url = CMT_SOURCE
        cmt.last_verified = _now()
        by_name[name] = cmt
    if not dry_run:
        session.flush()  # committee.id 확보

    # ── 2) 의원 위원회 경력(제22대) ──
    persons = {
        p.assembly_member_code: p
        for p in session.scalars(select(Person)).all()
        if p.assembly_member_code
    }
    existing = {
        (m.committee_id, m.person_id): m
        for m in session.scalars(select(CommitteeMembership)).all()
    }
    n_link = n_upd_link = n_nomatch = n_noperson = 0
    for row in client.iter_rows(SVC_CMT_CAREER, max_rows=limit):
        if (row.get("PROFILE_UNIT_NM") or "").strip() != "제22대":
            continue
        name = _AGE22_PREFIX.sub("", (row.get("PROFILE_SJ") or "").strip()).strip()
        cmt = by_name.get(name)
        if cmt is None:
            n_nomatch += 1  # 특위·구개편명 — 현행 상임위 아님(의도된 제외)
            continue
        person = persons.get((row.get("MONA_CD") or "").strip())
        if person is None:
            n_noperson += 1
            continue
        if dry_run:
            n_link += 1
            continue
        key = (cmt.id, person.id)
        m = existing.get(key)
        if m is None:
            m = CommitteeMembership(committee_id=cmt.id, person_id=person.id)
            existing[key] = m
            session.add(m)
            n_link += 1
        else:
            n_upd_link += 1
        m.term_label = (row.get("FRTO_DATE") or "").strip() or None
        m.source_url = CMT_SOURCE
        m.last_verified = _now()

    if not dry_run:
        session.commit()
    return {
        "new_committee": n_new_cmt, "updated_committee": n_upd_cmt,
        "linked": n_link, "updated_link": n_upd_link,
        "skipped_nonstanding": n_nomatch, "skipped_no_person": n_noperson,
    }


# ───────────────────────── bill_stages (처리 단계 의결일) ─────────────────────────
def run_bill_stages(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    """본회의 처리안건(`nwbpacrgavhjryiph`) → Bill 단계별 의결일 (Phase 1-3).

    funnel 을 실제 날짜 타임라인으로 승격: 소관위/법사위/본회의 의결일 + 공포일.
    의안번호(BILL_NO)로 기존 Bill 매칭(신규 생성 X). 발의일이 비어 있으면 PROPOSE_DT 로 보강.
    🟡 공식 일자 그대로 저장(판정 없음). 멱등 upsert.
    """
    bills = {b.bill_no: b for b in session.scalars(select(Bill)).all()}
    if not bills:
        return {"error": "법안 데이터 없음 — bills/proposers 잡 먼저 실행"}

    n_match = n_set = 0
    for row in client.iter_rows(SVC_PLENARY_BILLS, params={"AGE": age}, max_rows=limit):
        bill = bills.get((row.get("BILL_NO") or "").strip())
        if bill is None:
            continue
        n_match += 1
        cmte = _parse_date(row.get("COMMITTEE_PROC_DT"))
        law = _parse_date(row.get("LAW_PROC_DT"))
        plen = _parse_date(row.get("RGS_PROC_DT"))
        anno = _parse_date(row.get("ANNOUNCE_DT"))
        if not any((cmte, law, plen, anno)):
            continue
        bill.committee_proc_date = cmte
        bill.law_proc_date = law
        bill.plenary_proc_date = plen
        bill.announce_date = anno
        bill.proposed_date = bill.proposed_date or _parse_date(row.get("PROPOSE_DT"))
        bill.last_verified = _now()
        n_set += 1

    if not dry_run:
        session.commit()
    return {"matched": n_match, "set": n_set, "of_bills": len(bills)}


# ───────────────────────── petitions (청원 추적) ─────────────────────────
def _parse_sign_count(proposer: str | None) -> int | None:
    """PROPOSER "○○외 50,922인" → 50922. 매칭 안 되면 None."""
    if not proposer:
        return None
    m = _SIGN_COUNT.search(proposer)
    return int(m.group(1).replace(",", "")) if m else None


def run_petitions(
    session: Session, client: AssemblyClient, *, age: str = DEFAULT_AGE,
    dry_run: bool = False, limit: int | None = None,
) -> dict:
    """청원 계류현황 + 처리현황 → Petition (Phase 2 기능 A).

    민심 레이어 첫 축: 시민 청원이 '지금 어느 단계에 멈췄나'를 추적.
    1) 계류현황(`nvqbafvaajdiqhehi`) → proc_result 없는(=아직 처리 안 된) 청원.
    2) 처리현황(`ncryefyuaflxnqbqo`) → PROC_RESULT_CD(최종 처리결과) 채워 upsert.
       처리되면 계류현황에서 빠지므로, 처리현황을 나중에 적용해 결과를 덮어쓴다.
    의안번호(BILL_NO)로 멱등 upsert. 🟡 공개 기록 값만 보존, 처리결과 코드 원문 그대로.
    """
    existing = {p.bill_no: p for p in session.scalars(select(Petition)).all()}
    n_new = n_upd = 0

    def _upsert(row: dict, *, proc_result: str | None) -> None:
        nonlocal n_new, n_upd
        bill_no = (row.get("BILL_NO") or "").strip()
        if not bill_no:
            return
        p = existing.get(bill_no)
        if p is None:
            p = Petition(bill_no=bill_no)
            existing[bill_no] = p
            n_new += 1
            if not dry_run:
                session.add(p)
        else:
            n_upd += 1
        p.assembly_bill_id = (row.get("BILL_ID") or "").strip() or None
        p.title = (row.get("BILL_NAME") or "").strip()
        proposer = (row.get("PROPOSER") or "").strip() or None
        p.proposer = proposer
        introducer = (row.get("APPROVER") or "").strip() or None
        p.introducer = introducer
        p.is_national_consent = introducer == NATIONAL_CONSENT
        p.signature_count = _parse_sign_count(proposer)
        p.proposed_date = _parse_date(row.get("PROPOSE_DT"))
        p.committee = (row.get("CURR_COMMITTEE") or "").strip() or None
        p.committee_date = _parse_date(row.get("COMMITTEE_DT"))
        p.proc_result = proc_result
        p.source_url = (row.get("LINK_URL") or "").strip() or None
        p.last_verified = _now()

    # 1) 계류현황(처리결과 없음)
    for row in client.iter_rows(SVC_PETITION_PENDING, params={"AGE": age}, max_rows=limit):
        _upsert(row, proc_result=None)
    # 2) 처리현황(최종 처리결과 덮어쓰기)
    for row in client.iter_rows(SVC_PETITION_DONE, params={"AGE": age}, max_rows=limit):
        _upsert(row, proc_result=(row.get("PROC_RESULT_CD") or "").strip() or None)

    if not dry_run:
        session.commit()
    pending = sum(1 for p in existing.values() if p.proc_result is None)
    return {"new": n_new, "updated": n_upd, "total": len(existing), "pending": pending}
