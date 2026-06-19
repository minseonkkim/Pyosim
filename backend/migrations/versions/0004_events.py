"""event — 익명 퍼널 로깅 테이블 (Phase 1-6)

이탈 지점 측정용 익명 이벤트. PII 미수집(세션ID·이벤트명·소형 props 만).

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("props", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_event_session_id", "event", ["session_id"])
    op.create_index("ix_event_name", "event", ["name"])


def downgrade() -> None:
    op.drop_index("ix_event_name", table_name="event")
    op.drop_index("ix_event_session_id", table_name="event")
    op.drop_table("event")
