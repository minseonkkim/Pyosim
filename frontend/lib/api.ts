// 백엔드 API 클라이언트 + 타입 (Phase 1-3~1-4)
// 응답 스키마는 backend/app/api.py 와 1:1 대응.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export type Choice = "찬성" | "반대" | "모름";

export interface Option {
  label: string | null;
  pro: string | null;
  con: string | null;
}

export interface Question {
  id: number;
  issue: string;
  body: string;
  option_a: Option; // 채점상 '찬성' 방향(Ⓐ)
  option_b: Option; // 채점상 '반대' 방향(Ⓑ)
  source_note: string | null;
  likms_url: string | null;
  status: string;
}

export interface QuestionsResponse {
  questions: Question[];
  preview: boolean;
  notice: string | null;
}

export interface PartyMatch {
  party: string;
  color_hex: string | null;
  match_rate: number; // 0~1
  matched: number;
  total: number;
}

export interface QuestionResult {
  question_id: number;
  issue: string;
  body: string;
  your_choice: Choice;
  your_label: string | null;
  agree_parties: string[];
  disagree_parties: string[];
  source_note: string | null;
  likms_url: string | null;
}

export interface ResultsResponse {
  answered: number;
  skipped: number;
  party_match: PartyMatch[];
  per_question: QuestionResult[];
  disclaimer: string;
  method_note: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// 프로토타입: 승인 문항이 아직 없으므로 preview=1(초안 포함). 공개 전 외부 검토 필요.
export function fetchQuestions(preview = true): Promise<QuestionsResponse> {
  return getJSON<QuestionsResponse>(`/api/questions?preview=${preview ? 1 : 0}`);
}

export async function submitResults(
  sessionId: string,
  answers: { question_id: number; choice: Choice }[],
): Promise<ResultsResponse> {
  const res = await fetch(`${API_BASE}/api/results`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answers }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`결과 계산 실패: ${res.status} ${detail}`);
  }
  return res.json() as Promise<ResultsResponse>;
}
