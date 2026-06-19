"use client";

// 어드민 검토 대기열 (Phase 2-3, 👤 human-in-the-loop)
// 자동/사람 작성 초안 → 검토·수정·승인/반려. 승인 문항만 공개된다.
// 토큰은 localStorage 에만 보관(서버 계정 없음). 운영 노출 시 별도 보호 권장.

import { useCallback, useEffect, useState } from "react";

import {
  type AdminQuestion,
  type TransitionAction,
  getAdminToken,
  setAdminToken,
  listQuestions,
  patchQuestion,
  transitionQuestion,
} from "@/lib/admin";

const STATUS_TABS = ["전체", "초안", "검토중", "승인", "아카이브"] as const;
const STATUS_COLOR: Record<string, string> = {
  초안: "var(--ink-400)",
  검토중: "#B8860B",
  승인: "#1F7A3D",
  아카이브: "var(--ink-300)",
};

export default function AdminPage() {
  const [token, setToken] = useState("");
  const [authed, setAuthed] = useState(false);
  const [tab, setTab] = useState<(typeof STATUS_TABS)[number]>("초안");
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = getAdminToken();
    if (t) {
      setToken(t);
      setAuthed(true);
    }
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const status = tab === "전체" ? undefined : tab;
      setQuestions(await listQuestions(status));
      setAuthed(true);
    } catch (e) {
      setErr((e as Error).message);
      if ((e as Error).message.includes("토큰") || (e as Error).message.includes("401"))
        setAuthed(false);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    if (authed) reload();
  }, [authed, reload]);

  function saveToken() {
    setAdminToken(token.trim());
    setAuthed(true);
  }

  function logout() {
    setAdminToken("");
    setAuthed(false);
    setQuestions([]);
  }

  async function act(fn: () => Promise<unknown>) {
    setErr(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setErr((e as Error).message);
    }
  }

  if (!authed) {
    return (
      <main>
        <h1 style={{ fontSize: 22 }}>어드민 검토</h1>
        <p className="muted">검토 토큰을 입력하세요. (백엔드 ADMIN_TOKEN)</p>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="ADMIN_TOKEN"
          style={{ width: "100%", padding: 12, marginTop: 8, fontSize: 15 }}
        />
        <button className="btn btn-block" style={{ marginTop: 10 }} onClick={saveToken}>
          접속
        </button>
        {err && <p className="disclaimer">⚠️ {err}</p>}
      </main>
    );
  }

  return (
    <main>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ fontSize: 22 }}>어드민 검토</h1>
        <button className="btn btn-ghost" onClick={logout} style={{ padding: "6px 12px" }}>
          로그아웃
        </button>
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        🟡 승인된 문항만 공개됩니다. 자동(LLM) 초안은 반드시 사람 승인 후에만 노출.
      </p>

      {/* 상태 탭 */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "12px 0" }}>
        {STATUS_TABS.map((s) => (
          <button
            key={s}
            className={tab === s ? "btn" : "btn btn-ghost"}
            style={{ padding: "6px 12px", fontSize: 13 }}
            onClick={() => setTab(s)}
          >
            {s}
          </button>
        ))}
      </div>

      {err && <p className="disclaimer">⚠️ {err}</p>}
      {loading && <p className="muted">불러오는 중…</p>}

      {questions.map((q) => (
        <QuestionCard key={q.id} q={q} onAct={act} />
      ))}
      {!loading && questions.length === 0 && (
        <p className="muted">해당 상태의 문항이 없습니다.</p>
      )}
    </main>
  );
}

function QuestionCard({
  q,
  onAct,
}: {
  q: AdminQuestion;
  onAct: (fn: () => Promise<unknown>) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(q);

  const fields: [keyof AdminQuestion, string][] = [
    ["body", "질문(생활 언어)"],
    ["option_a_label", "Ⓐ 선택지(찬성 방향)"],
    ["option_a_pro", "Ⓐ 장점"],
    ["option_a_con", "Ⓐ 단점"],
    ["option_b_label", "Ⓑ 선택지(반대 방향)"],
    ["option_b_pro", "Ⓑ 장점"],
    ["option_b_con", "Ⓑ 단점"],
    ["source_note", "출처 메모"],
  ];

  async function save() {
    const patch: Partial<AdminQuestion> = {};
    for (const [k] of fields) {
      if (draft[k] !== q[k]) (patch as Record<string, unknown>)[k] = draft[k];
    }
    await onAct(() => patchQuestion(q.id, patch));
    setEditing(false);
  }

  function transition(action: TransitionAction) {
    let note: string | undefined;
    if (action === "반려") {
      note = window.prompt("반려 사유를 입력하세요(필수):") ?? undefined;
      if (!note) return;
    }
    const by = action === "승인" ? window.prompt("검수자 이름:", "admin") ?? "admin" : undefined;
    return onAct(() => transitionQuestion(q.id, action, { note, by }));
  }

  return (
    <div className="card">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span
          className="chip"
          style={{ background: STATUS_COLOR[q.status] ?? "var(--ink-400)", color: "#fff" }}
        >
          {q.status}
        </span>
        <span className="chip">{q.issue}</span>
        <span className="muted" style={{ fontSize: 12 }}>
          #{q.id} · {q.created_by === "auto" ? "🤖 자동" : "✍️ 사람"}
          {q.approved_by && ` · 승인:${q.approved_by}`}
        </span>
      </div>

      {!editing ? (
        <>
          <div style={{ fontWeight: 600, margin: "10px 0 8px" }}>{q.body}</div>
          <div style={{ fontSize: 13.5, lineHeight: 1.6 }}>
            <b>Ⓐ {q.option_a_label}</b> — 👍 {q.option_a_pro} / 👎 {q.option_a_con}
            <br />
            <b>Ⓑ {q.option_b_label}</b> — 👍 {q.option_b_pro} / 👎 {q.option_b_con}
          </div>
          {q.source_note && (
            <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>출처: {q.source_note}</p>
          )}
          {q.review_note && (
            <p
              style={{
                fontSize: 12.5,
                marginTop: 6,
                color: q.review_note.startsWith("[반려]") ? "#B00" : "var(--ink-500)",
              }}
            >
              📝 {q.review_note}
            </p>
          )}
        </>
      ) : (
        <div style={{ marginTop: 10 }}>
          {fields.map(([k, label]) => (
            <label key={k} style={{ display: "block", marginBottom: 8 }}>
              <span className="muted" style={{ fontSize: 12 }}>{label}</span>
              <textarea
                value={(draft[k] as string) ?? ""}
                onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                rows={k === "body" ? 2 : 1}
                style={{ width: "100%", padding: 8, fontSize: 14 }}
              />
            </label>
          ))}
        </div>
      )}

      {/* 액션 */}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 10 }}>
        {editing ? (
          <>
            <button className="btn" style={{ padding: "6px 12px", fontSize: 13 }} onClick={save}>
              저장
            </button>
            <button
              className="btn btn-ghost"
              style={{ padding: "6px 12px", fontSize: 13 }}
              onClick={() => {
                setDraft(q);
                setEditing(false);
              }}
            >
              취소
            </button>
          </>
        ) : (
          <>
            <button
              className="btn btn-ghost"
              style={{ padding: "6px 12px", fontSize: 13 }}
              onClick={() => setEditing(true)}
            >
              수정
            </button>
            {q.status === "초안" && (
              <Act label="검토시작" onClick={() => transition("검토시작")} />
            )}
            {(q.status === "초안" || q.status === "검토중") && (
              <>
                <Act label="승인" onClick={() => transition("승인")} />
                <Act label="반려" onClick={() => transition("반려")} danger />
              </>
            )}
            {q.status === "승인" && (
              <Act label="아카이브" onClick={() => transition("아카이브")} />
            )}
            {(q.status === "검토중" || q.status === "아카이브") && (
              <Act label="초안복귀" onClick={() => transition("초안복귀")} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Act({
  label,
  onClick,
  danger,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <button
      className="btn"
      style={{
        padding: "6px 12px",
        fontSize: 13,
        background: danger ? "#B00020" : undefined,
      }}
      onClick={onClick}
    >
      {label}
    </button>
  );
}
