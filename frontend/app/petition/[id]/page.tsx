// 청원 상세 (서버 컴포넌트) — SSR 로 본문·메타데이터·구조화 데이터를 HTML 에 박는다.
// 인터랙션(감시 토글)은 PetitionView(클라이언트)로 분리. 🟡 공식 기록·사실만.

import type { Metadata } from "next";
import { cache } from "react";

import { fetchPetition, type PetitionDetail } from "@/lib/api";
import PetitionView from "./PetitionView";

// 청원 진행은 가끔 바뀜 — 1시간 단위 ISR.
export const revalidate = 3600;

const getPetition = cache(async (id: number): Promise<PetitionDetail | null> => {
  if (!Number.isFinite(id)) return null;
  try {
    return await fetchPetition(id);
  } catch {
    return null;
  }
});

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const p = await getPetition(Number(id));
  if (!p) return { title: "청원을 찾을 수 없어요 · 표심", robots: { index: false } };

  const sign = p.signature_count != null ? `${p.signature_count.toLocaleString()}명 동의 · ` : "";
  const state = p.status === "계류" ? "심사 진행 중" : `처리완료${p.proc_result ? ` (${p.proc_result})` : ""}`;
  const title = `${p.title} — 청원 진행 · 표심`;
  const description = `${sign}${state}. ${p.objective ?? "국민동의청원 처리 단계와 결과를 국회 공식 기록으로 추적합니다."}`.slice(0, 155);

  return {
    title,
    description,
    alternates: { canonical: `/petition/${p.id}` },
    openGraph: { type: "article", title, description, url: `/petition/${p.id}` },
    twitter: { title, description },
  };
}

export default async function Page({ params }: Params) {
  const { id } = await params;
  const p = await getPetition(Number(id));

  if (!p) {
    return (
      <main>
        <p className="muted">청원을 찾을 수 없어요.</p>
      </main>
    );
  }

  // 구조화 데이터 — 청원은 schema.org 정형이 없어 일반 Article 로. 🟡 사실만.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: p.title,
    articleSection: "청원",
    ...(p.proposed_date ? { datePublished: p.proposed_date } : {}),
    ...(p.objective ? { description: p.objective.slice(0, 300) } : {}),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <PetitionView initial={p} />
    </>
  );
}
