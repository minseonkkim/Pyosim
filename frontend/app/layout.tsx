import type { Metadata } from "next";
import Link from "next/link";
import { GoogleAnalytics } from "@next/third-parties/google";
import WatchBell from "./WatchBell";
import FreshnessBadge from "./FreshnessBadge";
// Pretendard (가변 폰트 + 다이내믹 서브셋) — 디자인 시스템 기본 서체
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "표심 · Pyosim — Where do you stand?",
  description:
    "실제 국회 표결 데이터로 내 생각이 어떤 표결과 닮았는지 확인하고, 진행 중인 법안에 의견까지.",
  // SVG 아이콘은 <text>가 Pretendard 폰트에 의존 → 브라우저 밖(공유 크롤러·썸네일러)에서
  // 폰트 없이 래스터화되며 글자가 깨진다. 외부 노출용은 PNG, 탭용만 SVG 유지.
  icons: {
    icon: [
      { url: "/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: "/icon-180.png",
  },
  // 링크 공유 미리보기. og:image 는 app/opengraph-image.tsx 가 자동 생성.
  openGraph: {
    type: "website",
    siteName: "표심 · Pyosim",
    title: "표심 · Pyosim — Where do you stand?",
    description:
      "실제 국회 표결 데이터로 내 생각이 어떤 표결과 닮았는지 확인하고, 진행 중인 법안에 의견까지.",
    locale: "ko_KR",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "표심 · Pyosim — Where do you stand?",
    description:
      "실제 국회 표결 데이터로 내 생각이 어떤 표결과 닮았는지 확인하고, 진행 중인 법안에 의견까지.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" data-theme="light">
      {/* 일부 브라우저 확장(ColorZilla 등)이 <body>에 cz-shortcut-listen 같은
          속성을 주입해 SSR↔클라이언트 hydration 불일치가 난다. body 속성 한 단계만
          경고를 억제(내부 트리엔 영향 없음). */}
      <body suppressHydrationWarning>

        <header className="appbar">
          <Link href="/" className="wordmark">
            표심
          </Link>
          <div
            style={{
              marginLeft: "auto",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <FreshnessBadge />
            <WatchBell />
          </div>
        </header>
        {children}
      </body>
      {process.env.NEXT_PUBLIC_GA_ID && (
        <GoogleAnalytics gaId={process.env.NEXT_PUBLIC_GA_ID} />
      )}
    </html>
  );
}
