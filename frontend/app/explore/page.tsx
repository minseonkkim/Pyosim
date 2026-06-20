// 국회 둘러보기 (허브) — 첫 화면을 비우는 대신 플랫폼 입구를 여기 모은다.
// 법안·의원·세금은 공개(게이트 없음). 첫 화면 깔끔함은 유지하되 벽은 만들지 않는다.
import Link from "next/link";

import TrackOnMount from "../TrackOnMount";

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
    desc: "표가 팽팽했거나 정당 입장이 갈렸던 법안만 골라서",
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

export default function ExplorePage() {
  return (
    <main>
      <TrackOnMount event="explore" />
      <h1 style={{ fontSize: 26, margin: "8px 0 4px" }}>국회 둘러보기</h1>
      <p className="muted" style={{ fontSize: 14, marginBottom: 18 }}>
        실제 국회 표결·발의 데이터를 세 갈래로 봐요. 어디든 눌러서 들어가세요.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 12,
        }}
      >
        {DOORS.map((d) => (
          <DoorCard key={d.title} door={d} />
        ))}
      </div>

      <p
        className="muted"
        style={{ marginTop: 22, fontSize: 12.5, lineHeight: 1.6 }}
      >
        모든 항목은 의안정보시스템·국회 공식 데이터가 출처예요. 특정 정당·인물을
        추천하지 않습니다.
      </p>
    </main>
  );
}

function DoorCard({ door }: { door: Door }) {
  const inner = (
    <>
      <div style={{ fontSize: 26, lineHeight: 1 }}>{door.emoji}</div>
      <div style={{ fontSize: 17, fontWeight: 700, marginTop: 10 }}>
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
          fontSize: 13,
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
    minHeight: 132,
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
