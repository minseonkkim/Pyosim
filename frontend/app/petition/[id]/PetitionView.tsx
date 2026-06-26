"use client";

// 청원 상세 본문 (클라이언트 뷰) — 데이터는 서버(page.tsx)에서 SSR 로 받아 prop 으로 받는다.
// 색인·메타데이터·구조화 데이터는 서버가 처리하고, 여기선 감시 토글 등 인터랙션만 담당.

import Link from "next/link";

import { type PetitionDetail } from "@/lib/api";
import WatchButton from "@/app/WatchButton";

export default function PetitionView({ initial }: { initial: PetitionDetail }) {
  const p = initial;
  const id = p.id;
  const pending = p.status === "계류";

  return (
    <main>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <Link href="/petitions" className="muted" style={{ fontSize: 13, textDecoration: "none" }}>
          ← 청원 목록
        </Link>
        <WatchButton kind="petition" refId={id} />
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "12px 0 8px" }}>
        {p.is_national_consent && (
          <span className="chip" style={{ fontSize: 11.5, fontWeight: 700, background: "var(--ink-800)", color: "#fff" }}>
            🙋 국민동의청원
          </span>
        )}
        {p.signature_count != null && (
          <span className="chip" style={{ fontSize: 11.5, fontWeight: 600, color: "var(--ink-800)" }}>
            {p.signature_count.toLocaleString()}명 동의
          </span>
        )}
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
      </div>

      <h1 style={{ fontSize: 21, lineHeight: 1.4, wordBreak: "keep-all", margin: "0 0 6px" }}>
        {p.title}
      </h1>

      {/* '지금 어디' 한 줄 요약 */}
      <p className="muted" style={{ fontSize: 14, marginBottom: 18, wordBreak: "keep-all" }}>
        {pending
          ? p.committee
            ? `현재 ${p.committee}에 회부되어 ${
                p.days_pending != null ? `접수 ${p.days_pending}일째 ` : ""
              }심사 단계에 있어요.`
            : "접수되어 소관위 회부를 기다리고 있어요."
          : `최종 처리결과: ${p.proc_result ?? "—"}`}
      </p>

      {/* 청원 내용 — 국민동의청원 공식 원문(취지 + 전문). 🟡 요약·판정 없음 */}
      {(p.objective || p.content) && (
        <section style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 15, margin: "0 0 10px" }}>청원 내용</h2>
          {p.objective && (
            <div
              className="card"
              style={{ background: "var(--ink-50)", borderLeft: "3px solid var(--ink-400)", marginBottom: 8 }}
            >
              <span className="muted" style={{ fontSize: 11.5, fontWeight: 700 }}>청원의 취지</span>
              <div style={{ fontSize: 14.5, lineHeight: 1.6, marginTop: 4, wordBreak: "keep-all" }}>
                {p.objective}
              </div>
            </div>
          )}
          {p.content && (
            <div
              className="card"
              style={{
                fontSize: 14,
                lineHeight: 1.75,
                whiteSpace: "pre-wrap",
                wordBreak: "keep-all",
                background: "var(--surface)",
              }}
            >
              {p.content}
            </div>
          )}
          <p className="muted" style={{ fontSize: 11.5, marginTop: 6 }}>
            국민동의청원 공식 게시 원문이에요.
          </p>
        </section>
      )}

      {/* 처리 단계 타임라인 */}
      <h2 style={{ fontSize: 15, margin: "0 0 12px" }}>처리 단계</h2>
      <Timeline steps={p.stages} />

      {/* 왜 멈춰 있나 — 계류 청원의 멈춘 지점(사실) + 구조적 이유(🟡 분노가 아닌 이해) */}
      {p.stall_note && (
        <div
          className="card"
          style={{ marginTop: 16, background: "var(--ink-50)", borderLeft: "3px solid var(--ink-400)" }}
        >
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 6 }}>
            ⏳ 왜 멈춰 있나
          </div>
          {p.stall_line && (
            <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, wordBreak: "keep-all" }}>
              {p.stall_line}
            </div>
          )}
          <div className="muted" style={{ fontSize: 13, lineHeight: 1.65, wordBreak: "keep-all" }}>
            {p.stall_note}
          </div>
        </div>
      )}

      {/* 이렇게 끝났어요 — 처리완료 청원의 결과 + 용어 쉬운 풀이(🟡 사실 설명) */}
      {p.proc_result && (
        <div
          className="card"
          style={{ marginTop: 16, background: "var(--ink-50)", borderLeft: "3px solid var(--ink-400)" }}
        >
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 6 }}>
            🏁 이렇게 끝났어요
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, wordBreak: "keep-all" }}>
            처리결과: {p.proc_result}
          </div>
          {p.proc_result_note && (
            <div className="muted" style={{ fontSize: 13, lineHeight: 1.65, wordBreak: "keep-all" }}>
              {p.proc_result_note}
            </div>
          )}
        </div>
      )}

      {/* 메타 */}
      <div className="card" style={{ marginTop: 18, fontSize: 13.5, lineHeight: 1.9, background: "var(--ink-50)" }}>
        <Row label="의안번호" value={p.bill_no} mono />
        <Row label="소개" value={p.introducer} />
        <Row label="소관 위원회" value={p.committee} />
        <Row label="접수일" value={fmtDate(p.proposed_date)} mono />
        <Row label="회부일" value={fmtDate(p.committee_date)} mono />
      </div>

      {p.likms_url && (
        <a
          href={p.likms_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-block"
          style={{ marginTop: 14, background: "var(--surface)", border: "1px solid var(--border)", color: "var(--fg)" }}
        >
          국회 의안정보시스템에서 원문 보기 →
        </a>
      )}

      <div className="disclaimer" style={{ marginTop: 18 }}>
        ⚖️ {p.notice}
      </div>
    </main>
  );
}

// 처리 단계 세로 타임라인 — 법안 상세와 동일 양식. 거친 단계 진하게·미도달 옅게.
function Timeline({ steps }: { steps: { label: string; done: boolean; date: string | null }[] }) {
  return (
    <div style={{ position: "relative" }}>
      <div style={{ position: "absolute", left: 5, top: 8, bottom: 8, width: 2, background: "var(--ink-200)" }} />
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
          <span className={s.done ? undefined : "muted"} style={{ fontSize: 14, fontWeight: s.done ? 600 : 400, minWidth: 132 }}>
            {s.label}
          </span>
          <span className="muted numeral" style={{ fontSize: 13 }}>{fmtDate(s.date)}</span>
        </div>
      ))}
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      <span className="muted" style={{ minWidth: 84, flexShrink: 0 }}>{label}</span>
      <span className={mono ? "numeral" : undefined} style={{ wordBreak: "keep-all" }}>
        {value || "—"}
      </span>
    </div>
  );
}

function fmtDate(d: string | null): string {
  if (!d) return "—";
  return d.slice(0, 10).replace(/-/g, ".");
}
