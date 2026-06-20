"""의안 발의일(제안일자) 배치 수집 — likms 의안 상세에서 추출 (Phase 1-2 보완).

배경: 본회의 표결현황 OpenAPI(ncocpgfiaoituanbr)엔 처리일(PROC_DT=표결일)만 있고,
발의법률안 OpenAPI(nzmimeepazxkubdpn)엔 위원장 '대안(대안가결안)'이 빠져 있어
표결된 대안의 발의일이 비어 있다. 의안 상세(billDetail) HTML 의 '제안일자'로 채운다.

순수 추출 로직은 backend `app.bill_content.fetch_propose_date` 로 일원화(중복 방지).
여기선 DB 를 훑어 발의일 미수집 의안을 멱등 배치로 채우는 오케스트레이션만 담는다.

🟡 출처 = likms billDetail. ⚠️ 스크래핑이므로 sleep + 미수집분만 선별 수집.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

# ⚠️ jobs.db 를 먼저 import — 모듈 로드 시 backend(app.*) 를 sys.path 에 올린다.
from jobs.db import Bill  # noqa: I001 — app.* import 전에 경로 설정 필요
from app.bill_content import fetch_propose_date


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_propose_dates(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True, sleep_sec: float = 0.4,
) -> dict:
    """Bill.proposed_date 를 의안 상세 '제안일자'로 채움(멱등).

    only_missing: proposed_date 없는 의안만(재실행 시 건너뜀). 최신(의안번호 큰) 순.
    """
    q = select(Bill).where(Bill.assembly_bill_id.isnot(None))
    if only_missing:
        q = q.where(Bill.proposed_date.is_(None))
    q = q.order_by(Bill.bill_no.desc())  # 최근 의안 우선
    bills = list(session.scalars(q).all())

    n_ok = n_empty = n_err = n_done = 0
    for bill in bills:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        try:
            pd = fetch_propose_date(bill.assembly_bill_id)
            if pd is None:
                n_empty += 1
            else:
                if not dry_run:
                    bill.proposed_date = pd
                    bill.last_verified = _now()
                n_ok += 1
        except Exception:  # noqa: BLE001 — 개별 의안 실패는 건너뛰고 계속
            n_err += 1
        if not dry_run and n_done % 20 == 0:
            session.commit()
        if sleep_sec:
            time.sleep(sleep_sec)

    if not dry_run:
        session.commit()
    return {"processed": n_done, "filled": n_ok, "empty": n_empty, "error": n_err}
