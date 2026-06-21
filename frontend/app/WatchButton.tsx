"use client";

// 감시하기 토글 — 청원·법안·의원 상세에 붙는 재사용 버튼 (Phase 2 감시견 알림).
// 익명 세션(localStorage)으로 구독을 켜고 끈다. 구독하면 진행 변화가 /watch 받은함에 쌓인다.
// 🟡 알림은 공식 단계 변화 같은 사실만 전한다(판정 없음).

import { useEffect, useState } from "react";

import { getSessionId } from "@/lib/session";
import { watchCheck, watchSubscribe, watchUnsubscribe, type WatchKind } from "@/lib/api";

export default function WatchButton({
  kind,
  refId,
}: {
  kind: WatchKind;
  refId: number;
}) {
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const sid = getSessionId();
    if (!sid || !Number.isFinite(refId)) return;
    watchCheck(sid, kind, refId)
      .then((r) => setSubscribed(r.subscribed))
      .catch(() => setSubscribed(false));
  }, [kind, refId]);

  async function toggle() {
    if (busy || subscribed === null) return;
    const sid = getSessionId();
    setBusy(true);
    try {
      const r = subscribed
        ? await watchUnsubscribe(sid, kind, refId)
        : await watchSubscribe(sid, kind, refId);
      setSubscribed(r.subscribed);
    } catch {
      // 네트워크 실패 시 상태 유지 — 조용히 무시
    } finally {
      setBusy(false);
    }
  }

  const on = subscribed === true;
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={busy || subscribed === null}
      aria-pressed={on}
      className="btn"
      style={{
        fontSize: 13,
        fontWeight: 700,
        padding: "8px 14px",
        width: "auto",
        background: on ? "var(--ink-900)" : "var(--surface)",
        color: on ? "#fff" : "var(--fg)",
        border: `1px solid ${on ? "var(--ink-900)" : "var(--border)"}`,
        opacity: subscribed === null ? 0.5 : 1,
      }}
    >
      {on ? "🔔 감시 중" : "🔕 감시하기"}
    </button>
  );
}
