"""정당별 일치율 채점 로직 — Phase 1-4.

🟡 투명성(로드맵 1-4 "일치율 계산 로직 문서화·공개"):
  - 일치율 = (내 답과 정당의 표결 방향이 같은 문항 수) / (그 정당이 표결한, 내가 '모름'이 아닌 문항 수)
  - 이건 **표결 일치도**일 뿐이다. "이 정당을 지지/반대하라"는 의미가 아니다.

채점 규약(seed_questions.py 와 일치):
  - option_a = 앵커 법안 '찬성' 표결 방향 → 사용자가 Ⓐ(=AnswerChoice.찬성) 선택 시 '찬성' 정당과 일치
  - option_b = '반대' 표결 방향        → 사용자가 Ⓑ(=AnswerChoice.반대) 선택 시 '반대' 정당과 일치
  - '모름'(AnswerChoice.모름)은 분모·분자 모두에서 제외

정당 입장(stance)의 출처(🟡):
  - 프로덕션: 실제 `VoteRecord`(의원별 본회의 표결)의 정당 내 다수결 방향 — `party_stances_from_votes()`
  - 프로토타입: 본 환경엔 전수 표결기록이 없으므로, 실제 22대 본회의 표결에서 정당이 갈린
    집계 사실(의안번호 + 표결일로 출처 보유)을 `CURATED_PARTY_STANCES` 로 둔다.
    → 개별 의원 표를 임의로 만들지 않는다(중립성·출처 원칙). 정당 집계 수준의 '사실'만 쓴다.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import AnswerChoice, Party, Person, VoteChoice, VoteRecord

# 정당 약칭 → seed.py 정식 명칭
민 = "더불어민주당"
힘 = "국민의힘"
혁 = "조국혁신당"
개 = "개혁신당"
진 = "진보당"

# 의안번호 → 정당 집계 입장(찬성 측 / 반대 측). 출처: 각 의안의 22대 본회의 표결.
# seed_questions.py DRAFTS 의 주석([민·혁·진 찬 / 힘·개 반] 등)과 1:1 대응.
CURATED_PARTY_STANCES: dict[str, dict[str, list[str]]] = {
    "2212656": {"찬": [민, 혁, 진], "반": [힘, 개]},        # 법인세 인상
    "2208496": {"찬": [민, 혁, 개, 진], "반": [힘]},         # 상법 이사 충실의무
    "2213246": {"찬": [민, 혁, 개, 진], "반": [힘]},         # 공공기관 노동이사제
    "2202967": {"찬": [민, 혁, 개, 진], "반": [힘]},         # 국민연금 소득대체율
    "2211639": {"찬": [민, 혁, 진], "반": [힘, 개]},        # 지역화폐
    "2211925": {"찬": [민, 개], "반": [힘, 혁, 진]},        # 수업 중 휴대폰 금지
    "2211647": {"찬": [민, 혁, 진], "반": [힘, 개]},        # 교권·학생 분리
    "2214866": {"찬": [민, 힘], "반": [혁, 개, 진]},        # 주요시설 인근 집회 제한
}

# 채점에 쓰는 정당(원내 변별력 있는 5당). 군소·무소속은 표본이 작아 일치율 왜곡 → 제외.
SCORED_PARTIES: list[str] = [민, 힘, 혁, 개, 진]

DISCLAIMER = (
    "이 결과는 실제 국회 표결과 내 답의 '일치도'일 뿐입니다. "
    "특정 정당을 지지하거나 반대하라는 뜻이 아니며, 정치적 판단은 본인의 몫입니다."
)
METHOD_NOTE = (
    "일치율 = (내 답과 정당의 실제 표결 방향이 같은 문항 수) ÷ "
    "(그 정당이 표결에 참여한, 내가 '모름'이 아닌 문항 수). "
    "정당 입장은 각 법안의 본회의 표결(의안번호로 확인 가능) 집계를 따릅니다."
)

# '찬성 측'으로 매칭되는 사용자 선택. (Ⓐ=찬성 방향)
_AGREE_WITH_YES = AnswerChoice.찬성
_AGREE_WITH_NO = AnswerChoice.반대


@dataclass
class PartyMatch:
    party: str
    color_hex: str | None
    matched: int
    total: int

    @property
    def rate(self) -> float:
        return round(self.matched / self.total, 4) if self.total else 0.0


def party_stances_from_votes(db: Session, vote_id: int) -> dict[str, str]:
    """실제 표결기록에서 정당 내 다수결 방향을 도출(프로덕션 경로).

    반환: {정당명: "찬"|"반"} — 찬성·반대 중 더 많은 쪽. 동수/표본 없음은 제외.
    """
    rows = (
        db.query(Party.name, VoteRecord.choice)
        .join(Person, Person.id == VoteRecord.person_id)
        .join(Party, Party.id == Person.party_id)
        .filter(VoteRecord.vote_id == vote_id)
        .all()
    )
    tally: dict[str, Counter] = {}
    for party_name, choice in rows:
        if choice in (VoteChoice.찬성, VoteChoice.반대):
            tally.setdefault(party_name, Counter())[choice] += 1

    stances: dict[str, str] = {}
    for party_name, counter in tally.items():
        yes, no = counter[VoteChoice.찬성], counter[VoteChoice.반대]
        if yes == no:
            continue  # 정당 내 의견이 갈리면 입장 미정 → 제외
        stances[party_name] = "찬" if yes > no else "반"
    return stances


def stance_map_for_bill(db: Session, bill_no: str, vote_id: int | None) -> dict[str, str]:
    """문항(앵커 법안)의 정당 입장 맵. 실제 표결기록 우선, 없으면 큐레이션 사실로 폴백."""
    if vote_id is not None:
        live = party_stances_from_votes(db, vote_id)
        if live:
            return live
    curated = CURATED_PARTY_STANCES.get(bill_no)
    if not curated:
        return {}
    return {p: "찬" for p in curated["찬"]} | {p: "반" for p in curated["반"]}


def score(
    answers: dict[int, AnswerChoice],
    stance_by_question: dict[int, dict[str, str]],
    party_colors: dict[str, str | None],
) -> list[PartyMatch]:
    """정당별 일치율 집계.

    answers: {question_id: AnswerChoice}
    stance_by_question: {question_id: {정당명: "찬"|"반"}}
    """
    matched: Counter = Counter()
    total: Counter = Counter()

    for qid, choice in answers.items():
        if choice == AnswerChoice.모름:
            continue
        stances = stance_by_question.get(qid)
        if not stances:
            continue
        for party in SCORED_PARTIES:
            stance = stances.get(party)
            if stance is None:
                continue
            total[party] += 1
            agree = (choice == _AGREE_WITH_YES and stance == "찬") or (
                choice == _AGREE_WITH_NO and stance == "반"
            )
            if agree:
                matched[party] += 1

    results = [
        PartyMatch(p, party_colors.get(p), matched[p], total[p])
        for p in SCORED_PARTIES
        if total[p] > 0
    ]
    results.sort(key=lambda m: (m.rate, m.total), reverse=True)
    return results
