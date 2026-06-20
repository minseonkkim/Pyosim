"""person 인적사항 보강 — 생년월일·성별·선수·직책 (Phase 1-2)

열린국회정보 의원 API(`nwvrqwxyaytdsfvhu`)에 300/300 들어 있으나 미수집이던
생년월일(나이)·성별·선수(초선/재선)·직책을 프로필에 채우기 위한 컬럼.
🟡 공식 출처(국회) 기준 사실만. 판정·가공 없음.

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("person", sa.Column("birth_date", sa.Date(), nullable=True))
    op.add_column("person", sa.Column("gender", sa.String(length=10), nullable=True))
    op.add_column("person", sa.Column("term_label", sa.String(length=20), nullable=True))
    op.add_column("person", sa.Column("position", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("person", "position")
    op.drop_column("person", "term_label")
    op.drop_column("person", "gender")
    op.drop_column("person", "birth_date")
