"""위원회 — Committee 엔티티 + 의원↔위원회 경력 매핑 (Phase 1-1)

출처: 위원회 현황(nxrvzonlafugpqjuh) + 위원회 경력(nyzrglyvagmrypezq, 제22대).
상임위 17 + 예결특위 1 을 정규화하고, 의원의 제22대 위원회 경력을 엔티티에 매칭한다.
🟡 '현재 소속'이 아닌 공식 '위원회 경력'(활동기간 term_label 원문 보존).

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "committee",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dept_code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type_name", sa.String(length=40), nullable=True),
        sa.Column("member_limit", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_committee_dept_code", "committee", ["dept_code"], unique=True)
    op.create_index("ix_committee_name", "committee", ["name"], unique=False)

    op.create_table(
        "committee_membership",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("committee_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("term_label", sa.String(length=60), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("last_verified", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["committee_id"], ["committee.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("committee_id", "person_id", name="uq_committee_person"),
    )
    op.create_index(
        "ix_committee_membership_committee_id", "committee_membership", ["committee_id"]
    )
    op.create_index(
        "ix_committee_membership_person_id", "committee_membership", ["person_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_committee_membership_person_id", table_name="committee_membership")
    op.drop_index("ix_committee_membership_committee_id", table_name="committee_membership")
    op.drop_table("committee_membership")
    op.drop_index("ix_committee_name", table_name="committee")
    op.drop_index("ix_committee_dept_code", table_name="committee")
    op.drop_table("committee")
