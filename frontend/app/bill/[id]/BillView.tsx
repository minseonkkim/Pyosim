"use client";

// 법안 상세 본문 (클라이언트 뷰) — 본문 데이터는 서버(page.tsx)에서 SSR 로 받아 prop 으로 받는다.
// AI 참고 요약만 별도 호출(생성에 수십 초)로 여기서 늦게 채운다. 색인·메타데이터는 서버 담당.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  fetchBillSummary,
  type BillDetail,
  type BillSummary,
  type CivicOpinion,
  type PartyVote,
  type Voter,
} from "@/lib/api";
import { PartyDot } from "../../persons/PersonBits";
import WatchButton from "@/app/WatchButton";

const CHOICES: Voter["choice"][] = ["찬성", "반대", "기권", "불참"];

export default function BillView({ initial }: { initial: BillDetail }) {
  const b = initial;
  // AI 요약은 상세와 분리 호출(생성 수십 초) — undefined=로딩, null=불가/실패
  const [summary, setSummary] = useState<BillSummary | null | undefined>(undefined);

  // 상세에 이미 캐시돼 오면 그걸 쓰고, 없으면 별도로 호출(응답을 막지 않음).
  useEffect(() => {
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
    b.voters.forEach((v) => m[v.choice]?.push(v));
    return m;
  }, [b]);

  const v = b.vote;

  return (
    <main>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 4 }}>
        <span className="chip">의안 {b.bill_no}</span>
        <WatchButton kind="bill" refId={b.id} />
      </div>
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

      {/* 의원 외 제안자(정부·위원장·전직의원) — 프로필 링크 없음, 사실 표기만.
          🟡 정부안 소관부처(○○부)는 공식 API 에 없어 "정부"까지만 표시한다. */}
      {!b.proposer && b.proposer_text && (
        <div
          className="card"
          style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12 }}
        >
          <span className="muted" style={{ fontSize: 13 }}>
            {b.proposer_kind === "정부" ? "제출" : "대표발의"}
          </span>
          <span style={{ fontWeight: 700 }}>{b.proposer_text}</span>
        </div>
      )}

      {/* 처리 단계 — 날짜 타임라인. 🟡 공식 의결일 그대로. 미도달 단계는 '—'로 멈춘 지점을 드러냄 */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>처리 단계</h3>
      <Timeline steps={b.funnel} />
      {b.funnel.some((s) => s.done) && (
        <p className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
          국회 본회의 처리안건 기준 단계별 의결일입니다. ‘—’ 단계는 아직 거치지 않았어요.
        </p>
      )}

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

          {/* 정당별 찬반 — 정당명↔찬반수 양끝 정렬 + 찬:반 비율 막대. 당론 갈린 정당은 칩 표시.
              🟡 막대는 찬·반만으로 비율(기권·불참은 숫자로만), 색은 정당 도트뿐 — 중립 회색 유지 */}
          {b.party_breakdown.length > 0 && (
            <>
              <h3 style={{ marginTop: 20, marginBottom: 10, fontSize: 16 }}>정당별 찬반</h3>
              <div style={{ display: "grid", gap: 12 }}>
                {b.party_breakdown.map((pb) => (
                  <PartyBar key={pb.party} pb={pb} />
                ))}
              </div>
              <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
                진한 칸 = 찬성 · 옅은 칸 = 반대 · 기권·불참은 막대에서 제외했어요.
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

      {/* 입법예고 기간 시민 찬반 의견 — 민심 vs 국회(표결/처리)를 한 페이지에서 (기능 B-4.4) */}
      {b.civic_opinion && <CivicOpinionSection c={b.civic_opinion} />}

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

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return d.slice(0, 10).replace(/-/g, ".");
}

// 처리 단계 세로 타임라인 — 점·세로축·라벨/날짜. 거친 단계는 진하게, 미도달은 옅게.
function Timeline({ steps }: { steps: { label: string; done: boolean; date: string | null }[] }) {
  return (
    <div style={{ position: "relative" }}>
      <div
        style={{ position: "absolute", left: 5, top: 8, bottom: 8, width: 2, background: "var(--ink-200)" }}
      />
      {steps.map((s, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "baseline", marginBottom: 12 }}>
          <span
            style={{
              position: "relative",
              zIndex: 1,
              flexShrink: 0,
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: s.done ? "var(--ink-900)" : "var(--bg)",
              border: `2px solid ${s.done ? "var(--ink-900)" : "var(--ink-300)"}`,
              alignSelf: "center",
            }}
          />
          <span
            className={s.done ? undefined : "muted"}
            style={{ fontSize: 14, fontWeight: s.done ? 600 : 400, minWidth: 92 }}
          >
            {s.label}
          </span>
          <span className="muted numeral" style={{ fontSize: 13 }}>{fmtDate(s.date)}</span>
        </div>
      ))}
    </div>
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

// 정당 한 곳의 찬반 행 — 헤더(정당명 ↔ 찬반수 양끝 정렬) + 찬:반 비율 막대.
// 막대는 찬·반만으로 100% 채워 비율을 또렷하게(기권·불참 제외). 소수 쪽이 의미 있으면 '당론 갈림'.
function PartyBar({ pb }: { pb: PartyVote }) {
  const decided = pb.yes + pb.no;
  const yesPct = decided ? (pb.yes / decided) * 100 : 0;
  const minor = Math.min(pb.yes, pb.no);
  const split = decided >= 4 && minor >= 2 && minor / decided >= 0.15;
  return (
    <div>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          gap: 8,
          fontSize: 13.5,
          marginBottom: 4,
        }}
      >
        <span>
          <PartyDot color={pb.color_hex} />
          <b>{pb.party}</b>
          {split && (
            <span className="chip" style={{ marginLeft: 6, fontSize: 11 }}>
              당론 갈림
            </span>
          )}
        </span>
        <span className="muted numeral" style={{ fontSize: 13, whiteSpace: "nowrap" }}>
          찬 {pb.yes} · 반 {pb.no}
          {pb.abstain ? ` · 기 ${pb.abstain}` : ""}
          {pb.absent ? ` · 불참 ${pb.absent}` : ""}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          height: 14,
          borderRadius: 999,
          overflow: "hidden",
          background: "var(--ink-100)",
        }}
      >
        <span style={{ width: `${yesPct}%`, background: "var(--ink-800)" }} />
        <span style={{ width: `${100 - yesPct}%`, background: "var(--ink-400)" }} />
      </div>
    </div>
  );
}

// 입법예고 기간 시민 찬반 의견 — 🟡 의견 수는 공개 집계 그대로, 본문은 담지 않음.
// 색은 정당별 찬반과 같은 잉크 농도(진=찬성·옅=반대)로 통일 — 중립(특정 정치색 배제).
function CivicOpinionSection({ c }: { c: CivicOpinion }) {
  const hasSplit = c.agree != null && c.oppose != null;
  const etc = c.etc ?? (hasSplit ? Math.max(c.total - c.agree! - c.oppose!, 0) : 0);
  const pct = (v: number) => `${c.total ? ((v / c.total) * 100).toFixed(0) : 0}%`;
  const lean = hasSplit
    ? c.oppose! > c.agree! ? "반대" : c.agree! > c.oppose! ? "찬성" : null
    : null;
  return (
    <section style={{ marginTop: 24 }}>
      <h3 style={{ marginBottom: 8 }}>
        시민 의견 <span className="chip" style={{ fontSize: 11 }}>입법예고</span>
      </h3>
      <div className="card" style={{ background: "var(--ink-50)" }}>
        <div style={{ fontSize: 13.5, marginBottom: 10, wordBreak: "keep-all" }}>
          입법예고 기간에 시민 <b>{c.total.toLocaleString()}명</b>이 의견을 남겼어요
          {lean ? <> — <b>{lean} 의견이 더 많았어요.</b></> : "."}
        </div>
        {hasSplit ? (
          <>
            <div
              style={{ display: "flex", height: 14, borderRadius: 999, overflow: "hidden", background: "var(--ink-100)" }}
            >
              <span style={{ width: pct(c.agree!), background: "var(--ink-800)" }} />
              <span style={{ width: pct(c.oppose!), background: "var(--ink-400)" }} />
              <span style={{ width: pct(etc), background: "var(--ink-200)" }} />
            </div>
            <div style={{ display: "flex", gap: 14, marginTop: 8, fontSize: 12.5, flexWrap: "wrap" }}>
              <Legend color="var(--ink-800)" label="찬성" v={c.agree!} />
              <Legend color="var(--ink-400)" label="반대" v={c.oppose!} />
              <Legend color="var(--ink-200)" label="기타" v={etc} />
            </div>
          </>
        ) : (
          <div className="muted" style={{ fontSize: 12.5 }}>
            찬반 분해는 준비 중이에요 (의견이 많아 집계에 시간이 걸려요).
          </div>
        )}
      </div>
      <p className="muted" style={{ fontSize: 11.5, marginTop: 6, wordBreak: "keep-all" }}>ℹ️ {c.method_note}</p>
      {c.pal_url && (
        <a
          href={c.pal_url}
          target="_blank"
          rel="noreferrer"
          className="muted"
          style={{ fontSize: 12, display: "inline-block", marginTop: 2 }}
        >
          국민참여입법시스템에서 의견 보기 ↗
        </a>
      )}
    </section>
  );
}

function Legend({ color, label, v }: { color: string; label: string; v: number }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
      <span style={{ fontWeight: 600 }}>{label}</span>
      <span className="muted numeral">{v.toLocaleString()}</span>
    </span>
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
