"""bill 제안자 구분 — 정부·위원장·전직의원 표기 컬럼 (Phase 1-3c)

발의법률안 API(nzmimeepazxkubdpn)는 의원발의만 담아 정부·위원장 제출안은
대표발의자가 비어 보인다. 의안검색 API(TVBPMBILL11)의 PROPOSER_KIND/PROPOSER 로
모든 의안의 제안자 구분을 채워 빈칸을 메운다.
🟡 정부안 소관부처(○○부)는 API 에 없어 proposer_text 는 "정부" 까지만 담긴다.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bill", sa.Column("proposer_kind", sa.String(length=20), nullable=True))
    op.add_column("bill", sa.Column("proposer_text", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("bill", "proposer_text")
    op.drop_column("bill", "proposer_kind")
