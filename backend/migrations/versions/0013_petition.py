"""청원 — Petition 엔티티 (Phase 2 기능 A, 민심 레이어)

출처: 청원 계류현황(nvqbafvaajdiqhehi) + 처리현황(ncryefyuaflxnqbqo, 제22대).
시민 청원이 접수→소관위 회부→심사→처리 중 '지금 어디서 멈췄는지'를 공식 일자로 추적.
🟡 발안자 개인정보 최소화 — 공개 기록(likms) 값만 보존, 처리결과는 공식 코드 원문 그대로.

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "petition",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_no", sa.String(length=40), nullable=False),
        sa.Column("assembly_bill_id", sa.String(length=60), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("proposer", sa.String(length=200), nullable=True),
        sa.Column("introducer", sa.String(length=120), nullable=True),
        sa.Column("is_national_consent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signature_count", sa.Integer(), nullable=True),
        sa.Column("proposed_date", sa.Date(), nullable=True),
        sa.Column("committee", sa.String(length=120), nullable=True),
        sa.Column("committee_date", sa.Date(), nullable=True),
        sa.Column("proc_result", sa.String(length=60), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_petition_bill_no", "petition", ["bill_no"], unique=True)
    op.create_index("ix_petition_assembly_bill_id", "petition", ["assembly_bill_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_petition_assembly_bill_id", table_name="petition")
    op.drop_index("ix_petition_bill_no", table_name="petition")
    op.drop_table("petition")
