"""외부 API Key 동작 확인 — 의존성 없이(stdlib) 실행.

사용: python etl/scripts/check_api_keys.py
키는 etl/.env 또는 환경변수에서 읽는다.

열린국회정보(open.assembly.go.kr) 응답 형식:
  {"<SERVICE>": [{"head":[{"list_total_count":N},{"RESULT":{"CODE":"INFO-000",...}}]},
                 {"row":[...]}]}
  오류 시 head 가 없고 {"RESULT":{"CODE":"INFO-300", "MESSAGE":"인증키가 유효하지 않습니다"}}.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Windows 콘솔(cp949)에서도 이모지/한글 출력되도록
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
# gov API 는 기본 User-Agent 를 차단 → 브라우저 UA 필요
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    # 실제 환경변수가 우선
    for k in ("ASSEMBLY_API_KEY", "NEC_API_KEY", "DATA_GO_KR_API_KEY"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def check_assembly(key: str) -> bool:
    """국회의원 인적사항(ALLNAMEMBER) 1건 조회로 키 검증."""
    if not key:
        print("  ⏭  ASSEMBLY_API_KEY 없음 — 건너뜀")
        return False
    params = urllib.parse.urlencode({"KEY": key, "Type": "json", "pIndex": 1, "pSize": 1})
    url = f"https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 요청 실패: {e}")
        return False

    # 정상: {"ALLNAMEMBER":[{"head":[...,{"RESULT":{"CODE":"INFO-000"}}]}, {"row":[...]}]}
    if "ALLNAMEMBER" in data:
        try:
            head = data["ALLNAMEMBER"][0]["head"]
            total = head[0]["list_total_count"]
            code = head[1]["RESULT"]["CODE"]
            print(f"  ✅ 열린국회정보 OK — RESULT={code}, 총 {total}건 조회 가능")
            return code.startswith("INFO-0")
        except (KeyError, IndexError, TypeError):
            pass
    # 오류 형식
    result = data.get("RESULT") or {}
    print(f"  ❌ 열린국회정보 응답 이상 — {result.get('CODE','?')}: {result.get('MESSAGE', data)}")
    return False


def main() -> int:
    env = load_env()
    print("외부 API Key 검증\n" + "-" * 40)

    print("[열린국회정보 open.assembly.go.kr]")
    assembly_ok = check_assembly(env.get("ASSEMBLY_API_KEY", ""))

    print("\n[선관위 / 공공데이터포털]")
    if not env.get("NEC_API_KEY") and not env.get("DATA_GO_KR_API_KEY"):
        print("  ⏭  미발급 — Phase 2~3 착수 전 발급 필요")

    print("-" * 40)
    return 0 if assembly_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
