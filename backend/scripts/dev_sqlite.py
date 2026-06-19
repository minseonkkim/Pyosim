"""로컬 개발용 SQLite DB 부트스트랩 (Postgres 없이 프론트 연동 확인).

backend 디렉터리에서:
  DATABASE_URL 을 SQLite 로 두고 스키마 생성 + 시드.
  이후 같은 DATABASE_URL 로 uvicorn 실행:
    DATABASE_URL=sqlite:///./scripts/.dev.sqlite python -m uvicorn app.main:app

이 스크립트 단독 실행: python scripts/dev_sqlite.py  (DB 생성·시드)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_BACKEND / 'scripts' / '.dev.sqlite'}")

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from app.db import Base, engine  # noqa: E402
from app import seed, seed_demo, seed_questions  # noqa: E402


def main() -> None:
    # create_all 은 '없는 테이블'만 만들고 기존 테이블에 컬럼을 추가하지 못한다.
    # 모델이 바뀌면(예: review_note 추가) 낡은 dev DB와 어긋나 'no such column' 발생.
    # → SQLite(개발용)일 때만 drop_all 로 스키마를 모델과 강제 동기화한다(시드 전용이라 안전).
    #   Postgres 등 실제 DB는 절대 drop 하지 않는다 — 그쪽은 alembic 마이그레이션 사용.
    if engine.url.get_backend_name() == "sqlite":
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed.run()
    seed_demo.run()
    seed_questions.run()
    print(f"\n준비 완료: {engine.url}")


if __name__ == "__main__":
    main()
