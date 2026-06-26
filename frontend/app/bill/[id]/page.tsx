// 법안 상세 (서버 컴포넌트) — SSR 로 본문·메타데이터·구조화 데이터를 HTML 에 박는다.
// AI 요약은 BillView(클라이언트)가 별도로 늦게 채운다. 🟡 공식 출처·사실만. 그물망 '법안' 축 허브.

import type { Metadata } from "next";
import { cache } from "react";

import { fetchBill, type BillDetail } from "@/lib/api";
import BillView from "./BillView";

// 표결·처리 단계가 가끔 갱신됨 — 1시간 단위 ISR.
export const revalidate = 3600;

const getBill = cache(async (id: number): Promise<BillDetail | null> => {
  if (!Number.isFinite(id)) return null;
  try {
    return await fetchBill(id);
  } catch {
    return null;
  }
});

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const b = await getBill(Number(id));
  if (!b) return { title: "법안을 찾을 수 없어요 · 표심", robots: { index: false } };

  const meta = [b.committee, b.status].filter(Boolean).join(" · ");
  const tally = b.vote
    ? ` 본회의 표결 찬성 ${b.vote.yes ?? 0}·반대 ${b.vote.no ?? 0}.`
    : "";
  const title = `${b.title} — 법안 표결·처리 · 표심`;
  const description = `의안 ${b.bill_no}${meta ? ` · ${meta}` : ""}.${tally} 발의자·정당별 찬반·처리 단계를 국회 공식 기록으로.`.slice(0, 155);

  return {
    title,
    description,
    alternates: { canonical: `/bill/${b.id}` },
    openGraph: { type: "article", title, description, url: `/bill/${b.id}` },
    twitter: { title, description },
  };
}

export default async function Page({ params }: Params) {
  const { id } = await params;
  const b = await getBill(Number(id));

  if (!b) {
    return (
      <main>
        <h2>찾을 수 없어요</h2>
        <p className="muted">해당 법안이 없습니다.</p>
      </main>
    );
  }

  // 구조화 데이터(Legislation) — 법안에 맞는 schema.org 정형. 🟡 공식 사실만.
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Legislation",
    name: b.title,
    legislationIdentifier: b.bill_no,
    ...(b.proposed_date ? { datePublished: b.proposed_date } : {}),
    ...(b.committee ? { legislationResponsible: b.committee } : {}),
    ...(b.proposal_reason ? { description: b.proposal_reason.slice(0, 300) } : {}),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <BillView initial={b} />
    </>
  );
}
