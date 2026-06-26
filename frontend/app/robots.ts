import type { MetadataRoute } from "next";

// 크롤러 진입점 — 색인 허용 규칙 + 사이트맵 위치를 알린다.
// 세션/개인 상태 페이지(/result·/share·/watch)는 색인 가치가 없고 중복만 만들어 차단.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/result", "/share", "/watch"],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
