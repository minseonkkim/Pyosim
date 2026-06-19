// 정치인 화면 공용 조각 — 정당 색 점 + 아바타 (Phase 1-2)

export function PartyDot({ color }: { color: string | null }) {
  return (
    <span
      aria-hidden
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: 2,
        background: color ?? "var(--ink-400)",
        marginRight: 5,
        verticalAlign: "middle",
      }}
    />
  );
}

export function Avatar({ name, photo }: { name: string; photo: string | null }) {
  if (photo) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- 외부 의원 사진은 도메인 가변, next/image 최적화 대상 아님
      <img
        src={photo}
        alt={name}
        width={44}
        height={44}
        style={{ borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
      />
    );
  }
  return (
    <span
      aria-hidden
      style={{
        width: 44,
        height: 44,
        flexShrink: 0,
        borderRadius: "50%",
        background: "var(--ink-100)",
        color: "var(--ink-500)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 700,
        fontSize: 16,
      }}
    >
      {name.replace(/^\[데모\]\s*/, "").slice(0, 1)}
    </span>
  );
}
