"use client";

// 법안 상세 (Phase 1-3) — 그물망 '법안' 축 허브.
// 대표발의자·표결 의원 → 프로필로 연결(사람↔법안 그물망 닫힘). 🟡 공식 출처·사실만.

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import {
  fetchBill,
  fetchBillSummary,
  type BillDetail,
  type BillSummary,
  type Voter,
} from "@/lib/api";
import { PartyDot } from "../../persons/PersonBits";

const CHOICES: Voter["choice"][] = ["찬성", "반대", "기권", "불참"];

export default function BillPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [b, setB] = useState<BillDetail | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);
  // AI 요약은 상세와 분리 호출(생성 수십 초) — undefined=로딩, null=불가/실패
  const [summary, setSummary] = useState<BillSummary | null | undefined>(undefined);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    fetchBill(id)
      .then(setB)
      .catch((e) => {
        setErr((e as Error).message);
        setB(null);
      });
  }, [id]);

  // 상세가 뜬 뒤 요약을 별도로 호출(응답을 막지 않음). 상세에 이미 캐시돼 오면 그걸 사용.
  useEffect(() => {
    if (!b) return;
    if (b.summary_pros.length > 0 && b.summary_cons.length > 0) {
      setSummary({
        summary_pros: b.summary_pros,
        summary_cons: b.summary_cons,
        summary_notice: b.summary_notice,
        ready: true,
        available: true,
      });
      return;
    }
    let alive = true;
    setSummary(undefined);
    fetchBillSummary(b.id)
      .then((s) => alive && setSummary(s))
      .catch(() => alive && setSummary(null));
    return () => {
      alive = false;
    };
  }, [b]);

  const votersByChoice = useMemo(() => {
    const m: Record<string, Voter[]> = { 찬성: [], 반대: [], 기권: [], 불참: [] };
    b?.voters.forEach((v) => m[v.choice]?.push(v));
    return m;
  }, [b]);

  if (b === undefined && !err) {
    return (
      <main>
        <p className="muted">불러오는 중…</p>
      </main>
    );
  }
  if (b === null || err) {
    return (
      <main>
        <h2>찾을 수 없어요</h2>
        <p className="muted">{err ?? "해당 법안이 없습니다."}</p>
      </main>
    );
  }
  if (!b) return null;

  const v = b.vote;

  return (
    <main>
      <span className="chip" style={{ marginBottom: 4 }}>의안 {b.bill_no}</span>
      <h1 style={{ fontSize: 22, lineHeight: 1.35, margin: "6px 0 8px" }}>{b.title}</h1>
      <p className="muted" style={{ fontSize: 13.5 }}>
        {[b.committee, b.proposed_date ? `제안 ${b.proposed_date}` : null, b.status]
          .filter(Boolean)
          .join(" · ") || "처리 정보 없음"}
      </p>

      {/* 제안이유·주요내용 — 의안원문 공식 텍스트 (🟡 요약·판정 없는 원문) */}
      {(b.proposal_reason || b.main_content) && (
        <section style={{ marginTop: 16 }}>
          <h3 style={{ marginBottom: 8 }}>제안이유 및 주요내용</h3>
          {b.proposal_reason && <BodyText text={b.proposal_reason} />}
          {b.main_content && (
            <>
              <h4 style={{ fontSize: 15, margin: "14px 0 6px" }}>주요내용</h4>
              <BodyText text={b.main_content} />
            </>
          )}
          <p className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
            국회 의안정보시스템 의안원문에서 가져온 공식 텍스트입니다.
          </p>
        </section>
      )}

      {/* AI 참고 요약 — 좋은점/문제점(양쪽 대칭). 🟡 공식 원문과 분리, AI 생성 명시.
          상세와 분리 호출: 생성에 수십 초 걸려 "생성 중…" 표시 후 채운다. */}
      {summary === undefined ? (
        <section style={{ marginTop: 20 }}>
          <h3 style={{ marginBottom: 4 }}>
            AI 참고 요약 <span className="chip" style={{ fontSize: 11 }}>AI 생성</span>
          </h3>
          <p className="muted" style={{ fontSize: 13.5, marginTop: 8 }}>
            좋은점·문제점을 생성하는 중이에요… (수십 초 걸릴 수 있어요)
          </p>
        </section>
      ) : summary && summary.ready ? (
        <section style={{ marginTop: 20 }}>
          <h3 style={{ marginBottom: 4 }}>
            AI 참고 요약 <span className="chip" style={{ fontSize: 11 }}>AI 생성</span>
          </h3>
          <div style={{ display: "grid", gap: 10, marginTop: 8 }}>
            <ProsCons label="좋은점" items={summary.summary_pros} tone="pro" />
            <ProsCons label="문제점·우려" items={summary.summary_cons} tone="con" />
          </div>
          {summary.summary_notice && (
            <p className="muted" style={{ fontSize: 11.5, marginTop: 8 }}>
              ⚠️ {summary.summary_notice}
            </p>
          )}
        </section>
      ) : null}

      {/* 대표발의자 → 프로필(그물망) */}
      {b.proposer && (
        <Link
          href={`/person/${b.proposer.id}`}
          className="card"
          style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, textDecoration: "none" }}
        >
          <span className="muted" style={{ fontSize: 13 }}>대표발의</span>
          <span style={{ fontWeight: 700, color: "var(--fg)" }}>
            {b.proposer.party && <PartyDot color={b.proposer.party.color_hex} />}
            {b.proposer.name}
          </span>
          <span className="muted" style={{ fontSize: 13 }}>
            {b.proposer.party?.name ?? "무소속"} →
          </span>
        </Link>
      )}

      {/* 처리 funnel */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>처리 단계</h3>
      <div style={{ display: "flex", gap: 6 }}>
        {b.funnel.map((s, i) => (
          <div key={i} style={{ flex: 1, textAlign: "center" }}>
            <div
              style={{
                height: 6,
                borderRadius: 999,
                background: s.done ? "var(--ink-900)" : "var(--ink-200)",
              }}
            />
            <div
              className={s.done ? undefined : "muted"}
              style={{ fontSize: 12, marginTop: 6, fontWeight: s.done ? 600 : 400 }}
            >
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* 본회의 표결 */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>본회의 표결</h3>
      {!v ? (
        <p className="muted" style={{ fontSize: 14 }}>
          본회의 표결 기록이 없어요. (위원회 계류·처리 중이거나 표결 없이 처리)
        </p>
      ) : (
        <>
          <div className="card" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
            <Tally label="찬성" n={v.yes} />
            <Tally label="반대" n={v.no} />
            <Tally label="기권" n={v.blank} />
            {v.session_date && (
              <div style={{ marginLeft: "auto", alignSelf: "center" }}>
                <span className="muted" style={{ fontSize: 12 }}>{v.session_date}</span>
              </div>
            )}
          </div>

          {/* 정당별 찬반 */}
          {b.party_breakdown.length > 0 && (
            <>
              <h3 style={{ marginTop: 20, marginBottom: 8, fontSize: 16 }}>정당별 찬반</h3>
              {b.party_breakdown.map((pb) => {
                const total = pb.yes + pb.no + pb.abstain + pb.absent || 1;
                return (
                  <div key={pb.party} style={{ marginBottom: 10 }}>
                    <div style={{ fontSize: 13.5, marginBottom: 3 }}>
                      <PartyDot color={pb.color_hex} />
                      <b>{pb.party}</b>{" "}
                      <span className="muted">
                        찬 {pb.yes} · 반 {pb.no}
                        {pb.abstain ? ` · 기 ${pb.abstain}` : ""}
                        {pb.absent ? ` · 불참 ${pb.absent}` : ""}
                      </span>
                    </div>
                    <div style={{ display: "flex", height: 7, borderRadius: 999, overflow: "hidden", background: "var(--ink-100)" }}>
                      <span style={{ width: `${(pb.yes / total) * 100}%`, background: "var(--ink-800)" }} />
                      <span style={{ width: `${(pb.no / total) * 100}%`, background: "var(--ink-400)" }} />
                    </div>
                  </div>
                );
              })}
              <p className="muted" style={{ fontSize: 11.5 }}>
                ■ 진한 = 찬성 · ■ 옅은 = 반대
              </p>
            </>
          )}

          {/* 표결한 의원 → 프로필(그물망 닫힘) */}
          {b.voters.length > 0 && (
            <details className="source" style={{ marginTop: 14 }}>
              <summary>이 법안에 표결한 의원 {b.voters.length}명 보기 ▼</summary>
              {CHOICES.map((ch) =>
                votersByChoice[ch].length ? (
                  <div key={ch} style={{ marginTop: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
                      {ch} {votersByChoice[ch].length}명
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {votersByChoice[ch].map((vr) => (
                        <Link
                          key={vr.id}
                          href={`/person/${vr.id}`}
                          className="chip"
                          style={{ textDecoration: "none" }}
                        >
                          {vr.name}
                        </Link>
                      ))}
                    </div>
                  </div>
                ) : null,
              )}
            </details>
          )}
        </>
      )}

      {/* 🟡 출처 + 중립 고지 */}
      <div className="disclaimer" style={{ marginTop: 24 }}>
        ⚖️ {b.notice}
        {b.likms_url && (
          <>
            <br />
            <a href={b.likms_url} target="_blank" rel="noreferrer">
              의안정보시스템 원문 ↗
            </a>
          </>
        )}
      </div>
    </main>
  );
}

function BodyText({ text }: { text: string }) {
  return (
    <div
      className="card"
      style={{
        fontSize: 14.5,
        lineHeight: 1.7,
        whiteSpace: "pre-wrap",
        wordBreak: "keep-all",
        background: "var(--ink-50)",
      }}
    >
      {text}
    </div>
  );
}

function ProsCons({
  label,
  items,
  tone,
}: {
  label: string;
  items: string[];
  tone: "pro" | "con";
}) {
  return (
    <div
      className="card"
      style={{
        background: "var(--ink-50)",
        borderLeft: `3px solid ${tone === "pro" ? "var(--ink-800)" : "var(--ink-400)"}`,
      }}
    >
      <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 6 }}>{label}</div>
      <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.6 }}>
        {items.map((it, i) => (
          <li key={i} style={{ wordBreak: "keep-all" }}>
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Tally({ label, n }: { label: string; n: number | null }) {
  return (
    <div style={{ textAlign: "center", minWidth: 56 }}>
      <div className="numeral" style={{ fontSize: 20 }}>{n ?? "—"}</div>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
    </div>
  );
}
