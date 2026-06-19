"""프로토타입 데모 시드 — 앵커 법안 8건(Phase 1-3~1-4 로컬 구동용).

본 환경엔 Postgres·전수 표결기록이 없으므로, 문항이 법안과 매핑되도록(출처 노출)
seed_questions.DRAFTS 의 앵커 의안만 최소 정보로 적재한다.
정당 입장은 scoring.CURATED_PARTY_STANCES(실제 표결 집계 사실)로 채점된다.

⚠️ 데모 전용: 개별 의원 표결기록은 만들지 않는다(중립성·출처 원칙).
   프로덕션은 etl ingest(members/bills/vote_records)로 실데이터를 적재.

실행: python -m app.seed_demo  (seed → seed_demo → seed_questions 순서 권장, 멱등)
"""
from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Bill
from app.seed_questions import DRAFTS


def _title(source: str) -> str:
    """source 메모에서 법안명 추출: '<법안명> · 의안 ...' → '<법안명>'."""
    return source.split(" · 의안")[0].strip()


def run() -> None:
    db = SessionLocal()
    try:
        existing = {b.bill_no for b in db.scalars(select(Bill)).all()}
        n_new = 0
        for d in DRAFTS:
            if d.bill_no in existing:
                continue
            db.add(Bill(bill_no=d.bill_no, title=_title(d.source)))
            existing.add(d.bill_no)
            n_new += 1
        db.commit()
        print(f"데모 앵커 법안 시드: 신규 {n_new}, 전체 {len(DRAFTS)} (멱등)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
