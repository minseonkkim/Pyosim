import { ImageResponse } from "next/og";

// 링크 공유(카카오톡·슬랙·트위터 등) 미리보기 썸네일.
// 디자인 시스템 = Pyo Ink(무채색). app/icon.svg 와 결을 맞춘 다크 패널 카드.
// edge 런타임이어야 import.meta.url 로 콜로케이트한 폰트(.ttf)가 절대 URL 로 잡힌다.
export const runtime = "edge";
export const alt = "표심 · Pyosim — Where do you stand?";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpengraphImage() {
  const [extraBold, medium] = await Promise.all([
    fetch(new URL("./_fonts/Pretendard-ExtraBold.ttf", import.meta.url)).then(
      (r) => r.arrayBuffer(),
    ),
    fetch(new URL("./_fonts/Pretendard-Medium.ttf", import.meta.url)).then(
      (r) => r.arrayBuffer(),
    ),
  ]);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: 80,
          background: "linear-gradient(160deg, #2a2932 0%, #0e0d12 100%)",
          color: "#ffffff",
          fontFamily: "Pretendard",
        }}
      >
        {/* main — 워드마크 + 슬로건 (세로 중앙) */}
        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "column",
            justifyContent: "center",
            gap: 20,
          }}
        >
          <div style={{ display: "flex", alignItems: "baseline", gap: 26 }}>
            <div
              style={{
                display: "flex",
                fontSize: 158,
                fontWeight: 800,
                letterSpacing: "-0.045em",
                lineHeight: 1,
              }}
            >
              표심
            </div>
            <div
              style={{
                display: "flex",
                fontSize: 66,
                fontWeight: 500,
                color: "#9794a0",
                letterSpacing: "-0.02em",
              }}
            >
              · Pyosim
            </div>
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 62,
              fontWeight: 800,
              color: "#f0eff3",
              letterSpacing: "-0.02em",
            }}
          >
            Where do you stand?
          </div>
        </div>

        {/* footer — 한 줄 소개 */}
        <div
          style={{
            display: "flex",
            maxWidth: 1000,
            fontSize: 31,
            fontWeight: 500,
            lineHeight: 1.45,
            color: "#9794a0",
            letterSpacing: "-0.01em",
          }}
        >
          실제 국회 표결 데이터 기반 시민 참여 플랫폼
        </div>
      </div>
    ),
    {
      ...size,
      fonts: [
        { name: "Pretendard", data: extraBold, weight: 800, style: "normal" },
        { name: "Pretendard", data: medium, weight: 500, style: "normal" },
      ],
    },
  );
}
