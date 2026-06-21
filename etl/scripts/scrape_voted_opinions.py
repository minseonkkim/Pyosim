"""표결까지 끝난 법안의 입법예고 시민 찬반 의견을 우선 스크랩 (민심 vs 표결 불일치 채우기).

run_lawnotice_opinions(voted_only=True) 를 청크로 돌리며 진행상황을 stdout 에 흘린다.
큰 의안(수천 의견=수십 페이지)이 많아 오래 걸리므로 background 로 돌리고 진행을 본다.

사용: python etl/scripts/scrape_voted_opinions.py [건수상한]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # etl 루트(= jobs 패키지 부모)

from jobs.db import make_session_factory  # noqa: E402
from jobs.lawnotice_opinions import run_lawnotice_opinions  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass


def main() -> int:
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    session = make_session_factory()()
    # 10건씩 끊어 돌리며 진행을 출력(중간 결과를 바로 확인 가능)
    done_total = 0
    while done_total < cap:
        chunk = min(10, cap - done_total)
        stats = run_lawnotice_opinions(
            session, voted_only=True, only_missing=True, limit=chunk, sleep_sec=0.2
        )
        processed = stats["processed"]
        print(f"[+{processed}] {stats}", flush=True)
        done_total += processed
        if processed == 0:  # 더 이상 미수집 대상 없음
            break
    print(f"== 종료: 누적 처리 {done_total} ==", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
