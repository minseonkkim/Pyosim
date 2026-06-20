"""법안 AI 요약 배치 — 제안이유·주요내용 원문 → 좋은점/문제점(양쪽 대칭) 생성 (Phase 1-3).

순수 호출·파싱 로직은 backend `app.bill_summary` 로 일원화(중복 방지).
여기선 본문이 있으나 요약이 없는 의안을 멱등 배치로 채우는 오케스트레이션만 담는다.

🟡 원문은 건드리지 않고 좋은점/문제점만 별도 저장. 양쪽 대칭(한쪽이라도 비면 건너뜀).
참고: 백엔드는 법안 열람 시 미생성 요약을 그 자리에서 만들어 캐싱(on-demand)한다(app/bills.py).
배치는 미리 데우거나(warm) on-demand 실패분 보강에 쓴다.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

# jobs.db 를 먼저 import 해야 backend(app.*)·etl(config) 가 sys.path 에 올라간다.
from jobs.db import Bill
from app.bill_summary import summarize_bill  # noqa: E402 (위 import 가 경로 설정)
from config import settings  # noqa: E402 — etl/config.py


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_bill_summary(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True, sleep_sec: float = 0.5,
) -> dict:
    """본문(제안이유/주요내용)이 있는 의안의 좋은점/문제점을 생성해 채움(멱등).

    only_missing: summary_fetched 없는 의안만. limit: 생성 의안 상한.
    """
    if not settings.gemini_api_key:
        return {"error": "GEMINI_API_KEY 미설정 — 요약 생략", "processed": 0}

    q = select(Bill).where(
        (Bill.proposal_reason.isnot(None)) | (Bill.main_content.isnot(None))
    )
    if only_missing:
        q = q.where(Bill.summary_fetched.is_(None))
    q = q.order_by(Bill.proposed_date.desc().nullslast(), Bill.id.desc())
    bills = list(session.scalars(q).all())

    n_ok = n_skip = n_err = n_done = 0
    for bill in bills:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        try:
            pros, cons = summarize_bill(
                bill.title, bill.proposal_reason, bill.main_content,
                api_key=settings.gemini_api_key, model=settings.gemini_model,
            )
            if not pros or not cons:  # 대칭 깨짐 → 저장 안 함(다음에 재시도)
                n_skip += 1
                continue
            if not dry_run:
                bill.summary_pros = pros
                bill.summary_cons = cons
                bill.summary_model = settings.gemini_model
                bill.summary_fetched = _now()
            n_ok += 1
        except Exception:  # noqa: BLE001 — 개별 의안 실패는 건너뛰고 계속
            n_err += 1
        if not dry_run and n_done % 10 == 0:
            session.commit()
        if sleep_sec:
            time.sleep(sleep_sec)

    if not dry_run:
        session.commit()
    return {"processed": n_done, "ok": n_ok, "skipped": n_skip, "error": n_err}
