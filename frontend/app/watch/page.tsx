"use client";

// 감시 받은함 (Phase 2 감시견 알림) — 구독한 청원·법안·의원의 진행 변화를 모아 본다.
// 익명 세션 기준 pull 방식. 변화가 있는 항목을 위로, 확인하면 읽음 처리(다음 변화부터 다시 알림).
// 🟡 알림 문구는 공식 단계 변화 같은 사실만(판정·평가 없음).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { getSessionId } from "@/lib/session";
import {
  fetchWatch,
  watchSeen,
  watchUnsubscribe,
  type WatchFeed,
  type WatchItem,
} from "@/lib/api";

const KIND_LABEL: Record<WatchItem["kind"], string> = {
  petition: "청원",
  bill: "법안",
  person: "의원",
};

export default function WatchPage() {
  const [feed, setFeed] = useState<WatchFeed | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    const sid = getSessionId();
    if (!sid) return;
    fetchWatch(sid)
      .then(setFeed)
      .catch((e) => setErr((e as Error).message));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function markAllSeen() {
    const sid = getSessionId();
    await watchSeen(sid);
    load();
  }

  async function remove(item: WatchItem) {
    const sid = getSessionId();
    await watchUnsubscribe(sid, item.kind, item.ref_id);
    load();
  }

  if (err) {
    return (
      <main>
        <p className="disclaimer">⚠️ {err}</p>
      </main>
    );
  }
  if (feed === null) {
    return (
      <main>
        <p className="muted">불러오는 중…</p>
      </main>
    );
  }

  return (
    <main>
      <h1 style={{ fontSize: 22, margin: "8px 0 4px" }}>감시 목록</h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 16, wordBreak: "keep-all" }}>
        구독한 청원·법안·의원의 진행이 바뀌면 여기 모여요. 새 변화가 있는 항목이 위로 올라옵니다.
      </p>

      {feed.total === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "28px 16px" }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>🔕</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>아직 감시 중인 게 없어요</div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 14, wordBreak: "keep-all" }}>
            청원·법안·의원 상세에서 <b>감시하기</b>를 누르면, 그 진행이 바뀔 때 여기로 알려드려요.
          </p>
          <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
            <Link href="/petitions" className="btn btn-ghost" style={{ width: "auto", fontSize: 13 }}>
              청원 둘러보기
            </Link>
            <Link href="/bills" className="btn btn-ghost" style={{ width: "auto", fontSize: 13 }}>
              법안 둘러보기
            </Link>
            <Link href="/persons" className="btn btn-ghost" style={{ width: "auto", fontSize: 13 }}>
              국회의원 둘러보기
            </Link>
          </div>
        </div>
      ) : (
        <>
          {feed.unread > 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 10,
                marginBottom: 12,
              }}
            >
              <span style={{ fontSize: 13.5, fontWeight: 700 }}>
                🔔 새 변화 {feed.unread}건
              </span>
              <button
                type="button"
                onClick={markAllSeen}
                className="btn btn-ghost"
                style={{ width: "auto", fontSize: 12.5, padding: "6px 12px" }}
              >
                모두 읽음
              </button>
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {feed.items.map((it) => (
              <WatchRow key={`${it.kind}-${it.ref_id}`} item={it} onRemove={() => remove(it)} />
            ))}
          </div>
        </>
      )}

      <div className="disclaimer" style={{ marginTop: 18 }}>
        ⚖️ {feed.notice}
      </div>
    </main>
  );
}

function WatchRow({ item, onRemove }: { item: WatchItem; onRemove: () => void }) {
  return (
    <div
      className="card"
      style={{
        borderLeft: item.has_update ? "3px solid var(--ink-900)" : "3px solid var(--border)",
        background: item.has_update ? "var(--ink-50)" : "var(--surface)",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
        <span className="chip" style={{ fontSize: 11, fontWeight: 700 }}>
          {KIND_LABEL[item.kind]}
        </span>
        <button
          type="button"
          onClick={onRemove}
          className="muted"
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: 12,
            padding: 0,
          }}
          aria-label="감시 해제"
        >
          감시 해제
        </button>
      </div>

      <Link
        href={item.href}
        style={{
          display: "block",
          fontSize: 15,
          fontWeight: 600,
          margin: "6px 0 4px",
          color: "var(--fg)",
          textDecoration: "none",
          wordBreak: "keep-all",
        }}
      >
        {item.title}
      </Link>

      {item.changes.length > 0 ? (
        <ul style={{ margin: "6px 0 0", paddingLeft: 16 }}>
          {item.changes.map((c, i) => (
            <li
              key={i}
              style={{ fontSize: 13.5, lineHeight: 1.6, fontWeight: 600, wordBreak: "keep-all" }}
            >
              {c}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted" style={{ fontSize: 12.5, margin: "4px 0 0" }}>
          아직 새로운 변화가 없어요.
        </p>
      )}
    </div>
  );
}
