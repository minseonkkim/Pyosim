"""자동 갱신 파이프라인 — PipelineRun (1일 1회 데이터 갱신 실행 기록)

감시견 알림이 자동 점등되려면 추적 데이터가 매일 새로 적재돼야 한다.
이 표는 그 일일 갱신(`--job daily`)의 실행 결과를 기록해 신선도·모니터링을 가능케 한다.
"마지막 갱신 언제·성공했나" + 프론트 '데이터 기준일'(🟡 신뢰) 노출용.

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_run",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trigger", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("job_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("jobs", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pipeline_run_started_at", "pipeline_run", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_started_at", table_name="pipeline_run")
    op.drop_table("pipeline_run")
