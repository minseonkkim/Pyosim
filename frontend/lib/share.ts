// 공유 카드 링크 빌더 — 결과 요약을 쿼리로 인코딩(서버 저장 없이 무상태).
// /share 페이지가 이 파라미터로 OG 이미지를 생성한다.

import type { ResultsResponse } from "./api";

export interface ShareSummary {
  party: string; // 가장 많이 겹친 정당
  rate: number; // 0~100
  n: number; // 답한 문항 수(모름 제외)
  color: string; // hex (# 없이)
}

export function summarize(result: ResultsResponse): ShareSummary | null {
  const top = result.party_match[0];
  if (!top) return null;
  return {
    party: top.party,
    rate: Math.round(top.match_rate * 100),
    n: result.answered,
    color: (top.color_hex ?? "#888888").replace("#", ""),
  };
}

export function shareQuery(s: ShareSummary): string {
  const p = new URLSearchParams({
    party: s.party,
    rate: String(s.rate),
    n: String(s.n),
    color: s.color,
  });
  return p.toString();
}

export function shareUrl(s: ShareSummary, origin: string): string {
  return `${origin}/share?${shareQuery(s)}`;
}
