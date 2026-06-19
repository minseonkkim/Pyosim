// 어드민 검토 API 클라이언트 (Phase 2-3) — backend/app/admin.py 와 1:1.
// 토큰은 localStorage 에만 보관(서버 계정 없음). 모든 요청에 X-Admin-Token 헤더.

import { API_BASE } from "./api";

const TOKEN_KEY = "pyosim.admin_token";

export function getAdminToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export interface AdminQuestion {
  id: number;
  issue: string;
  issue_id: number;
  body: string;
  option_a_label: string | null;
  option_a_pro: string | null;
  option_a_con: string | null;
  option_b_label: string | null;
  option_b_pro: string | null;
  option_b_con: string | null;
  bill_id: number | null;
  bill_title: string | null;
  source_note: string | null;
  status: string;
  created_by: string;
  approved_by: string | null;
  review_note: string | null;
}

export type TransitionAction =
  | "검토시작"
  | "승인"
  | "반려"
  | "아카이브"
  | "초안복귀";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Token": getAdminToken(),
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* noop */
    }
    throw new Error(detail);
  }
  // 204 가능성은 없지만 안전하게
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export function listQuestions(status?: string): Promise<AdminQuestion[]> {
  const q = status ? `?status=${encodeURIComponent(status)}` : "";
  return req<AdminQuestion[]>(`/admin/questions${q}`);
}

export function patchQuestion(
  id: number,
  patch: Partial<AdminQuestion>,
): Promise<AdminQuestion> {
  return req<AdminQuestion>(`/admin/questions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function transitionQuestion(
  id: number,
  action: TransitionAction,
  opts: { by?: string; note?: string } = {},
): Promise<AdminQuestion> {
  return req<AdminQuestion>(`/admin/questions/${id}/transition`, {
    method: "POST",
    body: JSON.stringify({ action, ...opts }),
  });
}
