"""bill 제안이유·주요내용 본문 컬럼 (Phase 1-3 보완)

의안원문(HWP PrvText)에서 추출한 공식 본문 텍스트. AI 요약과 무관한 원문 그대로.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bill", sa.Column("proposal_reason", sa.Text(), nullable=True))
    op.add_column("bill", sa.Column("main_content", sa.Text(), nullable=True))
    op.add_column(
        "bill", sa.Column("content_fetched", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bill", "content_fetched")
    op.drop_column("bill", "main_content")
    op.drop_column("bill", "proposal_reason")
