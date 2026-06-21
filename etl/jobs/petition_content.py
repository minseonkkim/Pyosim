"""청원 본문 수집 — 국민동의청원(petitions.assembly.go.kr) API → Petition 취지·내용·분야.

열린국회정보 청원 API·likms 엔 청원 본문이 없어, 국민동의청원 사이트의 공개 JSON API에서
가져온다. 그쪽 레코드의 `billId` 가 우리 Petition.assembly_bill_id(PRC_…)와 동일해 그대로 매칭.

  GET https://petitions.assembly.go.kr/api/petits?sttusCode={상태}&pageIndex=&recordCountPerPage=
    레코드: petitObjet(취지)·petitCn(내용 전문)·petitRealmNm(분야)·billId(매칭 키)

🟡 공식 공개 원문 그대로 저장(요약·판정 없음). 일반청원(의원소개)은 이 사이트에 없어 매칭 안 됨(null 유지).
⚠️ 비공식 JSON API라 구조 변경 시 깨질 수 있음. billId 매칭이라 잘못 붙을 위험은 낮음.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobs.db import Petition

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Pyosim-ETL"
API = "https://petitions.assembly.go.kr/api/petits"
# billId 가 채워지는(=회부된) 청원이 모이는 상태들. 매칭은 billId로 하므로 대수 무관.
STATUSES = ["CMIT_FRWRD", "RCEPT", "EXAM", "PLN_FRWRD", "BILL_PT_RCEPT", "ALTBIL_RFLC", "PROCESS_END"]
PAGE_SIZE = 100
MAX_PAGES = 12  # 상태별 페이지 상한(안전장치)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch(status: str, page: int, timeout: int = 25) -> list[dict]:
    params = {"sttusCode": status, "pageIndex": page, "recordCountPerPage": PAGE_SIZE}
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    return data if isinstance(data, list) else []


def run_petition_content(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = True,
) -> dict:
    """국민동의청원 API 본문을 billId 매칭으로 Petition 에 적재(멱등).

    only_missing: content_fetched 없는 청원만 대상. limit: 적재 상한.
    """
    q = select(Petition).where(Petition.assembly_bill_id.isnot(None))
    if only_missing:
        q = q.where(Petition.content_fetched.is_(None))
    targets = {p.assembly_bill_id: p for p in session.scalars(q).all()}
    if not targets:
        return {"targets": 0, "matched": 0}

    # 상태들을 훑어 billId → 레코드 맵 구성. 우리 대상이 다 채워지면 조기 종료.
    seen: dict[str, dict] = {}
    pending = set(targets)
    for status in STATUSES:
        if not pending:
            break
        for page in range(1, MAX_PAGES + 1):
            try:
                rows = _fetch(status, page)
            except Exception:  # noqa: BLE001 — 상태/네트워크 오류는 건너뜀
                break
            if not rows:
                break
            for r in rows:
                bid = r.get("billId")
                if bid:
                    seen[bid] = r
                    pending.discard(bid)
            if len(rows) < PAGE_SIZE:
                break

    n_matched = n_content = 0
    for bid, p in targets.items():
        if limit is not None and n_matched >= limit:
            break
        r = seen.get(bid)
        if r is None:
            continue
        n_matched += 1
        objective = (r.get("petitObjet") or "").strip() or None
        content = (r.get("petitCn") or "").strip() or None
        if not dry_run:
            p.objective = objective
            p.content = content
            p.realm = (r.get("petitRealmNm") or "").strip() or None
            p.content_fetched = _now()
        if content:
            n_content += 1

    if not dry_run:
        session.commit()
    return {
        "targets": len(targets), "site_records": len(seen),
        "matched": n_matched, "with_content": n_content,
    }
