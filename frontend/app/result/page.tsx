"use client";

// 결과 화면 (Phase 1-4) — 개인 요약 + 정당별 일치율 + 문항별 비교 + 🟡 필수 고지문.
// 중립 원칙: 자극적 라벨 금지(중립 서술), "지지/반대" 권유 없음, 출처·집계 기준 표기.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import type { ResultsResponse } from "@/lib/api";
import { popResult } from "@/lib/session";
import { summarize, shareUrl } from "@/lib/share";
import PartyChart from "./PartyChart";

export default function ResultPage() {
  const [result, setResult] = useState<ResultsResponse | null | undefined>(
    undefined,
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setResult(popResult());
  }, []);

  const summary = useMemo(
    () => (result ? summarize(result) : null),
    [result],
  );

  if (result === undefined) {
    return (
      <main>
        <p className="muted">결과를 불러오는 중…</p>
      </main>
    );
  }

  if (result === null) {
    return (
      <main>
        <h2>결과가 없어요</h2>
        <p className="muted">먼저 테스트를 진행해 주세요.</p>
        <Link href="/test" className="btn">
          테스트 하러 가기 →
        </Link>
      </main>
    );
  }

  async function onShare() {
    if (!summary) return;
    const url = shareUrl(summary, window.location.origin);
    const text = `나와 가장 많이 겹친 건 ${summary.party} (${summary.rate}%) — 표심에서 확인해보세요`;
    if (navigator.share) {
      try {
        await navigator.share({ title: "표심 · Pyosim", text, url });
        return;
      } catch {
        /* 사용자가 취소 — 복사로 폴백 */
      }
    }
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const top = result.party_match[0];

  return (
    <main>
      <h1 style={{ fontSize: 24, marginBottom: 12 }}>내 표심 결과</h1>

      {/* 개인 요약 — 중립 서술 (정당색은 라벨과 함께 작은 점으로만) */}
      {top && (
        <div className="card card-emphasis">
          <p style={{ margin: 0, fontSize: 17, lineHeight: 1.65 }}>
            답한 <b>{result.answered}문항</b> 기준, 실제 표결이 내 생각과 가장
            많이 겹친 곳은{" "}
            <span
              aria-hidden
              style={{
                display: "inline-block",
                width: 9,
                height: 9,
                borderRadius: 3,
                background: top.color_hex ?? "var(--ink-400)",
                marginRight: 4,
                verticalAlign: "baseline",
              }}
            />
            <b>{top.party}</b>{" "}
            <b className="numeral">{Math.round(top.match_rate * 100)}%</b>
            이에요.
            {result.skipped > 0 && (
              <span className="muted"> · &lsquo;모름&rsquo; {result.skipped}문항 제외</span>
            )}
          </p>
        </div>
      )}

      {/* 정당별 일치율 */}
      <h3 style={{ marginBottom: 4 }}>정당별 표결 일치율</h3>
      <PartyChart data={result.party_match} />

      {/* 🟡 필수 고지문 */}
      <div className="disclaimer">
        ⚖️ {result.disclaimer}
        <br />
        <span style={{ fontSize: 12 }}>※ {result.method_note}</span>
      </div>

      {/* 공유 */}
      <button className="btn btn-block" onClick={onShare}>
        {copied ? "링크 복사됨 ✓" : "결과 공유하기"}
      </button>

      {/* 법안별 내 입장 vs 실제 표결 */}
      <h3 style={{ marginTop: 28 }}>문항별 — 내 답 vs 실제 표결</h3>
      {result.per_question.map((q) => (
        <div className="card" key={q.question_id}>
          <span className="chip">{q.issue}</span>
          <div style={{ fontWeight: 600, margin: "10px 0 8px" }}>{q.body}</div>
          <div style={{ fontSize: 14 }}>
            내 선택:{" "}
            <b>
              {q.your_choice === "모름"
                ? "잘 모르겠어요"
                : (q.your_label ?? q.your_choice)}
            </b>
          </div>
          {q.your_choice !== "모름" && (
            <div style={{ fontSize: 13.5, marginTop: 6, lineHeight: 1.6 }}>
              <span className="muted">같은 방향 표결:</span>{" "}
              {q.agree_parties.length ? q.agree_parties.join(", ") : "—"}
              <br />
              <span className="muted">다른 방향 표결:</span>{" "}
              {q.disagree_parties.length ? q.disagree_parties.join(", ") : "—"}
            </div>
          )}
          {q.source_note && (
            <details className="source">
              <summary>출처 ▼</summary>
              <p style={{ marginBottom: 4 }}>{q.source_note}</p>
              {q.likms_url && (
                <a href={q.likms_url} target="_blank" rel="noreferrer">
                  의안정보시스템에서 보기 ↗
                </a>
              )}
            </details>
          )}
        </div>
      ))}

      <div style={{ display: "flex", gap: 10, marginTop: 20 }}>
        <Link href="/test" className="btn btn-ghost">
          다시 하기
        </Link>
        <Link href="/" className="btn btn-ghost">
          처음으로
        </Link>
      </div>
    </main>
  );
}
