"use client";

// 민심과 다른 국회 — 플랫폼 핵심 명제(민심 vs 국회 불일치) 통합 뷰.
// 법안(입법예고 의견)·청원(동의) 가리지 않고, 시민이 표출한 민심과 국회 응답이 갈린 사안을
// 민심 규모(의견/동의 수) 큰 순으로. 🟡 주제로 거르지 않음(정쟁 필터 없음)·사실만 병치.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { fetchMismatch, type MismatchItem, type MismatchFeed } from "@/lib/api";
import Loading from "@/app/Loading";

const PAGE = 20;

export default function MismatchPage() {
  const [feed, setFeed] = useState<MismatchFeed | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [visible, setVisible] = useState(PAGE);

  useEffect(() => {
    fetchMismatch()
      .then(setFeed)
      .catch((e) => setErr((e as Error).message));
  }, []);

  const shown = feed?.items.slice(0, visible) ?? [];
  const hasMore = feed !== null && visible < feed.items.length;

  const sentinel = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!hasMore) return;
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) setVisible((v) => v + PAGE);
      },
      { rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, shown.length]);

  return (
    <main>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>민심과 다른 국회</h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>
        시민이 입법예고에 의견을 내거나 청원에 동의한 수와, 국회의 표결·처리가 다르게 간
        사안이에요. 주제를 가리지 않고, 민심이 컸던 순서로 사실만 나란히 둡니다.
      </p>

      {err && <p className="disclaimer">⚠️ 불러오지 못했어요: {err}</p>}
      {feed === null && !err && <Loading inline />}
      {feed !== null && feed.items.length === 0 && (
        <p className="muted">아직 보여줄 사안이 없어요.</p>
      )}

      {shown.map((m) => (
        <MismatchCard key={`${m.kind}-${m.ref_id}`} m={m} />
      ))}

      {hasMore && (
        <div ref={sentinel} className="muted" style={{ textAlign: "center", padding: 16, fontSize: 13 }}>
          더 불러오는 중…
        </div>
      )}

      {feed?.notice && (
        <div className="disclaimer" style={{ marginTop: 20 }}>
          ⚖️ {feed.notice}
        </div>
      )}
    </main>
  );
}

function MismatchCard({ m }: { m: MismatchItem }) {
  const isPetition = m.kind === "petition";
  return (
    <Link
      href={m.href}
      className="card"
      style={{ display: "block", textDecoration: "none", color: "var(--fg)" }}
    >
      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
        <span
          className="chip"
          style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-800)", color: "#fff" }}
        >
          {isPetition ? "🙋 청원" : "⚖️ 법안"}
        </span>
        {m.category && (
          <span className="chip" style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink-800)" }}>
            #{m.category}
          </span>
        )}
        {m.committee && (
          <span className="chip" style={{ fontSize: 11.5 }}>
            {m.committee}
          </span>
        )}
      </div>

      <div style={{ fontWeight: 700, fontSize: 15.5, lineHeight: 1.4, wordBreak: "keep-all" }}>
        {m.title}
      </div>

      {/* 민심 ↔ 국회 대비 — 양끝에 사실 그대로 */}
      <div
        style={{
          marginTop: 11,
          display: "flex",
          alignItems: "stretch",
          gap: 8,
          background: "var(--ink-50)",
          borderRadius: "var(--radius-md)",
          padding: "10px 12px",
        }}
      >
        <div style={{ flex: 1 }}>
          <div className="muted" style={{ fontSize: 11 }}>{m.voice_source}</div>
          <div style={{ fontWeight: 700, fontSize: 15, marginTop: 2 }}>
            {m.voice_label} <span className="numeral">{m.voice_count.toLocaleString()}</span>
          </div>
        </div>
        <div className="muted" style={{ alignSelf: "center", fontSize: 13 }}>↔</div>
        <div style={{ flex: 1, textAlign: "right" }}>
          <div className="muted" style={{ fontSize: 11 }}>국회</div>
          <div style={{ fontWeight: 700, fontSize: 15, marginTop: 2 }}>{m.response_label}</div>
          {m.detail && (
            <div className="muted numeral" style={{ fontSize: 11.5, marginTop: 1 }}>{m.detail}</div>
          )}
        </div>
      </div>
    </Link>
  );
}
