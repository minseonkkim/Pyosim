"use client";

// 결과 화면 (Phase 1-4) — 개인 요약 + 정당별 일치율 + 문항별 비교 + 🟡 필수 고지문.
// 중립 원칙: 자극적 라벨 금지(중립 서술), "지지/반대" 권유 없음, 출처·집계 기준 표기.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import type { PersonMatch, ResultsResponse } from "@/lib/api";
import { popResult } from "@/lib/session";
import { summarize, shareUrl } from "@/lib/share";
import { track } from "@/lib/analytics";
import Loading from "@/app/Loading";
import PartyChart from "./PartyChart";
import { Avatar, PartyDot } from "../persons/PersonBits";

export default function ResultPage() {
  const [result, setResult] = useState<ResultsResponse | null | undefined>(
    undefined,
  );
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const r = popResult();
    setResult(r);
    if (r) track("result_view", { answered: r.answered, skipped: r.skipped });
  }, []);

  const summary = useMemo(
    () => (result ? summarize(result) : null),
    [result],
  );

  if (result === undefined) {
    return <Loading text="결과를 불러오는 중…" />;
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
        track("share_click", { method: "native" });
        return;
      } catch {
        /* 사용자가 취소 — 복사로 폴백 */
      }
    }
    await navigator.clipboard.writeText(url);
    track("share_click", { method: "copy" });
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

      {/* 나와 닮은 의원 — 실제 본회의 표결기록이 있을 때만 (없으면 백엔드가 빈 배열) */}
      {(result.person_match?.length ?? 0) > 0 && (
        <>
          <h3 style={{ marginTop: 24, marginBottom: 8 }}>나와 닮은 의원</h3>
          {result.person_match.map((p) => (
            <PersonRow key={p.id} p={p} />
          ))}
        </>
      )}

      {/* 나와 가장 다른 의원 — 일치율이 가장 낮은 의원(같은 양식, 판정 아님) */}
      {(result.person_mismatch?.length ?? 0) > 0 && (
        <>
          <h3 style={{ marginTop: 24, marginBottom: 8 }}>나와 가장 다른 의원</h3>
          {result.person_mismatch.map((p) => (
            <PersonRow key={p.id} p={p} />
          ))}
        </>
      )}

      {/* 🟡 필수 고지문 */}
      <div className="disclaimer">
        ⚖️ {result.disclaimer}
        <br />
        <span style={{ fontSize: 12 }}>※ {result.method_note}</span>
        {result.person_method_note && (
          <>
            <br />
            <span style={{ fontSize: 12 }}>※ {result.person_method_note}</span>
          </>
        )}
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
          {q.bill_id && (
            <Link
              href={`/bill/${q.bill_id}`}
              className="chip"
              style={{ display: "inline-block", marginTop: 10, textDecoration: "none" }}
              onClick={() => track("source_open", { question_id: q.question_id })}
            >
              이 법안 자세히 보기 (본문·표결·출처) →
            </Link>
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

// 의원 한 줄 카드 — 닮은/가장 다른 의원 공용. 모두 같은 양식(중립).
function PersonRow({ p }: { p: PersonMatch }) {
  return (
    <Link
      href={`/person/${p.id}`}
      className="card"
      style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}
      onClick={() => track("source_open", { person_id: p.id })}
    >
      <Avatar name={p.name} photo={p.photo_url} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 700, color: "var(--fg)" }}>{p.name}</div>
        <div className="muted" style={{ fontSize: 13 }}>
          <PartyDot color={p.color_hex} />
          {p.party ?? "무소속"}
          {p.district ? ` · ${p.district}` : ""}
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div className="numeral" style={{ fontSize: 18, fontWeight: 700 }}>
          {Math.round(p.match_rate * 100)}%
        </div>
        <div className="muted" style={{ fontSize: 11 }}>
          {p.matched}/{p.total}문항
        </div>
      </div>
    </Link>
  );
}
