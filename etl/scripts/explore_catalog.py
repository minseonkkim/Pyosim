"""발급된 키 2개로 '추가로 뽑을 수 있는' 서비스를 라이브 실측.

- 열린국회정보(ASSEMBLY_API_KEY): 전체 271개 서비스가 동일 키 하나로 열린다.
  여기선 제품(로드맵) 관련 후보만 찍어 CODE/총건수/필드키를 확정한다.
- 열린재정(OFD_API_KEY): OPFI 코드 연속대를 스윕해 분야/부처/회계/사업 서비스를 발견.

사용: python etl/scripts/explore_catalog.py
키는 etl/.env. 결과는 stdout + etl/scripts/explore_catalog_result.txt(UTF-8).
"""
import io
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
OUT_PATH = Path(__file__).resolve().parent / "explore_catalog_result.txt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
ASM_BASE = "https://open.assembly.go.kr/portal/openapi"
OFD_BASE = "https://openapi.openfiscaldata.go.kr"

# (서비스코드, 한글명, 추가파라미터) — 로드맵 매핑 후보
ASSEMBLY = [
    # 위원회 (Phase 1-1)
    ("nxrvzonlafugpqjuh", "위원회 현황 정보", {}),
    ("nktulghcadyhmiqxi", "위원회 위원 명단", {}),
    ("nyzrglyvagmrypezq", "국회의원 위원회 경력", {}),
    ("nuvypcdgahexhvrjt", "국회의원 상임위 활동", {}),
    ("ndiwuqmpambgvnfsj", "위원회 계류법률안", {}),
    ("ncwgseseafwbuheph", "위원회 회의록", {}),
    # 청원 (Phase 2 기능 A)
    ("nvqbafvaajdiqhehi", "청원 계류현황", {"AGE": "22"}),
    ("ncryefyuaflxnqbqo", "청원 처리현황", {"AGE": "22"}),
    ("PTTRCP", "청원 접수목록", {}),
    ("PTTINFODETAIL", "청원 상세정보", {}),
    ("NAMEMBERLEGIPTT", "국회의원 청원현황", {}),
    # 입법예고 (Phase 2 기능 B-4.4)
    ("nknalejkafmvgzmpt", "진행중 입법예고", {}),
    ("nohgwtzsamojdozky", "종료된 입법예고", {}),
    # 의안 심사/공동발의 (Phase 1-3 / 2-5)
    ("BILLINFODETAIL", "의안 상세정보", {}),
    ("BILLINFOPPSR", "의안 제안자정보(공동발의)", {}),
    ("BILLJUDGE", "의안 심사정보", {}),
    ("BILLRCP", "의안 접수목록", {}),
    ("nayjnliqaexiioauy", "본회의 부의안건", {"AGE": "22"}),
    ("nwbpacrgavhjryiph", "본회의 처리안건_법률안", {"AGE": "22"}),
    # 처리 의안통계 (기능 B-4.2 활동량)
    ("BILLCNTPRPSR", "처리 의안통계(발의주체별)", {}),
    ("BILLCNTRSVT", "계류의안 통계", {}),
    ("nzivskufaliivfhpb", "역대 의안 통계", {}),
    # 의원 프로필 보강
    ("negnlnyvatsjwocar", "국회의원 SNS정보", {}),
    ("nexgtxtmaamffofof", "국회의원 의원이력", {}),
    ("nqfvrbsdafrmuzixe", "날짜별 의정활동", {}),
    # 회의록/발언 (콘텐츠)
    ("nzbyfwhwaoanttzje", "본회의 회의록", {}),
    ("npeslxqbanwkimebr", "국회의원 영상회의록(발언영상)", {}),
    # 일정 (감시견/타임라인)
    ("ALLSCHEDULE", "국회일정 통합", {}),
    ("nekcaiymatialqlxr", "본회의 일정", {}),
    # 정당
    ("nepjpxkkabqiqpbvk", "정당·교섭단체 의석수", {}),
    # 국정감사 (시즌)
    ("AUDITREPORTRESULT", "국정감사 결과보고서", {}),
    ("nrvsawtaauyihadij", "인사청문회", {}),
    # 국회 자체 예산
    ("nztwkhgzakucszgls", "사업별 예산 편성 규모", {}),
    # 교차 검증(타 기관도 같은 키로 열리나)
    ("negjnychalvyrcifv", "[NABO] 결산 분석", {}),
    ("nxlcxbbkapsrjayur", "[입법조사처] 이슈와 논점", {}),
]


def load_key(name: str) -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return ""


def _get(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as e:  # noqa: BLE001
        return {"_err": str(e)}
    try:
        data = json.loads(raw)
        if isinstance(data, str):  # 열린재정 이중 인코딩
            data = json.loads(data)
        return data
    except json.JSONDecodeError:
        return {"_raw": raw[:160]}


def _envelope(service: str, data: dict, w) -> None:
    if "_err" in data:
        w(f"  ❌ 요청실패: {data['_err']}")
        return
    if "_raw" in data:
        w(f"  ⚠ JSON아님: {data['_raw']}")
        return
    if service in data and isinstance(data[service], list):
        head = data[service][0].get("head", [])
        total = next((h.get("list_total_count") for h in head if "list_total_count" in h), "?")
        code = next((h["RESULT"]["CODE"] for h in head if "RESULT" in h), "?")
        rows = data[service][1].get("row", []) if len(data[service]) > 1 else []
        fields = list(rows[0].keys()) if rows else []
        w(f"  ✅ CODE={code} 총={total}")
        if fields:
            w(f"     필드: {fields}")
        return
    result = data.get("RESULT") or {}
    w(f"  ⛔ {result.get('CODE','?')}: {result.get('MESSAGE', str(data)[:140])}")


def main() -> int:
    buf: list[str] = []

    def w(s: str = "") -> None:
        print(s)
        buf.append(s)

    asm_key = load_key("ASSEMBLY_API_KEY")
    ofd_key = load_key("OFD_API_KEY")

    w("=" * 70)
    w("[열린국회정보] 동일 ASSEMBLY_API_KEY 로 추가 접근 가능 서비스 실측")
    w("=" * 70)
    for service, name, extra in ASSEMBLY:
        w(f"\n[{service}] {name}  extra={extra}")
        params = {"KEY": asm_key, "Type": "json", "pIndex": 1, "pSize": 2, **extra}
        data = _get(f"{ASM_BASE}/{service}?{urllib.parse.urlencode(params)}")
        _envelope(service, data or {}, w)

    w("\n" + "=" * 70)
    w("[열린재정] OFD_API_KEY 로 OPFI 코드대 스윕 (ACNT_YR=2024)")
    w("=" * 70)
    for n in range(160, 186):
        service = f"OPFI{n}"
        params = {"Key": ofd_key, "Type": "json", "pIndex": 1, "pSize": 1, "ACNT_YR": "2024"}
        data = _get(f"{OFD_BASE}/{service}?{urllib.parse.urlencode(params)}")
        w(f"\n[{service}]")
        _envelope(service, data or {}, w)

    OUT_PATH.write_text("\n".join(buf) + "\n", encoding="utf-8")
    w(f"\n→ 저장: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
