"""입법예고 — LawNotice 엔티티 (Phase 2 기능 B-4.4, 민심 레이어 둘째 축)

출처: 종료된 입법예고(nohgwtzsamojdozky)·진행중(nknalejkafmvgzmpt) 메타데이터
  + 국민참여입법시스템(pal.assembly.go.kr) 의견목록 입장별 집계(스크랩).
법안 입법예고 기간 시민 찬반 의견을 집계해 국회 처리(통과)와 대비한다.
🟡 의견 본문·작성자는 저장 안 하고 입장별 건수만. 처리 대비는 공식 일자(Bill)만.

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "law_notice",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bill_no", sa.String(length=40), nullable=False),
        sa.Column("assembly_bill_id", sa.String(length=60), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("proposer", sa.String(length=200), nullable=True),
        sa.Column("proposer_kind", sa.String(length=20), nullable=True),
        sa.Column("committee", sa.String(length=120), nullable=True),
        sa.Column("notice_end_date", sa.Date(), nullable=True),
        sa.Column("is_ongoing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opinion_total", sa.Integer(), nullable=True),
        sa.Column("agree_count", sa.Integer(), nullable=True),
        sa.Column("oppose_count", sa.Integer(), nullable=True),
        sa.Column("etc_count", sa.Integer(), nullable=True),
        sa.Column("opinion_fetched", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_law_notice_bill_no", "law_notice", ["bill_no"], unique=True)
    op.create_index(
        "ix_law_notice_assembly_bill_id", "law_notice", ["assembly_bill_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_law_notice_assembly_bill_id", table_name="law_notice")
    op.drop_index("ix_law_notice_bill_no", table_name="law_notice")
    op.drop_table("law_notice")
