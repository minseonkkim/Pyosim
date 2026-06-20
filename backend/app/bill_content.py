"""의안 본문 수집·파싱 — likms 의안원문(HWP) BodyText 에서 제안이유·주요내용 추출.

열린국회정보 OpenAPI 엔 본문이 없어, 의안정보시스템(likms)의 '의안원문' HWP 를 받아
**BodyText 섹션(전체 본문)**에서 제안이유/주요내용을 뽑는다.
(PrvText 미리보기는 ~1024자에서 잘려 본문엔 부적합 → BodyText 레코드를 직접 파싱.)

수집 흐름(라이브 역추적 확정):
  1) billDetail.do?billId=  방문 → 세션 쿠키(JSESSIONID)
  2) downloadDtlZip.do  POST(billId, docChkList=의안원문) → zip
  3) zip 안의 .hwp → olefile 로 OLE 열기 → BodyText/Section* 레코드 파싱 → 제안이유/주요내용

🟡 원문 그대로(요약·판정 없음). 출처 = likms billDetail. AI 요약(좋은점/문제점)은 별도 단계.
⚠️ likms 스크래핑이므로 on-demand(법안 열람 시 1건) 또는 선별 배치로만 호출.

이 모듈은 순수 함수(네트워크 + 파싱)만 담는다. DB 적재는 호출 측(backend on-demand /
etl 배치)에서 담당한다.
"""
from __future__ import annotations

import http.cookiejar
import io
import re
import struct
import urllib.parse
import urllib.request
import zipfile
import zlib
from datetime import date

import olefile

LIKMS = "https://likms.assembly.go.kr"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"

# 의안 상세(billDetail) HTML 의 '제안일자' — OpenAPI 표결현황엔 처리일(PROC_DT)만 있고
# 위원장 '대안' 가결안의 발의일이 빠져, 상세 페이지에서 직접 추출(발의법률안 목록엔 대안 미포함).
_PROPOSE_DT = re.compile(r"제안일자[^0-9]{0,40}(\d{4}-\d{2}-\d{2})")


def fetch_propose_date(bill_id: str) -> date | None:
    """billId(PRC_…/ARC_…) 의 의안 상세에서 '제안일자' 추출. 없으면 None.

    네트워크/파싱 예외는 호출 측에서 처리(여기선 그대로 전파).
    """
    req = urllib.request.Request(
        f"{LIKMS}/bill/billDetail.do?billId={bill_id}", headers={"User-Agent": UA}
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    # 태그 제거 후 공백 압축 — 라벨·값이 표 셀로 떨어져 있어 줄바꿈/공백이 길게 낀다.
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    m = _PROPOSE_DT.search(text)
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


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


# HWP5 PARA_TEXT 안의 8-wchar(16바이트) 인라인 컨트롤 문자 코드
_INLINE_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
_HWPTAG_PARA_TEXT = 0x43


def _decode_paratext(rec: bytes) -> str:
    """PARA_TEXT 레코드(UTF-16LE + 인라인 컨트롤) → 텍스트."""
    out: list[str] = []
    j, n = 0, len(rec)
    while j + 1 < n:
        code = rec[j] | (rec[j + 1] << 8)
        if code in _INLINE_CTRL:
            j += 16  # 8 wchar 컨트롤(표·그림 등) 건너뜀
        elif code in (10, 13):
            out.append("\n")
            j += 2
        elif code < 32:
            j += 2  # 기타 제어문자 무시
        else:
            out.append(chr(code))
            j += 2
    return "".join(out)


def extract_bodytext(hwp: bytes) -> str:
    """HWP5(OLE) 의 BodyText 섹션에서 **전체 본문** 추출.

    PrvText(미리보기)는 ~1024자에서 잘리므로 본문엔 부적합 → BodyText 레코드를 직접 파싱.
    """
    ole = olefile.OleFileIO(io.BytesIO(hwp))
    try:
        compressed = bool(ole.openstream("FileHeader").read()[36] & 1)
        sections = sorted("/".join(e) for e in ole.listdir() if e and e[0] == "BodyText")
        parts: list[str] = []
        for sec in sections:
            data = ole.openstream(sec).read()
            if compressed:
                data = zlib.decompress(data, -15)
            i, n = 0, len(data)
            while i + 4 <= n:
                header = struct.unpack_from("<I", data, i)[0]
                i += 4
                tag = header & 0x3FF
                size = (header >> 20) & 0xFFF
                if size == 0xFFF:
                    size = struct.unpack_from("<I", data, i)[0]
                    i += 4
                rec = data[i : i + size]
                i += size
                if tag == _HWPTAG_PARA_TEXT:
                    parts.append(_decode_paratext(rec))
        return "\n".join(parts)
    finally:
        ole.close()


def _clean(s: str) -> str:
    s = s.replace("\x00", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip(" \n\r<>")


# 본문 끝 경계(법안 원문/대비표/부칙 시작) — 제안이유·주요내용 뒤에 법안 본문이 이어짐
_END = re.compile(r"법률\s*제\s*[\d ]*호|구조문대비표|\n\s*부\s*칙")
# 마커(`<>` 유무·공백 무관). 결합형 우선.
_COMBINED = re.compile(r"<?\s*제안이유\s*및\s*주요\s*내용\s*>?")
_REASON = re.compile(r"<?\s*제안이유\s*>?")
_MAIN = re.compile(r"<?\s*주요\s*내용\s*>?")


def _section_to_end(text: str, start: int) -> str | None:
    seg = text[start:]
    m = _END.search(seg)
    return _clean(seg[: m.start()] if m else seg) or None


def parse_reason_content(text: str) -> tuple[str | None, str | None]:
    """본문 → (제안이유, 주요내용). PrvText/BodyText, `<>` 유무 모두 처리.

    - 결합형 '제안이유 및 주요내용': 통째로 첫 필드, 둘째 None.
    - 분리형 '제안이유' … '주요내용' …: 각각 분리.
    마커 없으면 (None, None).
    """
    text = text.replace("\x00", "")

    cm = _COMBINED.search(text)
    if cm:
        return _section_to_end(text, cm.end()), None

    reason = main = None
    rm = _REASON.search(text)
    mm = _MAIN.search(text)
    if rm:
        start = rm.end()
        if mm and mm.start() > rm.start():
            reason = _clean(text[start : mm.start()]) or None
        else:
            reason = _section_to_end(text, start)
    if mm:
        main = _section_to_end(text, mm.end())
    return reason, main


def fetch_bill_content(bill_id: str) -> tuple[str | None, str | None]:
    """billId → (제안이유, 주요내용). 문서 없으면 (None, None).

    네트워크/파싱 예외는 호출 측에서 처리(여기선 그대로 전파).
    """
    hwp = download_uian_hwp(bill_id)
    if not hwp:
        return None, None
    return parse_reason_content(extract_bodytext(hwp))
