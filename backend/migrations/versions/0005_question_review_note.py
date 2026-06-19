"""question.review_note (Phase 2-3 어드민 검토 메모/반려 사유)

반려는 별도 enum 값 대신 status=아카이브 + review_note('[반려] …')로 표현 →
크로스DB(enum ALTER) 마이그레이션 회피, 문서화된 status 흐름(초안→검토중→승인→아카이브) 유지.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("question", sa.Column("review_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("question", "review_note")
