"""법안 AI 참고 요약 — 제안이유·주요내용 원문 → 좋은점/문제점(양쪽 대칭) 생성.

🟡 중립성(기획 1.3·로드맵 1-3):
  - 원문(제안이유=발의이유, 주요내용=내용)은 **건드리지 않는다**. 이 모듈은 좋은점/문제점만 생성.
  - **양쪽 대칭**: 좋은점과 문제점을 같은 개수로, 한쪽에 치우치지 않게 생성하도록 강제.
  - 판정·찬반 권유 금지. "이 법은 통과돼야/막아야" 류 표현 배제.
  - 어느 모델이 생성했는지는 호출 측에서 summary_model 로 기록(출처 공개).

구현: Google Gemini REST(generateContent)를 urllib 로 호출(의존성 추가 없음 — bill_content 와 동일 방식).
순수 함수(네트워크 + 파싱)만 담는다. DB 적재는 호출 측(backend on-demand / etl 배치).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# 좋은점/문제점 각 항목 수(대칭). 본문이 짧으면 모델이 줄일 수 있으나 같은 수를 권장.
_N_POINTS = 3

_SYSTEM = (
    "너는 대한민국 법안을 시민에게 중립적으로 설명하는 보조 도구다. "
    "주어진 법안의 제안이유·주요내용만 근거로, 이 법안이 통과될 경우의 "
    "'좋은점'과 '문제점(우려)'을 작성한다.\n"
    "절대 규칙:\n"
    "1) 좋은점과 문제점을 정확히 같은 개수로, 비슷한 분량·구체성으로 대칭되게 쓴다.\n"
    "2) 어느 쪽이 옳다고 판정하거나 찬성/반대를 권유하지 않는다.\n"
    "3) 제공된 본문에 없는 사실을 지어내지 않는다. 추측은 '~할 수 있다' 식으로만.\n"
    "4) 정치 진영·인물을 평가하지 않는다. 정책의 효과/우려에만 집중한다.\n"
    "5) 각 항목은 한 문장, 쉬운 말로. 전문용어는 풀어 쓴다.\n"
    "반드시 아래 JSON 형식으로만 답한다(설명·마크다운 없이):\n"
    '{"pros": ["...", "..."], "cons": ["...", "..."]}'
)


def _build_prompt(title: str, reason: str | None, main: str | None) -> str:
    parts = [f"[법안명]\n{title}\n"]
    if reason:
        parts.append(f"[제안이유]\n{reason}\n")
    if main:
        parts.append(f"[주요내용]\n{main}\n")
    parts.append(
        f"\n위 법안에 대해 좋은점 {_N_POINTS}개, 문제점 {_N_POINTS}개를 "
        "대칭되게 JSON 으로만 답하라."
    )
    return "\n".join(parts)


def _parse_response(payload: dict) -> tuple[list[str], list[str]]:
    """Gemini 응답 → (pros, cons). 형식 어긋나면 ([], []) 로 안전 반환."""
    try:
        text = payload["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return [], []
    text = text.strip()
    # ```json … ``` 펜스가 붙어 오면 제거
    if text.startswith("```"):
        text = text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], []
    pros = [str(x).strip() for x in data.get("pros", []) if str(x).strip()]
    cons = [str(x).strip() for x in data.get("cons", []) if str(x).strip()]
    return pros, cons


def summarize_bill(
    title: str,
    reason: str | None,
    main: str | None,
    *,
    api_key: str,
    model: str = "gemini-2.5-flash",
    timeout: int = 60,
) -> tuple[str | None, str | None]:
    """(좋은점, 문제점) 텍스트. 각 항목은 줄바꿈으로 join. 생성 불가 시 (None, None).

    좋은점/문제점 중 한쪽이라도 비면 대칭이 깨졌다고 보고 (None, None) 반환(중립성).
    네트워크/파싱 예외는 호출 측에서 처리하도록 그대로 전파한다.
    """
    if not api_key or not (reason or main):
        return None, None

    body = {
        "system_instruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [{"parts": [{"text": _build_prompt(title, reason, main)}]}],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        GEMINI_ENDPOINT.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read())

    pros, cons = _parse_response(payload)
    if not pros or not cons:
        return None, None
    return "\n".join(pros), "\n".join(cons)
