// 진입 화면 — "나"에서 시작. 정치 용어 0, 법안목록 X (기획서 설계 원칙).
import Link from "next/link";

export default function Home() {
  return (
    <main>
      <h1 style={{ marginBottom: 4 }}>표심 · Pyosim</h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Where do you stand?</p>
      <p style={{ fontSize: 17, lineHeight: 1.6 }}>
        정치 용어는 하나도 없습니다. 일상 속 선택 8가지에 답하면, 실제 국회
        표결과 내 생각이 얼마나 닮았는지 보여드려요.
      </p>

      <Link href="/test" className="btn btn-block" style={{ marginTop: 20 }}>
        내 정치성향 알아보기 →
      </Link>

      <ul
        style={{
          marginTop: 28,
          paddingLeft: 18,
          fontSize: 14,
          lineHeight: 1.8,
          color: "var(--muted)",
        }}
      >
        <li>약 2분, 8문항 · 모바일에서 편하게</li>
        <li>각 문항은 실제 발의·표결된 법안이 출처예요 (▼로 확인)</li>
        <li>특정 정당을 추천하지 않습니다 — &ldquo;표결 일치도&rdquo;일 뿐</li>
      </ul>

      <p style={{ marginTop: 24, fontSize: 12.5, color: "var(--muted)" }}>
        ⚠️ 현재 문항은 외부 교차검토 전 <b>초안</b>입니다(프로토타입).
      </p>
    </main>
  );
}
