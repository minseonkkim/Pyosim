"use client";

// 청원 상세 (Phase 2 기능 A) — 처리 단계 타임라인 + 출처.
// 🟡 공식 기록·사실만. 처리결과는 공식 표기 그대로, 미도달 단계는 '—'로 멈춘 지점을 드러냄.

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { fetchPetition, type PetitionDetail } from "@/lib/api";

export default function PetitionPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [p, setP] = useState<PetitionDetail | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    fetchPetition(id)
      .then(setP)
      .catch((e) => {
        setErr((e as Error).message);
        setP(null);
      });
  }, [id]);

  if (err) return <main><p className="disclaimer">⚠️ {err}</p></main>;
  if (p === undefined) return <main><p className="muted">불러오는 중…</p></main>;
  if (p === null) return <main><p className="muted">청원을 찾을 수 없어요.</p></main>;

  const pending = p.status === "계류";
  return (
    <main>
      <Link href="/petitions" className="muted" style={{ fontSize: 13, textDecoration: "none" }}>
        ← 청원 목록
      </Link>

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

// 처리 단계 세로 타임라인 — 법안 상세(Phase 1-3)와 동일 양식. 거친 단계 진하게·미도달 옅게.
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
