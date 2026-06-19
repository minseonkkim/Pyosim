"use client";

// 정치인 프로필 상세 (Phase 1-2) — 그물망 허브.
// 발의 법안 → 법안(현재 likms 직링크), 표결 요약, 전과(🟡 출처 동반·동일 양식).

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { fetchPerson, type PersonProfile } from "@/lib/api";
import { Avatar, PartyDot } from "../../persons/PersonBits";

export default function PersonPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const [p, setP] = useState<PersonProfile | null | undefined>(undefined);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    fetchPerson(id)
      .then(setP)
      .catch((e) => {
        setErr((e as Error).message);
        setP(null);
      });
  }, [id]);

  if (p === undefined && !err) {
    return (
      <main>
        <p className="muted">불러오는 중…</p>
      </main>
    );
  }
  if (p === null || err) {
    return (
      <main>
        <h2>찾을 수 없어요</h2>
        <p className="muted">{err ?? "해당 의원이 없습니다."}</p>
        <Link href="/persons" className="btn btn-ghost">
          ← 목록으로
        </Link>
      </main>
    );
  }
  if (!p) return null;

  const vs = p.vote_summary;

  return (
    <main>
      <Link href="/persons" className="muted" style={{ fontSize: 13 }}>
        ← 국회의원
      </Link>

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
        </div>
      </div>

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
        p.proposed_bills.map((b) => (
          <div className="card" key={b.id}>
            <div style={{ fontWeight: 600 }}>{b.title}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              의안 {b.bill_no}
              {b.status ? ` · ${b.status}` : ""}
            </div>
            {b.likms_url && (
              <a
                href={b.likms_url}
                target="_blank"
                rel="noreferrer"
                style={{ fontSize: 13, fontWeight: 600 }}
              >
                의안정보시스템에서 보기 ↗
              </a>
            )}
          </div>
        ))
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

      {/* 전과 — 🟡 동일 양식·출처 동반 */}
      <h3 style={{ marginTop: 24, marginBottom: 8 }}>전과 기록</h3>
      {p.criminal_records.length === 0 ? (
        <p className="muted" style={{ fontSize: 14 }}>공개된 전과 기록이 없어요.</p>
      ) : (
        p.criminal_records.map((c, i) => (
          <div className="card" key={i}>
            <div style={{ fontWeight: 600 }}>{c.charge}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
              {[c.sentence, c.date_sentenced, c.is_final == null ? null : c.is_final ? "확정" : "미확정"]
                .filter(Boolean)
                .join(" · ")}
            </div>
            <div style={{ fontSize: 12, marginTop: 6 }}>
              {c.source_url ? (
                <a href={c.source_url} target="_blank" rel="noreferrer">
                  출처 ↗
                </a>
              ) : (
                <span className="muted">출처 미연동(데모)</span>
              )}
            </div>
          </div>
        ))
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
