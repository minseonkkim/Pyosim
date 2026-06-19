// 공유 랜딩 (Phase 1-5) — 공유 링크로 들어온 사람이 보는 카드 + 테스트 유도.
// OG 메타는 generateMetadata 가 쿼리로 /api/og 동적 이미지를 가리킨다.

import type { Metadata } from "next";
import Link from "next/link";

type SP = Promise<Record<string, string | string[] | undefined>>;

function one(v: string | string[] | undefined, fallback: string): string {
  if (Array.isArray(v)) return v[0] ?? fallback;
  return v ?? fallback;
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: SP;
}): Promise<Metadata> {
  const sp = await searchParams;
  const party = one(sp.party, "");
  const rate = one(sp.rate, "0");
  const n = one(sp.n, "0");
  const color = one(sp.color, "152484");
  const ogUrl = `/api/og?party=${encodeURIComponent(party)}&rate=${rate}&n=${n}&color=${color}`;
  const title = party
    ? `나와 가장 많이 겹친 곳: ${party} (${rate}%) · 표심`
    : "표심 · Pyosim";
  const description = "실제 국회 표결로 보는 내 정치성향 — 표결 일치도일 뿐, 정치적 판단은 본인 몫.";

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [{ url: ogUrl, width: 1200, height: 630 }],
    },
    twitter: { card: "summary_large_image", title, description, images: [ogUrl] },
  };
}

export default async function SharePage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const party = one(sp.party, "");
  const rate = one(sp.rate, "0");
  const n = one(sp.n, "0");
  const color = `#${one(sp.color, "18171D").replace(/[^0-9a-fA-F]/g, "")}`;

  return (
    <main>
      {party ? (
        <div className="card card-emphasis" style={{ marginTop: 8, padding: 24 }}>
          <div className="muted" style={{ fontSize: 15 }}>
            나와 가장 많이 겹친 곳
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginTop: 10,
            }}
          >
            <span
              style={{ width: 12, height: 44, background: color, borderRadius: 4, display: "inline-block" }}
            />
            <span style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.02em" }}>
              {party}
            </span>
          </div>
          <div
            className="numeral"
            style={{ fontSize: 56, lineHeight: 1.1, color, marginTop: 4 }}
          >
            {rate}%
          </div>
          <div className="muted" style={{ fontSize: 13 }}>
            {n}문항 응답 · 실제 국회 표결 일치도
          </div>
        </div>
      ) : (
        <p style={{ marginTop: 16, fontSize: 17 }}>
          실제 국회 표결로 내 정치성향을 확인해 보세요.
        </p>
      )}

      <p style={{ fontSize: 17, lineHeight: 1.6, marginTop: 16 }}>
        나는 어떤 표결과 가장 닮았을까? 정치 용어 없이 8문항으로 확인해요.
      </p>
      <Link href="/test" className="btn btn-block" style={{ marginTop: 12 }}>
        나도 해보기 →
      </Link>

      <p className="disclaimer" style={{ marginTop: 20 }}>
        ⚖️ 이 결과는 실제 국회 표결과 답의 &lsquo;일치도&rsquo;일 뿐입니다. 특정 정당을
        지지/반대하라는 뜻이 아니며, 정치적 판단은 본인의 몫입니다.
      </p>
    </main>
  );
}
