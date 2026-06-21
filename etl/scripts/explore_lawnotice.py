"""입법예고 두 서비스(진행중·종료) 전체 필드+샘플값 라이브 덤프.

기능 B-4.4(입법예고 댓글 vs 통과) 착수 전 관문 검증:
  - 어떤 필드를 주는가? 특히 **시민 찬반 의견 카운트**(찬성/반대/기타 수)가 있는가?
  - 없으면 메타만 → 국민참여입법센터(opinion.lawmaking.go.kr) 별도 OC 키 병행 필요.

여러 파라미터 조합(AGE/DAE_NUM 유무)을 시도해 데이터가 채워지는 호출을 찾는다.
사용: python etl/scripts/explore_lawnotice.py
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

# 같은 서비스를 여러 파라미터 조합으로 두드려본다.
PARAM_TRIES = [
    {},
    {"AGE": "22"},
    {"DAE_NUM": "22"},
    {"AGE": "21"},
    {"DAE_NUM": "21"},
]

SERVICES = [
    ("nknalejkafmvgzmpt", "진행중 입법예고"),
    ("nohgwtzsamojdozky", "종료된 입법예고"),
]


def load_key(name: str) -> str:
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return ""


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"_err": str(e)}


def probe(key: str, service: str, extra: dict):
    params = {"KEY": key, "Type": "json", "pIndex": 1, "pSize": 3, **extra}
    data = get(f"{BASE}/{service}?{urllib.parse.urlencode(params)}")
    if "_err" in data:
        return None, f"요청실패 {data['_err']}", []
    env = data.get(service)
    if not isinstance(env, list):
        result = data.get("RESULT") or {}
        return None, f"{result.get('CODE','?')}: {result.get('MESSAGE', str(data)[:160])}", []
    head = env[0].get("head", [])
    total = next((h.get("list_total_count") for h in head if "list_total_count" in h), "?")
    code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
    rows = env[1].get("row", []) if len(env) > 1 else []
    return total, code, rows


def main() -> int:
    key = load_key("ASSEMBLY_API_KEY")
    for service, name in SERVICES:
        print("=" * 72)
        print(f"[{service}] {name}")
        best = None
        for extra in PARAM_TRIES:
            total, code, rows = probe(key, service, extra)
            mark = "✅" if rows else ("·" if code == "INFO-000" or code == "INFO-200" else "⛔")
            print(f"  {mark} extra={extra or '{}'} → CODE={code} 총={total} rows={len(rows)}")
            if rows and best is None:
                best = (extra, rows)
        if best:
            extra, rows = best
            print(f"\n  ── 필드 덤프 (extra={extra}) ──")
            for i, row in enumerate(rows):
                print(f"  --- row {i} ---")
                for k, v in row.items():
                    print(f"    {k}: {v!r}")
        else:
            print("  (어떤 조합에서도 row 0건 — 회기상 비어있거나 다른 필수 파라미터 필요)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
