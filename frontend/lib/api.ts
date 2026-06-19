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

// ───────── 정치인 프로필 (Phase 1-2, 그물망 '사람' 축) ─────────
export interface PartyBrief {
  name: string;
  color_hex: string | null;
}

export interface PersonListItem {
  id: number;
  name: string;
  party: PartyBrief | null;
  district: string | null;
  photo_url: string | null;
}

export interface BillBrief {
  id: number;
  bill_no: string;
  title: string;
  status: string | null;
  likms_url: string | null;
}

export interface CriminalRecordOut {
  charge: string;
  sentence: string | null;
  date_sentenced: string | null;
  is_final: boolean | null;
  source_url: string | null;
}

export interface VoteSummary {
  yes: number;
  no: number;
  abstain: number;
  absent: number;
  total: number;
}

export interface PersonProfile {
  id: number;
  name: string;
  party: PartyBrief | null;
  district: string | null;
  photo_url: string | null;
  attendance_rate: number | null;
  profile_source_url: string | null;
  last_verified: string | null;
  proposed_count: number;
  proposed_bills: BillBrief[];
  vote_summary: VoteSummary;
  criminal_records: CriminalRecordOut[];
  notice: string;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export function fetchPersons(opts: { party?: string; q?: string } = {}): Promise<
  PersonListItem[]
> {
  const p = new URLSearchParams();
  if (opts.party) p.set("party", opts.party);
  if (opts.q) p.set("q", opts.q);
  const qs = p.toString();
  return getJSON<PersonListItem[]>(`/api/persons${qs ? `?${qs}` : ""}`);
}

export function fetchPerson(id: number): Promise<PersonProfile> {
  return getJSON<PersonProfile>(`/api/persons/${id}`);
}

// ───────── 법안 상세 (Phase 1-3, 그물망 '법안' 축) ─────────
export interface ProposerBrief {
  id: number;
  name: string;
  party: PartyBrief | null;
}

export interface VoteAggregate {
  session_date: string | null;
  member_total: number | null;
  vote_total: number | null;
  yes: number | null;
  no: number | null;
  blank: number | null;
}

export interface PartyVote {
  party: string;
  color_hex: string | null;
  yes: number;
  no: number;
  abstain: number;
  absent: number;
}

export interface Voter {
  id: number;
  name: string;
  party: string | null;
  choice: "찬성" | "반대" | "기권" | "불참";
}

export interface FunnelStep {
  label: string;
  done: boolean;
}

export interface BillDetail {
  id: number;
  bill_no: string;
  title: string;
  committee: string | null;
  status: string | null;
  proposed_date: string | null;
  likms_url: string | null;
  proposal_reason: string | null;
  main_content: string | null;
  proposer: ProposerBrief | null;
  vote: VoteAggregate | null;
  party_breakdown: PartyVote[];
  voters: Voter[];
  funnel: FunnelStep[];
  notice: string;
}

export function fetchBill(id: number): Promise<BillDetail> {
  return getJSON<BillDetail>(`/api/bills/${id}`);
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
