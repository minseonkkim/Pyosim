"""스모크 적재 — 실제 API → 임시 SQLite 로 적재 경로 end-to-end 검증.

본 환경엔 Postgres 가 없으므로 SQLite 로 backend 스키마를 만들고
실제 열린국회정보에서 소량 수집해 적재 → row 수/샘플을 확인한다.
(프로덕션은 Postgres + alembic. 이 스크립트는 검증 전용.)

사용: python etl/scripts/smoke_load.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ETL = Path(__file__).resolve().parents[1]
if str(_ETL) not in sys.path:
    sys.path.insert(0, str(_ETL))

# backend app.db 가 import 시점에 엔진을 만든다 → psycopg 회피 위해 SQLite 로 지정.
DB_PATH = _ETL / "scripts" / ".smoke.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

# etl/.env 의 키를 환경변수로 주입(repo 루트에서 실행해도 동작하도록)
_ENV = _ETL / ".env"
if _ENV.exists():
    for _line in _ENV.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import jobs.db as jdb  # noqa: E402  (backend 경로 등록 + 모델 재export)
from app.db import Base  # noqa: E402
from clients.assembly import AssemblyClient  # noqa: E402
from config import settings  # noqa: E402
from jobs import ingest  # noqa: E402

DB_PATH = _ETL / "scripts" / ".smoke.sqlite"


def main() -> int:
    if not settings.assembly_api_key:
        print("ASSEMBLY_API_KEY 없음 — etl/.env 확인")
        return 1
    if DB_PATH.exists():
        DB_PATH.unlink()

    engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    # 페이지 대기 줄여 빠르게
    client = AssemblyClient(settings.assembly_api_key, sleep_sec=0.0)

    print("── members (전체 300명) ──")
    s = Session()
    print(" ", ingest.run_members(s, client))
    s.close()

    print("── bills (최근 30건) ──")
    s = Session()
    print(" ", ingest.run_bills(s, client, limit=30))
    s.close()

    print("── vote_records (의안 1건) ──")
    s = Session()
    print(" ", ingest.run_vote_records(s, client, limit=1))
    s.close()

    # 검증: row 수 + 샘플
    s = Session()
    counts = {
        "party": s.scalar(select(func.count()).select_from(jdb.Party)),
        "person": s.scalar(select(func.count()).select_from(jdb.Person)),
        "bill": s.scalar(select(func.count()).select_from(jdb.Bill)),
        "vote": s.scalar(select(func.count()).select_from(jdb.Vote)),
        "vote_record": s.scalar(select(func.count()).select_from(jdb.VoteRecord)),
    }
    print("\n── DB row 수 ──")
    for k, v in counts.items():
        print(f"  {k:12} {v}")

    print("\n── 표결 집계 샘플 (Bill ↔ Vote) ──")
    rows = s.execute(
        select(jdb.Bill.bill_no, jdb.Bill.title, jdb.Vote.yes_total, jdb.Vote.no_total,
               jdb.Vote.blank_total, jdb.Bill.likms_url)
        .join(jdb.Vote, jdb.Vote.bill_id == jdb.Bill.id)
        .limit(3)
    ).all()
    for r in rows:
        print(f"  [{r.bill_no}] {r.title[:30]} | 찬{r.yes_total}/반{r.no_total}/기{r.blank_total}")
        print(f"     출처: {r.likms_url}")

    print("\n── 정당별 표결기록 분포 (1개 의안) ──")
    dist = s.execute(
        select(jdb.Party.name, jdb.VoteRecord.choice, func.count())
        .join(jdb.Person, jdb.Person.id == jdb.VoteRecord.person_id)
        .join(jdb.Party, jdb.Party.id == jdb.Person.party_id)
        .group_by(jdb.Party.name, jdb.VoteRecord.choice)
        .order_by(jdb.Party.name)
    ).all()
    for name, choice, cnt in dist:
        c = choice.value if hasattr(choice, "value") else choice
        print(f"  {name:10} {c:4} {cnt}")
    s.close()

    ok = counts["person"] > 0 and counts["bill"] > 0 and counts["vote_record"] > 0
    print("\n" + ("✅ 스모크 적재 성공" if ok else "❌ 적재 결과 비정상"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
