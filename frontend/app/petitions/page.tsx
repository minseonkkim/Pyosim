"use client";

// 청원 추적 (Phase 2 기능 A, 민심 레이어) — "그 청원 지금 어디?"
// 시민이 올린 청원이 접수→소관위→심사→처리 중 지금 어느 단계에 멈췄는지 사실로 보여준다.
// 🟡 추천·순위 없이 같은 양식. 발안자 개인정보 최소화(동의 인원수를 헤드라인으로).

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

import { fetchPetitions, type PetitionCard, type PetitionFeed } from "@/lib/api";

const PAGE = 20; // 무한스크롤 한 번에 더 그리는 카드 수
type Filter = "전체" | "계류" | "처리완료";

export default function PetitionsPage() {
  const [feed, setFeed] = useState<PetitionFeed | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("전체");
  const [visible, setVisible] = useState(PAGE);

  useEffect(() => {
    setFeed(null);
    setErr(null);
    setVisible(PAGE);
    fetchPetitions({ status: filter === "전체" ? undefined : filter })
      .then(setFeed)
      .catch((e) => setErr((e as Error).message));
  }, [filter]);

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
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>그 청원, 지금 어디?</h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 14 }}>
        시민이 올린 청원이 국회 어디까지 갔는지 추적해요. 접수만 되고 멈춰 있는지,
        위원회에서 심사 중인지, 끝내 어떻게 처리됐는지 — 공식 기록 그대로.
      </p>

      {/* 상태 필터 칩 */}
      {feed && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
          <FilterChip label="전체" on={filter === "전체"} onClick={() => setFilter("전체")} />
          <FilterChip
            label={`계류 중 ${feed.pending}`}
            on={filter === "계류"}
            onClick={() => setFilter("계류")}
          />
          <FilterChip
            label={`처리완료 ${feed.done}`}
            on={filter === "처리완료"}
            onClick={() => setFilter("처리완료")}
          />
        </div>
      )}

      {err && <p className="disclaimer">⚠️ 불러오지 못했어요: {err}</p>}
      {feed === null && !err && <p className="muted">불러오는 중…</p>}
      {feed !== null && feed.items.length === 0 && (
        <p className="muted">여기에 보여줄 청원이 아직 없어요.</p>
      )}

      {shown.map((p) => (
        <PetitionCardItem key={p.id} p={p} />
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

function FilterChip({
  label,
  on,
  onClick,
}: {
  label: string;
  on: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="chip"
      style={{
        fontSize: 12.5,
        fontWeight: on ? 700 : 500,
        cursor: "pointer",
        border: "none",
        background: on ? "var(--ink-800)" : "var(--ink-100)",
        color: on ? "#fff" : "var(--muted)",
      }}
    >
      {label}
    </button>
  );
}

function PetitionCardItem({ p }: { p: PetitionCard }) {
  const pending = p.status === "계류";
  return (
    <Link
      href={`/petition/${p.id}`}
      className="card"
      style={{ display: "block", textDecoration: "none", color: "var(--fg)" }}
    >
      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
        {p.is_national_consent && (
          <span
            className="chip"
            style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-800)", color: "#fff" }}
          >
            🙋 국민동의청원
          </span>
        )}
        {p.signature_count != null && (
          <span className="chip" style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink-800)" }}>
            {p.signature_count.toLocaleString()}명 동의
          </span>
        )}
        {p.committee && (
          <span className="chip" style={{ fontSize: 11.5 }}>
            {p.committee}
          </span>
        )}
      </div>

      <div style={{ fontWeight: 700, fontSize: 15.5, lineHeight: 1.4, wordBreak: "keep-all" }}>
        {p.title}
      </div>

      {/* '지금 어디' 한 줄 — 사실만 */}
      <div style={{ marginTop: 8, fontSize: 13, display: "flex", gap: 8, alignItems: "center" }}>
        <span
          className="chip"
          style={{
            fontSize: 11.5,
            fontWeight: 700,
            background: pending ? "var(--ink-100)" : "var(--ink-50)",
            color: pending ? "var(--ink-800)" : "var(--muted)",
          }}
        >
          {pending ? "계류 중" : "처리완료"}
        </span>
        <span className="muted" style={{ wordBreak: "keep-all" }}>
          {pending
            ? p.days_pending != null
              ? `접수 ${p.days_pending}일째 — 아직 처리 안 됨`
              : "심사 진행 중"
            : `처리결과: ${p.proc_result ?? "—"}`}
        </span>
      </div>
    </Link>
  );
}
