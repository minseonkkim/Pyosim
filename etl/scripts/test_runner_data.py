"""문항 테스트용 — 14개 앵커 법안의 정당별 실제 표결 집계.

각 앵커 의안에 대해 의원별 표결(nojepdqqaweusdfbi)을 모아 정당별 찬/반/기권/불참 카운트.
결과를 JSON 으로 저장 → 테스트 응답과 비교해 정당 일치율 산출.

사용: python etl/scripts/test_runner_data.py
"""
import json
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

ENV = Path(__file__).resolve().parent.parent / ".env"
OUT = Path(__file__).resolve().parent / "test_anchor_votes.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
TALLY = "ncocpgfiaoituanbr"
PERMEMBER = "nojepdqqaweusdfbi"

# 앵커 의안번호 (4차 개편 — 최근 2025년 이후 변별력 8문항)
ANCHORS = [
    "2212656", "2208496", "2213246", "2202967",
    "2211639", "2211925", "2211647", "2214866",
]


def key() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASSEMBLY_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def get(service: str, params: dict) -> list[dict]:
    rows: list[dict] = []
    p = 1
    while True:
        q = urllib.parse.urlencode({"KEY": KEY, "Type": "json", "pIndex": p, "pSize": 1000, **params})
        req = urllib.request.Request(f"https://open.assembly.go.kr/portal/openapi/{service}?{q}",
                                     headers={"User-Agent": UA})
        d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        if service not in d:
            break
        env = d[service]
        total = env[0]["head"][0]["list_total_count"]
        batch = env[1].get("row", []) if len(env) > 1 else []
        rows += batch
        if len(rows) >= total or not batch:
            break
        p += 1
    return rows


KEY = key()


def main() -> int:
    # bill_no -> (BILL_ID, name, 집계)
    meta: dict[str, dict] = {}
    for r in get(TALLY, {"AGE": "22"}):
        bn = r.get("BILL_NO")
        if bn in ANCHORS:
            meta[bn] = {
                "bill_id": r.get("BILL_ID"),
                "name": r.get("BILL_NAME"),
                "yes": r.get("YES_TCNT"), "no": r.get("NO_TCNT"), "blank": r.get("BLANK_TCNT"),
                "link": r.get("LINK_URL"),
            }

    result: dict[str, dict] = {}
    for bn in ANCHORS:
        m = meta.get(bn)
        if not m:
            print(f"  ⚠ {bn} 집계에 없음")
            continue
        by_party: dict[str, dict] = defaultdict(lambda: {"찬성": 0, "반대": 0, "기권": 0, "불참": 0})
        for row in get(PERMEMBER, {"AGE": "22", "BILL_ID": m["bill_id"]}):
            party = (row.get("POLY_NM") or "무소속").strip()
            ch = (row.get("RESULT_VOTE_MOD") or "").strip()
            if ch in by_party[party]:
                by_party[party][ch] += 1
        result[bn] = {**m, "by_party": by_party}
        print(f"  [{bn}] {m['name'][:30]} 찬{m['yes']}/반{m['no']} · 정당 {len(by_party)}곳")

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n저장: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
