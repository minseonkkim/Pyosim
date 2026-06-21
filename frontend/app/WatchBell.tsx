"use client";

// 앱바 감시 벨 — 구독한 청원·법안·의원에 변화가 있으면 안 읽은 수를 뱃지로 (Phase 2).
// 익명 세션 기준. 라우트 이동마다 가볍게 갱신해 받은함(/watch)으로 유도한다.

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { getSessionId } from "@/lib/session";
import { fetchWatch } from "@/lib/api";

export default function WatchBell() {
  const pathname = usePathname();
  const [unread, setUnread] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const sid = getSessionId();
    if (!sid) return;
    let alive = true;
    fetchWatch(sid)
      .then((f) => {
        if (!alive) return;
        setUnread(f.unread);
        setTotal(f.total);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [pathname]);

  // 구독이 하나도 없으면 벨을 숨겨 빈 기능을 노출하지 않는다.
  if (total === 0) return null;

  return (
    <Link
      href="/watch"
      aria-label={`감시 목록${unread > 0 ? ` — 변화 ${unread}건` : ""}`}
      style={{
        marginLeft: "auto",
        position: "relative",
        textDecoration: "none",
        fontSize: 19,
        lineHeight: 1,
      }}
    >
      <span aria-hidden>{unread > 0 ? "🔔" : "🔕"}</span>
      {unread > 0 && (
        <span
          style={{
            position: "absolute",
            top: -6,
            right: -8,
            minWidth: 16,
            height: 16,
            padding: "0 4px",
            borderRadius: 8,
            background: "var(--ink-900)",
            color: "#fff",
            fontSize: 10.5,
            fontWeight: 800,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {unread}
        </span>
      )}
    </Link>
  );
}
