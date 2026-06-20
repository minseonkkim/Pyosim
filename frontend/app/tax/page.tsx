"use client";

// 세금 계산기 (진입 장치 1단계) — 기획서 4.6 개인화 훅.
// "내 월급 → 내 소득세 → 그 돈이 어느 분야로". 사실만 보여주고 판정하지 않는다(기획서 1.3 중립성).
// Pyo Ink: 무채색만 사용. 막대는 잉크 농담으로만 구분(정당색 아님).

import { useMemo, useState } from "react";
import Link from "next/link";

import TrackOnMount from "../TrackOnMount";
import { track } from "@/lib/analytics";
import { estimateTax, distributeByBudget, won, BUDGET_META, type SmeReduction } from "@/lib/tax";
import TaxDonut from "./TaxDonut";

const numInputStyle: React.CSSProperties = {
  width: 64,
  textAlign: "center",
  fontSize: 17,
  fontWeight: 700,
  padding: "8px 6px",
  border: "1.5px solid var(--border)",
  borderRadius: "var(--radius-sm)",
  background: "var(--surface)",
  color: "var(--fg)",
  fontVariantNumeric: "tabular-nums",
};

export default function TaxPage() {
  const [input, setInput] = useState(""); // 월 세전 급여(만원)
  const [submitted, setSubmitted] = useState<number | null>(null);

  // 같은 급여라도 세금이 갈리는 '큰 변수'만 선택 입력(기본값은 1인·감면없음).
  const [dependents, setDependents] = useState(0);
  const [children, setChildren] = useState(0);
  const [sme, setSme] = useState<SmeReduction>("none");

  const monthlyWon = submitted !== null ? submitted * 10_000 : 0;
  const result = useMemo(
    () =>
      submitted !== null
        ? estimateTax(monthlyWon, { dependents, children, sme })
        : null,
    [submitted, monthlyWon, dependents, children, sme],
  );
  const fields = useMemo(
    () => (result ? distributeByBudget(result.nationalTax) : []),
    [result],
  );

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const man = Math.round(Number(input.replace(/[^0-9]/g, "")));
    if (!man || man <= 0) return;
    setSubmitted(man);
    track("tax_calc", { monthly_man: man, dependents, children, sme });
  }

  return (
    <main>
      <TrackOnMount event="tax_view" />

      <span className="chip" style={{ marginTop: 8 }}>
        내 세금이 어디로 가나
      </span>

      <h1 style={{ fontSize: 28, lineHeight: 1.3, margin: "14px 0 0" }}>
        내가 낸 소득세,
        <br />
        어디에 쓰였을까?
      </h1>
      <p style={{ fontSize: 16, lineHeight: 1.6, color: "var(--ink-700)" }}>
        월급만 넣으면 한 해 내는 세금(소득세 + 물건 살 때 내는 부가세까지)과, 그
        돈이 정부 예산 비율대로 어느 분야에 나뉘는지 보여드려요.
      </p>

      <form onSubmit={onSubmit} style={{ marginTop: 20 }}>
        <label htmlFor="salary" style={{ fontSize: 14, fontWeight: 600 }}>
          월 세전 급여
        </label>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginTop: 8,
            border: "1.5px solid var(--border)",
            borderRadius: "var(--radius-md)",
            background: "var(--surface)",
            padding: "0 16px",
          }}
        >
          <input
            id="salary"
            inputMode="numeric"
            placeholder="예: 300"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontSize: 22,
              fontWeight: 800,
              padding: "14px 0",
              color: "var(--fg)",
              fontVariantNumeric: "tabular-nums",
            }}
          />
          <span style={{ fontSize: 16, fontWeight: 700, color: "var(--muted)" }}>
            만원
          </span>
        </div>

        {/* 선택 입력 — 세금이 가장 크게 갈리는 변수만. 안 건드려도 계산됨(1인 기준). */}
        <details className="source" style={{ marginTop: 14 }}>
          <summary style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>
            내 상황 반영하기 (선택) — 더 정확해져요
          </summary>
          <div style={{ marginTop: 14, display: "grid", gap: 16 }}>
            <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <span style={{ fontSize: 14.5 }}>
                부양가족 수 <span className="muted">(배우자·부모·자녀 등, 본인 제외)</span>
              </span>
              <input
                type="number"
                min={0}
                max={15}
                value={dependents}
                onChange={(e) => setDependents(Math.max(0, Number(e.target.value) || 0))}
                style={numInputStyle}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
              <span style={{ fontSize: 14.5 }}>
                그중 자녀 수 <span className="muted">(8~20세)</span>
              </span>
              <input
                type="number"
                min={0}
                max={15}
                value={children}
                onChange={(e) => setChildren(Math.max(0, Number(e.target.value) || 0))}
                style={numInputStyle}
              />
            </label>
            <div>
              <div style={{ fontSize: 14.5, marginBottom: 8 }}>
                중소기업 취업자 소득세 감면
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {([
                  ["none", "해당 없음"],
                  ["youth", "청년(90%)"],
                  ["general", "그 외(70%)"],
                ] as [SmeReduction, string][]).map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setSme(val)}
                    className="chip"
                    style={{
                      flex: 1,
                      padding: "10px 8px",
                      cursor: "pointer",
                      border: "1.5px solid",
                      borderColor: sme === val ? "var(--ink-900)" : "var(--border)",
                      background: sme === val ? "var(--ink-100)" : "var(--surface)",
                      fontWeight: sme === val ? 700 : 600,
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <p style={{ margin: "8px 0 0", fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>
                중소기업 취업 청년(취업일 기준 15~34세)은 5년간 90%, 그 외 대상은 3년간 70% 감면(연 200만원 한도).
              </p>
            </div>
          </div>
        </details>

        <button
          className="btn btn-block"
          type="submit"
          style={{ marginTop: 16 }}
          disabled={!input.trim()}
        >
          내 세금 쓰임 보기 →
        </button>
      </form>

      {result && (
        <>
          {/* 한 줄 요약 — 첫 후크: 세금 '총액' */}
          <div className="card card-emphasis" style={{ marginTop: 24 }}>
            <p style={{ margin: 0, fontSize: 16, lineHeight: 1.7 }}>
              세전 월 <b>{submitted!.toLocaleString("ko-KR")}만원</b>이면, 한 해 내는
              세금은 약 <b className="numeral">{won(result.totalTax)}</b>으로
              추정돼요.
            </p>
            {/* 세금 레이어 분해 */}
            <div style={{ marginTop: 12, display: "grid", gap: 6, fontSize: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>월급에서 직접 — 소득세+지방소득세</span>
                <b className="numeral">{won(result.incomeTaxTotal)}</b>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>쓰면서 — 부가가치세(소비 추정)</span>
                <b className="numeral">{won(result.vat)}</b>
              </div>
            </div>
            <p style={{ margin: "12px 0 0", fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
              월 실수령 약 <b>{won(result.netMonthly)}</b> · 4대보험 약{" "}
              <b>{won(result.socialInsTotal)}</b>/년은 세금과 별개(아래 설명)
            </p>
          </div>

          {/* 분야별 배분 — 무채색 막대. 배분 대상은 국세(소득세+부가세). */}
          <h3 style={{ marginTop: 24, marginBottom: 2 }}>
            내 국세 {won(result.nationalTax)}의 분야별 쓰임
          </h3>
          <p style={{ margin: "0 0 4px", fontSize: 13, color: "var(--muted)" }}>
            {BUDGET_META.year}년 <b>{BUDGET_META.basis}</b>(실제 집행) 16대 분야
            비율로 (지방세는 지자체 예산이라 제외)
          </p>
          <div style={{ marginTop: 12 }}>
            <TaxDonut fields={fields} total={result.nationalTax} />
          </div>

          {/* 4대보험 분리 안내 — 정확성·중립성(기획서 1.3) */}
          <div className="card" style={{ marginTop: 8 }}>
            <h3 style={{ fontSize: 15, margin: "0 0 6px" }}>
              4대보험은 왜 위에 안 들어가나요?
            </h3>
            <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-700)" }}>
              국민연금·건강보험·장기요양·고용보험(약{" "}
              <b>{won(result.socialInsTotal)}</b>/년)은 국가 일반예산이 아니라
              각각의 <b>사회보험 기금</b>으로 들어가 정해진 용도(연금 지급, 의료비
              보장 등)에만 쓰여요. 그래서 위 분야 배분과 분리했습니다.
            </p>
          </div>

          {/* 그물망 입구 — 성향 테스트로 연결(기획서 5.1 유입 장치) */}
          <div className="card card-emphasis" style={{ marginTop: 8 }}>
            <p style={{ margin: "0 0 12px", fontSize: 15, lineHeight: 1.6 }}>
              그럼 <b>당신이 중요하다고 보는 분야</b>와 실제 예산은 얼마나 맞을까요?
            </p>
            <Link
              href="/test"
              className="btn btn-block"
              onClick={() => track("tax_to_test")}
            >
              3분 성향 테스트로 확인하기 →
            </Link>
          </div>

          {/* 🟡 필수 고지 — 추정치·알고리즘 공개(기획서 1.3) */}
          <div className="disclaimer">
            ⚖️ 모두 <b>추정치</b>입니다.
            <br />· <b>소득세</b>는 영향이 큰 항목(부양가족·자녀·중소기업 감면)만
            반영하고 연금저축·의료비·신용카드·월세 등 개인별 공제는 넣지 않았어요(정확한
            세금은 연말정산에서 정해집니다).
            <br />· <b>부가세</b>는 가처분소득에 평균 소비성향·과세비중을 가정해 추정한
            값이라 실제 소비에 따라 달라집니다.
            <br />· <b>분야 배분</b>은 내 국세 원 단위를 추적한 게 아니라,
            {BUDGET_META.year}년 정부가 실제 집행한({BUDGET_META.basis}) 분야별 비율을
            내 국세에 투영한 값입니다.
            <details className="source" style={{ marginTop: 10 }}>
              <summary>계산·데이터 출처</summary>
              <div style={{ marginTop: 6, lineHeight: 1.7 }}>
                · 분야별 비율 —{" "}
                <a href={BUDGET_META.sourceUrl} target="_blank" rel="noopener noreferrer">
                  열린재정 OpenAPI
                </a>{" "}
                {BUDGET_META.source} · {BUDGET_META.year} {BUDGET_META.basis} (총{" "}
                {BUDGET_META.totalTrillion}조)
                <br />· 세율·공제 — 국세청 종합소득세율·근로소득공제·4대보험 요율, 부가가치세 10%
              </div>
            </details>
          </div>

          <button
            className="btn btn-ghost btn-block"
            onClick={() => {
              setSubmitted(null);
              setInput("");
            }}
          >
            다시 계산하기
          </button>
        </>
      )}

      {!result && (
        <ul
          style={{
            marginTop: 28,
            paddingLeft: 18,
            fontSize: 14.5,
            lineHeight: 1.9,
            color: "var(--muted)",
          }}
        >
          <li>월급만 입력 — 다른 정보는 받지 않아요</li>
          <li>분야 비율 출처: 열린재정 2024 본예산 (▼로 확인)</li>
          <li>특정 분야가 많다/적다고 판정하지 않습니다 — 사실만</li>
        </ul>
      )}
    </main>
  );
}
