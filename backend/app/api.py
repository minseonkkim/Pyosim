"""공개 API — 테스트 문항·결과 채점 (Phase 1-3 ~ 1-4).

엔드포인트:
  GET  /api/parties        채점 대상 정당 + color_hex (차트용)
  GET  /api/questions      공개 문항(기본 status=승인). 프로토타입은 ?preview=1 로 초안 포함
  POST /api/results        답변 → 정당별 일치율 + 문항별 비교 + 🟡 필수 고지문

🟡 안전선:
  - 기본은 '승인' 문항만 공개(반자동 승인 흐름). 초안은 외부 교차검토 전이므로 preview 로만.
  - 결과에는 필수 고지문(DISCLAIMER)·집계 기준(METHOD_NOTE)을 항상 동봉.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.db import get_db
from app.models import (
    Answer,
    AnswerChoice,
    Bill,
    Event,
    Party,
    Question,
    QuestionStatus,
    Vote,
)
from app.scoring import (
    DISCLAIMER,
    METHOD_NOTE,
    SCORED_PARTIES,
    score,
    stance_map_for_bill,
)

router = APIRouter(prefix="/api")


# ───────────────────────── 스키마 ─────────────────────────
class Option(BaseModel):
    label: str | None
    pro: str | None
    con: str | None


class QuestionOut(BaseModel):
    id: int
    issue: str
    body: str
    option_a: Option  # 채점상 '찬성' 방향
    option_b: Option  # 채점상 '반대' 방향
    source_note: str | None
    likms_url: str | None
    status: str


class QuestionsResponse(BaseModel):
    questions: list[QuestionOut]
    preview: bool
    notice: str | None = None


class PartyOut(BaseModel):
    name: str
    color_hex: str | None


class AnswerIn(BaseModel):
    question_id: int
    choice: AnswerChoice  # 찬성(Ⓐ) / 반대(Ⓑ) / 모름


class ResultsRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    answers: list[AnswerIn]


class PartyMatchOut(BaseModel):
    party: str
    color_hex: str | None
    match_rate: float
    matched: int
    total: int


class QuestionResultOut(BaseModel):
    question_id: int
    issue: str
    body: str
    your_choice: AnswerChoice
    your_label: str | None
    agree_parties: list[str]  # 내 답과 같은 방향으로 표결한 정당
    disagree_parties: list[str]
    source_note: str | None
    likms_url: str | None


class ResultsResponse(BaseModel):
    answered: int
    skipped: int
    party_match: list[PartyMatchOut]
    per_question: list[QuestionResultOut]
    disclaimer: str
    method_note: str


# ───────────────────────── 헬퍼 ─────────────────────────
def _option(label, pro, con) -> Option:
    return Option(label=label, pro=pro, con=con)


def _public_questions(db: Session, preview: bool) -> list[Question]:
    stmt = select(Question)
    if not preview:
        stmt = stmt.where(Question.status == QuestionStatus.승인)
    stmt = stmt.order_by(Question.id)
    return list(db.scalars(stmt).all())


# ───────────────────────── 엔드포인트 ─────────────────────────
@router.get("/parties", response_model=list[PartyOut])
def list_parties(db: Session = Depends(get_db)) -> list[PartyOut]:
    parties = {p.name: p for p in db.scalars(select(Party)).all()}
    return [
        PartyOut(name=name, color_hex=parties[name].color_hex if name in parties else None)
        for name in SCORED_PARTIES
    ]


@router.get("/questions", response_model=QuestionsResponse)
def list_questions(
    preview: bool = Query(False, description="초안 포함(외부 검토 전 프로토타입용)"),
    db: Session = Depends(get_db),
) -> QuestionsResponse:
    questions = _public_questions(db, preview)
    out = [
        QuestionOut(
            id=q.id,
            issue=q.issue.name,
            body=q.body,
            option_a=_option(q.option_a_label, q.option_a_pro, q.option_a_con),
            option_b=_option(q.option_b_label, q.option_b_pro, q.option_b_con),
            source_note=q.source_note,
            likms_url=q.bill.likms_url if q.bill else None,
            status=q.status.value,
        )
        for q in questions
    ]
    notice = (
        "⚠️ 검토 전 초안 문항이 포함된 미리보기입니다(공개 전 외부 교차검토 필요)."
        if preview
        else None
    )
    return QuestionsResponse(questions=out, preview=preview, notice=notice)


@router.post("/results", response_model=ResultsResponse)
def compute_results(
    req: ResultsRequest, db: Session = Depends(get_db)
) -> ResultsResponse:
    if not req.answers:
        raise HTTPException(status_code=400, detail="답변이 없습니다.")

    qids = [a.question_id for a in req.answers]
    questions = {
        q.id: q
        for q in db.scalars(select(Question).where(Question.id.in_(qids))).all()
    }
    unknown = set(qids) - set(questions)
    if unknown:
        raise HTTPException(status_code=400, detail=f"존재하지 않는 문항: {sorted(unknown)}")

    # 앵커 법안별 vote_id (실제 표결기록 기반 채점 시 사용)
    bill_ids = {q.bill_id for q in questions.values() if q.bill_id}
    vote_by_bill: dict[int, int] = {}
    if bill_ids:
        for v in db.scalars(select(Vote).where(Vote.bill_id.in_(bill_ids))).all():
            vote_by_bill.setdefault(v.bill_id, v.id)

    party_colors = {p.name: p.color_hex for p in db.scalars(select(Party)).all()}

    answers: dict[int, AnswerChoice] = {}
    stance_by_question: dict[int, dict[str, str]] = {}
    per_question: list[QuestionResultOut] = []
    skipped = 0

    for a in req.answers:
        q = questions[a.question_id]
        answers[q.id] = a.choice

        bill = q.bill
        stances: dict[str, str] = {}
        if bill is not None:
            stances = stance_map_for_bill(
                db, bill.bill_no, vote_by_bill.get(bill.id)
            )
        stance_by_question[q.id] = stances

        if a.choice == AnswerChoice.모름:
            skipped += 1

        # 내 답과 같은/다른 방향 정당
        my_side = "찬" if a.choice == AnswerChoice.찬성 else (
            "반" if a.choice == AnswerChoice.반대 else None
        )
        agree = [p for p in SCORED_PARTIES if stances.get(p) == my_side] if my_side else []
        disagree = (
            [p for p in SCORED_PARTIES if stances.get(p) and stances.get(p) != my_side]
            if my_side
            else []
        )
        your_label = (
            q.option_a_label if a.choice == AnswerChoice.찬성
            else q.option_b_label if a.choice == AnswerChoice.반대
            else None
        )
        per_question.append(
            QuestionResultOut(
                question_id=q.id,
                issue=q.issue.name,
                body=q.body,
                your_choice=a.choice,
                your_label=your_label,
                agree_parties=agree,
                disagree_parties=disagree,
                source_note=q.source_note,
                likms_url=bill.likms_url if bill else None,
            )
        )

        # 익명 세션 저장 (이탈 분석·중간 저장)
        db.add(Answer(session_id=req.session_id, question_id=q.id, choice=a.choice))

    db.commit()

    matches = score(answers, stance_by_question, party_colors)
    party_match = [
        PartyMatchOut(
            party=m.party,
            color_hex=m.color_hex,
            match_rate=m.rate,
            matched=m.matched,
            total=m.total,
        )
        for m in matches
    ]

    return ResultsResponse(
        answered=len(answers) - skipped,
        skipped=skipped,
        party_match=party_match,
        per_question=per_question,
        disclaimer=DISCLAIMER,
        method_note=METHOD_NOTE,
    )


# ───────────────────────── 익명 퍼널 로깅 (Phase 1-6) ─────────────────────────
# 이탈 지점 측정용 화이트리스트. 정의되지 않은 이벤트명은 조용히 버린다(임의 적재 방지).
ALLOWED_EVENTS: frozenset[str] = frozenset(
    {
        "landing",        # 진입 화면 노출
        "test_start",     # 테스트 진입(문항 로드)
        "question_view",  # 문항 노출 (props: idx, total)
        "answer",         # 답변 선택 (props: idx, choice)
        "test_complete",  # 제출 완료 (props: answered, skipped)
        "result_view",    # 결과 화면 노출
        "share_click",    # 공유 시도 (props: method)
        "source_open",    # ▼출처 펼침(데이터 신뢰 engagement)
    }
)
_MAX_EVENTS_PER_BATCH = 50
_MAX_PROP_KEYS = 8


def _sanitize_props(props: object) -> dict | None:
    """🟡 원시값(str/int/float/bool)만 통과. 중첩·임의 데이터·PII 적재 차단."""
    if not isinstance(props, dict):
        return None
    clean: dict = {}
    for k, v in props.items():
        if len(clean) >= _MAX_PROP_KEYS:
            break
        if not isinstance(k, str) or len(k) > 40:
            continue
        if isinstance(v, bool) or isinstance(v, (int, float)):
            clean[k] = v
        elif isinstance(v, str):
            clean[k] = v[:120]
    return clean or None


@router.post("/events")
async def collect_events(request: Request, db: Session = Depends(get_db)) -> dict[str, int]:
    """익명 이벤트 배치 적재. text/plain(sendBeacon)·application/json 모두 허용.

    sendBeacon 은 CORS 프리플라이트를 못 하므로 프론트가 text/plain 으로 보낸다.
    → content-type 무관하게 본문을 직접 파싱한다.
    """
    raw = await request.body()
    try:
        data = json.loads(raw or b"{}")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="잘못된 본문(JSON 아님).")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="잘못된 본문 형식.")
    session_id = str(data.get("session_id") or "")[:64]
    events = data.get("events")
    if not session_id or not isinstance(events, list):
        raise HTTPException(status_code=400, detail="session_id 와 events 가 필요합니다.")

    accepted = 0
    for e in events[:_MAX_EVENTS_PER_BATCH]:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "")
        if name not in ALLOWED_EVENTS:
            continue
        db.add(Event(session_id=session_id, name=name, props=_sanitize_props(e.get("props"))))
        accepted += 1

    db.commit()
    return {"accepted": accepted}
