"use client";

// 세금 분야별 쓰임 — 도넛(가운데 총액) + 상위 7분야+기타 + 색 스와치 전체 목록.
// 16개를 통짜 원그래프로 하면 작은 조각이 안 보여서, 상위만 도넛에 쓰고 나머지는 '기타'로 묶는다.
// Pyo Ink: 무채색만(잉크 농담). 디자인 토큰 hex 를 직접 사용(Recharts 는 CSS var 불가).

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import type { FieldShare } from "@/lib/tax";
import { won } from "@/lib/tax";

// globals.css 의 --ink-900..-300 (상위 7분야)
const INK = ["#18171d", "#2a2932", "#3d3b45", "#56535f", "#6e6b77", "#9794a0", "#c7c5ce"];
const ETC = "#e4e2e9"; // --ink-200 (기타)
const TOP_N = 7;

export default function TaxDonut({
  fields,
  total,
}: {
  fields: FieldShare[]; // 금액 내림차순 정렬 가정
  total: number; // 가운데 표시할 합계(원)
}) {
  const top = fields.slice(0, TOP_N);
  const rest = fields.slice(TOP_N);
  const restAmt = rest.reduce((s, f) => s + f.amount, 0);

  const slices = [
    ...top.map((f, i) => ({ name: f.name, value: f.amount, color: INK[i] })),
    ...(rest.length ? [{ name: "기타", value: restAmt, color: ETC }] : []),
  ];

  // 색 매핑: 상위는 잉크 농담, 나머지는 기타색
  const colorFor = (i: number) => (i < TOP_N ? INK[i] : ETC);

  return (
    <div>
      <div style={{ position: "relative", width: "100%", height: 240 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius="62%"
              outerRadius="92%"
              startAngle={90}
              endAngle={-270}
              stroke="var(--surface)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.name} fill={s.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* 가운데 총액 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <span style={{ fontSize: 12, color: "var(--muted)" }}>내 국세</span>
          <span className="numeral" style={{ fontSize: 22 }}>
            {won(total)}
          </span>
        </div>
      </div>

      {/* 전체 목록 — 스와치 색이 도넛과 매칭(상위 7), 나머지는 기타색 */}
      <ul style={{ listStyle: "none", margin: "12px 0 0", padding: 0 }}>
        {fields.map((f, i) => (
          <li
            key={f.code || f.name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 0",
              borderTop: i === 0 ? "none" : "1px solid var(--border)",
            }}
          >
            <span
              aria-hidden
              style={{
                flex: "0 0 auto",
                width: 10,
                height: 10,
                borderRadius: 3,
                background: colorFor(i),
                border: i >= TOP_N ? "1px solid var(--ink-300)" : "none",
              }}
            />
            <span style={{ flex: 1, fontWeight: 600, fontSize: 14 }}>{f.name}</span>
            <span style={{ fontSize: 13.5, color: "var(--ink-700)", whiteSpace: "nowrap" }}>
              <b className="numeral">{won(f.amount)}</b>{" "}
              <span className="muted">({(f.ratio * 100).toFixed(1)}%)</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
