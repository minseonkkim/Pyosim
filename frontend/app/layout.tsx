import type { Metadata } from "next";
import Link from "next/link";
// Pretendard (가변 폰트 + 다이내믹 서브셋) — 디자인 시스템 기본 서체
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "표심 · Pyosim — Where do you stand?",
  description:
    "실제 국회 표결 데이터로 내 생각이 어떤 표결과 닮았는지 확인하고, 진행 중인 법안에 의견까지.",
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
        </header>
        {children}
      </body>
    </html>
  );
}
