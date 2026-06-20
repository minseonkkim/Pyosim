// 진입 화면 — "나"에서 시작. 정치 용어 0, 법안목록 X (기획서 설계 원칙).
import Link from "next/link";

import TrackOnMount from "./TrackOnMount";

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
        뉴스는 안 봐도,
        <br />
        내 생각은 있잖아요
      </h1>

      <p style={{ fontSize: 17, lineHeight: 1.6, color: "var(--ink-700)" }}>
        정치 잘 몰라도 괜찮아요. 끌리는 쪽만 고르면, 내 생각이 국회의 실제 표결과
        얼마나 닮았는지 3분 만에 보여드려요.
      </p>

      <Link href="/test" className="btn btn-block" style={{ marginTop: 20 }}>
        3분 만에 확인하기 →
      </Link>

      <Link
        href="/bills"
        className="btn btn-ghost btn-block"
        style={{ marginTop: 10 }}
      >
        의견이 갈린 법안 보기 →
      </Link>

      <Link
        href="/persons"
        className="btn btn-ghost btn-block"
        style={{ marginTop: 10 }}
      >
        국회의원 둘러보기 →
      </Link>

      <ul
        style={{
          marginTop: 28,
          paddingLeft: 18,
          fontSize: 14.5,
          lineHeight: 1.9,
          color: "var(--muted)",
        }}
      >
        <li>약 3분, 20문항 · 모바일에서 편하게</li>
        <li>각 문항은 실제 발의·표결된 법안이 출처예요 (▼로 확인)</li>
        <li>특정 정당을 추천하지 않습니다 — &ldquo;표결 일치도&rdquo;일 뿐</li>
      </ul>

      <p style={{ marginTop: 24, fontSize: 12.5, color: "var(--muted)" }}>
        ⚠️ 현재 문항은 외부 교차검토 전 <b>초안</b>입니다(프로토타입).
      </p>
    </main>
  );
}
