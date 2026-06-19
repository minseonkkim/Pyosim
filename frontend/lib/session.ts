// 익명 세션 ID + 진행 중 답변 임시 저장 (이탈 방지·중간 저장, Phase 1-3)
// 서버 계정 없이 localStorage 기반. session_id 는 백엔드 Answer.session_id 로 전달.

import type { Choice, ResultsResponse } from "./api";

const SID_KEY = "pyosim.sid";
const ANSWERS_KEY = "pyosim.answers";
const RESULT_KEY = "pyosim.result";

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `s-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem(SID_KEY);
  if (!sid) {
    sid = randomId();
    localStorage.setItem(SID_KEY, sid);
  }
  return sid;
}

export type AnswerMap = Record<number, Choice>;

export function loadAnswers(): AnswerMap {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(ANSWERS_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function saveAnswers(answers: AnswerMap): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ANSWERS_KEY, JSON.stringify(answers));
}

export function clearAnswers(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ANSWERS_KEY);
}

// 결과는 새로고침 후에도 보이도록 sessionStorage 에 잠깐 보관.
export function stashResult(result: ResultsResponse): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(RESULT_KEY, JSON.stringify(result));
}

export function popResult(): ResultsResponse | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(RESULT_KEY);
    return raw ? (JSON.parse(raw) as ResultsResponse) : null;
  } catch {
    return null;
  }
}
