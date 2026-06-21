"""감시견 알림 — Subscription (익명 세션의 청원·법안·의원 구독)

기획 4 "감시견 알림": 시민이 관심 대상을 구독하면 진행 변화 시 알린다.
익명 세션(localStorage UUID) 기반이라 OS 푸시가 아닌 앱 내 '변화 알림' 받은함으로 전달.
snapshot(상태 서명)을 기준선으로 두고 GET /api/watch 가 현재 상태와 diff 한다.

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "kind", "ref_id", name="uq_subscription_target"),
    )
    op.create_index("ix_subscription_session_id", "subscription", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_subscription_session_id", table_name="subscription")
    op.drop_table("subscription")
