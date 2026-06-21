"use client";

// 앱바 '데이터 기준일' 배지 — 1일 1회 자동 갱신(🤖)이 마지막으로 성공한 날짜를 노출한다.
// 🟡 신뢰(기획 1.3): 데이터가 살아있음을 '사실'로만 보여준다(가치 판단 없음). 출처는 title 고지.
//
// 표시 규칙(빈 기능 미노출):
//   · 파이프라인 실행 기록이 아예 없으면(last_run=null) 숨긴다.
//   · 마지막 성공이 2일 넘게 지났거나 최근 실행이 실패했으면 '경고' 색으로 — 데이터가 오래됐을 수 있음.

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { fetchPipelineHealth, type PipelineHealth } from "@/lib/api";

const KST = "Asia/Seoul";
const STALE_DAYS = 2; // 이 일수를 넘게 갱신 성공이 없으면 경고

function fmtDate(iso: string): string {
  // tz 포함 ISO → KST 'M월 D일'. 사용자에겐 분 단위가 아니라 '며칠 기준'이 중요.
  const d = new Date(iso);
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: KST,
    month: "long",
    day: "numeric",
  }).format(d);
  return parts;
}

function daysSince(iso: string): number {
  const diffMs = Date.now() - new Date(iso).getTime();
  return Math.floor(diffMs / 86_400_000);
}

export default function FreshnessBadge() {
  const pathname = usePathname();
  const [health, setHealth] = useState<PipelineHealth | null>(null);

  useEffect(() => {
    let alive = true;
    fetchPipelineHealth()
      .then((h) => {
        if (alive) setHealth(h);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [pathname]);

  // 갱신이 한 번도 안 돌았으면 배지를 숨긴다(빈 상태 노출 방지).
  if (!health || !health.last_run) return null;

  const successAt = health.last_success_at;
  const lastFailed = !health.last_run.ok;
  const stale = !successAt || daysSince(successAt) > STALE_DAYS;
  const warn = stale || lastFailed;

  // 라벨: 성공 기록이 있으면 그 날짜, 없으면 '갱신 확인 필요'.
  const label = successAt ? `데이터 ${fmtDate(successAt)} 기준` : "데이터 갱신 확인 필요";

  // title: 공식 고지 + (오래됨/실패 시) 사실 맥락. 판정 아님.
  const detail: string[] = [health.notice];
  if (successAt && stale) {
    detail.push(`마지막 성공 갱신이 ${daysSince(successAt)}일 전입니다.`);
  }
  if (lastFailed) {
    const f = health.last_run.failed_jobs;
    detail.push(
      f.length > 0
        ? `최근 갱신에서 일부 작업이 실패했습니다: ${f.join(", ")}.`
        : "최근 갱신 실행이 완료되지 못했습니다.",
    );
  }

  return (
    <span
      title={detail.join(" ")}
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontSize: 11,
        fontWeight: 600,
        lineHeight: 1,
        whiteSpace: "nowrap",
        color: warn ? "var(--warning)" : "var(--muted)",
        cursor: "default",
      }}
    >
      <span
        aria-hidden
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: warn ? "var(--warning)" : "var(--ink-400)",
        }}
      />
      {label}
    </span>
  );
}
