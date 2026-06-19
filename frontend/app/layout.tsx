import type { Metadata } from "next";
import Link from "next/link";
// Pretendard (가변 폰트 + 다이내믹 서브셋) — 디자인 시스템 기본 서체
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "표심 · Pyosim — Where do you stand?",
  description:
    "실제 국회 표결 데이터로 내 정치 성향을 확인하고, 진행 중인 법안에 의견까지.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
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
