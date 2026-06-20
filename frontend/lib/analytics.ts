// 익명 퍼널 로깅 — 이탈 지점 측정("한 단계 더 들어오는가", 기획서 2장·6장).
// 🟡 PII 없음: 익명 세션ID + 이벤트명 + 소형 props 만. 백엔드가 화이트리스트로 검증.
// 전송: 이벤트를 잠깐 모았다가(800ms) sendBeacon 으로 한 번에. 탭 종료 시 즉시 flush.

import { API_BASE } from "./api";
import { getSessionId } from "./session";

export type EventName =
  | "landing"
  | "test_start"
  | "question_view"
  | "answer"
  | "test_complete"
  | "result_view"
  | "share_click"
  | "source_open"
  | "tax_view"
  | "tax_calc"
  | "tax_to_test";

type Props = Record<string, string | number | boolean>;
interface Queued {
  name: EventName;
  ts: number;
  props?: Props;
}

const queue: Queued[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;

export function track(name: EventName, props?: Props): void {
  if (typeof window === "undefined") return;
  queue.push({ name, ts: Date.now(), props });
  if (timer === null) {
    timer = setTimeout(flush, 800);
  }
}

export function flush(): void {
  if (typeof window === "undefined" || queue.length === 0) return;
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
  const events = queue.splice(0, queue.length);
  const body = JSON.stringify({ session_id: getSessionId(), events });
  const url = `${API_BASE}/api/events`;

  // sendBeacon: 탭 종료 중에도 전송 보장. text/plain → CORS 프리플라이트 없이 cross-origin 가능.
  try {
    if (navigator.sendBeacon) {
      const ok = navigator.sendBeacon(url, new Blob([body], { type: "text/plain" }));
      if (ok) return;
    }
  } catch {
    /* 폴백으로 진행 */
  }

  // 폴백: keepalive fetch. 로깅 실패는 서비스에 영향 주지 않으므로 무시.
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body,
    keepalive: true,
  }).catch(() => {});
}

// 탭을 떠날 때 큐에 남은 이벤트를 흘려보낸다(이탈 직전 이벤트 유실 방지).
if (typeof window !== "undefined") {
  window.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);
}
