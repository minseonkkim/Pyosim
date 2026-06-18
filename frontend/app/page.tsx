// Phase 1-3 에서 실제 테스트 진입 화면으로 대체.
// 진입은 "나"에서 시작 — 정치 용어 0, 법안목록 X (기획서 설계 원칙).

export default function Home() {
  return (
    <main>
      <h1>표심 · Pyosim</h1>
      <p style={{ color: "var(--muted)" }}>Where do you stand?</p>
      <p>
        실제 국회 표결 데이터로 내 정치 성향을 확인하고, 지금 진행 중인 법안에
        직접 의견까지.
      </p>
      <button
        style={{
          marginTop: 16,
          padding: "12px 20px",
          fontSize: 16,
          color: "#fff",
          background: "var(--accent)",
          border: "none",
          borderRadius: 8,
          cursor: "pointer",
        }}
      >
        내 정치성향 알아보기
      </button>
      <p style={{ marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
        Phase 0 — 기반 공사 완료. 테스트 화면은 Phase 1 에서 구현됩니다.
      </p>
    </main>
  );
}
