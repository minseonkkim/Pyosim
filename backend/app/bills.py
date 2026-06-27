"""법안 상세 허브 — Phase 1-3 (그물망 '법안' 축).

기획 2.1: 법안=발의·표결 정보 허브. 대표발의자·정당별 찬반·표결 의원이 모여
사람 축으로 다시 뻗는다(사람→법안→표결 의원→다시 사람, 그물망 닫힘).

🟡 중립성(기획 1.3): 공식 기록(의안정보시스템·열린국회정보)만, 출처 동반, 판정 배제.

엔드포인트:
  GET /api/bills/{id}   법안 상세(대표발의·처리 funnel·본회의 집계·정당별 찬반·표결 의원)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.bill_content import fetch_bill_content
from app.bill_summary import summarize_bill
from app.config import settings
from app.db import get_db
from app.models import Bill, LawNotice, Party, Person, Vote, VoteChoice, VoteRecord
from app.persons import PartyBrief

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bills", tags=["bills"])

NOTICE = (
    "법안 정보와 표결 기록은 국회 의안정보시스템·열린국회정보의 공식 데이터입니다. "
    "사실만 표시하며 가치 판단을 담지 않습니다."
)

SUMMARY_NOTICE = (
    "아래 좋은점·문제점은 공식 원문이 아니라 AI({model})가 제안이유·주요내용을 바탕으로 "
    "양쪽을 대칭되게 정리한 참고용 요약입니다. 찬반 판단은 담지 않으며, 판단은 원문을 보고 "
    "직접 하시길 권합니다."
)

FEED_NOTICE = (
    "정쟁·절차성 안건을 제외하고, 본회의에서 의견이 갈린(반대표가 많거나 정당 입장이 갈린) "
    "정책 법안을 보여드립니다. 추천이 아니라 '논쟁이 있었다'는 사실에 따른 선별입니다."
)

# 입법예고 시민 의견(기능 B-4.4) — 출처·방법 고지 (🟡)
CIVIC_NOTICE = (
    "입법예고 의견 수는 국회 국민참여입법시스템의 공개 집계를 그대로 옮긴 것입니다. "
    "찬성·반대·기타는 시민이 의견 등록 시 선택한 입장이며, 의견 내용·작성자는 담지 않습니다."
)
CIVIC_METHOD = (
    "입법예고 의견은 관심 있는 시민이 자발적으로 남기는 것이라 반대 의견이 많이 모이는 "
    "경향이 있습니다. '여론 전체'가 아니라 '의견을 낸 시민들의 입장 분포'입니다."
)

# 정쟁성·절차성 안건 — 중립성(🟡)·일상 관련성 위해 피드에서 제외(discriminating_bills 와 동일 기준)
FEED_EXCLUDE = [
    "특별검사", "특검", "내란", "계엄", "탄핵", "감사요구", "감사 요구", "국정조사",
    "결산", "예산안", "기금운용", "회기", "의사일정", "규칙", "구성의 건", "사퇴",
    "해임", "위원 정수", "선출", "선임", "추천", "임명동의", "결의안",
    "본회의록", "징계", "체포동의", "자격심사", "의혹",
]

MAJOR_PARTIES = ("더불어민주당", "국민의힘")


# ───────────────────────── 스키마 ─────────────────────────
class ProposerBrief(BaseModel):
    id: int
    name: str
    party: PartyBrief | None


class VoteAggregate(BaseModel):
    session_date: date | None
    member_total: int | None
    vote_total: int | None
    yes: int | None
    no: int | None
    blank: int | None


class PartyVote(BaseModel):
    party: str
    color_hex: str | None
    yes: int
    no: int
    abstain: int
    absent: int


class Voter(BaseModel):
    id: int
    name: str
    party: str | None
    choice: str


class FunnelStep(BaseModel):
    label: str
    done: bool
    date: date | None  # 단계 의결일(있으면) — 🟡 공식 일자 그대로


class CivicOpinion(BaseModel):
    """입법예고 기간 시민 찬반 의견 집계 (기능 B-4.4) — 본문 없이 수치만.

    출처: 국민참여입법시스템(pal.assembly.go.kr) 공개 집계(LawNotice).
    찬반 분해(agree/oppose)가 보류된 대형 의안은 total 만 채워질 수 있다(agree=None).
    """
    total: int  # 전체 의견 수
    agree: int | None  # 찬성(분해 보류 시 None)
    oppose: int | None  # 반대
    etc: int | None  # 기타
    pal_url: str | None  # 국민참여입법시스템 입법예고 원문
    notice: str
    method_note: str


class BillDetail(BaseModel):
    id: int
    bill_no: str
    title: str
    committee: str | None
    category: str | None  # 생활 카테고리(세금·노동·주거…)
    status: str | None
    proposed_date: date | None
    likms_url: str | None
    proposal_reason: str | None  # 제안이유(또는 제안이유 및 주요내용) — 의안원문 공식 텍스트
    main_content: str | None  # 주요내용(분리형일 때)
    summary_pros: list[str]  # AI 참고 요약 — 좋은점(대칭)
    summary_cons: list[str]  # AI 참고 요약 — 문제점(대칭)
    summary_notice: str | None  # AI 요약이 있을 때만 동봉하는 🟡 고지
    proposer: ProposerBrief | None  # 의원 대표발의(프로필 링크). 정부·위원장안은 None
    proposer_kind: str | None  # 의원/정부/위원장 — proposer 가 없을 때 표기 분기용
    proposer_text: str | None  # 예: "정부", "정무위원장" — proposer 가 없을 때 화면 표시
    vote: VoteAggregate | None  # 본회의 집계(있는 경우)
    party_breakdown: list[PartyVote]  # 정당별 찬반(의원별 기록 있을 때)
    voters: list[Voter]  # 표결 의원 → 프로필 연결(그물망)
    funnel: list[FunnelStep]
    civic_opinion: CivicOpinion | None  # 입법예고 기간 시민 찬반(있을 때만) — 민심 vs 국회
    notice: str


class BillCard(BaseModel):
    """피드용 법안 카드 — '논쟁'을 한눈에. 탭하면 상세(BillDetail)로."""
    id: int
    title: str
    committee: str | None
    category: str | None  # 생활 카테고리(세금·노동·주거…) — 미분류면 None
    proposed_date: date | None
    yes: int | None
    no: int | None
    contested_reason: str  # 왜 골랐는지(사실 기반): "정당 입장 갈림" / "반대 NN표"
    party_split: bool  # 민주 vs 국힘 다수 입장이 갈렸는가
    pro: str | None  # AI 요약 좋은점 첫 줄(있으면)
    con: str | None  # AI 요약 문제점 첫 줄(있으면)
    # 입법예고 시민 의견(있을 때만) — 진입 후크: "시민 N명이 의견 냈다" (기능 B-4.4)
    opinion_total: int | None = None
    opinion_lean: str | None = None  # 찬성/반대(우세 입장) — 분해 보류·동수면 None


class BillFeed(BaseModel):
    items: list[BillCard]
    notice: str


class CategoryCount(BaseModel):
    category: str
    count: int


class CategoryList(BaseModel):
    items: list[CategoryCount]


OPINIONS_NOTICE = (
    "입법예고 기간에 시민 의견이 많이 모인 법안을 의견 수 많은 순으로 보여드립니다. "
    "표결 전(계류) 법안도 포함됩니다. 의견 수는 국민참여입법시스템 공개 집계이며, "
    "관심 있는 시민이 자발적으로 남기는 것이라 반대 의견이 많이 모이는 경향이 있습니다."
)

SEARCH_NOTICE = (
    "큐레이션 피드(표결·의견)와 달리, 제목으로 22대 국회 의안 전체를 찾습니다. "
    "표결 전 계류 법안도 포함되며, 최근 발의순으로 보여드립니다. 사실 일치 결과만 표시합니다."
)

def _exclude_political(q):
    """정쟁·절차성 안건 제외(피드 공통 — 중립성·일상 관련성)."""
    for kw in FEED_EXCLUDE:
        q = q.where(Bill.title.notilike(f"%{kw}%"))
    return q


def _feed_filtered(q):
    """피드 공통 필터 — 정쟁·절차성 제외 + 본회의 반대표 집계 있는 의안만."""
    return _exclude_political(q).where(Vote.no_total.isnot(None))


def _lean(agree: int | None, oppose: int | None) -> str | None:
    """찬반 우세 입장 — 분해 보류(None)·동수면 None."""
    if agree is None or oppose is None:
        return None
    return "반대" if oppose > agree else ("찬성" if agree > oppose else None)


def _attach_opinions(db: Session, cards: list["BillCard"]) -> None:
    """카드 목록에 입법예고 시민 의견 수·우세입장을 붙인다(있는 것만). 한 번의 쿼리.

    진입 후크: 표결로 고른 법안 중에서도 '시민 의견이 쏟아진' 것을 카드에서 바로 드러낸다.
    """
    if not cards:
        return
    ids = [c.id for c in cards]
    rows = db.execute(
        select(Bill.id, LawNotice.opinion_total, LawNotice.agree_count, LawNotice.oppose_count)
        .join(LawNotice, LawNotice.bill_no == Bill.bill_no)
        .where(Bill.id.in_(ids), LawNotice.opinion_total.isnot(None), LawNotice.opinion_total > 0)
    ).all()
    m = {bid: (tot, ag, op) for bid, tot, ag, op in rows}
    for c in cards:
        if c.id in m:
            tot, ag, op = m[c.id]
            c.opinion_total = tot
            c.opinion_lean = _lean(ag, op)


def _opinion_cards(db: Session, limit: int, category: str | None) -> list["BillCard"]:
    """'시민 의견 많은 순' 카드 — 입법예고 의견이 집계된 법안을 의견 수 순으로.

    🟡 표결 유무와 무관(계류 법안 포함). 정쟁·절차성은 제외. 추천이 아니라 '참여 많은 순' 사실 정렬.
    """
    q = _exclude_political(
        select(Bill, LawNotice).join(LawNotice, LawNotice.bill_no == Bill.bill_no)
    ).where(LawNotice.opinion_total.isnot(None), LawNotice.opinion_total > 0)
    if category:
        q = q.where(Bill.category == category)
    q = q.order_by(LawNotice.opinion_total.desc()).limit(limit)
    rows = db.execute(q).all()
    if not rows:
        return []

    bill_ids = [b.id for b, _ in rows]
    votes = {
        v.bill_id: v
        for v in db.scalars(select(Vote).where(Vote.bill_id.in_(bill_ids))).all()
    }
    cards = []
    for bill, ln in rows:
        v = votes.get(bill.id)
        pro = bill.summary_pros.split("\n")[0] if bill.summary_pros else None
        con = bill.summary_cons.split("\n")[0] if bill.summary_cons else None
        cards.append(BillCard(
            id=bill.id, title=bill.title, committee=bill.committee, category=bill.category,
            proposed_date=bill.proposed_date,
            yes=(v.yes_total if v else None), no=(v.no_total if v else None),
            contested_reason=f"의견 {ln.opinion_total:,}건", party_split=False,
            pro=pro, con=con,
            opinion_total=ln.opinion_total, opinion_lean=_lean(ln.agree_count, ln.oppose_count),
        ))
    return cards


def _contested_cards(db: Session, limit: int, category: str | None) -> list["BillCard"]:
    """'표결로 갈린 순' 카드 — 본회의 반대표/정당갈림 순. (기존 피드 본체)

    🟡 정쟁·절차성 제외, 반대표 많은 순 후보 → 정당(민주 vs 국힘) 입장이 갈린 법안을 위로.
    """
    pool = max(limit * 4, 40)
    q = _feed_filtered(select(Bill, Vote).join(Vote, Vote.bill_id == Bill.id))
    if category:
        q = q.where(Bill.category == category)
    q = q.order_by(Vote.no_total.desc().nullslast()).limit(pool)
    rows = db.execute(q).all()
    if not rows:
        return []

    # 후보들의 정당(민주·국힘) 다수 입장 계산 → 갈림 판정(한 번의 집계 쿼리)
    vote_ids = [v.id for _, v in rows]
    splits: dict[int, bool] = {}
    party_rows = db.execute(
        select(VoteRecord.vote_id, Party.name, VoteRecord.choice, func.count())
        .join(Person, Person.id == VoteRecord.person_id)
        .join(Party, Party.id == Person.party_id)
        .where(VoteRecord.vote_id.in_(vote_ids), Party.name.in_(MAJOR_PARTIES))
        .group_by(VoteRecord.vote_id, Party.name, VoteRecord.choice)
    ).all()
    tally: dict[int, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"y": 0, "n": 0})
    )
    for vid, pname, choice, cnt in party_rows:
        if choice == VoteChoice.찬성:
            tally[vid][pname]["y"] += cnt
        elif choice == VoteChoice.반대:
            tally[vid][pname]["n"] += cnt
    for vid, parties in tally.items():
        def major(p: str) -> str | None:
            t = parties.get(p)
            if not t or (t["y"] == 0 and t["n"] == 0):
                return None
            return "찬" if t["y"] >= t["n"] else "반"
        a, b = major("더불어민주당"), major("국민의힘")
        splits[vid] = bool(a and b and a != b)

    cards: list[BillCard] = []
    for bill, vote in rows:
        split = splits.get(vote.id, False)
        reason = "정당 입장이 갈림" if split else f"반대 {vote.no_total}표"
        pro = bill.summary_pros.split("\n")[0] if bill.summary_pros else None
        con = bill.summary_cons.split("\n")[0] if bill.summary_cons else None
        cards.append(BillCard(
            id=bill.id, title=bill.title, committee=bill.committee,
            category=bill.category,
            proposed_date=bill.proposed_date, yes=vote.yes_total, no=vote.no_total,
            contested_reason=reason, party_split=split, pro=pro, con=con,
        ))

    cards.sort(key=lambda c: (c.party_split, c.no or 0), reverse=True)
    top = cards[:limit]
    _attach_opinions(db, top)  # 표결로 고른 법안에도 시민 의견 수 배지(겹치는 것만)
    return top


@router.get("", response_model=BillFeed)
def list_bills(
    limit: int = 20, category: str | None = None, sort: str | None = None,
    db: Session = Depends(get_db),
) -> BillFeed:
    """법안 피드 — 두 축은 섞지 않고 보기(sort)별로 분리한다.

    - 기본/`contested`: 본회의 반대표·정당갈림 순(표결 끝난 법안).
    - `opinions`: 입법예고 시민 의견 많은 순(표결 무관, 계류 포함).
    🟡 추천이 아니라 사실 기반 선별·정렬. category(세금·노동·주거…)로 좁힐 수 있다.
    (민심 vs 국회 불일치 통합 뷰는 별도 `GET /api/mismatch` — 법안+청원.)
    """
    if sort == "opinions":
        return BillFeed(items=_opinion_cards(db, limit, category), notice=OPINIONS_NOTICE)
    return BillFeed(items=_contested_cards(db, limit, category), notice=FEED_NOTICE)


@router.get("/search", response_model=BillFeed)
def search_bills(q: str, limit: int = 50, db: Session = Depends(get_db)) -> BillFeed:
    """제목·의안번호로 22대 의안 전체를 검색 — 표결 여부와 무관(계류 포함).

    피드는 '논쟁'(표결·의견)으로 큐레이션해 표결 끝난 의안만 담기지만, 특정 법안을
    이름으로 찾을 땐 계류 중인 최근 발의안까지 닿아야 한다. 여기선 DB의 모든 Bill 을
    제목으로 훑어 최근 발의순으로 돌려준다. 🟡 추천·판정 없이 일치 결과만.
    """
    term = (q or "").strip()
    if len(term) < 2:
        return BillFeed(items=[], notice=SEARCH_NOTICE)
    like = f"%{term}%"
    bills = db.scalars(
        select(Bill)
        .where(or_(Bill.title.ilike(like), Bill.bill_no.ilike(like)))
        .order_by(Bill.proposed_date.desc().nullslast())
        .limit(limit)
    ).all()
    if not bills:
        return BillFeed(items=[], notice=SEARCH_NOTICE)

    bill_ids = [b.id for b in bills]
    votes = {
        v.bill_id: v
        for v in db.scalars(select(Vote).where(Vote.bill_id.in_(bill_ids))).all()
    }
    cards: list[BillCard] = []
    for b in bills:
        v = votes.get(b.id)
        pro = b.summary_pros.split("\n")[0] if b.summary_pros else None
        con = b.summary_cons.split("\n")[0] if b.summary_cons else None
        voted = v is not None and v.no_total is not None
        reason = "본회의 표결 완료" if voted else (b.status or "계류 중")
        cards.append(BillCard(
            id=b.id, title=b.title, committee=b.committee, category=b.category,
            proposed_date=b.proposed_date,
            yes=(v.yes_total if v else None), no=(v.no_total if v else None),
            contested_reason=reason, party_split=False, pro=pro, con=con,
        ))
    _attach_opinions(db, cards)  # 검색 결과에도 시민 의견 배지(있는 것만)
    return BillFeed(items=cards, notice=SEARCH_NOTICE)


@router.get("/categories", response_model=CategoryList)
def list_categories(db: Session = Depends(get_db)) -> CategoryList:
    """피드에 실제 존재하는 생활 카테고리 + 건수 — 칩 필터용.

    피드와 동일한 필터(정쟁 제외·표결 있음) 위에서 집계해, 칩을 눌렀을 때
    빈 피드가 나오지 않도록 보장한다. 건수 많은 순.
    """
    q = _feed_filtered(
        select(Bill.category, func.count(func.distinct(Bill.id)))
        .join(Vote, Vote.bill_id == Bill.id)
    ).where(Bill.category.isnot(None)).group_by(Bill.category)
    rows = db.execute(q).all()
    items = [CategoryCount(category=c, count=n) for c, n in rows]
    items.sort(key=lambda x: -x.count)
    return CategoryList(items=items)


def _ensure_content(db: Session, bill: Bill) -> None:
    """본문 미수집 의안이면 likms 의안원문을 그 자리에서 받아 캐싱(on-demand).

    클릭한 법안은 (likms 에 원문이 있는 한) 항상 본문이 보이도록 보장한다.
    🟡 원문 그대로 저장(요약·판정 없음). 출처 = likms billDetail.
    네트워크/파싱 실패는 페이지를 막지 않도록 삼키고, content_fetched 를 남기지 않아
    다음 열람 때 재시도한다.
    """
    if bill.content_fetched is not None or not bill.assembly_bill_id:
        return
    try:
        reason, main = fetch_bill_content(bill.assembly_bill_id)
    except Exception:  # noqa: BLE001 — 본문 수집 실패가 법안 페이지를 막지 않도록
        logger.warning("법안 본문 on-demand 수집 실패 bill=%s", bill.id, exc_info=True)
        return
    bill.proposal_reason = reason
    bill.main_content = main
    bill.content_fetched = datetime.now(timezone.utc)
    db.commit()


def _ensure_summary(db: Session, bill: Bill) -> None:
    """본문이 있으나 AI 요약이 없으면 그 자리에서 생성해 캐싱(on-demand).

    🟡 원문은 건드리지 않고 좋은점/문제점만 별도 필드에 저장. 양쪽 대칭이 아니면(한쪽 공백)
    summarize_bill 이 (None, None) 을 돌려주며, 그 경우 summary_fetched 를 남기지 않아
    다음 열람 때 재시도한다. 본문 없음/생성 실패는 페이지를 막지 않는다.
    """
    if bill.summary_fetched is not None:
        return
    if not (bill.proposal_reason or bill.main_content):
        return
    try:
        pros, cons = summarize_bill(
            bill.title, bill.proposal_reason, bill.main_content,
            provider=settings.summary_provider, model=settings.summary_model,
            api_key=settings.gemini_api_key, base_url=settings.ollama_base_url,
        )
    except Exception:  # noqa: BLE001 — 요약 실패가 법안 페이지를 막지 않도록
        logger.warning("법안 AI 요약 on-demand 생성 실패 bill=%s", bill.id, exc_info=True)
        return
    if not pros or not cons:  # 대칭 깨짐 → 저장 안 하고 다음에 재시도
        return
    bill.summary_pros = pros
    bill.summary_cons = cons
    bill.summary_model = settings.summary_model
    bill.summary_fetched = datetime.now(timezone.utc)
    db.commit()


@router.get("/{bid}", response_model=BillDetail)
def get_bill(bid: int, db: Session = Depends(get_db)) -> BillDetail:
    bill = db.get(Bill, bid)
    if bill is None:
        raise HTTPException(status_code=404, detail="해당 법안을 찾을 수 없습니다.")

    # 본문 미수집이면 그 자리에서 받아 캐싱(on-demand). 본문은 페이지 본체라 동기로 둠(수 초).
    # ⚠️ AI 요약(로컬 LLM, 수십 초)은 응답을 막지 않도록 분리 — 프론트가 /summary 로 따로 호출.
    _ensure_content(db, bill)

    # 대표발의자 (party 를 함께 적재 — lazy load 왕복 제거)
    proposer = None
    if bill.proposer_id:
        p = db.scalars(
            select(Person)
            .options(selectinload(Person.party))
            .where(Person.id == bill.proposer_id)
        ).first()
        if p is not None:
            proposer = ProposerBrief(
                id=p.id, name=p.name,
                party=PartyBrief(name=p.party.name, color_hex=p.party.color_hex)
                if p.party else None,
            )

    # 본회의 집계(의안당 0~1건)
    vote = db.scalars(
        select(Vote).where(Vote.bill_id == bid).order_by(Vote.session_date.desc().nullslast())
    ).first()
    vote_out = None
    party_breakdown: list[PartyVote] = []
    voters: list[Voter] = []
    if vote is not None:
        vote_out = VoteAggregate(
            session_date=vote.session_date,
            member_total=vote.member_total, vote_total=vote.vote_total,
            yes=vote.yes_total, no=vote.no_total, blank=vote.blank_total,
        )
        # 의원별 기록(있으면 정당별 분해 + 표결 의원 명단)
        rows = db.execute(
            select(Person.id, Person.name, Party.name, Party.color_hex, VoteRecord.choice)
            .join(Person, Person.id == VoteRecord.person_id)
            .outerjoin(Party, Party.id == Person.party_id)
            .where(VoteRecord.vote_id == vote.id)
            .order_by(Party.name, Person.name)
        ).all()
        agg: dict[str, dict] = defaultdict(
            lambda: {"color": None, "yes": 0, "no": 0, "abstain": 0, "absent": 0}
        )
        key = {
            VoteChoice.찬성: "yes", VoteChoice.반대: "no",
            VoteChoice.기권: "abstain", VoteChoice.불참: "absent",
        }
        for pid, pname, party_name, color, choice in rows:
            pn = party_name or "무소속"
            agg[pn]["color"] = color
            agg[pn][key[choice]] += 1
            voters.append(Voter(id=pid, name=pname, party=party_name, choice=choice.value))
        party_breakdown = [
            PartyVote(
                party=pn, color_hex=v["color"],
                yes=v["yes"], no=v["no"], abstain=v["abstain"], absent=v["absent"],
            )
            for pn, v in sorted(agg.items(), key=lambda kv: -sum(
                x for k, x in kv[1].items() if k != "color"
            ))
        ]

    # 처리 단계 날짜 타임라인 — 단계 의결일(nwbpacrgavhjryiph). 본회의 의결일은
    # 단계 데이터(plenary_proc_date) 우선, 없으면 표결 집계일(vote.session_date)로 보강.
    plenary_date = bill.plenary_proc_date or (vote.session_date if vote else None)
    funnel = [
        FunnelStep(label="발의", date=bill.proposed_date, done=bill.proposed_date is not None),
        FunnelStep(label="소관위 의결", date=bill.committee_proc_date,
                   done=bill.committee_proc_date is not None),
        FunnelStep(label="법사위 의결", date=bill.law_proc_date,
                   done=bill.law_proc_date is not None),
        FunnelStep(label="본회의 의결", date=plenary_date,
                   done=plenary_date is not None or vote is not None),
        FunnelStep(label="공포", date=bill.announce_date, done=bill.announce_date is not None),
    ]

    pros = bill.summary_pros.split("\n") if bill.summary_pros else []
    cons = bill.summary_cons.split("\n") if bill.summary_cons else []
    summary_notice = (
        SUMMARY_NOTICE.format(model=bill.summary_model or "생성 모델")
        if (pros and cons) else None
    )

    # 입법예고 기간 시민 찬반 의견(있고, 집계된 경우만) — 민심 vs 국회(표결/처리)를 한 페이지에서.
    civic = None
    notice_row = db.scalar(
        select(LawNotice).where(
            LawNotice.bill_no == bill.bill_no, LawNotice.opinion_total.isnot(None)
        )
    )
    if notice_row is not None and (notice_row.opinion_total or 0) > 0:
        civic = CivicOpinion(
            total=notice_row.opinion_total,
            agree=notice_row.agree_count, oppose=notice_row.oppose_count,
            etc=notice_row.etc_count, pal_url=notice_row.source_url,
            notice=CIVIC_NOTICE, method_note=CIVIC_METHOD,
        )

    return BillDetail(
        id=bill.id, bill_no=bill.bill_no, title=bill.title,
        committee=bill.committee, category=bill.category, status=bill.status,
        proposed_date=bill.proposed_date, likms_url=bill.likms_url,
        proposal_reason=bill.proposal_reason, main_content=bill.main_content,
        summary_pros=pros, summary_cons=cons, summary_notice=summary_notice,
        proposer=proposer, proposer_kind=bill.proposer_kind,
        proposer_text=bill.proposer_text, vote=vote_out,
        party_breakdown=party_breakdown, voters=voters, funnel=funnel,
        civic_opinion=civic, notice=NOTICE,
    )


class BillSummary(BaseModel):
    """AI 참고 요약(좋은점/문제점) — 상세와 분리해 별도 호출(생성에 수십 초 소요).

    pending: 본문은 있으나 아직 요약 생성 중/실패(다음 호출 때 재시도). 양쪽이 채워지면 ready.
    """
    summary_pros: list[str]
    summary_cons: list[str]
    summary_notice: str | None
    ready: bool  # 좋은점·문제점 양쪽이 준비됨
    available: bool  # 원문이 있어 요약 생성이 가능함(없으면 영구 빈값)


@router.get("/{bid}/summary", response_model=BillSummary)
def get_bill_summary(bid: int, db: Session = Depends(get_db)) -> BillSummary:
    """법안 AI 요약 — 미생성이면 그 자리에서 생성(on-demand, 로컬 LLM).

    상세 응답을 막지 않도록 분리한 엔드포인트. 프론트는 상세 표시 후 이걸 따로 호출해
    "생성 중…" 표시 → 완료되면 채운다. 본문 없는 법안은 available=False(영구 빈값).
    """
    bill = db.get(Bill, bid)
    if bill is None:
        raise HTTPException(status_code=404, detail="해당 법안을 찾을 수 없습니다.")

    _ensure_content(db, bill)  # 요약엔 원문이 필요 — 미수집이면 먼저 확보
    _ensure_summary(db, bill)

    pros = bill.summary_pros.split("\n") if bill.summary_pros else []
    cons = bill.summary_cons.split("\n") if bill.summary_cons else []
    ready = bool(pros and cons)
    return BillSummary(
        summary_pros=pros, summary_cons=cons,
        summary_notice=SUMMARY_NOTICE.format(model=bill.summary_model or "생성 모델")
        if ready else None,
        ready=ready,
        available=bool(bill.proposal_reason or bill.main_content),
    )
