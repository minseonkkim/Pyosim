"""문항 앵커용 — 본회의 표결에서 의견이 갈린(반대표 유의미) 의안 추출.

성향 판별 테스트(Phase 1-1)는 정당이 갈리는 쟁점에서 변별력이 생긴다.
의안별 표결현황(ncocpgfiaoituanbr)에서 NO_TCNT 가 큰 의안을 내림차순 출력.

사용: python etl/scripts/contested_bills.py [최소반대수]
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

ENV = Path(__file__).resolve().parent.parent / ".env"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
SVC = "ncocpgfiaoituanbr"
MIN_NO = int(sys.argv[1]) if len(sys.argv) > 1 else 30


def key() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASSEMBLY_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_all(k: str) -> list[dict]:
    rows: list[dict] = []
    p = 1
    while True:
        q = urllib.parse.urlencode({"KEY": k, "Type": "json", "pIndex": p, "pSize": 1000, "AGE": "22"})
        req = urllib.request.Request(f"https://open.assembly.go.kr/portal/openapi/{SVC}?{q}",
                                     headers={"User-Agent": UA})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        env = d[SVC]
        total = env[0]["head"][0]["list_total_count"]
        batch = env[1].get("row", []) if len(env) > 1 else []
        rows.extend(batch)
        if len(rows) >= total or not batch:
            break
        p += 1
    return rows


def main() -> int:
    rows = fetch_all(key())
    def no(r):
        try:
            return int(r.get("NO_TCNT") or 0)
        except ValueError:
            return 0
    contested = sorted((r for r in rows if no(r) >= MIN_NO), key=no, reverse=True)
    print(f"전체 {len(rows)}건 중 반대 {MIN_NO}표 이상: {len(contested)}건\n")
    for r in contested:
        print(f"반{no(r):>3} 찬{r.get('YES_TCNT'):>3} 기{r.get('BLANK_TCNT'):>3} "
              f"[{r.get('BILL_NO')}] {r.get('BILL_NAME')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
