"""의안 본문 배치 수집 — likms 의안원문(HWP)에서 제안이유·주요내용 추출 (Phase 1-3 보완).

순수 다운로드·파싱 로직은 backend `app.bill_content` 로 일원화(중복 방지).
여기선 DB 를 훑어 미수집 의안을 멱등 배치로 채우는 오케스트레이션만 담는다.

🟡 원문 그대로 저장(요약·판정 없음). 출처 = likms billDetail.
⚠️ likms 스크래핑이므로 예의상 sleep + 필요한 의안만(표결/featured) 선별 수집 권장.

참고: 백엔드는 법안 열람 시 미수집 본문을 그 자리에서 받아 캐싱(on-demand)한다
(app/bills.py). 배치는 미리 데우거나(warm), on-demand 실패분 보강에 쓴다.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

# backend 패키지(app.*)는 jobs.db 가 sys.path 에 올려둠
from app.bill_content import (  # noqa: F401 — 재export(하위 호환)
    download_uian_hwp,
    extract_bodytext,
    fetch_bill_content,
    parse_reason_content,
)
from jobs.db import Bill


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_bill_content(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True, sleep_sec: float = 0.4,
) -> dict:
    """의안원문 본문을 수집해 Bill.proposal_reason/main_content 채움(멱등).

    only_missing: content_fetched 없는 의안만(재실행 시 건너뜀). limit: 수집 의안 상한.
    """
    q = select(Bill).where(Bill.assembly_bill_id.isnot(None))
    if only_missing:
        q = q.where(Bill.content_fetched.is_(None))
    q = q.order_by(Bill.proposed_date.desc().nullslast(), Bill.id.desc())
    bills = list(session.scalars(q).all())

    n_ok = n_empty = n_err = n_done = 0
    for bill in bills:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        try:
            reason, main = fetch_bill_content(bill.assembly_bill_id)
            if not dry_run:
                bill.proposal_reason = reason
                bill.main_content = main
                bill.content_fetched = _now()
            if reason or main:
                n_ok += 1
            else:
                n_empty += 1
        except Exception:  # noqa: BLE001 — 개별 의안 실패는 건너뛰고 계속
            n_err += 1
        if not dry_run and n_done % 20 == 0:
            session.commit()
        if sleep_sec:
            time.sleep(sleep_sec)

    if not dry_run:
        session.commit()
    return {"processed": n_done, "ok": n_ok, "empty": n_empty, "error": n_err}
