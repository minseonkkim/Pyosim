"""열린재정(openapi.openfiscaldata.go.kr) OpenAPI 클라이언트.

규약(실측 확인):
- Base: https://openapi.openfiscaldata.go.kr/{SERVICE}
- 인증: 쿼리 Key=, 포맷 Type=json, 페이징 pIndex(1부터)/pSize
- ⚠️ User-Agent 필수(기본 파이썬 UA 차단)
- ⚠️ 응답이 JSON '문자열'로 한 번 더 감싸져 옴 → json.loads 두 번 필요.
- 봉투는 열린국회정보와 동일:
  {SERVICE:[{head:[{list_total_count},{RESULT:{CODE}}]},{row:[...]}]}
  정상 CODE=INFO-000. 데이터 없음 INFO-200. 그 외/최상위 RESULT 는 오류.

서비스 코드 메모:
- OPFI165: 16대 분야별 재원배분(총지출 기준) — DIV_NM='결산'(실제 집행), 파라미터 ACNT_YR.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator

BASE = "https://openapi.openfiscaldata.go.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"


class OpenFiscalAPIError(RuntimeError):
    """INFO-000/INFO-200 이외 응답."""


class OpenFiscalClient:
    def __init__(
        self,
        api_key: str,
        *,
        page_size: int = 1000,
        sleep_sec: float = 0.2,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ValueError("OFD_API_KEY 가 비어 있습니다.")
        self.api_key = api_key
        self.page_size = page_size
        self.sleep_sec = sleep_sec
        self.timeout = timeout
        self.max_retries = max_retries

    def _request(self, service: str, params: dict) -> dict:
        query = urllib.parse.urlencode({"Key": self.api_key, "Type": "json", **params})
        url = f"{BASE}/{service}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                # 열린재정은 JSON 문자열로 한 번 더 감싸 보냄
                if isinstance(data, str):
                    data = json.loads(data)
                return data
            except Exception as e:  # noqa: BLE001 — 네트워크/일시 오류 재시도
                last_err = e
                time.sleep(self.sleep_sec * (attempt + 1))
        raise OpenFiscalAPIError(f"{service} 요청 실패: {last_err}")

    @staticmethod
    def _parse(service: str, data: dict) -> tuple[int, list[dict]]:
        """(전체건수, row리스트). INFO-200(데이터없음)은 (0, [])."""
        if service in data and isinstance(data[service], list):
            envelope = data[service]
            head = envelope[0].get("head", []) if envelope else []
            code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
            total = next(
                (h["list_total_count"] for h in head if "list_total_count" in h), 0
            )
            if not str(code).startswith("INFO-0"):
                raise OpenFiscalAPIError(f"{service}: {code}")
            rows = envelope[1].get("row", []) if len(envelope) > 1 else []
            return int(total), rows
        result = data.get("RESULT") or {}
        code = result.get("CODE", "?")
        if code == "INFO-200":
            return 0, []
        raise OpenFiscalAPIError(f"{service}: {code} {result.get('MESSAGE', '')}")

    def fetch_page(self, service: str, *, p_index: int, params: dict) -> tuple[int, list[dict]]:
        data = self._request(service, {"pIndex": p_index, "pSize": self.page_size, **params})
        return self._parse(service, data)

    def iter_rows(
        self, service: str, *, params: dict | None = None, max_rows: int | None = None
    ) -> Iterator[dict]:
        params = dict(params or {})
        p_index = 1
        yielded = 0
        total: int | None = None
        while True:
            count, rows = self.fetch_page(service, p_index=p_index, params=params)
            if total is None:
                total = count
            if not rows:
                break
            for row in rows:
                yield row
                yielded += 1
                if max_rows is not None and yielded >= max_rows:
                    return
            if yielded >= total:
                break
            p_index += 1
            if self.sleep_sec:
                time.sleep(self.sleep_sec)
