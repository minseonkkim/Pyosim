"use client";

// 서버 컴포넌트에서 마운트 시 1회 이벤트를 쏘기 위한 얇은 클라이언트 래퍼.
import { useEffect } from "react";

import { track, type EventName } from "@/lib/analytics";

export default function TrackOnMount({ event }: { event: EventName }) {
  useEffect(() => {
    track(event);
    // event 는 렌더 동안 고정 — 마운트당 1회만 전송.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}
