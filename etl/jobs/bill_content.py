"""의안 본문 수집 — likms 의안원문(HWP) PrvText 에서 제안이유·주요내용 추출 (Phase 1-3 보완).

열린국회정보 OpenAPI 엔 본문이 없어, 의안정보시스템(likms)의 '의안원문' HWP 를 받아
미리보기텍스트(PrvText) 스트림(UTF-16LE 평문)에서 제안이유/주요내용을 뽑는다.

수집 흐름(라이브 역추적 확정):
  1) billDetail.do?billId=  방문 → 세션 쿠키(JSESSIONID)
  2) downloadDtlZip.do  POST(billId, docChkList=의안원문) → zip
  3) zip 안의 .hwp → olefile 로 PrvText 스트림 디코드 → 제안이유/주요내용 파싱

🟡 원문 그대로 저장(요약·판정 없음). 출처 = likms billDetail. AI 요약(좋은점/문제점)은 별도 단계.
⚠️ likms 스크래핑이므로 예의상 sleep + 필요한 의안만(표결/featured) 선별 수집 권장.
"""
from __future__ import annotations

import http.cookiejar
import io
import re
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

import olefile
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobs.db import Bill

LIKMS = "https://likms.assembly.go.kr"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def download_uian_hwp(bill_id: str) -> bytes | None:
    """billId(PRC_…) 의 '의안원문' HWP 바이트. 문서 없으면 None."""
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA)]
    op.open(f"{LIKMS}/bill/billDetail.do?billId={bill_id}", timeout=30).read()  # 세션 쿠키
    data = urllib.parse.urlencode([("billId", bill_id), ("docChkList", "의안원문")]).encode()
    req = urllib.request.Request(
        f"{LIKMS}/bill/bi/bill/detail/downloadDtlZip.do",
        data=data,
        headers={"User-Agent": UA, "Referer": f"{LIKMS}/bill/billDetail.do?billId={bill_id}"},
    )
    body = op.open(req, timeout=60).read()
    if body[:2] != b"PK":  # zip 아님(문서 없음/에러)
        return None
    z = zipfile.ZipFile(io.BytesIO(body))
    hwps = [n for n in z.namelist() if n.lower().endswith(".hwp")]
    return z.read(hwps[0]) if hwps else None


def extract_prvtext(hwp: bytes) -> str:
    """HWP5(OLE) 의 PrvText(미리보기 평문, UTF-16LE) 스트림 → 텍스트."""
    ole = olefile.OleFileIO(io.BytesIO(hwp))
    try:
        if not ole.exists("PrvText"):
            return ""
        return ole.openstream("PrvText").read().decode("utf-16-le", "replace")
    finally:
        ole.close()


def _clean(s: str) -> str:
    s = s.replace("\x00", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip(" \n\r<>")


# 본문 끝 경계(법안 본문/대비표 시작 신호) — 제안이유/주요내용 뒤에 법안 원문이 이어짐
_END = re.compile(r"\n\s*법률\s*제|\n\s*신구조문|\n\s*부\s*칙")


def _section_to_end(text: str, start: int) -> str | None:
    seg = text[start:]
    m = _END.search(seg)
    return _clean(seg[: m.start()] if m else seg) or None


def parse_reason_content(text: str) -> tuple[str | None, str | None]:
    """PrvText → (제안이유, 주요내용). 두 형식 모두 처리.

    - 결합형 `<제안이유 및 주요내용>`: 통째로 첫 필드에 담고 둘째는 None.
    - 분리형 `<제안이유>` … `<주요내용>` …: 각각 분리.
    마커 없으면 (None, None).
    """
    text = text.replace("\x00", "")

    ci = text.find("<제안이유 및 주요내용>")
    if ci >= 0:
        return _section_to_end(text, ci + len("<제안이유 및 주요내용>")), None

    reason = main = None
    ri = text.find("<제안이유>")
    mi = text.find("<주요내용>")
    if ri >= 0:
        start = ri + len("<제안이유>")
        reason = (_clean(text[start:mi]) or None) if mi >= 0 else _section_to_end(text, start)
    if mi >= 0:
        main = _section_to_end(text, mi + len("<주요내용>"))
    return reason, main


def run_bill_content(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True, sleep_sec: float = 0.4,
) -> dict:
    """의안원문 본문을 수집해 Bill.proposal_reason/main_content 채움(멱등).

    only_missing: content_fetched 없는 의안만(재실행 시 건너뜀). limit: 수집 의안 상한.
    """
    q = select(Bill).where(Bill.assembly_bill_id.isnot(None))
    if only_missing:
        q = q.where(Bill.content_fetched.is_(None))
    q = q.order_by(Bill.proposed_date.desc().nullslast(), Bill.id.desc())
    bills = list(session.scalars(q).all())

    n_ok = n_empty = n_err = n_done = 0
    for bill in bills:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        try:
            hwp = download_uian_hwp(bill.assembly_bill_id)
            reason = main = None
            if hwp:
                reason, main = parse_reason_content(extract_prvtext(hwp))
            if not dry_run:
                bill.proposal_reason = reason
                bill.main_content = main
                bill.content_fetched = _now()
            if reason or main:
                n_ok += 1
            else:
                n_empty += 1
        except Exception:  # noqa: BLE001 — 개별 의안 실패는 건너뛰고 계속
            n_err += 1
        if not dry_run and n_done % 20 == 0:
            session.commit()
        if sleep_sec:
            time.sleep(sleep_sec)

    if not dry_run:
        session.commit()
    return {"processed": n_done, "ok": n_ok, "empty": n_empty, "error": n_err}
