"""변별력 있는 정책 법안 추출 — 정당이 실제로 갈린 본회의 표결.

성향 테스트 문항의 앵커는 '정당이 갈리는' 법안일수록 변별력이 크다.
- 반대표 유의미(NO_TCNT >= MINNO) 의안만 후보
- 정치갈등성(특검·계엄·내란·감사요구·국정조사·예결산 등)은 중립성 위해 제외
- 각 후보의 정당별 다수 입장(찬/반) 계산 → 민주 vs 국힘이 갈리면 변별력↑

사용: python etl/scripts/discriminating_bills.py [MINNO]
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

ENV = Path(__file__).resolve().parent.parent / ".env"
OUT = Path(__file__).resolve().parent / "discriminating_bills.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
TALLY = "ncocpgfiaoituanbr"
PERMEMBER = "nojepdqqaweusdfbi"
MINNO = int(sys.argv[1]) if len(sys.argv) > 1 else 20

# 정치갈등성/절차성 — 정책 성향 테스트에 부적합 → 제외
EXCLUDE = [
    "특별검사", "특검", "내란", "계엄", "탄핵", "감사요구", "감사 요구", "국정조사",
    "결산", "예산안", "기금운용", "회기", "의사일정", "규칙", "구성의 건", "사퇴",
    "해임", "위원 정수", "선출", "선임", "추천", "임명동의", "결의안",  # 결의안은 대개 정쟁성
    "본회의록", "징계", "체포동의", "자격심사",
]
MAJOR = ["더불어민주당", "국민의힘", "조국혁신당", "개혁신당", "진보당"]


def key() -> str:
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith("ASSEMBLY_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


KEY = key()


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


def pos(counts: dict) -> str:
    return "찬" if counts.get("찬성", 0) >= counts.get("반대", 0) and counts.get("찬성", 0) > 0 else "반"


def main() -> int:
    def no(r):
        try:
            return int(r.get("NO_TCNT") or 0)
        except ValueError:
            return 0

    tally = get(TALLY, {"AGE": "22"})
    cands = [
        r for r in tally
        if no(r) >= MINNO and not any(k in (r.get("BILL_NAME") or "") for k in EXCLUDE)
    ]
    cands.sort(key=no, reverse=True)
    print(f"전체 {len(tally)} → 반대≥{MINNO} & 정쟁제외 후보 {len(cands)}건. 정당별 입장 계산…\n")

    results = []
    for r in cands:
        bid = r.get("BILL_ID")
        by_party: dict[str, dict] = defaultdict(lambda: {"찬성": 0, "반대": 0, "기권": 0, "불참": 0})
        for row in get(PERMEMBER, {"AGE": "22", "BILL_ID": bid}):
            party = (row.get("POLY_NM") or "무소속").strip()
            ch = (row.get("RESULT_VOTE_MOD") or "").strip()
            if party in by_party or True:
                if ch in by_party[party]:
                    by_party[party][ch] += 1
        positions = {p: pos(by_party[p]) for p in MAJOR if p in by_party}
        split = positions.get("더불어민주당") != positions.get("국민의힘")
        n_distinct = len(set(positions.values()))
        results.append({
            "bill_no": r.get("BILL_NO"), "name": r.get("BILL_NAME"),
            "no": no(r), "yes": r.get("YES_TCNT"),
            "positions": positions, "민주국힘갈림": split, "구분수": n_distinct,
            "by_party": {p: dict(by_party[p]) for p in by_party},
            "link": r.get("LINK_URL"),
        })
        time.sleep(0.05)

    # 변별력: 민주vs국힘 갈림 우선, 그 다음 구분수, 반대수
    results.sort(key=lambda x: (x["민주국힘갈림"], x["구분수"], x["no"]), reverse=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    print("변별력 순 (민주/국힘/혁신/개혁/진보 입장):")
    for x in results:
        pstr = " ".join(f"{p[:2]}:{v}" for p, v in x["positions"].items())
        flag = "⚡갈림" if x["민주국힘갈림"] else "      "
        print(f"  {flag} 반{x['no']:>3} [{x['bill_no']}] {x['name'][:42]}")
        print(f"            {pstr}")
    print(f"\n저장: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
