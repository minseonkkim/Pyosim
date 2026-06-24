"use client";

// 분야 → 위원회 → 법안·의원 그물망 패널 (기획서 4.6).
// /tax 도넛 목록에서 분야를 펼치면 이 패널이 뜬다: 그 분야를 심의·감독하는 상임위원회와
// 소관 법안·소속 의원으로 잇는다. 세금 → 분야 → 위원회 → 법안·의원, 그물망이 닫힌다.
// 🟡 정직성: 예산 항목↔법안 1:1 추적이 아니라 '소관 위원회 다리'. 사실만, 출처 화면으로 연결.

import { useEffect, useState } from "react";
import Link from "next/link";

import { fetchBudgetNetwork, type BudgetNetwork } from "@/lib/api";

function formatDate(d: string | null): string {
  if (!d) return "";
  return d.replaceAll("-", ".").slice(2); // 2024-05-30 → 24.05.30
}

export default function FieldNetwork({
  fieldCode,
  fieldName,
}: {
  fieldCode: string;
  fieldName: string;
}) {
  const [data, setData] = useState<BudgetNetwork | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    let alive = true;
    setState("loading");
    fetchBudgetNetwork(fieldCode, { billLimit: 6, memberLimit: 10 })
      .then((d) => {
        if (!alive) return;
        setData(d);
        setState("ok");
      })
      .catch(() => alive && setState("error"));
    return () => {
      alive = false;
    };
  }, [fieldCode]);

  if (state === "loading") {
    return (
      <div style={{ padding: "12px 2px", fontSize: 13, color: "var(--muted)" }}>
        {fieldName} 분야의 소관 위원회·법안·의원을 불러오는 중…
      </div>
    );
  }
  if (state === "error" || !data) {
    return (
      <div style={{ padding: "12px 2px", fontSize: 13, color: "var(--muted)" }}>
        지금은 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
      </div>
    );
  }
  if (data.committees.length === 0) {
    return (
      <div style={{ padding: "12px 2px", fontSize: 13, color: "var(--muted)" }}>
        이 분야는 특정 소관 상임위원회로 묶기 어려워, 연결을 제공하지 않습니다.
      </div>
    );
  }

  return (
    <div style={{ padding: "4px 2px 14px" }}>
      {/* 소관 위원회 — 다리 */}
      <div style={{ fontSize: 13, color: "var(--ink-700)", lineHeight: 1.6 }}>
        이 분야를 심의·감독하는 국회 상임위원회{" "}
        {data.committees.map((c, i) => (
          <span key={c.name}>
            {i > 0 && " · "}
            <b>{c.name}</b>
            <span className="muted"> ({c.member_count}명)</span>
          </span>
        ))}
      </div>

      {/* 소속 의원 — 사람 축 */}
      {data.members.length > 0 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--muted)", marginBottom: 8 }}>
            소속 의원 {data.member_total}명 중
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {data.members.map((m) => (
              <Link
                key={m.id}
                href={`/person/${m.id}`}
                className="chip"
                style={{ fontSize: 12.5, padding: "5px 10px", textDecoration: "none" }}
              >
                {m.name}
                {m.party && (
                  <span className="muted" style={{ marginLeft: 4 }}>
                    {m.party.name}
                  </span>
                )}
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* 소관 법안 — 법안 축 */}
      {data.bills.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--muted)", marginBottom: 6 }}>
            소관 법안 {data.bill_total.toLocaleString("ko-KR")}건 중 최근
          </div>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {data.bills.map((b, i) => (
              <li
                key={b.id}
                style={{ borderTop: i === 0 ? "none" : "1px solid var(--border)" }}
              >
                <Link
                  href={`/bill/${b.id}`}
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: 8,
                    padding: "9px 0",
                    textDecoration: "none",
                    color: "var(--fg)",
                  }}
                >
                  <span style={{ flex: 1, fontSize: 13.5, lineHeight: 1.45 }}>{b.title}</span>
                  {b.proposed_date && (
                    <span
                      className="numeral"
                      style={{ flexShrink: 0, fontSize: 11.5, color: "var(--muted)" }}
                    >
                      {formatDate(b.proposed_date)}
                    </span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 🟡 정직성 고지 */}
      <p style={{ margin: "12px 0 0", fontSize: 11.5, color: "var(--muted)", lineHeight: 1.6 }}>
        {data.notice}
      </p>
    </div>
  );
}
