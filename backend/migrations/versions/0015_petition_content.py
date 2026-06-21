"""청원 본문 — Petition 에 취지·내용·분야 (국민동의청원 API)

출처: petitions.assembly.go.kr /api/petits (billId = assembly_bill_id 로 매칭).
petitObjet(취지)·petitCn(내용 전문)·petitRealmNm(분야)을 보존.
🟡 공식 공개 원문 그대로. 일반청원(의원소개)은 이 사이트에 없어 null.

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("petition", sa.Column("objective", sa.Text(), nullable=True))
    op.add_column("petition", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("petition", sa.Column("realm", sa.String(length=40), nullable=True))
    op.add_column(
        "petition", sa.Column("content_fetched", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("petition", "content_fetched")
    op.drop_column("petition", "realm")
    op.drop_column("petition", "content")
    op.drop_column("petition", "objective")
