"use client";

// 법안 피드 (큐레이션 홈) — 흩어진 법안 대신 '논쟁이 있던' 정책 법안만 골라 보여준다.
// 🟡 추천이 아니라 사실 기반 선별(정쟁 제외·반대표/정당갈림 순). 탭하면 상세 그물망으로.

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  fetchBills,
  fetchBillCategories,
  searchBills,
  type BillCard,
  type CategoryCount,
} from "@/lib/api";

// 큐레이션 피드는 재랭킹(정당 갈림→반대표 순) 때문에 offset 페이지네이션이 불안정하다.
// 그래서 한정적인 전체 피드를 한 번에 받아 스크롤에 따라 점진 렌더링한다(국회의원 목록과 동일).
const FEED_LIMIT = 1000; // 사실상 전체(정쟁 제외·표결 있는 정책 법안만이라 규모 한정적)
const PAGE = 20; // 무한스크롤 한 번에 더 그리는 카드 수

type Mode = "contested" | "opinions";

// 두 축은 별개 화면이다(섞지 않음). 랜딩의 진입 문이 ?view 로 초기 보기를 정한다.
export default function BillsFeedPage() {
  return (
    <Suspense fallback={<main><p className="muted">불러오는 중…</p></main>}>
      <BillsFeed />
    </Suspense>
  );
}

function BillsFeed() {
  const searchParams = useSearchParams();
  // 보기는 진입한 문(?view)으로 고정 — 페이지 안 전환 토글 없음(랜딩에서 이미 분리).
  const mode: Mode = searchParams.get("view") === "opinions" ? "opinions" : "contested";

  const [feed, setFeed] = useState<BillCard[] | null>(null);
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [cats, setCats] = useState<CategoryCount[]>([]);
  const [active, setActive] = useState<string | null>(null); // 선택 카테고리(없으면 전체)
  const [visible, setVisible] = useState(PAGE);

  // 검색 — 큐레이션 피드(표결·의견)는 표결 끝난 법안만 담아, 계류 중인 최근 발의안은
  // 닿지 못한다. 검색은 제목으로 22대 의안 전체를 훑는다(별도 모드).
  const [q, setQ] = useState("");
  const [results, setResults] = useState<BillCard[] | null>(null);
  const [searching, setSearching] = useState(false);
  const searchMode = q.trim().length >= 2;

  // 카테고리 칩은 한 번만 불러온다(피드 필터와 무관하게 고정).
  useEffect(() => {
    fetchBillCategories()
      .then((r) => setCats(r.items))
      .catch(() => setCats([]));
  }, []);

  // 모드·카테고리가 바뀌면 피드를 다시 불러오고, 처음부터 다시 그린다.
  useEffect(() => {
    setFeed(null);
    setErr(null);
    setVisible(PAGE);
    fetchBills(FEED_LIMIT, active ?? undefined, mode)
      .then((f) => {
        setFeed(f.items);
        setNotice(f.notice);
      })
      .catch((e) => setErr((e as Error).message));
  }, [active, mode]);

  // 검색어가 바뀌면 300ms 디바운스 후 전체 의안을 제목으로 검색한다.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const t = setTimeout(() => {
      searchBills(term)
        .then((f) => setResults(f.items))
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const shown = feed?.slice(0, visible) ?? [];
  const hasMore = feed !== null && visible < feed.length;

  // 바닥 센티넬이 보이면 다음 묶음을 추가로 렌더링.
  const sentinel = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!hasMore) return;
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisible((v) => v + PAGE);
        }
      },
      { rootMargin: "400px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, shown.length]);

  return (
    <main>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>
        {mode === "opinions" ? "시민 의견이 쏟아진 법안" : "표결로 갈린 법안"}
      </h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 12 }}>
        {mode === "opinions"
          ? "입법예고 때 시민이 찬반 의견을 많이 남긴 법안이에요. 표결 전(계류)이라도, 시민이 무엇에 반응했는지 의견 수로 보여드려요."
          : "국회 본회의에서 표가 팽팽했거나 정당 입장이 갈린 법안이에요. 어떤 점이 좋고 무엇이 우려되는지 보고, 내 생각과 견줘보세요."}
      </p>

      {/* 검색 — 큐레이션 피드에 안 잡히는 계류·최근 발의안까지 제목으로 찾기 */}
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="법안 제목 또는 의안번호 검색"
        style={{
          width: "100%",
          padding: 12,
          fontSize: 15,
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          background: "var(--surface)",
          color: "var(--fg)",
          marginBottom: 12,
        }}
      />

      {searchMode ? (
        <SearchResults q={q.trim()} searching={searching} results={results} />
      ) : (
        <>
      {/* 생활 카테고리 칩 — 내 관심 분야로 좁혀보기 */}
      {cats.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
          <CatChip label="전체" on={active === null} onClick={() => setActive(null)} />
          {cats.map((c) => (
            <CatChip
              key={c.category}
              label={`${c.category} ${c.count}`}
              on={active === c.category}
              onClick={() => setActive(c.category)}
            />
          ))}
        </div>
      )}

      {err && <p className="disclaimer">⚠️ 불러오지 못했어요: {err}</p>}
      {feed === null && !err && <p className="muted">불러오는 중…</p>}
      {feed !== null && feed.length === 0 && (
        <p className="muted">이 분야엔 아직 보여줄 법안이 없어요.</p>
      )}

      {shown.map((b) => (
        <BillCardItem key={b.id} b={b} />
      ))}

      {hasMore && (
        <div ref={sentinel} className="muted" style={{ textAlign: "center", padding: 16, fontSize: 13 }}>
          더 불러오는 중…
        </div>
      )}

      {notice && (
        <div className="disclaimer" style={{ marginTop: 20 }}>
          ⚖️ {notice}
        </div>
      )}
        </>
      )}
    </main>
  );
}

// 검색 결과 — 큐레이션과 별개 모드. 전체 의안을 제목으로 훑은 최근 발의순 목록.
function SearchResults({
  q,
  searching,
  results,
}: {
  q: string;
  searching: boolean;
  results: BillCard[] | null;
}) {
  return (
    <div>
      {searching && results === null && <p className="muted">검색 중…</p>}
      {results !== null && results.length === 0 && !searching && (
        <p className="muted">‘{q}’에 해당하는 법안을 찾지 못했어요.</p>
      )}
      {results !== null && results.length > 0 && (
        <p className="muted" style={{ fontSize: 13, marginBottom: 8 }}>
          ‘{q}’ 검색 결과 {results.length}건 (최근 발의순)
        </p>
      )}
      {(results ?? []).map((b) => (
        <BillCardItem key={b.id} b={b} />
      ))}
    </div>
  );
}

function CatChip({
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


function BillCardItem({ b }: { b: BillCard }) {
  const hasVote = b.yes != null || b.no != null;
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
        {/* 시민 의견 배지 — 진입 후크(있을 때 가장 먼저) */}
        {b.opinion_total != null && (
          <span
            className="chip"
            style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-800)", color: "#fff" }}
          >
            🗣 의견 {b.opinion_total.toLocaleString()}건
            {b.opinion_lean ? ` · ${b.opinion_lean} 우세` : ""}
          </span>
        )}
        {b.party_split ? (
          <span
            className="chip"
            style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-800)", color: "#fff" }}
          >
            ⚡ 정당 입장 갈림
          </span>
        ) : b.opinion_total == null ? (
          <span className="chip" style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-100)", color: "var(--muted)" }}>
            {b.contested_reason}
          </span>
        ) : null}
        {b.category && (
          <span
            className="chip"
            style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink-800)" }}
          >
            #{b.category}
          </span>
        )}
        {b.committee && (
          <span className="chip" style={{ fontSize: 11.5 }}>
            {b.committee}
          </span>
        )}
      </div>

      <div style={{ fontWeight: 700, fontSize: 15.5, lineHeight: 1.4, wordBreak: "keep-all" }}>
        {b.title}
      </div>

      {hasVote ? (
        /* 찬반 미니 바 — 표결이 있을 때만 */
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
      ) : b.opinion_total != null ? (
        <div className="muted" style={{ marginTop: 8, fontSize: 12.5 }}>
          아직 본회의 표결 전 — 입법예고에서 시민 {b.opinion_total.toLocaleString()}명이 의견을 남겼어요.
        </div>
      ) : null}

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
