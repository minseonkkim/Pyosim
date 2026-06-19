"use client";

// 정치인 목록 (Phase 1-2) — 그물망 '사람' 축 입구.
// 🟡 모든 의원을 같은 양식으로. 순위·점수 없이 나열, 검색/정당 필터만.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { fetchPersons, type PersonListItem } from "@/lib/api";
import { Avatar, PartyDot } from "./PersonBits";

export default function PersonsPage() {
  const [persons, setPersons] = useState<PersonListItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [party, setParty] = useState<string | null>(null);

  useEffect(() => {
    fetchPersons()
      .then(setPersons)
      .catch((e) => setErr((e as Error).message));
  }, []);

  const parties = useMemo(() => {
    const names = new Set<string>();
    persons?.forEach((p) => p.party && names.add(p.party.name));
    return [...names];
  }, [persons]);

  const filtered = useMemo(() => {
    if (!persons) return [];
    return persons.filter(
      (p) =>
        (!party || p.party?.name === party) &&
        (!q || p.name.includes(q) || (p.district ?? "").includes(q)),
    );
  }, [persons, party, q]);

  return (
    <main>
      <h1 style={{ fontSize: 24, marginBottom: 4 }}>국회의원</h1>
      <p className="muted" style={{ fontSize: 13.5, marginBottom: 16 }}>
        이름이나 지역으로 찾아보세요. 클릭하면 발의·표결·기록이 한 곳에 모여요.
      </p>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="이름 또는 지역구 검색"
        style={{
          width: "100%",
          padding: 12,
          fontSize: 15,
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-md)",
          background: "var(--surface)",
          color: "var(--fg)",
        }}
      />

      {parties.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "12px 0" }}>
          <FilterChip label="전체" active={party === null} onClick={() => setParty(null)} />
          {parties.map((name) => (
            <FilterChip
              key={name}
              label={name}
              active={party === name}
              onClick={() => setParty(name)}
            />
          ))}
        </div>
      )}

      {err && <p className="disclaimer">⚠️ 불러오지 못했어요: {err}</p>}
      {persons === null && !err && <p className="muted">불러오는 중…</p>}
      {persons !== null && filtered.length === 0 && (
        <p className="muted">조건에 맞는 의원이 없어요.</p>
      )}

      {filtered.map((p) => (
        <Link
          key={p.id}
          href={`/person/${p.id}`}
          className="card"
          style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}
        >
          <Avatar name={p.name} photo={p.photo_url} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, color: "var(--fg)" }}>{p.name}</div>
            <div className="muted" style={{ fontSize: 13 }}>
              {p.party && (
                <PartyDot color={p.party.color_hex} />
              )}
              {p.party?.name ?? "무소속"}
              {p.district ? ` · ${p.district}` : ""}
            </div>
          </div>
        </Link>
      ))}
    </main>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={active ? "btn" : "btn btn-ghost"}
      style={{ padding: "6px 12px", fontSize: 13, minHeight: 0 }}
    >
      {label}
    </button>
  );
}
