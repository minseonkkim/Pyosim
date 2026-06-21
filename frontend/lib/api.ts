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
  bill_id: number | null;
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
  proposed_date: string | null;
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

export interface CommitteeBrief {
  name: string;
  type_name: string | null;
  role: string | null;
  term_label: string | null;
}

export interface PersonProfile {
  id: number;
  name: string;
  party: PartyBrief | null;
  district: string | null;
  photo_url: string | null;
  birth_date: string | null;
  age: number | null;
  gender: string | null;
  term_label: string | null;
  position: string | null;
  attendance_rate: number | null;
  profile_source_url: string | null;
  last_verified: string | null;
  committees: CommitteeBrief[];
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
  date: string | null;
}

// 입법예고 기간 시민 찬반 의견 집계 (기능 B-4.4) — 법안 상세에 함께 표시(민심 vs 국회).
export interface CivicOpinion {
  total: number;
  agree: number | null;
  oppose: number | null;
  etc: number | null;
  pal_url: string | null;
  notice: string;
  method_note: string;
}

export interface BillDetail {
  id: number;
  bill_no: string;
  title: string;
  committee: string | null;
  category: string | null;
  status: string | null;
  proposed_date: string | null;
  likms_url: string | null;
  proposal_reason: string | null;
  main_content: string | null;
  summary_pros: string[];
  summary_cons: string[];
  summary_notice: string | null;
  proposer: ProposerBrief | null;
  proposer_kind: string | null; // 의원/정부/위원장
  proposer_text: string | null; // 예: "정부", "정무위원장" — proposer 없을 때 표시
  vote: VoteAggregate | null;
  party_breakdown: PartyVote[];
  voters: Voter[];
  funnel: FunnelStep[];
  civic_opinion: CivicOpinion | null;
  notice: string;
}

export function fetchBill(id: number): Promise<BillDetail> {
  return getJSON<BillDetail>(`/api/bills/${id}`);
}

// AI 참고 요약 — 상세와 분리(생성에 수십 초). 상세 표시 후 따로 호출해 "생성 중…" → 채움.
export interface BillSummary {
  summary_pros: string[];
  summary_cons: string[];
  summary_notice: string | null;
  ready: boolean; // 좋은점·문제점 양쪽 준비됨
  available: boolean; // 원문이 있어 생성 가능(없으면 영구 빈값)
}

export function fetchBillSummary(id: number): Promise<BillSummary> {
  return getJSON<BillSummary>(`/api/bills/${id}/summary`);
}

export interface BillCard {
  id: number;
  title: string;
  committee: string | null;
  category: string | null;
  proposed_date: string | null;
  yes: number | null;
  no: number | null;
  contested_reason: string;
  party_split: boolean;
  pro: string | null;
  con: string | null;
  opinion_total: number | null; // 입법예고 시민 의견 수(있을 때만) — 진입 후크
  opinion_lean: string | null; // 찬성/반대 우세
}

export interface BillFeed {
  items: BillCard[];
  notice: string;
}

export function fetchBills(
  limit = 20,
  category?: string,
  sort?: "contested" | "opinions",
): Promise<BillFeed> {
  const p = new URLSearchParams({ limit: String(limit) });
  if (category) p.set("category", category);
  if (sort) p.set("sort", sort);
  return getJSON<BillFeed>(`/api/bills?${p.toString()}`);
}

// 피드에 존재하는 생활 카테고리(세금·노동·주거…) + 건수 — 칩 필터용.
export interface CategoryCount {
  category: string;
  count: number;
}

export function fetchBillCategories(): Promise<{ items: CategoryCount[] }> {
  return getJSON<{ items: CategoryCount[] }>(`/api/bills/categories`);
}

// ───────── 청원 추적 (Phase 2 기능 A, 민심 레이어) ─────────
export interface PetitionStage {
  label: string;
  date: string | null;
  done: boolean;
}

export interface PetitionCard {
  id: number;
  title: string;
  committee: string | null;
  is_national_consent: boolean;
  signature_count: number | null;
  proposed_date: string | null;
  status: string; // 계류 / 처리완료
  proc_result: string | null;
  days_pending: number | null;
}

export interface StatusCount {
  label: string;
  count: number;
}

export interface PetitionFeed {
  items: PetitionCard[];
  pending: number;
  done: number;
  total: number;
  status_breakdown: StatusCount[];
  notice: string;
}

export interface PetitionDetail {
  id: number;
  bill_no: string;
  title: string;
  proposer: string | null;
  introducer: string | null;
  is_national_consent: boolean;
  signature_count: number | null;
  objective: string | null;
  content: string | null;
  realm: string | null;
  committee: string | null;
  proposed_date: string | null;
  committee_date: string | null;
  status: string;
  proc_result: string | null;
  proc_result_note: string | null;
  days_pending: number | null;
  referred_days: number | null;
  stall_line: string | null;
  stall_note: string | null;
  stages: PetitionStage[];
  likms_url: string | null;
  last_verified: string | null;
  notice: string;
}

export function fetchPetitions(
  opts: { status?: string; q?: string; limit?: number } = {},
): Promise<PetitionFeed> {
  const p = new URLSearchParams();
  if (opts.status) p.set("status", opts.status);
  if (opts.q) p.set("q", opts.q);
  if (opts.limit) p.set("limit", String(opts.limit));
  const qs = p.toString();
  return getJSON<PetitionFeed>(`/api/petitions${qs ? `?${qs}` : ""}`);
}

export function fetchPetition(id: number): Promise<PetitionDetail> {
  return getJSON<PetitionDetail>(`/api/petitions/${id}`);
}

// ───────── 민심과 다른 국회 (법안+청원 통합 불일치) ─────────
export interface MismatchItem {
  kind: "bill" | "petition";
  ref_id: number;
  href: string;
  title: string;
  committee: string | null;
  category: string | null;
  voice_count: number;
  voice_label: string; // 반대 / 찬성 / 동의
  voice_source: string; // 입법예고 의견 / 국민동의청원 / 청원
  response_label: string; // 가결 / 부결 / 본회의 불부의 / 계류 …
  response_kind: "passed" | "rejected" | "pending";
  detail: string | null;
}

export interface MismatchFeed {
  items: MismatchItem[];
  notice: string;
}

export function fetchMismatch(limit = 300): Promise<MismatchFeed> {
  return getJSON<MismatchFeed>(`/api/mismatch?limit=${limit}`);
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
