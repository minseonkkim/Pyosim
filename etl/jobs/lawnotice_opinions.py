"""입법예고 시민 찬반 의견 집계 — 국민참여입법시스템(pal.assembly.go.kr) 스크랩 (Phase 2 기능 B-4.4).

열린국회정보 입법예고 API 는 메타만 주고 **찬반 카운트가 없다**(라이브 확인).
찬반 수치는 국민참여입법시스템 의견목록 공개 페이지의 각 의견 **행에 찍힌 입장 텍스트**
("찬성합니다"/"반대합니다"/그 외=기타)에만 있다 → 입장별 필터 파라미터가 없으므로
페이지를 넘기며 입장 문구를 센다(searchConRng 는 전체/나의/공개 구분일 뿐 찬반이 아님 — 확인).

  GET /napal/lgsltpa/lgsltpaOpn/list.do?lgsltPaId={BILL_ID}&searchConClosed={0|1}&searchConRng=0&pageUnit=100&pageIndex={n}
    board_count <strong>N</strong> = 전체 의견 수(헤더에서 1회 읽음).
    각 페이지 본문에서 '찬성합니다'/'반대합니다' 등장 횟수 = 그 페이지의 찬성/반대 의견 수.
    기타 = 전체 - 찬성 - 반대.

비용: 한 의안당 ceil(전체/100) 페이지. 의견 폭주 의안(수천 건)만 수십 페이지 → MAX_PAGES 로 상한.
상한 초과 의안은 정확 분해를 보류하고 전체 수만 저장(🟡 부정확한 분해를 보여주지 않음).

🟡 의견 본문·작성자는 가져오지 않고 입장별 집계 수치만 저장. 비공식 스크래핑이라 sleep + 선별 수집.
⚠️ pal.assembly 구조 변경 시 깨질 수 있음(robots/ToS 유의). assembly_bill_id 있는 예고만 대상.
"""
from __future__ import annotations

import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobs.db import Bill, LawNotice

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
OPN_BASE = "https://pal.assembly.go.kr/napal/lgsltpa/lgsltpaOpn/list.do"
PAGE_UNIT = 100  # 한 페이지 의견 수(요청 절감)
MAX_PAGES = 80  # 의안당 최대 페이지(=8,000 의견). 초과 시 분해 보류·전체 수만.
# board_count 헤더의 전체 건수: <div class="board_count">...<strong>3,742</strong>
_TOTAL = re.compile(r"board_count.*?<strong>\s*([\d,]+)\s*</strong>", re.S)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_html(bill_id: str, *, closed: bool, page_index: int, timeout: int = 25) -> str:
    params = {
        "lgsltPaId": bill_id,
        "searchConClosed": "1" if closed else "0",
        "searchConRng": "0",  # 전체 의견(찬반 필터 아님 — 본문에서 입장 문구를 센다)
        "pageUnit": str(PAGE_UNIT),
        "pageIndex": str(page_index),
    }
    url = f"{OPN_BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _parse_total(html: str) -> int | None:
    m = _TOTAL.search(html)
    return int(m.group(1).replace(",", "")) if m else None


def _scrape_one(
    notice: LawNotice, *, sleep_sec: float = 0.3,
) -> tuple[int, int | None, int | None, int | None] | None:
    """한 입법예고의 (전체, 찬성, 반대, 기타) 집계.

    bill_id 없거나 전체 수 파싱 실패 → None.
    의견 0건 → (0,0,0,0). 페이지 상한 초과 → (전체, None,None,None)(분해 보류).
    """
    bid = notice.assembly_bill_id
    if not bid:
        return None
    closed = not notice.is_ongoing
    h1 = _fetch_html(bid, closed=closed, page_index=1)
    total = _parse_total(h1)
    if total is None:
        return None
    if total == 0:
        return (0, 0, 0, 0)
    npages = -(-total // PAGE_UNIT)
    if npages > MAX_PAGES:
        return (total, None, None, None)  # 너무 큼 — 전체 수만, 분해 보류

    agree = oppose = 0
    for i in range(1, npages + 1):
        html = h1 if i == 1 else _fetch_html(bid, closed=closed, page_index=i)
        agree += html.count("찬성합니다")
        oppose += html.count("반대합니다")
        if i < npages and sleep_sec:
            time.sleep(sleep_sec)
    etc = max(total - agree - oppose, 0)
    return (total, agree, oppose, etc)


def run_lawnotice_opinions(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True, only_linked: bool = True, sleep_sec: float = 0.3,
) -> dict:
    """입법예고 찬반 의견을 스크랩해 LawNotice 집계 컬럼을 채움(멱등).

    only_linked: 우리 DB 의 Bill 과 연결된(=화면에 노출될) 예고만(17,709개 전부 X).
    only_missing: opinion_fetched 없는 예고만(재실행 시 건너뜀). limit: 수집 의안 상한.
    """
    bill_ids = {b.assembly_bill_id for b in session.scalars(select(Bill)).all() if b.assembly_bill_id}

    q = select(LawNotice).where(LawNotice.assembly_bill_id.isnot(None))
    if only_missing:
        q = q.where(LawNotice.opinion_fetched.is_(None))
    q = q.order_by(LawNotice.notice_end_date.desc().nullslast(), LawNotice.id.desc())
    notices = list(session.scalars(q).all())
    if only_linked:
        notices = [n for n in notices if n.assembly_bill_id in bill_ids]

    n_ok = n_empty = n_err = n_capped = n_done = 0
    for notice in notices:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        try:
            counts = _scrape_one(notice, sleep_sec=sleep_sec)
            if counts is None:
                n_err += 1
                continue
            total, agree, oppose, etc = counts
            if not dry_run:
                notice.opinion_total = total
                notice.agree_count = agree
                notice.oppose_count = oppose
                notice.etc_count = etc
                notice.opinion_fetched = _now()
            if agree is None:
                n_capped += 1
            elif total > 0:
                n_ok += 1
            else:
                n_empty += 1
        except Exception:  # noqa: BLE001 — 개별 실패는 건너뛰고 계속
            n_err += 1
        if not dry_run and n_done % 10 == 0:
            session.commit()
        if sleep_sec:
            time.sleep(sleep_sec)

    if not dry_run:
        session.commit()
    return {
        "processed": n_done, "with_split": n_ok, "zero": n_empty,
        "capped": n_capped, "error": n_err, "candidates": len(notices),
    }
