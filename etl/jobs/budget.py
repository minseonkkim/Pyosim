"""분야별 예산(계획)·결산(실제) 수집 잡 (열린재정 OPFI165 + OPFI172).

세금 계산기(/tax)의 두 가지 막대를 실제 공식 데이터로 채운다.
  1) '내 세금이 어느 분야로'      → OPFI165 결산(실제 집행) 16대 분야 총지출(조원).
  2) '계획(본예산) vs 실제(결산)' → OPFI172 본예산 배정액(억원) + 세부사업 수.

두 서비스는 분야코드 FLD_CD(16대 분야)로 동일 키 매칭된다. 같은 회계연도(ACNT_YR)로
맞춰 '처음 짠 예산' vs '실제 쓴 돈'을 사과 대 사과로 비교한다. 결산은 회계연도 종료 후
확정되므로 '당해(집행 중) 연도'는 데이터가 없을 수 있다(가장 최근 확정연도 사용).

⚠️ 비교 기준은 '본예산'(처음 짠 예산)이다. 결산은 추경·예비비를 포함하므로 분야에 따라
   결산 > 본예산(계획보다 더 씀) / 결산 < 본예산(덜 씀) 모두 나온다. 이 갭 자체가 사실이며
   '집행률'(분모=예산현액)과는 다르다 → 프론트는 '계획 vs 실제'로만 표기(판정 금지).

DB 가 아니라 프론트가 import 하는 JSON 으로 떨어뜨린다(연 1회 갱신 + 정적 소비).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

SERVICE_STL = "OPFI165"  # 16대 분야별 재원배분 — DIV_NM='결산'(실제 집행), 조원
SERVICE_BDG = "OPFI172"  # 16대 분야별 본예산 배정 + 부문/프로그램/단위/세부사업 수, 억원
SOURCE_NAME = "열린재정 OPFI165(분야별 결산)·OPFI172(분야별 본예산)"
SOURCE_URL = "https://www.openfiscaldata.go.kr"

# etl/jobs/budget.py → ../../frontend/lib/budget-data.json
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "budget-data.json"


def _latest_settlement_year(client, *, start: int) -> int | None:
    """start 연도부터 거슬러 올라가며 결산 데이터가 있는 가장 최근 연도를 찾는다."""
    for yr in range(start, start - 4, -1):
        _, rows = client.fetch_page(SERVICE_STL, p_index=1, params={"ACNT_YR": str(yr), "pSize": 1})
        if rows:
            return yr
    return None


def _fetch_budget_by_field(client, *, year: int) -> dict[str, dict]:
    """OPFI172 본예산 배정(억원→조원) + 세부사업 수를 FLD_CD 기준 dict 로."""
    out: dict[str, dict] = {}
    for r in client.iter_rows(SERVICE_BDG, params={"ACNT_YR": str(year)}):
        code = r.get("FLD_CD")
        amt = r.get("FLD_AMT")
        if not code or amt is None:
            continue
        out[str(code)] = {
            "budget_trillion": round(float(amt) / 10_000, 1),  # 억원 → 조원
            "say_count": int(r["SAY_CNT"]) if r.get("SAY_CNT") is not None else None,
            "program_count": int(r["PGM_CNT"]) if r.get("PGM_CNT") is not None else None,
        }
    return out


def run_budget(client, *, year: int | None = None, dry_run: bool = False) -> dict:
    if year is None:
        year = _latest_settlement_year(client, start=_dt.date.today().year)
        if year is None:
            raise RuntimeError("최근 4년 내 결산 데이터를 찾지 못했습니다.")

    rows = list(client.iter_rows(SERVICE_STL, params={"ACNT_YR": str(year)}))
    if not rows:
        raise RuntimeError(f"{year}년 {SERVICE_STL} 데이터가 없습니다(결산 미확정 가능).")

    basis = rows[0].get("DIV_NM", "")
    budget_by_code = _fetch_budget_by_field(client, year=year)

    fields = []
    for r in rows:
        code = r.get("FLD_CD")
        if not code or r.get("SUM_AMT") is None:
            continue
        bdg = budget_by_code.get(str(code), {})
        fields.append(
            {
                "code": str(code),
                "name": str(r["FLD_NM"]).strip(),
                "trillion": round(float(r["SUM_AMT"]), 1),  # 결산(실제 집행)
                "budget_trillion": bdg.get("budget_trillion"),  # 본예산(계획)
                "say_count": bdg.get("say_count"),  # 세부사업 수
                "program_count": bdg.get("program_count"),
            }
        )

    fields.sort(key=lambda f: f["trillion"], reverse=True)
    total = round(sum(f["trillion"] for f in fields), 1)
    budget_total = round(
        sum(f["budget_trillion"] for f in fields if f["budget_trillion"] is not None), 1
    )

    payload = {
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "year": year,
        "basis": basis,  # '결산'(실제 집행)
        "budget_basis": "본예산",  # 비교 기준(계획) — 추경·예비비 제외
        "total_trillion": total,  # 결산 합
        "budget_total_trillion": budget_total,  # 본예산 합
        "fetched_at": _dt.date.today().isoformat(),
        "fields": fields,
    }

    matched = sum(1 for f in fields if f["budget_trillion"] is not None)
    stats = {
        "year": year,
        "basis": basis,
        "fields": len(fields),
        "budget_matched": matched,
        "total_trillion": total,
        "budget_total_trillion": budget_total,
    }
    if dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return stats

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    stats["written"] = str(OUTPUT_PATH)
    return stats
