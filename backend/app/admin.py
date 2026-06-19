"""어드민 검토 API — Phase 2-3 (👤 human-in-the-loop).

반자동 승인 흐름: 자동/사람 작성 초안을 사람이 검토→수정→승인/반려한다.
승인된 문항만 공개(api.py 의 기본 status=승인 필터).

🟡 안전선:
  - 모든 엔드포인트는 `X-Admin-Token` 헤더 필요. settings.admin_token 미설정 시 전부 401(기본 잠금).
  - LLM 생성물은 항상 status=초안, created_by=auto → 사람 승인 전 비공개.
  - '반려'는 status=아카이브 + review_note='[반려] 사유'로 기록(문서화된 흐름 유지).

엔드포인트:
  GET   /admin/questions[?status=]        검토 큐(전체 필드, 모든 상태)
  GET   /admin/questions/{id}             단건
  PATCH /admin/questions/{id}             문항 수정
  POST  /admin/questions/{id}/transition  상태 전이(검토시작/승인/반려/아카이브/초안복귀)
  POST  /admin/questions/generate         🤖 법안 → LLM 중립 초안 생성
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.llm_questions import LLMUnavailable, draft_question_for_bill
from app.models import (
    Bill,
    Issue,
    Question,
    QuestionCreator,
    QuestionStatus,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ───────────────────────── 인증 ─────────────────────────
def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """🟡 토큰 잠금. admin_token 미설정이면 어드민 API 전체가 비활성(401)."""
    if not settings.admin_token:
        raise HTTPException(status_code=401, detail="어드민 비활성(ADMIN_TOKEN 미설정).")
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="유효하지 않은 어드민 토큰.")


# ───────────────────────── 스키마 ─────────────────────────
class AdminQuestionOut(BaseModel):
    id: int
    issue: str
    issue_id: int
    body: str
    option_a_label: str | None
    option_a_pro: str | None
    option_a_con: str | None
    option_b_label: str | None
    option_b_pro: str | None
    option_b_con: str | None
    bill_id: int | None
    bill_title: str | None
    source_note: str | None
    status: str
    created_by: str
    approved_by: str | None
    review_note: str | None


class QuestionPatch(BaseModel):
    issue_id: int | None = None
    body: str | None = None
    option_a_label: str | None = None
    option_a_pro: str | None = None
    option_a_con: str | None = None
    option_b_label: str | None = None
    option_b_pro: str | None = None
    option_b_con: str | None = None
    bill_id: int | None = None
    source_note: str | None = None


class TransitionIn(BaseModel):
    action: str = Field(description="검토시작|승인|반려|아카이브|초안복귀")
    by: str = Field(default="admin", max_length=100)
    note: str | None = Field(default=None, max_length=2000)


class GenerateIn(BaseModel):
    bill_id: int


# ───────────────────────── 헬퍼 ─────────────────────────
def _out(q: Question) -> AdminQuestionOut:
    return AdminQuestionOut(
        id=q.id,
        issue=q.issue.name,
        issue_id=q.issue_id,
        body=q.body,
        option_a_label=q.option_a_label,
        option_a_pro=q.option_a_pro,
        option_a_con=q.option_a_con,
        option_b_label=q.option_b_label,
        option_b_pro=q.option_b_pro,
        option_b_con=q.option_b_con,
        bill_id=q.bill_id,
        bill_title=q.bill.title if q.bill else None,
        source_note=q.source_note,
        status=q.status.value,
        created_by=q.created_by.value,
        approved_by=q.approved_by,
        review_note=q.review_note,
    )


def _get_question(db: Session, qid: int) -> Question:
    q = db.get(Question, qid)
    if q is None:
        raise HTTPException(status_code=404, detail=f"문항 {qid} 없음.")
    return q


# action → (허용 출발 상태들, 도착 상태)
_TRANSITIONS: dict[str, tuple[set[QuestionStatus], QuestionStatus]] = {
    "검토시작": ({QuestionStatus.초안}, QuestionStatus.검토중),
    "승인": ({QuestionStatus.초안, QuestionStatus.검토중}, QuestionStatus.승인),
    "반려": ({QuestionStatus.초안, QuestionStatus.검토중}, QuestionStatus.아카이브),
    "아카이브": ({QuestionStatus.승인}, QuestionStatus.아카이브),
    "초안복귀": ({QuestionStatus.검토중, QuestionStatus.아카이브}, QuestionStatus.초안),
}


# ───────────────────────── 문항 검토 ─────────────────────────
@router.get(
    "/questions",
    response_model=list[AdminQuestionOut],
    dependencies=[Depends(require_admin)],
)
def list_questions(
    status: str | None = None, db: Session = Depends(get_db)
) -> list[AdminQuestionOut]:
    stmt = select(Question)
    if status:
        try:
            stmt = stmt.where(Question.status == QuestionStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"알 수 없는 상태: {status}")
    stmt = stmt.order_by(Question.status, Question.id)
    return [_out(q) for q in db.scalars(stmt).all()]


@router.get(
    "/questions/{qid}",
    response_model=AdminQuestionOut,
    dependencies=[Depends(require_admin)],
)
def get_question(qid: int, db: Session = Depends(get_db)) -> AdminQuestionOut:
    return _out(_get_question(db, qid))


@router.patch(
    "/questions/{qid}",
    response_model=AdminQuestionOut,
    dependencies=[Depends(require_admin)],
)
def patch_question(
    qid: int, patch: QuestionPatch, db: Session = Depends(get_db)
) -> AdminQuestionOut:
    q = _get_question(db, qid)
    data = patch.model_dump(exclude_unset=True)

    if "issue_id" in data and db.get(Issue, data["issue_id"]) is None:
        raise HTTPException(status_code=400, detail=f"쟁점 {data['issue_id']} 없음.")
    if data.get("bill_id") is not None and db.get(Bill, data["bill_id"]) is None:
        raise HTTPException(status_code=400, detail=f"법안 {data['bill_id']} 없음.")

    for field, value in data.items():
        setattr(q, field, value)

    # 승인 문항을 수정하면 재검토 필요 → 검토중으로 되돌림(중립성 안전망).
    if q.status == QuestionStatus.승인:
        q.status = QuestionStatus.검토중
        q.approved_by = None
        q.approved_at = None

    db.commit()
    db.refresh(q)
    return _out(q)


@router.post(
    "/questions/{qid}/transition",
    response_model=AdminQuestionOut,
    dependencies=[Depends(require_admin)],
)
def transition_question(
    qid: int, req: TransitionIn, db: Session = Depends(get_db)
) -> AdminQuestionOut:
    q = _get_question(db, qid)
    rule = _TRANSITIONS.get(req.action)
    if rule is None:
        raise HTTPException(
            status_code=400,
            detail=f"알 수 없는 action: {req.action} (검토시작|승인|반려|아카이브|초안복귀)",
        )
    allowed_from, target = rule
    if q.status not in allowed_from:
        raise HTTPException(
            status_code=409,
            detail=f"'{q.status.value}' 상태에서 '{req.action}' 불가.",
        )

    if req.action == "반려":
        if not req.note:
            raise HTTPException(status_code=400, detail="반려에는 사유(note)가 필요합니다.")
        q.review_note = f"[반려] {req.note}"
        q.approved_by = None
        q.approved_at = None
    elif req.action == "승인":
        q.approved_by = req.by
        q.approved_at = datetime.now(timezone.utc)
        if req.note:
            q.review_note = req.note
    else:
        if req.note:
            q.review_note = req.note

    q.status = target
    db.commit()
    db.refresh(q)
    return _out(q)


@router.post(
    "/questions/generate",
    response_model=AdminQuestionOut,
    dependencies=[Depends(require_admin)],
)
def generate_question(req: GenerateIn, db: Session = Depends(get_db)) -> AdminQuestionOut:
    """🤖 법안 → LLM 중립 초안. 항상 status=초안, created_by=auto."""
    bill = db.get(Bill, req.bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail=f"법안 {req.bill_id} 없음.")

    try:
        draft = draft_question_for_bill(bill)
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:  # LLM 출력 형식 불량 — 재시도 가능
        raise HTTPException(status_code=502, detail=f"LLM 초안 파싱 실패: {e}")

    issue = db.scalar(select(Issue).where(Issue.name == draft.issue))
    if issue is None:
        raise HTTPException(
            status_code=500, detail=f"LLM이 고른 쟁점 '{draft.issue}'이 시드에 없음."
        )

    source = f"{bill.title} · 의안 {bill.bill_no}"
    if bill.likms_url:
        source += f" ({bill.likms_url})"

    q = Question(
        issue_id=issue.id,
        body=draft.body,
        agree_meaning=draft.option_a_pro,  # 하위호환 요약
        disagree_meaning=draft.option_b_pro,
        option_a_label=draft.option_a_label,
        option_a_pro=draft.option_a_pro,
        option_a_con=draft.option_a_con,
        option_b_label=draft.option_b_label,
        option_b_pro=draft.option_b_pro,
        option_b_con=draft.option_b_con,
        bill_id=bill.id,
        source_note=source,
        status=QuestionStatus.초안,
        created_by=QuestionCreator.auto,
        review_note=f"[LLM초안] {draft.rationale}",
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    return _out(q)
