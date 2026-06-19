"""🤖 LLM 문항 초안 생성 — Phase 2-3.

안전선(기획서 11장, 로드맵 2-3): **데이터는 100% 자동, 문항은 반자동.**
  - 이 모듈은 법안 요약 → **중립 Ⓐ/Ⓑ 문항 초안**(body·장단점)만 생성한다.
  - 생성물은 항상 `status=초안`, `created_by=auto`로 저장되고, 사람이 승인하기 전엔 비공개.
  - 정당 입장(찬/반) 매핑은 만들지 않는다 — 그건 실제 표결기록(Phase 2-2)·큐레이션의 몫.
    (LLM이 정당 입장을 지어내면 출처·중립성 원칙 위반.)

🟡 중립 프롬프트 설계(양쪽 논리 대칭 강제):
  - 정치 용어·법안명·정당명 미포함, 생활 언어 상황 질문
  - Ⓐ/Ⓑ 각각 장점(pro)+단점(con) 대칭 — 어느 쪽도 도덕적으로 우월하게 들리지 않게
  - 채점 규약: option_a = 법안을 '시행/도입하자'(찬성 방향), option_b = '하지 말자/현행 유지'(반대 방향)
  - 응답의 "잘 모르겠어요"는 UI(AnswerChoice.모름)가 항상 제공 → 문항 자체엔 넣지 않음

SDK: 공식 Anthropic SDK(claude-opus-4-8), 구조화 출력(output_config.format)로 스키마 강제.
키(`ANTHROPIC_API_KEY`)가 없으면 `LLMUnavailable`을 던진다(어드민 generate 엔드포인트만 비활성).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from app.config import settings
from app.models import Bill

# seed.py ISSUES 와 일치해야 채점·시드가 맞물린다.
ALLOWED_ISSUES: list[str] = [
    "노동",
    "복지·분배",
    "경제·시장",
    "안보·외교",
    "환경·기후",
    "젠더·가족",
    "사회질서·치안",
    "교육",
]


class LLMUnavailable(RuntimeError):
    """API 키 미설정 또는 SDK 미설치 — generate 엔드포인트 비활성 신호."""


@dataclass
class DraftQuestion:
    issue: str
    body: str
    option_a_label: str
    option_a_pro: str
    option_a_con: str
    option_b_label: str
    option_b_pro: str
    option_b_con: str
    rationale: str  # 검토자용: 왜 중립·대칭인지 한 줄 근거


_SYSTEM = """당신은 정치 성향 테스트의 **중립 문항 작성자**입니다.
실제 국회 법안 하나를 받아, 정치를 전혀 모르는 사람도 자기 답을 고를 수 있는
'생활 언어 상황 질문'과 Ⓐ/Ⓑ 두 선택지를 만듭니다.

반드시 지킬 규칙(어기면 문항은 폐기됩니다):
1. 법안명·법률용어·정당명·정치인 이름을 질문과 선택지에 절대 넣지 마세요. 일상 언어만.
2. 입장을 묻지 말고 **Ⓐ/Ⓑ 비교형**으로 만드세요. 두 선택지 각각에 장점(pro) 1개와
   단점(con) 1개를 대칭으로 답니다. 한쪽만 장점이 많거나 도덕적으로 우월하게 들리면 안 됩니다.
3. Ⓐ는 **이 법안이 하려는 변화(도입/강화/시행)에 찬성하는 방향**,
   Ⓑ는 **그 변화에 반대하거나 현행을 유지하는 방향**으로 고정하세요. (채점 규약)
4. 양쪽 모두 실제로 존재하는 합리적 우려와 이점을 균형 있게 담으세요.
   한쪽을 허수아비(약한 논리)로 만들지 마세요.
5. 질문(body)은 한 문장, 부드러운 물음으로. 선택지 label은 짧고 중립적으로.
6. 쟁점(issue)은 주어진 목록에서 가장 알맞은 하나만 고르세요: {issues}

반드시 아래 키를 가진 **JSON 객체 하나만** 출력하세요. 코드펜스·설명·머리말 없이 JSON 만:
{{"issue": "...", "body": "...",
  "option_a_label": "...", "option_a_pro": "...", "option_a_con": "...",
  "option_b_label": "...", "option_b_pro": "...", "option_b_con": "...",
  "rationale": "<왜 양쪽이 중립·대칭인지 검토자용 한 줄>"}}""".format(
    issues=", ".join(ALLOWED_ISSUES)
)

_REQUIRED_KEYS = (
    "issue",
    "body",
    "option_a_label",
    "option_a_pro",
    "option_a_con",
    "option_b_label",
    "option_b_pro",
    "option_b_con",
    "rationale",
)


def _parse_json_object(text: str) -> dict:
    """모델 출력에서 JSON 객체를 견고하게 추출(코드펜스/잡텍스트 허용)."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s.split("\n", 1)[1] if "\n" in s else s
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("LLM 응답에서 JSON 객체를 찾지 못했습니다.")
    data = json.loads(s[start : end + 1])
    missing = [k for k in _REQUIRED_KEYS if not str(data.get(k, "")).strip()]
    if missing:
        raise ValueError(f"LLM 응답 필드 누락: {missing}")
    if data["issue"] not in ALLOWED_ISSUES:
        raise ValueError(f"LLM이 허용되지 않은 쟁점을 골랐습니다: {data['issue']}")
    return data


def _bill_brief(bill: Bill) -> str:
    parts = [f"법안명: {bill.title}"]
    if bill.committee:
        parts.append(f"소관위원회: {bill.committee}")
    if bill.status:
        parts.append(f"처리상태: {bill.status}")
    if bill.proposed_date:
        parts.append(f"제안일: {bill.proposed_date.isoformat()}")
    return "\n".join(parts)


def draft_question_for_bill(bill: Bill) -> DraftQuestion:
    """법안 1건 → 중립 Ⓐ/Ⓑ 문항 초안. 키 없으면 LLMUnavailable."""
    if not settings.anthropic_api_key:
        raise LLMUnavailable(
            "ANTHROPIC_API_KEY 미설정 — LLM 문항 초안 생성 비활성(.env 에 키 추가 필요)."
        )
    try:
        import anthropic  # 지연 임포트: 키 없는 환경에선 의존성도 선택사항
    except ModuleNotFoundError as e:  # pragma: no cover - 환경 의존
        raise LLMUnavailable("anthropic SDK 미설치 — pip install anthropic") from e

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user = (
        "다음 법안을 바탕으로 중립 Ⓐ/Ⓑ 문항 초안 하나를 만들어 주세요.\n\n"
        f"{_bill_brief(bill)}\n\n"
        "이 법안이 '하려는 변화'를 파악해, 그 변화에 찬성=Ⓐ / 반대·현행유지=Ⓑ 로 두세요."
    )
    resp = client.messages.create(
        model=settings.llm_model,
        max_tokens=2000,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    data = _parse_json_object(text)
    return DraftQuestion(
        issue=data["issue"],
        body=data["body"].strip(),
        option_a_label=data["option_a_label"].strip(),
        option_a_pro=data["option_a_pro"].strip(),
        option_a_con=data["option_a_con"].strip(),
        option_b_label=data["option_b_label"].strip(),
        option_b_pro=data["option_b_pro"].strip(),
        option_b_con=data["option_b_con"].strip(),
        rationale=data["rationale"].strip(),
    )
