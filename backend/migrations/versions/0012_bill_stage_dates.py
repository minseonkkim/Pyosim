"""bill 처리 단계별 의결일 — 날짜 타임라인 (Phase 1-3)

본회의 처리안건(nwbpacrgavhjryiph)의 단계별 일자로 funnel 을 실제 날짜 타임라인으로
승격한다. 소관위/법사위/본회의 의결일 + 공포일. 발의일은 기존 proposed_date 사용.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bill", sa.Column("committee_proc_date", sa.Date(), nullable=True))
    op.add_column("bill", sa.Column("law_proc_date", sa.Date(), nullable=True))
    op.add_column("bill", sa.Column("plenary_proc_date", sa.Date(), nullable=True))
    op.add_column("bill", sa.Column("announce_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("bill", "announce_date")
    op.drop_column("bill", "plenary_proc_date")
    op.drop_column("bill", "law_proc_date")
    op.drop_column("bill", "committee_proc_date")
