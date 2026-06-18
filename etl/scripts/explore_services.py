"""의안·표결 OpenAPI 서비스 탐색 — 후보 서비스 코드를 라이브로 검증.

열린국회정보 서비스 코드는 암호화 문자열이라 문서가 불일치 → 직접 호출로 확정.
각 후보에 대해: RESULT 코드 / 총건수 / 첫 row 의 필드 키 / 샘플 1건을 출력.

사용: python etl/scripts/explore_services.py
키는 etl/.env 의 ASSEMBLY_API_KEY.
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

# (서비스코드, 설명, 추가 파라미터)
CANDIDATES: list[tuple[str, str, dict]] = [
    ("ALLNAMEMBER", "국회의원 인적사항(기지원)", {}),
    ("nwvrqwxyaytdsfvhu", "국회의원 본회의 표결정보?", {"AGE": "22"}),
    ("ncocpgfiaoituanbr", "의안별 표결현황?", {"AGE": "22"}),
    ("nzmimeepazxkubdpn", "국회의원 발의법률안?", {"AGE": "22"}),
    ("TVBPMBILL11", "의안검색?", {"AGE": "22"}),
    ("BILLINFODETAIL", "의안 상세정보?", {}),
    ("nwbpacrgavhjryiph", "본회의 처리안건?", {"AGE": "22"}),
    ("ALLBILL", "의안정보 통합?", {}),
]


def load_key() -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ASSEMBLY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def probe(key: str, service: str, extra: dict) -> None:
    params = {"KEY": key, "Type": "json", "pIndex": 1, "pSize": 2, **extra}
    url = f"{BASE}/{service}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 요청 실패: {e}\n")
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  ⚠ JSON 아님(앞 200자): {raw[:200]}\n")
        return

    # 봉투: {SERVICE: [{head:[{list_total_count}, {RESULT}]}, {row:[...]}]}
    if service in data and isinstance(data[service], list):
        head = data[service][0].get("head", [])
        total = next((h.get("list_total_count") for h in head if "list_total_count" in h), "?")
        code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
        rows = data[service][1].get("row", []) if len(data[service]) > 1 else []
        print(f"  ✅ CODE={code} 총={total}")
        if rows:
            print(f"     필드: {list(rows[0].keys())}")
            print(f"     샘플: {json.dumps(rows[0], ensure_ascii=False)[:600]}")
        print()
        return
    result = data.get("RESULT") or {}
    print(f"  ⛔ {result.get('CODE','?')}: {result.get('MESSAGE', str(data)[:200])}\n")


def main() -> int:
    key = load_key()
    if not key:
        print("ASSEMBLY_API_KEY 없음")
        return 1
    for service, desc, extra in CANDIDATES:
        print(f"[{service}] {desc}  extra={extra}")
        probe(key, service, extra)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
