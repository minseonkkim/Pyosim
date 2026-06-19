"use client";

// 정당별 일치율 막대그래프 (Recharts). 색은 각 정당 color_hex.
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import type { PartyMatch } from "@/lib/api";

export default function PartyChart({ data }: { data: PartyMatch[] }) {
  const rows = data.map((m) => ({
    party: m.party,
    pct: Math.round(m.match_rate * 100),
    color: m.color_hex ?? "#888",
  }));

  return (
    <ResponsiveContainer width="100%" height={rows.length * 46 + 20}>
      <BarChart
        layout="vertical"
        data={rows}
        margin={{ top: 4, right: 44, bottom: 4, left: 8 }}
        barCategoryGap={10}
      >
        <XAxis type="number" domain={[0, 100]} hide />
        <YAxis
          type="category"
          dataKey="party"
          width={84}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 13, fill: "#1a1a1a" }}
        />
        <Bar dataKey="pct" radius={[4, 4, 4, 4]} isAnimationActive={false}>
          {rows.map((r) => (
            <Cell key={r.party} fill={r.color} />
          ))}
          <LabelList
            dataKey="pct"
            position="right"
            formatter={(v: number) => `${v}%`}
            style={{ fontSize: 13, fontWeight: 700, fill: "#1a1a1a" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
