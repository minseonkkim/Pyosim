// 의원 프로필 상세 (서버 컴포넌트) — SSR 로 본문·메타데이터·구조화 데이터를 HTML 에 박는다.
// 인터랙션(감시 토글 등)은 PersonView(클라이언트)로 분리. 🟡 그물망 '사람' 축 허브.

import type { Metadata } from "next";
import { cache } from "react";
import Link from "next/link";

import { fetchPerson, type PersonProfile } from "@/lib/api";
import PersonView from "./PersonView";

// 프로필 갱신 빈도는 낮음 — 1시간 단위 ISR 로 SSR 비용을 캐시.
export const revalidate = 3600;

// generateMetadata 와 페이지가 같은 요청에서 두 번 호출 → React cache 로 한 번만 페치.
const getPerson = cache(async (id: number): Promise<PersonProfile | null> => {
  if (!Number.isFinite(id)) return null;
  try {
    return await fetchPerson(id);
  } catch {
    return null;
  }
});

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const p = await getPerson(Number(id));
  if (!p) return { title: "의원을 찾을 수 없어요 · 표심", robots: { index: false } };

  const party = p.party?.name ?? "무소속";
  const where = p.district ? ` · ${p.district}` : "";
  const title = `${p.name} 의원 (${party}) — 발의·표결 기록 · 표심`;
  const description = `${p.name} (${party}${where}) 국회의원 — 대표발의 ${p.proposed_count}건, 본회의 표결 ${p.vote_summary.total}건. 국회 공식 기록 기반 발의·표결 이력.`;

  return {
    title,
    description,
    alternates: { canonical: `/person/${p.id}` },
    openGraph: { type: "profile", title, description, url: `/person/${p.id}` },
    twitter: { title, description },
  };
}

export default async function Page({ params }: Params) {
  const { id } = await params;
  const p = await getPerson(Number(id));

  if (!p) {
    return (
      <main>
        <h2>찾을 수 없어요</h2>
        <p className="muted">해당 의원이 없습니다.</p>
        <Link href="/persons" className="btn btn-ghost">
          ← 목록으로
        </Link>
      </main>
    );
  }

  // 구조화 데이터(Person) — 검색 리치 결과·지식 패널 후보. 🟡 공식 데이터의 사실만.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: p.name,
    jobTitle: "국회의원",
    ...(p.party?.name ? { affiliation: { "@type": "Organization", name: p.party.name } } : {}),
    ...(p.photo_url ? { image: p.photo_url } : {}),
    ...(p.profile_source_url ? { sameAs: [p.profile_source_url] } : {}),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <PersonView initial={p} />
    </>
  );
}
