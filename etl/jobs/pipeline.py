"""자동 갱신 파이프라인 (1일 1회) — 감시견 알림 자동 점등의 전제.

감시견 diff(`backend/app/watch.py`)는 **DB의 현재 상태를 실시간으로** 읽어 구독
스냅샷과 비교한다. 즉 DB만 매일 새로 채우면 알림은 저절로 점등된다. 이 파이프라인이
그 '매일 새로 채우기'를 한 번의 진입점(`python -m jobs.run --job daily`)으로 묶는다.

설계 원칙:
  - **잡별 격리**: 한 잡이 실패해도(예: 외부 API 일시 장애) 나머지는 계속 — 부분
    실패가 전체 갱신을 막지 않게.
  - **세션·클라이언트 재사용**: 한 DB 세션·한 AssemblyClient 를 잡들이 공유.
  - **기록**: 각 실행을 PipelineRun 한 행으로 남겨 신선도·모니터링 가능
    (마지막 갱신 언제·성공했나 / 프론트 '데이터 기준일').

일일 세트(DAILY): 감시견이 추적하는 세 종류(청원·법안·의원)를 신선하게 유지하는
가벼운 공식-API 잡만. 스크래핑(bill_content/lawnotice_opinions/propose_dates)·
LLM(bill_summary)·연단위(budget)·거의 안 바뀌는 것(photos)은 제외 → 별도 수동/주간.

🟡 PII 없음 — PipelineRun 은 시스템 실행 메타만 저장(세션·개인정보 무관).
"""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone

from jobs import categorize, ingest


# ── 일일 갱신 잡 순서 (의존성 고려) ──────────────────────────────
# members(사람 기준) → bills(새 법안) → proposers/vote_records(의원 활동 diff)
# → bill_stages(법안 단계 diff) → petitions(청원 단계 diff) → categorize(피드 태깅).
# 각 항목: (잡 이름, 호출 함수, kwargs). kwargs 의 limit 은 무거운 잡 보호용 기본값.
def _api_job(fn):
    """ingest.run_* 류: (session, client, *, age, dry_run, limit) 시그니처."""
    def call(session, client, *, age, dry_run, limit):
        return fn(session, client, age=age, dry_run=dry_run, limit=limit)
    return call


def _no_client_job(fn):
    """categorize 류: (session, *, dry_run, limit) — 클라이언트 불필요."""
    def call(session, client, *, age, dry_run, limit):
        return fn(session, dry_run=dry_run, limit=limit)
    return call


# limit_default: 해당 잡의 기본 상한(None=전수). CLI --limit 가 오면 그것으로 덮어씀.
DAILY: list[tuple[str, "callable", int | None]] = [
    ("members", _api_job(ingest.run_members), None),
    ("bills", _api_job(ingest.run_bills), None),
    ("proposers", _api_job(ingest.run_proposers), None),
    ("vote_records", _api_job(ingest.run_vote_records), None),
    ("bill_stages", _api_job(ingest.run_bill_stages), None),
    ("petitions", _api_job(ingest.run_petitions), None),
    ("categorize", _no_client_job(categorize.run_categorize), None),
]

PROFILES: dict[str, list] = {"daily": DAILY}


def run_pipeline(
    session,
    client,
    *,
    profile: str = "daily",
    only: list[str] | None = None,
    age: str = "22",
    dry_run: bool = False,
    limit: int | None = None,
    trigger: str = "manual",
) -> dict:
    """프로필의 잡들을 순서대로 실행. 잡별 실패는 격리하고 끝까지 진행 후 기록.

    only: 이 이름들만 실행(나머지 건너뜀). limit: 모든 잡에 적용(기본 상한 덮어씀).
    """
    steps = PROFILES.get(profile)
    if steps is None:
        raise ValueError(f"알 수 없는 프로필: {profile}. 등록됨: {', '.join(PROFILES)}")
    if only:
        wanted = set(only)
        steps = [s for s in steps if s[0] in wanted]

    from jobs.db import PipelineRun

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    results: dict[str, dict] = {}
    fail_count = 0

    print(f"[pipeline] {profile} 시작 — 잡 {len(steps)}개{' (dry-run)' if dry_run else ''}")
    for name, fn, limit_default in steps:
        eff_limit = limit if limit is not None else limit_default
        jt0 = time.monotonic()
        try:
            stats = fn(session, client, age=age, dry_run=dry_run, limit=eff_limit)
            dur = int((time.monotonic() - jt0) * 1000)
            results[name] = {
                "status": "ok",
                "stats": stats if isinstance(stats, dict) else {"result": str(stats)},
                "duration_ms": dur,
            }
            print(f"[pipeline]   ✓ {name} ({dur}ms): {stats}")
        except Exception as exc:  # noqa: BLE001 — 잡별 격리: 끝까지 진행
            session.rollback()  # 실패 잡의 미완 트랜잭션 정리
            fail_count += 1
            dur = int((time.monotonic() - jt0) * 1000)
            results[name] = {
                "status": "fail",
                "error": f"{type(exc).__name__}: {exc}",
                "duration_ms": dur,
            }
            print(f"[pipeline]   ✗ {name} ({dur}ms) 실패: {type(exc).__name__}: {exc}")
            traceback.print_exc()

    duration_ms = int((time.monotonic() - t0) * 1000)
    ok = fail_count == 0
    summary = {
        "profile": profile,
        "ok": ok,
        "job_count": len(steps),
        "fail_count": fail_count,
        "duration_ms": duration_ms,
        "jobs": results,
    }

    # 실행 기록(dry-run 도 남겨 두면 리허설 확인 가능 — 단 ok/통계는 그대로).
    try:
        run = PipelineRun(
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            ok=ok,
            trigger=trigger,
            job_count=len(steps),
            fail_count=fail_count,
            duration_ms=duration_ms,
            jobs=json.loads(json.dumps(results, ensure_ascii=False, default=str)),
        )
        session.add(run)
        session.commit()
    except Exception as exc:  # noqa: BLE001 — 기록 실패가 갱신 자체를 무효화하진 않게
        session.rollback()
        print(f"[pipeline] ⚠ 실행 기록 저장 실패: {type(exc).__name__}: {exc}")

    print(
        f"[pipeline] {profile} 완료 — {'성공' if ok else f'{fail_count}개 실패'} "
        f"({duration_ms}ms)"
    )
    return summary
