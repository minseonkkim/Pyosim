"""데이터 신선도·파이프라인 모니터링 — 자동 갱신(🤖) 가시화.

1일 1회 자동 갱신 파이프라인(`etl/jobs/pipeline.py`)이 실행될 때마다 PipelineRun
한 행이 쌓인다. 이 라우터는 그 기록을 노출해 두 가지를 가능케 한다:
  1) **모니터링** — 마지막 실행 언제·성공했나, 어떤 잡이 실패했나(운영).
  2) **신선도** — 프론트가 '데이터 기준일'을 표시(🟡 신뢰: 데이터가 살아있음을 사실로).

감시견 알림(`app/watch.py`)은 DB 현재 상태를 실시간 diff 하므로, 이 갱신이 돌면
구독자의 받은함이 자동 점등된다. 즉 이 엔드포인트의 last_success 가 곧 '알림이
언제까지 최신인가'의 사실 근거다.

엔드포인트:
  GET /api/health/pipeline   최근 실행 요약 + 마지막 성공 시각(신선도)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PipelineRun

router = APIRouter(prefix="/api/health", tags=["health"])


class PipelineRunInfo(BaseModel):
    started_at: datetime
    finished_at: datetime | None
    ok: bool
    trigger: str
    job_count: int
    fail_count: int
    duration_ms: int | None
    failed_jobs: list[str]  # 실패한 잡 이름(운영 한눈에)


class PipelineHealth(BaseModel):
    last_run: PipelineRunInfo | None
    last_success_at: datetime | None  # 신선도 기준 — 프론트 '데이터 기준일'
    notice: str


NOTICE = (
    "데이터는 국회 공식 소스(의안정보시스템·열린국회정보)를 1일 1회 자동 갱신합니다. "
    "아래 시각은 마지막 갱신 사실이며, 가치 판단을 담지 않습니다."
)


def _failed_jobs(jobs: dict | None) -> list[str]:
    if not isinstance(jobs, dict):
        return []
    return [name for name, info in jobs.items()
            if isinstance(info, dict) and info.get("status") == "fail"]


@router.get("/pipeline", response_model=PipelineHealth)
def pipeline_health(db: Session = Depends(get_db)) -> PipelineHealth:
    """최근 실행 1건 + 마지막 성공 시각. 기록이 없으면 last_run=None."""
    last = db.scalar(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(1)
    )
    last_ok = db.scalar(
        select(PipelineRun)
        .where(PipelineRun.ok.is_(True))
        .order_by(PipelineRun.started_at.desc())
        .limit(1)
    )

    info = None
    if last is not None:
        info = PipelineRunInfo(
            started_at=last.started_at,
            finished_at=last.finished_at,
            ok=last.ok,
            trigger=last.trigger,
            job_count=last.job_count,
            fail_count=last.fail_count,
            duration_ms=last.duration_ms,
            failed_jobs=_failed_jobs(last.jobs),
        )
    return PipelineHealth(
        last_run=info,
        last_success_at=last_ok.finished_at if last_ok else None,
        notice=NOTICE,
    )
