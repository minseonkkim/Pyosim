"""ingest external ids & vote tallies — Phase 1-2 수집 파이프라인 지원

열린국회정보 수집을 위한 외부 식별자/집계 컬럼 추가:
- person.assembly_member_code (MONA_CD) — 표결기록 매핑 키
- bill.assembly_bill_id (BILL_ID, PRC_...) — 표결기록·likms 직링크 키
- vote.{member_total, vote_total, yes_total, no_total, blank_total} — 본회의 표결 집계

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("person", sa.Column("assembly_member_code", sa.String(20), nullable=True))
    op.create_index(
        "ix_person_assembly_member_code", "person", ["assembly_member_code"], unique=True
    )

    op.add_column("bill", sa.Column("assembly_bill_id", sa.String(60), nullable=True))
    op.create_index("ix_bill_assembly_bill_id", "bill", ["assembly_bill_id"])

    op.add_column("vote", sa.Column("member_total", sa.Integer(), nullable=True))
    op.add_column("vote", sa.Column("vote_total", sa.Integer(), nullable=True))
    op.add_column("vote", sa.Column("yes_total", sa.Integer(), nullable=True))
    op.add_column("vote", sa.Column("no_total", sa.Integer(), nullable=True))
    op.add_column("vote", sa.Column("blank_total", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("vote", "blank_total")
    op.drop_column("vote", "no_total")
    op.drop_column("vote", "yes_total")
    op.drop_column("vote", "vote_total")
    op.drop_column("vote", "member_total")

    op.drop_index("ix_bill_assembly_bill_id", table_name="bill")
    op.drop_column("bill", "assembly_bill_id")

    op.drop_index("ix_person_assembly_member_code", table_name="person")
    op.drop_column("person", "assembly_member_code")
