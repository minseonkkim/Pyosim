"""ETL DB 세션 — backend 모델 재사용(동일 DATABASE_URL).

backend/app/models.py 의 ORM 클래스를 그대로 적재에 쓴다(스키마 중복 방지).
세션 엔진은 etl 설정(database_url)으로 별도 구성.
"""
from __future__ import annotations

import sys
from pathlib import Path

# etl 루트(config.py) + backend 패키지(app.*) 를 import 경로에 추가
_ETL = Path(__file__).resolve().parents[1]
_BACKEND = Path(__file__).resolve().parents[2] / "backend"
for _p in (str(_ETL), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models import (  # noqa: E402,F401 — 적재에서 재export
    Bill,
    Party,
    Person,
    Vote,
    VoteChoice,
    VoteRecord,
)

from config import settings  # noqa: E402  (etl/config.py)


def make_session_factory(database_url: str | None = None) -> sessionmaker:
    engine = create_engine(database_url or settings.database_url, future=True, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
