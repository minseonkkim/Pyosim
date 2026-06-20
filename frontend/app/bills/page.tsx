"use client";

// 법안 피드 (큐레이션 홈) — 흩어진 법안 대신 '논쟁이 있던' 정책 법안만 골라 보여준다.
// 🟡 추천이 아니라 사실 기반 선별(정쟁 제외·반대표/정당갈림 순). 탭하면 상세 그물망으로.

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchBills, type BillCard } from "@/lib/api";

export default function BillsFeedPage() {
  const [feed, setFeed] = useState<BillCard[] | null>(null);
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchBills(20)
      .then((f) => {
        setFeed(f.items);
        setNotice(f.notice);
      })
      .catch((e) => setErr((e as Error).message));
  }, []);

  return (
    <main>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>의견이 갈린 법안</h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 16 }}>
        국회에서 표가 팽팽했거나 정당 입장이 갈린 법안들이에요. 어떤 점이 좋고
        무엇이 우려되는지 한눈에 보고, 내 생각과 견줘보세요.
      </p>

      {err && <p className="disclaimer">⚠️ 불러오지 못했어요: {err}</p>}
      {feed === null && !err && <p className="muted">불러오는 중…</p>}
      {feed !== null && feed.length === 0 && (
        <p className="muted">아직 보여줄 법안이 없어요.</p>
      )}

      {feed?.map((b) => (
        <BillCardItem key={b.id} b={b} />
      ))}

      {notice && (
        <div className="disclaimer" style={{ marginTop: 20 }}>
          ⚖️ {notice}
        </div>
      )}
    </main>
  );
}

function BillCardItem({ b }: { b: BillCard }) {
  const yes = b.yes ?? 0;
  const no = b.no ?? 0;
  const total = yes + no || 1;
  return (
    <Link
      href={`/bill/${b.id}`}
      className="card"
      style={{ display: "block", textDecoration: "none", color: "var(--fg)" }}
    >
      <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
        <span
          className="chip"
          style={{
            fontSize: 11.5,
            fontWeight: 700,
            background: b.party_split ? "var(--ink-800)" : "var(--ink-100)",
            color: b.party_split ? "#fff" : "var(--muted)",
          }}
        >
          {b.party_split ? "⚡ 정당 입장 갈림" : b.contested_reason}
        </span>
        {b.committee && (
          <span className="chip" style={{ fontSize: 11.5 }}>
            {b.committee}
          </span>
        )}
      </div>

      <div style={{ fontWeight: 700, fontSize: 15.5, lineHeight: 1.4, wordBreak: "keep-all" }}>
        {b.title}
      </div>

      {/* 찬반 미니 바 — 긴장을 시각적으로 */}
      <div style={{ marginTop: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 3 }}>
          <span style={{ fontWeight: 600 }}>찬성 {yes}</span>
          <span className="muted">반대 {no}</span>
        </div>
        <div style={{ display: "flex", height: 7, borderRadius: 999, overflow: "hidden", background: "var(--ink-100)" }}>
          <span style={{ width: `${(yes / total) * 100}%`, background: "var(--ink-800)" }} />
          <span style={{ width: `${(no / total) * 100}%`, background: "var(--ink-400)" }} />
        </div>
      </div>

      {/* AI 한 줄 요약(있을 때만) — 좋은점/문제점 대칭 */}
      {b.pro && b.con && (
        <div style={{ marginTop: 10, fontSize: 13, lineHeight: 1.55 }}>
          <div style={{ wordBreak: "keep-all" }}>
            <b style={{ color: "var(--ink-800)" }}>좋은점</b> {b.pro}
          </div>
          <div style={{ wordBreak: "keep-all", marginTop: 2 }}>
            <b className="muted">문제점</b> <span className="muted">{b.con}</span>
          </div>
        </div>
      )}
    </Link>
  );
}
