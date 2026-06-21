"""청원 두 서비스(계류현황·처리현황) 전체 필드+샘플값 라이브 덤프.

기능 A(청원 추적) 모델 설계 전 실제 필드명/값 확정용.
사용: python etl/scripts/explore_petitions.py
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

SERVICES = [
    ("nvqbafvaajdiqhehi", "청원 계류현황", {"AGE": "22"}),
    ("ncryefyuaflxnqbqo", "청원 처리현황", {"AGE": "22"}),
]


def load_key(name: str) -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return ""


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    key = load_key("ASSEMBLY_API_KEY")
    for service, name, extra in SERVICES:
        print("=" * 70)
        print(f"[{service}] {name}")
        params = {"KEY": key, "Type": "json", "pIndex": 1, "pSize": 3, **extra}
        data = get(f"{BASE}/{service}?{urllib.parse.urlencode(params)}")
        env = data.get(service)
        if not isinstance(env, list):
            print("  ⛔", json.dumps(data, ensure_ascii=False)[:300])
            continue
        head = env[0].get("head", [])
        total = next((h.get("list_total_count") for h in head if "list_total_count" in h), "?")
        code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
        rows = env[1].get("row", []) if len(env) > 1 else []
        print(f"  CODE={code} 총={total} rows={len(rows)}")
        for i, row in enumerate(rows):
            print(f"  --- row {i} ---")
            for k, v in row.items():
                print(f"    {k}: {v!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
