// 진입 화면 — "나"에서 시작. 설문은 친근한 입구(다크 잉크패널 히어로),
// 플랫폼(법안·의원·세금·우리동네)은 게이트 없이 그 아래 2×2 카드로 바로 펼친다.
// (정치 용어 0, 법안목록 X — 기획서 설계 원칙. 무관심층 진입장벽 0.)
import Link from "next/link";

import TrackOnMount from "./TrackOnMount";

type Door = {
  href: string;
  emoji: string;
  title: string;
  desc: string;
  disabled?: boolean;
};

const DOORS: Door[] = [
  {
    href: "/bills",
    emoji: "⚖️",
    title: "갈린 법안",
    desc: "표가 팽팽했거나 정당 입장이 갈렸던 법안만",
  },
  {
    href: "/persons",
    emoji: "👥",
    title: "국회의원",
    desc: "현역 300명 — 발의·표결 기록을 한 곳에서",
  },
  {
    href: "/tax",
    emoji: "🧾",
    title: "내 세금",
    desc: "내 월급에서 떼인 세금이 어디 쓰이는지",
  },
  {
    href: "#",
    emoji: "🏘",
    title: "우리 동네",
    desc: "주소로 내 지역구·내 의원 찾기",
    disabled: true,
  },
];

export default function Home() {
  return (
    <main>
      <TrackOnMount event="landing" />
      <span className="chip" style={{ marginTop: 8 }}>
        실제 국회 표결 기반
      </span>

      <h1
        style={{
          fontSize: 34,
          lineHeight: 1.25,
          letterSpacing: "-0.03em",
          margin: "16px 0 0",
        }}
      >
        국회, 내 편 맞아?
      </h1>

      <p style={{ fontSize: 17, lineHeight: 1.6, color: "var(--ink-700)" }}>
        직접 확인해봐요.
        <br />
        모르면 당하잖아요.
      </p>

      {/* 설문 = 친근한 입구. 잉크패널(다크)로 "여기서 시작" 신호. */}
      <section
        style={{
          marginTop: 20,
          padding: "22px 20px 20px",
          background: "var(--ink-panel)",
          borderRadius: "var(--radius-xl)",
          color: "var(--white)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        <span
          style={{
            display: "inline-block",
            padding: "3px 10px",
            fontSize: 12,
            fontWeight: 600,
            color: "var(--ink-200)",
            background: "rgba(255,255,255,0.12)",
            borderRadius: "var(--radius-full)",
          }}
        >
          처음이라면
        </span>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.55,
            margin: "12px 0 16px",
            color: "var(--ink-100)",
          }}
        >
          3분이면 내 생각이 국회의 실제 표결과 얼마나 닮았는지 나와요. 닮은
          의원·정당까지 한 번에.
        </p>
        <Link
          href="/test"
          className="btn btn-block"
          style={{ background: "var(--white)", color: "var(--ink-900)" }}
        >
          3분 테스트 시작 →
        </Link>
      </section>

      {/* 플랫폼 진입 — 게이트 없이 진입 화면에 바로. 구분되는 2×2 카드. */}
      <div
        style={{
          marginTop: 12,
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
        }}
      >
        {DOORS.map((d) => (
          <DoorCard key={d.title} door={d} />
        ))}
      </div>

      <ul
        style={{
          marginTop: 28,
          paddingLeft: 18,
          fontSize: 14.5,
          lineHeight: 1.9,
          color: "var(--muted)",
        }}
      >
        <li>모든 내용은 실제 발의·표결된 법안이 출처예요</li>
        <li>특정 정당·인물을 추천하지 않습니다 — &ldquo;표결 일치도&rdquo;일 뿐</li>
      </ul>
    </main>
  );
}

function DoorCard({ door }: { door: Door }) {
  const inner = (
    <>
      <div style={{ fontSize: 24, lineHeight: 1 }}>{door.emoji}</div>
      <div style={{ fontSize: 16, fontWeight: 700, marginTop: 10 }}>
        {door.title}
        {door.disabled && (
          <span
            className="chip"
            style={{ marginLeft: 6, fontSize: 10.5, padding: "2px 7px" }}
          >
            준비중
          </span>
        )}
      </div>
      <div
        style={{
          fontSize: 12.5,
          lineHeight: 1.5,
          color: "var(--muted)",
          marginTop: 4,
        }}
      >
        {door.desc}
      </div>
    </>
  );

  const cardStyle: React.CSSProperties = {
    display: "block",
    padding: "16px 16px 18px",
    minHeight: 128,
    background: "var(--surface)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-md)",
    boxShadow: "var(--shadow-sm)",
    textDecoration: "none",
    color: "var(--fg)",
  };

  if (door.disabled) {
    return (
      <div style={{ ...cardStyle, opacity: 0.55, cursor: "not-allowed" }}>
        {inner}
      </div>
    );
  }

  return (
    <Link href={door.href} style={cardStyle}>
      {inner}
    </Link>
  );
}
