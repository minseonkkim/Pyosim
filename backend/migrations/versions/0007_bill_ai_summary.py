"""bill AI 요약(좋은점/문제점) 컬럼 (Phase 1-3)

제안이유·주요내용 원문(0006)은 그대로 두고, 그 위에 LLM 이 생성한
**좋은점/문제점 양쪽 대칭 요약**을 별도 필드로 보관한다.
🟡 중립성: 원문과 분리, 어느 모델이 생성했는지(summary_model) 출처 기록.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bill", sa.Column("summary_pros", sa.Text(), nullable=True))
    op.add_column("bill", sa.Column("summary_cons", sa.Text(), nullable=True))
    op.add_column("bill", sa.Column("summary_model", sa.String(length=60), nullable=True))
    op.add_column(
        "bill", sa.Column("summary_fetched", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("bill", "summary_fetched")
    op.drop_column("bill", "summary_model")
    op.drop_column("bill", "summary_cons")
    op.drop_column("bill", "summary_pros")
