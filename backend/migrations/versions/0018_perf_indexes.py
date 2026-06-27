"""성능 인덱스 — FK·정렬 컬럼 인덱스 + pg_trgm 부분검색 GIN

읽기 전용 공개 서비스의 핫 경로(인물 프로필·법안 피드·제목 검색) 가속:
- bill.proposer_id  : 인물 프로필의 '대표발의 법안' 조회(FK 무인덱스 → seq scan 제거)
- bill.proposed_date: 검색·목록의 최근발의순 정렬
- vote.no_total     : 피드의 반대표 많은순 정렬
- law_notice.opinion_total : '의견 많은순' 정렬
- pg_trgm GIN(bill.title/bill_no): ILIKE '%term%' 선행 와일드카드 검색 인덱싱
  (선행 % 라 btree 불가 → trigram GIN 으로 부분 문자열 매칭 가속)

🟡 데이터·로직 변경 없음. 순수 조회 성능용 인덱스만 추가.

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK·정렬 컬럼 btree 인덱스
    op.create_index("ix_bill_proposer_id", "bill", ["proposer_id"])
    op.create_index("ix_bill_proposed_date", "bill", ["proposed_date"])
    op.create_index("ix_vote_no_total", "vote", ["no_total"])
    op.create_index("ix_law_notice_opinion_total", "law_notice", ["opinion_total"])

    # 부분 문자열 검색(ILIKE '%term%') — pg_trgm GIN
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_bill_title_trgm ON bill "
        "USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_bill_bill_no_trgm ON bill "
        "USING gin (bill_no gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bill_bill_no_trgm")
    op.execute("DROP INDEX IF EXISTS ix_bill_title_trgm")
    # 확장(pg_trgm)은 다른 곳에서 쓸 수 있어 남겨둔다.
    op.drop_index("ix_law_notice_opinion_total", table_name="law_notice")
    op.drop_index("ix_vote_no_total", table_name="vote")
    op.drop_index("ix_bill_proposed_date", table_name="bill")
    op.drop_index("ix_bill_proposer_id", table_name="bill")
