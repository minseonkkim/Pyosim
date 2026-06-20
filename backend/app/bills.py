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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bill_content import fetch_bill_content
from app.bill_summary import summarize_bill
from app.config import settings
from app.db import get_db
from app.models import Bill, Party, Person, Vote, VoteChoice, VoteRecord
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


class BillFeed(BaseModel):
    items: list[BillCard]
    notice: str


class CategoryCount(BaseModel):
    category: str
    count: int


class CategoryList(BaseModel):
    items: list[CategoryCount]


def _feed_filtered(q):
    """피드 공통 필터 — 정쟁·절차성 제외 + 본회의 반대표 집계 있는 의안만."""
    for kw in FEED_EXCLUDE:
        q = q.where(Bill.title.notilike(f"%{kw}%"))
    return q.where(Vote.no_total.isnot(None))


@router.get("", response_model=BillFeed)
def list_bills(
    limit: int = 20, category: str | None = None, db: Session = Depends(get_db)
) -> BillFeed:
    """큐레이션 피드 — 본회의에서 의견이 갈린 정책 법안을 '논쟁' 순으로.

    🟡 추천이 아니라 사실 기반 선별: 정쟁·절차성 제외, 반대표 많은 순 후보 →
    정당(민주 vs 국힘) 다수 입장이 갈린 법안을 위로. AI 요약 있으면 좋은점/문제점 한 줄 동봉.
    category(세금·노동·주거…)가 오면 해당 분야로 좁힌다.
    """
    pool = max(limit * 4, 40)
    q = _feed_filtered(select(Bill, Vote).join(Vote, Vote.bill_id == Bill.id))
    if category:
        q = q.where(Bill.category == category)
    q = q.order_by(Vote.no_total.desc().nullslast()).limit(pool)
    rows = db.execute(q).all()
    if not rows:
        return BillFeed(items=[], notice=FEED_NOTICE)

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
    # vote_id -> party -> {찬,반}
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

    # 정당 갈림 우선, 그 다음 반대표 많은 순
    cards.sort(key=lambda c: (c.party_split, c.no or 0), reverse=True)
    return BillFeed(items=cards[:limit], notice=FEED_NOTICE)


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

    # 대표발의자
    proposer = None
    if bill.proposer_id:
        p = db.get(Person, bill.proposer_id)
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

    funnel = [
        FunnelStep(label="발의", done=bill.proposed_date is not None),
        FunnelStep(label="위원회", done=bill.committee is not None),
        FunnelStep(label="본회의", done=vote is not None),
        FunnelStep(label="처리", done=bool(bill.status)),
    ]

    pros = bill.summary_pros.split("\n") if bill.summary_pros else []
    cons = bill.summary_cons.split("\n") if bill.summary_cons else []
    summary_notice = (
        SUMMARY_NOTICE.format(model=bill.summary_model or "생성 모델")
        if (pros and cons) else None
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
        notice=NOTICE,
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
