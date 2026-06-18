"""열린국회정보(open.assembly.go.kr) OpenAPI 공용 클라이언트.

규약(외부_API.md):
- Base: https://open.assembly.go.kr/portal/openapi/{SERVICE}
- 인증: 쿼리 KEY=, 포맷 Type=json, 페이징 pIndex(1부터)/pSize
- ⚠️ User-Agent 필수: 기본 파이썬 UA 는 HTTP 400 → 브라우저류 UA 필수.
- 봉투: {SERVICE:[{head:[{list_total_count},{RESULT:{CODE}}]},{row:[...]}]}
  정상 CODE=INFO-000. 데이터 없음 INFO-200. 그 외/최상위 RESULT 는 오류.

자체 DB 캐싱·배치 수집 전제(기획서 13장 rate limit 대응)라 page 단위 generator 제공.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator

BASE = "https://open.assembly.go.kr/portal/openapi"
# gov API 는 기본 UA 차단 → 브라우저류 UA 필수(실측 확인)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"


class AssemblyAPIError(RuntimeError):
    """INFO-000/INFO-200 이외 응답."""


class AssemblyClient:
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
            raise ValueError("ASSEMBLY_API_KEY 가 비어 있습니다.")
        self.api_key = api_key
        self.page_size = page_size
        self.sleep_sec = sleep_sec  # rate limit 예의상 페이지 간 대기
        self.timeout = timeout
        self.max_retries = max_retries

    # ── 단일 페이지 ──────────────────────────────────────────
    def _request(self, service: str, params: dict) -> dict:
        query = urllib.parse.urlencode(
            {"KEY": self.api_key, "Type": "json", **params}
        )
        url = f"{BASE}/{service}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except Exception as e:  # noqa: BLE001 — 네트워크/일시 오류 재시도
                last_err = e
                time.sleep(self.sleep_sec * (attempt + 1))
        raise AssemblyAPIError(f"{service} 요청 실패: {last_err}")

    @staticmethod
    def _parse(service: str, data: dict) -> tuple[int, list[dict]]:
        """(전체건수, row리스트) 반환. INFO-200(데이터없음)은 (0, [])."""
        if service in data and isinstance(data[service], list):
            envelope = data[service]
            head = envelope[0].get("head", []) if envelope else []
            code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
            total = next(
                (h["list_total_count"] for h in head if "list_total_count" in h), 0
            )
            if not str(code).startswith("INFO-0"):
                raise AssemblyAPIError(f"{service}: {code}")
            rows = envelope[1].get("row", []) if len(envelope) > 1 else []
            return int(total), rows
        # 최상위 RESULT — INFO-200(데이터없음)은 정상 빈 결과로 취급
        result = data.get("RESULT") or {}
        code = result.get("CODE", "?")
        if code == "INFO-200":
            return 0, []
        raise AssemblyAPIError(f"{service}: {code} {result.get('MESSAGE', '')}")

    def fetch_page(self, service: str, *, p_index: int, params: dict) -> tuple[int, list[dict]]:
        data = self._request(service, {"pIndex": p_index, "pSize": self.page_size, **params})
        return self._parse(service, data)

    # ── 전체 페이지 순회 ─────────────────────────────────────
    def iter_rows(
        self, service: str, *, params: dict | None = None, max_rows: int | None = None
    ) -> Iterator[dict]:
        """서비스의 모든 row 를 페이지 순회하며 yield. max_rows 로 상한 지정 가능."""
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
