"use client";

// 의원 프로필 본문 (클라이언트 뷰) — 데이터는 서버(page.tsx)에서 SSR 로 받아 prop 으로 받는다.
// 색인·메타데이터는 서버가 처리하고, 여기선 감시 토글 등 인터랙션만 담당.

import Link from "next/link";

import { type PersonProfile } from "@/lib/api";
import { Avatar, PartyDot } from "../../persons/PersonBits";
import WatchButton from "@/app/WatchButton";

// 타임라인용 날짜 표기: "2024-06-15" → "2024.06.15" (없으면 "날짜 미상")
function fmtTimelineDate(d: string | null): string {
  if (!d) return "날짜 미상";
  return d.slice(0, 10).replace(/-/g, ".");
}

export default function PersonView({ initial }: { initial: PersonProfile }) {
  const p = initial;
  const id = p.id;
  const vs = p.vote_summary;

  return (
    <main>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <Link href="/persons" className="muted" style={{ fontSize: 13 }}>
          ← 국회의원
        </Link>
        <WatchButton kind="person" refId={id} />
      </div>

      {/* 헤더 */}
      <div style={{ display: "flex", gap: 14, alignItems: "center", margin: "12px 0 4px" }}>
        <Avatar name={p.name} photo={p.photo_url} />
        <div>
          <h1 style={{ fontSize: 24, margin: 0 }}>{p.name}</h1>
          <div className="muted" style={{ fontSize: 14, marginTop: 2 }}>
            {p.party && <PartyDot color={p.party.color_hex} />}
            {p.party?.name ?? "무소속"}
            {p.district ? ` · ${p.district}` : ""}
          </div>
          {(() => {
            // 인적사항 — 국회 공식 데이터 기준 사실만(선수·나이·성별·직책)
            const bits = [
              p.term_label,
              p.age != null ? `${p.age}세` : null,
              p.gender,
              p.position,
            ].filter(Boolean);
            return bits.length ? (
              <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                {bits.join(" · ")}
              </div>
            ) : null;
          })()}
        </div>
      </div>

      {/* 위원회 — 🟡 '현재 소속' 단정 대신 공식 '제22대 위원회 경력'(활동기간 동반) */}
      {p.committees.length > 0 && (
        <div style={{ margin: "14px 0 2px" }}>
          <div className="muted" style={{ fontSize: 12.5, marginBottom: 6 }}>
            위원회 · 제22대 경력
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {p.committees.map((c) => (
              <span
                key={c.name}
                className="card"
                title={c.term_label ?? undefined}
                style={{ margin: 0, padding: "5px 10px", fontSize: 13, fontWeight: 600 }}
              >
                {c.name}
                {c.role && c.role !== "위원" ? (
                  <span style={{ color: "var(--primary)", marginLeft: 4 }}>· {c.role}</span>
                ) : null}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 요약 지표 */}
      <div style={{ display: "flex", gap: 10, margin: "16px 0" }}>
        <Stat label="출석률" value={p.attendance_rate != null ? `${Math.round(p.attendance_rate * 100)}%` : "—"} />
        <Stat label="대표발의" value={`${p.proposed_count}건`} />
        <Stat label="표결 참여" value={vs.total ? `${vs.total}건` : "—"} />
      </div>

      {/* 대표발의 법안 → 그물망(법안) */}
      <h3 style={{ marginBottom: 8 }}>대표발의 법안</h3>
      {p.proposed_bills.length === 0 ? (
        <p className="muted" style={{ fontSize: 14 }}>
          대표발의 데이터는 아직 연결 전이에요. (발의자 정보 연동 예정)
        </p>
      ) : (
        <div style={{ position: "relative" }}>
          {/* 세로 타임라인 축 — 날짜(왼쪽) · 점 · 법안 카드(오른쪽) */}
          <div
            style={{
              position: "absolute",
              left: 71,
              top: 6,
              bottom: 6,
              width: 2,
              background: "var(--border)",
            }}
          />
          {p.proposed_bills.map((b) => (
            <div key={b.id} style={{ display: "flex", gap: 12, marginBottom: 10 }}>
              {/* 날짜 */}
              <div
                className="muted"
                style={{
                  width: 60,
                  flexShrink: 0,
                  fontSize: 12.5,
                  textAlign: "right",
                  paddingTop: 14,
                  lineHeight: 1.3,
                }}
              >
                {fmtTimelineDate(b.proposed_date)}
              </div>
              {/* 점 */}
              <div style={{ position: "relative", width: 2, flexShrink: 0 }}>
                <span
                  style={{
                    position: "absolute",
                    left: -4,
                    top: 16,
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: "var(--primary)",
                    border: "2px solid var(--bg)",
                  }}
                />
              </div>
              {/* 법안 카드 */}
              <Link
                href={`/bill/${b.id}`}
                className="card"
                style={{ display: "block", textDecoration: "none", flex: 1, marginLeft: 8 }}
              >
                <div style={{ fontWeight: 600, color: "var(--fg)" }}>{b.title}</div>
                <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                  의안 {b.bill_no}
                  {b.status ? ` · ${b.status}` : ""} →
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
      {p.proposed_count > p.proposed_bills.length && (
        <p className="muted" style={{ fontSize: 13 }}>
          최근 {p.proposed_bills.length}건 표시 · 외 {p.proposed_count - p.proposed_bills.length}건 더
        </p>
      )}

      {/* 본회의 표결 참여 */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>본회의 표결 참여</h3>
      {vs.total === 0 ? (
        <p className="muted" style={{ fontSize: 14 }}>
          표결 기록이 아직 없어요. (실데이터 적재 후 채워집니다)
        </p>
      ) : (
        <div className="card" style={{ display: "flex", gap: 14, flexWrap: "wrap" }}>
          <VoteStat label="찬성" n={vs.yes} />
          <VoteStat label="반대" n={vs.no} />
          <VoteStat label="기권" n={vs.abstain} />
          <VoteStat label="불참" n={vs.absent} />
        </div>
      )}

      {/* 🟡 중립 고지 + 출처 */}
      <div className="disclaimer" style={{ marginTop: 24 }}>
        ⚖️ {p.notice}
        {p.profile_source_url && (
          <>
            <br />
            <a href={p.profile_source_url} target="_blank" rel="noreferrer">
              프로필 출처 ↗
            </a>
          </>
        )}
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card" style={{ flex: 1, textAlign: "center", margin: 0, padding: "12px 8px" }}>
      <div className="numeral" style={{ fontSize: 19 }}>{value}</div>
      <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function VoteStat({ label, n }: { label: string; n: number }) {
  return (
    <div style={{ textAlign: "center", minWidth: 56 }}>
      <div className="numeral" style={{ fontSize: 18 }}>{n}</div>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
    </div>
  );
}
