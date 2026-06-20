"""bill 생활 카테고리 — 세금·노동·주거 등 "내 삶과 상관" 태깅 (Phase 1-3b)

법안 피드(/bills)에서 관심 분야로 좁혀볼 수 있게 하는 분류 컬럼.
🟡 결정론적 키워드 분류(etl/jobs/categorize.py)로 채운다 — 규칙이 코드로 공개됨.
값은 분류기가 채우며, 미매칭 법안은 NULL(칩에 노출 안 됨).

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bill", sa.Column("category", sa.String(length=20), nullable=True))
    op.create_index("ix_bill_category", "bill", ["category"])


def downgrade() -> None:
    op.drop_index("ix_bill_category", table_name="bill")
    op.drop_column("bill", "category")
