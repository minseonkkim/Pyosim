"""데이터 모델 — 기획서 10장 스키마.

원칙(🟡):
- 모든 외부 수집 데이터에 `source_url` / `last_verified` 일관 적용.
- 관계 그래프 `Relationship.evidence_url` 은 NOT NULL (엣지마다 근거 필수).
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ───────────────────────── Enums ─────────────────────────
class VoteChoice(str, enum.Enum):
    찬성 = "찬성"
    반대 = "반대"
    기권 = "기권"
    불참 = "불참"


class AnswerChoice(str, enum.Enum):
    찬성 = "찬성"
    반대 = "반대"
    모름 = "모름"


class QuestionStatus(str, enum.Enum):
    초안 = "초안"
    검토중 = "검토중"
    승인 = "승인"
    아카이브 = "아카이브"


class QuestionCreator(str, enum.Enum):
    auto = "auto"
    admin = "admin"


class PalStatus(str, enum.Enum):
    진행중 = "진행중"
    종료 = "종료"


# ───────────────────────── 핵심 인물·정당·지역 ─────────────────────────
class Party(Base):
    __tablename__ = "party"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    color_hex: Mapped[str | None] = mapped_column(String(7))  # 예: #004EA2

    persons: Mapped[list[Person]] = relationship(back_populates="party")


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # 열린국회정보 의원코드(MONA_CD) — 표결기록 매핑 키. 현직 22대 기준 고유.
    assembly_member_code: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"))
    district: Mapped[str | None] = mapped_column(String(120))
    photo_url: Mapped[str | None] = mapped_column(Text)
    attendance_rate: Mapped[float | None] = mapped_column()

    # 인적 사항(열린국회정보 의원 API) — 프로필 보강
    birth_date: Mapped[date | None] = mapped_column(Date)  # 생년월일(BTH_DATE)
    gender: Mapped[str | None] = mapped_column(String(10))  # 성별(SEX_GBN_NM)
    term_label: Mapped[str | None] = mapped_column(String(20))  # 선수(REELE_GBN_NM: 초선/재선…)
    position: Mapped[str | None] = mapped_column(String(60))  # 직책(JOB_RES_NM: 위원/위원장…)

    # 🟡 출처·검증
    profile_source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    party: Mapped[Party | None] = relationship(back_populates="persons")
    vote_records: Mapped[list[VoteRecord]] = relationship(back_populates="person")
    criminal_records: Mapped[list[CriminalRecord]] = relationship(back_populates="person")
    committee_memberships: Mapped[list[CommitteeMembership]] = relationship(back_populates="person")


class District(Base):
    __tablename__ = "district"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(60))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))

    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ───────────────────────── 법안·표결 ─────────────────────────
class Bill(Base):
    __tablename__ = "bill"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)  # 의안번호
    # 열린국회정보 BILL_ID(PRC_...) — 표결기록·likms 직링크 키
    assembly_bill_id: Mapped[str | None] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    proposer_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"), index=True)
    # 의원 외 제안자(정부·위원장·전직의원) 표기용 — proposer_id 가 없을 때 화면에 표시.
    # 출처: 의안검색 OpenAPI(TVBPMBILL11) PROPOSER_KIND / PROPOSER.
    # 🟡 정부안 소관부처(○○부)는 API 에 없어 PROPOSER 는 "정부" 까지만 제공된다.
    proposer_kind: Mapped[str | None] = mapped_column(String(20))  # 의원/정부/위원장
    proposer_text: Mapped[str | None] = mapped_column(String(200))  # 예: "정부", "정무위원장"
    proposed_date: Mapped[date | None] = mapped_column(Date, index=True)  # 검색·목록 최근발의순 정렬
    # 처리 단계별 의결일 (본회의 처리안건 nwbpacrgavhjryiph) — 날짜 타임라인(Phase 1-3)
    # 🟡 공식 일자 그대로. 미도달 단계는 null(= '여기서 멈췄다'를 사실로 드러냄).
    committee_proc_date: Mapped[date | None] = mapped_column(Date)  # 소관위 의결
    law_proc_date: Mapped[date | None] = mapped_column(Date)  # 법사위(체계·자구) 의결
    plenary_proc_date: Mapped[date | None] = mapped_column(Date)  # 본회의 의결
    announce_date: Mapped[date | None] = mapped_column(Date)  # 공포
    committee: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str | None] = mapped_column(String(60))
    # 생활 카테고리(세금·노동·주거 등) — "내 삶과 상관" 강화용 (Phase 1-3b)
    # 🟡 결정론적 키워드 분류(jobs/categorize.py). 규칙이 코드로 공개됨(알고리즘 공개 원칙).
    category: Mapped[str | None] = mapped_column(String(20), index=True)
    law_link: Mapped[str | None] = mapped_column(Text)
    likms_url: Mapped[str | None] = mapped_column(Text)  # 의안정보시스템 billId 직링크
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 입법예고 (Phase 2)
    pal_status: Mapped[PalStatus | None] = mapped_column(Enum(PalStatus))
    pal_url: Mapped[str | None] = mapped_column(Text)

    # 법안 본문 — 의안원문(HWP PrvText)에서 추출한 공식 텍스트 (Phase 1-3 보완)
    # 🟡 원문 그대로(요약·판정 없음). AI 요약(좋은점/문제점)은 별도 필드/단계.
    proposal_reason: Mapped[str | None] = mapped_column(Text)  # 제안이유
    main_content: Mapped[str | None] = mapped_column(Text)  # 주요내용
    content_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # AI 참고 요약 — 원문(위)에서 LLM 이 생성한 좋은점/문제점 (Phase 1-3)
    # 🟡 원문과 분리된 별도 필드. 양쪽 대칭 생성. summary_model 로 생성 출처 공개.
    summary_pros: Mapped[str | None] = mapped_column(Text)  # 좋은점(줄바꿈 구분)
    summary_cons: Mapped[str | None] = mapped_column(Text)  # 문제점(줄바꿈 구분)
    summary_model: Mapped[str | None] = mapped_column(String(60))  # 생성 모델명
    summary_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 🟡 출처·검증
    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    votes: Mapped[list[Vote]] = relationship(back_populates="bill")
    questions: Mapped[list[Question]] = relationship(back_populates="bill")


class Vote(Base):
    __tablename__ = "vote"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bill.id"), nullable=False, index=True)
    session_date: Mapped[date | None] = mapped_column(Date)

    # 본회의 표결 집계 (의안별 표결현황 ncocpgfiaoituanbr) — 의원별 기록 없이도 전체 찬반 표시용
    member_total: Mapped[int | None] = mapped_column(Integer)  # 재적
    vote_total: Mapped[int | None] = mapped_column(Integer)  # 총투표
    yes_total: Mapped[int | None] = mapped_column(Integer)  # 찬성
    no_total: Mapped[int | None] = mapped_column(Integer, index=True)  # 반대 — 피드 반대표순 정렬
    blank_total: Mapped[int | None] = mapped_column(Integer)  # 기권

    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    bill: Mapped[Bill] = relationship(back_populates="votes")
    records: Mapped[list[VoteRecord]] = relationship(back_populates="vote")


class VoteRecord(Base):
    __tablename__ = "vote_record"
    __table_args__ = (UniqueConstraint("vote_id", "person_id", name="uq_vote_person"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vote_id: Mapped[int] = mapped_column(ForeignKey("vote.id"), nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    choice: Mapped[VoteChoice] = mapped_column(Enum(VoteChoice), nullable=False)

    vote: Mapped[Vote] = relationship(back_populates="records")
    person: Mapped[Person] = relationship(back_populates="vote_records")


class CriminalRecord(Base):
    __tablename__ = "criminal_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    charge: Mapped[str] = mapped_column(Text, nullable=False)  # 죄명
    sentence: Mapped[str | None] = mapped_column(Text)  # 형량
    date_sentenced: Mapped[date | None] = mapped_column(Date)
    is_final: Mapped[bool | None] = mapped_column(Boolean)  # 확정여부

    # 🟡 사실만, 출처 필수
    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped[Person] = relationship(back_populates="criminal_records")


# ───────────────────────── 위원회 (Phase 1-1) ─────────────────────────
class Committee(Base):
    """상임위원회·상설특별위원회 엔티티 — 법안 소관·의원 소속의 연결 키.

    출처: 열린국회정보 위원회 현황(nxrvzonlafugpqjuh). 현행 상임위 17 + 예결특위 1.
    임시·국정조사 특위(340)는 잡음이 커 Phase 1 에선 제외(상임/상설만 정규화).
    """
    __tablename__ = "committee"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dept_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # HR_DEPT_CD
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)  # COMMITTEE_NAME
    type_name: Mapped[str | None] = mapped_column(String(40))  # CMT_DIV_NM(상임위원회/상설특별위원회)
    member_limit: Mapped[int | None] = mapped_column(Integer)  # LIMIT_CNT(정원)

    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list[CommitteeMembership]] = relationship(back_populates="committee")


class CommitteeMembership(Base):
    """의원 ↔ 위원회 (제22대 위원회 경력). 🟡 '현재 소속'이 아니라 공식 '위원회 경력'.

    출처: 위원회 경력(nyzrglyvagmrypezq) 제22대 행을 위원회 엔티티명으로 매칭.
    2025 위원회 개편으로 신·구 명칭이 섞여, 현행 엔티티명 매칭이 자연스레 현행만 남긴다.
    term_label 에 공식 활동기간(FRTO_DATE)을 원문 그대로 보존(판정 없이 사실 표기).
    """
    __tablename__ = "committee_membership"
    __table_args__ = (
        UniqueConstraint("committee_id", "person_id", name="uq_committee_person"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    committee_id: Mapped[int] = mapped_column(ForeignKey("committee.id"), nullable=False, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(20))  # 위원장/간사/위원 (소스에 없으면 null)
    term_label: Mapped[str | None] = mapped_column(String(60))  # 활동기간(FRTO_DATE) 원문

    source_url: Mapped[str | None] = mapped_column(Text)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    committee: Mapped[Committee] = relationship(back_populates="memberships")
    person: Mapped[Person] = relationship(back_populates="committee_memberships")


# ───────────────────────── 청원 (Phase 2 기능 A) ─────────────────────────
class Petition(Base):
    """국민동의청원·일반청원 추적 — "그 청원 지금 어디?" (Phase 2 기능 A).

    민심 레이어의 첫 축: 시민이 올린 청원이 접수→소관위 회부→심사→처리 중
    '지금 어느 단계에 멈춰 있는지'를 공식 일자로 드러낸다.

    출처: 열린국회정보 청원 계류현황(`nvqbafvaajdiqhehi`) + 처리현황(`ncryefyuaflxnqbqo`).
    🟡 발안자 개인정보 최소화: 공식 공개 기록(likms)에 있는 값만 그대로 보존하고,
       화면은 동의 인원수(국민동의청원)를 헤드라인으로 쓴다. 처리결과는 공식 코드 원문 그대로.
    """
    __tablename__ = "petition"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)  # 의안번호
    assembly_bill_id: Mapped[str | None] = mapped_column(String(60), index=True)  # BILL_ID(PRC_…)
    title: Mapped[str] = mapped_column(Text, nullable=False)  # BILL_NAME

    proposer: Mapped[str | None] = mapped_column(String(200))  # PROPOSER(청원인, "○○외 N인" 원문)
    introducer: Mapped[str | None] = mapped_column(String(120))  # APPROVER(소개: 국민동의청원/○○의원)
    is_national_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 국민동의청원 여부
    signature_count: Mapped[int | None] = mapped_column(Integer)  # 동의 인원(PROPOSER "외 N인"에서 파싱)

    proposed_date: Mapped[date | None] = mapped_column(Date)  # PROPOSE_DT 접수일
    committee: Mapped[str | None] = mapped_column(String(120))  # CURR_COMMITTEE 소관위
    committee_date: Mapped[date | None] = mapped_column(Date)  # COMMITTEE_DT 회부일
    # 최종 처리결과(PROC_RESULT_CD) — 계류 중이면 null(= '아직 처리 안 됨'을 사실로 드러냄).
    # 예: 본회의불부의 / 대안반영폐기 / 채택 / 불채택 / 철회. 🟡 공식 코드 원문 그대로.
    proc_result: Mapped[str | None] = mapped_column(String(60))

    # 청원 본문 — 국민동의청원(petitions.assembly.go.kr) API, billId(assembly_bill_id)로 매칭.
    # 🟡 공식 공개 원문 그대로(요약·판정 없음). 일반청원(의원소개)은 이 사이트에 없어 null.
    objective: Mapped[str | None] = mapped_column(Text)  # 청원의 취지/목적(petitObjet)
    content: Mapped[str | None] = mapped_column(Text)  # 청원 내용 전문(petitCn)
    realm: Mapped[str | None] = mapped_column(String(40))  # 분야(petitRealmNm)
    content_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 🟡 출처·검증
    source_url: Mapped[str | None] = mapped_column(Text)  # likms billDetail 직링크
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LawNotice(Base):
    """입법예고 + 시민 찬반 의견 집계 — "법안에 시민이 뭐라 했나 vs 통과" (Phase 2 기능 B-4.4).

    민심 레이어의 둘째 축: 법안 입법예고 기간에 시민이 남긴 찬성/반대 의견을 집계해
    국회 처리(통과 여부)와 대비한다("반대가 압도적인데 통과됐나?").

    메타데이터 출처: 열린국회정보 종료된 입법예고(`nohgwtzsamojdozky`)·진행중(`nknalejkafmvgzmpt`).
      API 는 의안 메타(제목·소관위·예고종료일·링크)만 주고 **찬반 카운트는 없다**(라이브 확인).
    찬반 집계 출처: 국민참여입법시스템(pal.assembly.go.kr) 의견목록 공개 페이지를
      입장별(searchConRng 0=전체/1=찬성/2=반대) 전체 건수로 스크랩한다(jobs/lawnotice_opinions.py).
    🟡 의견 본문·작성자는 저장하지 않고 집계 수치만 보존. 처리 대비는 공식 일자(Bill)만 사용.
    """
    __tablename__ = "law_notice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bill_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)  # BILL_NO
    assembly_bill_id: Mapped[str | None] = mapped_column(String(60), index=True)  # BILL_ID(PRC_…) — Bill 연결+스크랩 키
    title: Mapped[str] = mapped_column(Text, nullable=False)  # BILL_NAME

    proposer: Mapped[str | None] = mapped_column(String(200))  # PROPOSER ("○○의원 등 N인")
    proposer_kind: Mapped[str | None] = mapped_column(String(20))  # PROPOSER_KIND_CD (의원/정부/위원장)
    committee: Mapped[str | None] = mapped_column(String(120))  # CURR_COMMITTEE 소관위
    notice_end_date: Mapped[date | None] = mapped_column(Date)  # NOTI_ED_DT 예고 종료일
    is_ongoing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 진행중 예고 여부

    # 시민 찬반 의견 집계(스크랩) — 미수집이면 null. 🟡 본문 없이 입장별 건수만.
    opinion_total: Mapped[int | None] = mapped_column(Integer, index=True)  # searchConRng=0 전체 — 의견순 정렬
    agree_count: Mapped[int | None] = mapped_column(Integer)  # searchConRng=1 찬성
    oppose_count: Mapped[int | None] = mapped_column(Integer)  # searchConRng=2 반대
    etc_count: Mapped[int | None] = mapped_column(Integer)  # 전체 - 찬성 - 반대
    opinion_fetched: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # 마지막 스크랩 시각

    # 🟡 출처·검증
    source_url: Mapped[str | None] = mapped_column(Text)  # LINK_URL (pal.assembly 입법예고 view)
    last_verified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ───────────────────────── 감시견 알림 (Phase 2) ─────────────────────────
class Subscription(Base):
    """익명 세션의 '감시' 구독 — 청원·법안·의원의 진행 변화를 추적 (Phase 2 리텐션 핵심).

    기획 4: "감시견 알림" — 시민이 관심 대상을 구독하면 진행이 바뀔 때 알린다.
    이 앱은 계정·이메일·푸시 등록이 없는 익명 세션(localStorage UUID)이라,
    OS 푸시가 아니라 **앱 내 '변화 알림' 받은함**(재방문 시 pull)으로 전달한다.

    동작(스냅샷 diff): 구독 시 대상의 '상태 서명'(snapshot)을 저장하고,
    `GET /api/watch` 가 현재 상태를 다시 계산해 비교 → 바뀐 것만 알림으로 준다.
    사용자가 확인하면 snapshot 을 현재로 갱신(읽음 처리).

    🟡 사실만: 알림 문구는 단계 이동·경과일 같은 공식 사실만(판정·평가 없음).
       세션ID 외 개인정보는 저장하지 않는다(Event 와 동일 원칙).
    """
    __tablename__ = "subscription"
    __table_args__ = (
        UniqueConstraint("session_id", "kind", "ref_id", name="uq_subscription_target"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 익명 세션
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # petition / bill / person
    ref_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 대상의 id

    # 마지막으로 사용자가 본 상태의 서명(state signature). diff 의 기준선.
    snapshot: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # snapshot 갱신 시각
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ───────────────────────── 테스트 (문항·답변) ─────────────────────────
class Issue(Base):
    __tablename__ = "issue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)  # 노동/복지/…

    questions: Mapped[list[Question]] = relationship(back_populates="issue")


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issue.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)  # 생활 언어로 된 상황 질문 (법안명·정당명 미포함)
    agree_meaning: Mapped[str] = mapped_column(Text, nullable=False)  # = option_a_pro (요약·하위호환)
    disagree_meaning: Mapped[str] = mapped_column(Text, nullable=False)  # = option_b_pro (요약·하위호환)

    # 장단점 중심 Ⓐ/Ⓑ 선택지 — 정치 용어 없이 양쪽 장점+단점을 대칭 제시.
    # 채점 규약: option_a = 앵커 법안 '찬성' 표결 방향, option_b = '반대' 방향.
    option_a_label: Mapped[str | None] = mapped_column(Text)
    option_a_pro: Mapped[str | None] = mapped_column(Text)  # 👍
    option_a_con: Mapped[str | None] = mapped_column(Text)  # 👎
    option_b_label: Mapped[str | None] = mapped_column(Text)
    option_b_pro: Mapped[str | None] = mapped_column(Text)
    option_b_con: Mapped[str | None] = mapped_column(Text)

    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bill.id"), index=True)  # 문항↔법안 매핑
    source_note: Mapped[str | None] = mapped_column(Text)  # "원래 어떤 법안인지" 출처 메모

    # 반자동 승인 흐름 (Phase 2-3)
    # 흐름: 초안 → 검토중 → 승인 → 아카이브. '반려'는 아카이브 + review_note('[반려] …')로 기록.
    status: Mapped[QuestionStatus] = mapped_column(
        Enum(QuestionStatus), default=QuestionStatus.초안, nullable=False, index=True
    )
    created_by: Mapped[QuestionCreator] = mapped_column(
        Enum(QuestionCreator), default=QuestionCreator.admin, nullable=False
    )
    approved_by: Mapped[str | None] = mapped_column(String(100))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)  # 검토 메모/반려 사유 (👤 사람 검토 기록)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    issue: Mapped[Issue] = relationship(back_populates="questions")
    bill: Mapped[Bill | None] = relationship(back_populates="questions")
    answers: Mapped[list[Answer]] = relationship(back_populates="question")


class Answer(Base):
    __tablename__ = "answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 익명 세션
    question_id: Mapped[int] = mapped_column(ForeignKey("question.id"), nullable=False, index=True)
    choice: Mapped[AnswerChoice] = mapped_column(Enum(AnswerChoice), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    question: Mapped[Question] = relationship(back_populates="answers")


# ───────────────────────── 익명 퍼널 로깅 (Phase 1-6) ─────────────────────────
class Event(Base):
    """이탈 지점 측정용 익명 이벤트 — "한 단계 더 들어오는가"(기획서 2장·6장).

    🟡 PII 미수집: 익명 세션ID(localStorage UUID) + 이벤트명 + 소형 props 만.
       IP·User-Agent·개인식별정보는 저장하지 않는다. props 는 API에서 화이트리스트로
       원시값(str/int/float/bool)만 통과시킨다.
    """
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # 익명 세션
    name: Mapped[str] = mapped_column(String(40), nullable=False, index=True)  # 화이트리스트 이벤트명
    props: Mapped[dict | None] = mapped_column(JSON)  # 소형 원시값만
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ───────────────────────── 관계 그래프 (Phase 3) ─────────────────────────
class Relationship(Base):
    __tablename__ = "relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_node: Mapped[str] = mapped_column(String(120), nullable=False)
    from_type: Mapped[str] = mapped_column(String(40), nullable=False)
    to_node: Mapped[str] = mapped_column(String(120), nullable=False)
    to_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(80), nullable=False)

    # 🟡 엣지마다 근거 링크 필수 — NOT NULL
    evidence_url: Mapped[str] = mapped_column(Text, nullable=False)

    curated_by: Mapped[str | None] = mapped_column(String(100))
    curated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ───────────────────────── 자동 갱신 파이프라인 (Phase 2 🤖) ─────────────────────────
class PipelineRun(Base):
    """1일 1회 데이터 갱신 실행 기록 — 신선도·모니터링 (감시견 알림 자동 점등의 전제).

    `python -m jobs.run --job daily` 한 번이 한 행. 잡별 성공/실패·소요시간·통계를
    `jobs`(JSON)에 담는다. 이 기록으로 "마지막 갱신은 언제·성공했나"를 답하고,
    프론트에 '데이터 기준일'을 노출한다(🟡 신뢰: 데이터가 살아있음을 사실로 보임).

    🟡 PII 없음 — 시스템 실행 메타만 저장(세션·개인정보 무관).
    """
    __tablename__ = "pipeline_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # 전 잡 무사 완료 여부
    trigger: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # scheduler/manual
    job_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    jobs: Mapped[dict | None] = mapped_column(JSON)  # 잡별 {status, stats, duration_ms, error}
    error: Mapped[str | None] = mapped_column(Text)  # 파이프라인 수준 치명적 오류
