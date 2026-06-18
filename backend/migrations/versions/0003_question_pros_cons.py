"""question 장단점 Ⓐ/Ⓑ 선택지 — Phase 1-1 접근성 개편

정치 용어 없이 양쪽 장점+단점을 대칭 제시하는 포맷으로 전환.
question 에 선택지별 라벨·장점·단점 6개 컬럼 추가(nullable).
채점 규약: option_a = 앵커 법안 '찬성' 표결 방향, option_b = '반대' 방향.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for col in (
        "option_a_label", "option_a_pro", "option_a_con",
        "option_b_label", "option_b_pro", "option_b_con",
    ):
        op.add_column("question", sa.Column(col, sa.Text(), nullable=True))


def downgrade() -> None:
    for col in (
        "option_b_con", "option_b_pro", "option_b_label",
        "option_a_con", "option_a_pro", "option_a_label",
    ):
        op.drop_column("question", col)
