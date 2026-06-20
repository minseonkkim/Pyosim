"""분야별 재원배분/결산 수집 잡 (열린재정 OPFI165).

세금 계산기(/tax)의 '내 세금이 어느 분야로' 막대를 실제 공식 데이터로 채운다.
OPFI165 는 DIV_NM='결산'(실제 집행) 16대 분야별 총지출. 결산은 회계연도 종료 후
확정되므로 '당해(집행 중) 연도'는 데이터가 없을 수 있다(가장 최근 확정연도 사용).

DB 가 아니라 프론트가 import 하는 JSON 으로 떨어뜨린다(연 1회 갱신 + 정적 소비).
나중에 규모가 커지면 DB+API 로 승격 가능.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

SERVICE = "OPFI165"
SOURCE_NAME = "열린재정 OPFI165 — 16대 분야별 재원배분(총지출 기준)"
SOURCE_URL = "https://openapi.openfiscaldata.go.kr/OPFI165"

# etl/jobs/budget.py → ../../frontend/lib/budget-data.json
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "budget-data.json"


def _latest_settlement_year(client, *, start: int) -> int | None:
    """start 연도부터 거슬러 올라가며 결산 데이터가 있는 가장 최근 연도를 찾는다."""
    for yr in range(start, start - 4, -1):
        _, rows = client.fetch_page(SERVICE, p_index=1, params={"ACNT_YR": str(yr), "pSize": 1})
        if rows:
            return yr
    return None


def run_budget(client, *, year: int | None = None, dry_run: bool = False) -> dict:
    if year is None:
        year = _latest_settlement_year(client, start=_dt.date.today().year)
        if year is None:
            raise RuntimeError("최근 4년 내 결산 데이터를 찾지 못했습니다.")

    rows = list(client.iter_rows(SERVICE, params={"ACNT_YR": str(year)}))
    if not rows:
        raise RuntimeError(f"{year}년 {SERVICE} 데이터가 없습니다(결산 미확정 가능).")

    basis = rows[0].get("DIV_NM", "")
    fields = [
        {
            "code": str(r["FLD_CD"]),
            "name": str(r["FLD_NM"]).strip(),
            "trillion": round(float(r["SUM_AMT"]), 1),
        }
        for r in rows
        if r.get("FLD_CD") and r.get("SUM_AMT") is not None
    ]
    fields.sort(key=lambda f: f["trillion"], reverse=True)
    total = round(sum(f["trillion"] for f in fields), 1)

    payload = {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "year": year,
        "basis": basis,  # '결산'(실제 집행) 등
        "total_trillion": total,
        "fetched_at": _dt.date.today().isoformat(),
        "fields": fields,
    }

    stats = {"year": year, "basis": basis, "fields": len(fields), "total_trillion": total}
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return stats

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    stats["written"] = str(OUTPUT_PATH)
    return stats
