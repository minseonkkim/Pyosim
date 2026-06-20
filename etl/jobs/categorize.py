"""법안 생활 카테고리 분류 — 세금·노동·주거 등 (Phase 1-3b).

목적: 법안 피드에서 "내 삶과 상관" 있는 분야로 좁혀보게 한다.
무관심층이 멈추지 않도록, 추상적 위원회명 대신 일상 언어 분류를 붙인다.

🟡 중립성(기획 1.3 — 알고리즘 공개): LLM·추천이 아니라 **결정론적 키워드 규칙**이다.
   규칙(아래 RULES)이 곧 분류 근거이며 코드로 공개된다. 가치 판단·우선순위 매김 없음.

방식:
  1) 제목 키워드 매칭(RULES 순서대로 — 먼저 맞는 카테고리가 1차 분류).
  2) 제목 미매칭이면, 명확히 대응되는 위원회만 보수적으로 폴백(COMMITTEE_FALLBACK).
  3) 둘 다 없으면 None(미분류 — 피드 칩에 노출 안 됨).

한 법안에 단일 대표 카테고리만 부여(MVP). 다중 태깅은 추후 확장.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

# ⚠️ jobs.db 를 먼저 import — 모듈 로드 시 backend(app.*) 를 sys.path 에 올린다.
from jobs.db import Bill  # noqa: I001

# 카테고리 → 제목 키워드. 순서가 우선순위(앞선 카테고리가 먼저 매칭).
# 생활 밀착·구체 주제를 앞에 둬, 광범위한 키워드가 구체 주제를 가리지 않게 한다.
RULES: list[tuple[str, tuple[str, ...]]] = [
    ("세금", (
        "조세", "소득세", "부가가치세", "부가세", "법인세", "종합부동산세", "종부세",
        "상속세", "증여세", "양도소득", "관세", "과세", "세액공제", "비과세", "면세",
        "국세", "지방세", "세무", "납세", "세제", "세금",
    )),
    ("주거", (
        "주택", "부동산", "임대차", "전세", "월세", "재건축", "재개발", "분양",
        "주거", "임대주택", "청약", "공공주택", "다가구", "재정비", "도시정비",
    )),
    ("노동", (
        "근로", "노동", "임금", "최저임금", "고용", "일자리", "산업재해", "산재",
        "노동조합", "퇴직", "비정규직", "해고", "근로시간", "노사", "직장", "실업",
    )),
    ("복지", (
        "기초연금", "국민연금", "돌봄", "보육", "장애인", "노인", "한부모",
        "기초생활", "사회보장", "아동수당", "취약계층", "복지", "연금", "수당",
    )),
    ("의료", (
        "의료", "건강보험", "의약품", "병원", "감염병", "보건", "약사", "간호",
        "의사", "치료", "백신", "응급의료", "정신건강", "공공의료", "의료기관",
    )),
    ("교육", (
        "교육", "학교", "대학", "학자금", "사교육", "유아교육", "어린이집",
        "교원", "입시", "등록금", "학교폭력", "학폭", "유치원", "학생",
    )),
    ("환경", (
        "기후", "탄소", "미세먼지", "재생에너지", "온실가스", "대기오염", "폐기물",
        "자원순환", "생태", "녹색", "일회용", "환경오염", "탄소중립", "환경",
    )),
    ("교통", (
        "도로교통", "자동차관리", "철도", "운수", "버스", "택시", "주차", "대중교통",
        "항공", "운전면허", "교통안전", "도로", "교통",
    )),
    ("안전", (
        "재난", "화재", "소방", "재해", "범죄", "성폭력", "가정폭력", "아동학대",
        "학대", "피해자", "스토킹", "음주운전", "마약", "안전관리", "산업안전",
    )),
    ("디지털", (
        "개인정보", "정보통신", "플랫폼", "인공지능", "전자상거래", "보이스피싱",
        "데이터", "디지털", "온라인", "통신", "사이버",
    )),
    ("먹거리", (
        "농업", "농어업", "축산", "수산", "식품", "농민", "어민", "먹거리",
        "농산물", "식품안전", "농촌", "농림", "양곡",
    )),
    ("가족", (
        "성평등", "양성평등", "다문화", "모성", "육아휴직", "출산", "저출산",
        "가족", "여성", "보육료",
    )),
]

# 제목 미매칭 시 폴백 — 카테고리가 명확히 일대일인 위원회만(애매한 곳은 제외).
COMMITTEE_FALLBACK: dict[str, str] = {
    "보건복지위원회": "복지",
    "교육위원회": "교육",
    "농림축산식품해양수산위원회": "먹거리",
    "성평등가족위원회": "가족",
    "여성가족위원회": "가족",
}

# 분류기가 부여할 수 있는 전체 카테고리(표시 순서 = 피드 칩 순서).
CATEGORIES: list[str] = [c for c, _ in RULES]


def classify(title: str | None, committee: str | None = None) -> str | None:
    """제목(+위원회)으로 생활 카테고리 1개를 반환. 미매칭이면 None.

    🟡 순수 함수 — 규칙(RULES/COMMITTEE_FALLBACK)이 곧 분류 근거. 외부 호출·LLM 없음.
    """
    text = title or ""
    for category, keywords in RULES:
        if any(kw in text for kw in keywords):
            return category
    if committee:
        return COMMITTEE_FALLBACK.get(committee)
    return None


def run_categorize(
    session: Session, *, dry_run: bool = False, limit: int | None = None,
    only_missing: bool = False,
) -> dict:
    """모든 법안에 category 를 (재)부여. 멱등 — 규칙 바뀌면 재실행해 갱신.

    only_missing=True 면 category 가 비어있는 법안만(증분). 기본은 전수 재분류
    (규칙은 코드라 재실행 비용이 없고, 규칙 갱신 반영을 위해 전수가 기본).
    """
    q = select(Bill)
    if only_missing:
        q = q.where(Bill.category.is_(None))
    bills = list(session.scalars(q).all())

    counts: dict[str, int] = {}
    n_changed = n_none = n_done = 0
    for bill in bills:
        if limit is not None and n_done >= limit:
            break
        n_done += 1
        cat = classify(bill.title, bill.committee)
        if cat is None:
            n_none += 1
        else:
            counts[cat] = counts.get(cat, 0) + 1
        if cat != bill.category:
            n_changed += 1
            if not dry_run:
                bill.category = cat
        if not dry_run and n_done % 500 == 0:
            session.commit()

    if not dry_run:
        session.commit()
    return {
        "processed": n_done, "changed": n_changed, "uncategorized": n_none,
        "by_category": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
    }
