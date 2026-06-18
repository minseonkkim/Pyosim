"""의원별 표결기록(VoteRecord) 서비스 탐색 — 특정 BILL_ID 의 의원별 찬반.

의안별 표결현황(ncocpgfiaoituanbr)은 집계만 → 의원 개인별 찬/반/기권 서비스 필요.
실제 BILL_ID 로 후보 서비스 코드를 검증한다.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
BASE = "https://open.assembly.go.kr/portal/openapi"

# 의안별 표결현황에서 가져온 실제 본회의 표결 BILL_ID (기후위기 특위 구성의 건)
SAMPLE_BILL_ID = "PRC_T2F6O0M6X1Y1S0K9R0E0Q1M7C7Y5L3"

CANDIDATES: list[tuple[str, dict]] = [
    ("nojepdqqaweusdfbi", {"AGE": "22", "BILL_ID": SAMPLE_BILL_ID}),
    ("ncocpgfiaoituanbr", {"AGE": "22", "BILL_ID": SAMPLE_BILL_ID}),  # 비교용(집계)
    ("nwbpacrgavhjryiph", {"AGE": "22", "BILL_ID": SAMPLE_BILL_ID}),
    ("nzgdpaswqkprotlbm", {"AGE": "22", "BILL_ID": SAMPLE_BILL_ID}),
]


def load_key() -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("ASSEMBLY_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def probe(key: str, service: str, extra: dict) -> None:
    params = {"KEY": key, "Type": "json", "pIndex": 1, "pSize": 3, **extra}
    url = f"{BASE}/{service}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    print(f"[{service}] extra={extra}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ {e}\n")
        return
    if service in data and isinstance(data[service], list):
        head = data[service][0].get("head", [])
        total = next((h.get("list_total_count") for h in head if "list_total_count" in h), "?")
        code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
        rows = data[service][1].get("row", []) if len(data[service]) > 1 else []
        print(f"  ✅ CODE={code} 총={total}")
        if rows:
            print(f"     필드: {list(rows[0].keys())}")
            print(f"     샘플: {json.dumps(rows[0], ensure_ascii=False)[:700]}")
        print()
        return
    result = data.get("RESULT") or {}
    print(f"  ⛔ {result.get('CODE','?')}: {result.get('MESSAGE', str(data)[:200])}\n")


def main() -> int:
    key = load_key()
    for service, extra in CANDIDATES:
        probe(key, service, extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
