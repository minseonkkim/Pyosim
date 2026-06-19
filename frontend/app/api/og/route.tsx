// 동적 OG 이미지 (Phase 1-5) — 공유 카드 썸네일.
// 🟡 카드에도 출처·집계 기준 표기. "나" 중심 발견 프레이밍(자극 X).
//
// 폰트: ./NotoSansKR-og.ttf (정당명 5개 + 고정 문구 + 숫자/영문 서브셋, ~12KB).
//   scripts/fetch-og-font.mjs 로 생성. new URL 로 라우트에 콜로케이트한 자산을 읽는다.
// 런타임: edge — node 변형의 번들 기본폰트 로딩(Windows 경로 버그)을 피한다.
//   (edge 변형은 fallback 폰트를 fetch 로 받아 해당 버그가 없다.)

import { ImageResponse } from "next/og";

export const runtime = "edge";

let fontCache: ArrayBuffer | null = null;
async function koreanFont(): Promise<ArrayBuffer> {
  if (!fontCache) {
    const data = await fetch(
      new URL("./NotoSansKR-og.ttf", import.meta.url),
    ).then((r) => r.arrayBuffer());
    fontCache = data;
    return data;
  }
  return fontCache;
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const party = searchParams.get("party") ?? "";
  const rate = searchParams.get("rate") ?? "0";
  const n = searchParams.get("n") ?? "0";
  const color = `#${(searchParams.get("color") ?? "152484").replace(/[^0-9a-fA-F]/g, "")}`;

  const font = await koreanFont();

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "#ffffff",
          fontFamily: "NotoKR",
        }}
      >
        <div style={{ display: "flex", fontSize: 34, color: "#18171D", fontWeight: 700 }}>
          표심 · Pyosim
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 30, color: "#666" }}>
            나와 가장 많이 겹친 곳
          </div>
          <div style={{ display: "flex", alignItems: "center", marginTop: 8 }}>
            <div
              style={{ width: 28, height: 64, background: color, borderRadius: 6, marginRight: 20 }}
            />
            <div style={{ display: "flex", fontSize: 64, fontWeight: 700, color: "#1a1a1a" }}>
              {party}
            </div>
          </div>
          <div style={{ display: "flex", fontSize: 96, fontWeight: 700, color }}>{rate}%</div>
        </div>

        <div style={{ display: "flex", fontSize: 23, color: "#888" }}>
          {n}문항 응답 · 실제 국회 표결 일치도 (지지 반대 권유 아님)
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: [{ name: "NotoKR", data: font, weight: 700, style: "normal" }],
    },
  );
}
