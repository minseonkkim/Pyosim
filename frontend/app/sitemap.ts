import type { MetadataRoute } from "next";

// 검색엔진이 동적 상세(의원·법안·청원)를 빠짐없이 찾도록 하는 사이트맵.
// 링크만으로는 도달이 느리거나 누락되는 롱테일 페이지를 한 번에 노출한다.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// 매 크롤 요청마다 백엔드를 때리지 않도록 한 시간 캐시 후 재생성.
export const revalidate = 3600;

// 사이트맵 전용 fetch — 실패해도 사이트맵 전체가 깨지지 않도록 빈 배열로 흡수.
// (빌드/배포 순간 백엔드가 잠시 안 떠 있어도 정적 라우트는 항상 나가야 한다.)
async function fetchIds<T>(
  path: string,
  pick: (json: T) => Array<{ id: number }>,
): Promise<number[]> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { next: { revalidate } });
    if (!res.ok) return [];
    return pick((await res.json()) as T).map((x) => x.id);
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  // 정적 라우트 — 진입·목록 페이지만. 세션/개인 페이지는 robots 에서 차단했으므로 제외.
  const staticPaths = ["", "/bills", "/persons", "/petitions", "/mismatch", "/tax", "/test"];
  const staticEntries = staticPaths.map(
    (p): MetadataRoute.Sitemap[number] => ({
      url: `${SITE_URL}${p}`,
      lastModified: now,
      changeFrequency: "daily",
      priority: p === "" ? 1 : 0.8,
    }),
  );

  // 동적 상세 — 그물망의 실제 콘텐츠 페이지(검색 롱테일의 핵심).
  // 의원: 전체 반환 / 청원: limit 넉넉히 / 법안: 표결·시민의견이 실제 있는 큐레이션 피드에서.
  type IdList = Array<{ id: number }>;
  type Feed = { items: IdList };
  const [persons, petitions, contested, opinions] = await Promise.all([
    fetchIds<IdList>("/api/persons", (j) => j),
    fetchIds<Feed>("/api/petitions?limit=1000", (j) => j.items),
    fetchIds<Feed>("/api/bills?limit=1000&sort=contested", (j) => j.items),
    fetchIds<Feed>("/api/bills?limit=1000&sort=opinions", (j) => j.items),
  ]);
  const billIds = Array.from(new Set([...contested, ...opinions]));

  const detail = (
    prefix: string,
    idList: number[],
    priority: number,
  ): MetadataRoute.Sitemap =>
    idList.map((id) => ({
      url: `${SITE_URL}${prefix}/${id}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority,
    }));

  return [
    ...staticEntries,
    ...detail("/person", persons, 0.7),
    ...detail("/bill", billIds, 0.7),
    ...detail("/petition", petitions, 0.6),
  ];
}
