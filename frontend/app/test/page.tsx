"use client";

// 테스트 진행 UI (Phase 1-3) — 진행률, Ⓐ/Ⓑ/모름, ▼출처 접기, 중간 저장.
// 이탈 방지: 한 화면에 한 문항, 선택 시 자동 진행, 이전/다음 이동.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  fetchQuestions,
  submitResults,
  type Choice,
  type Question,
} from "@/lib/api";
import Loading from "@/app/Loading";
import {
  getSessionId,
  loadAnswers,
  saveAnswers,
  clearAnswers,
  stashResult,
  type AnswerMap,
} from "@/lib/session";
import { track } from "@/lib/analytics";

export default function TestPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<AnswerMap>({});
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchQuestions(true)
      .then((res) => {
        setQuestions(res.questions);
        setNotice(res.notice);
        const saved = loadAnswers();
        setAnswers(saved);
        // 저장된 답이 있으면 첫 미응답 문항으로 점프
        const firstUnanswered = res.questions.findIndex((q) => !(q.id in saved));
        setIdx(firstUnanswered === -1 ? res.questions.length - 1 : firstUnanswered);
        track("test_start", { total: res.questions.length });
      })
      .catch((e) =>
        setError(
          `문항을 불러오지 못했어요. 백엔드(API)가 켜져 있는지 확인해 주세요.\n(${e})`,
        ),
      );
  }, []);

  // 문항 노출 추적 — 어느 문항에서 이탈하는지(드롭오프) 측정.
  useEffect(() => {
    if (!questions || !questions[idx]) return;
    track("question_view", {
      idx,
      total: questions.length,
      question_id: questions[idx].id,
    });
  }, [idx, questions]);

  if (error) {
    return (
      <main>
        <h2>앗, 문제가 생겼어요</h2>
        <p className="muted" style={{ whiteSpace: "pre-wrap" }}>
          {error}
        </p>
        <button className="btn btn-ghost" onClick={() => location.reload()}>
          다시 시도
        </button>
      </main>
    );
  }

  if (!questions) {
    return <Loading text="문항을 불러오는 중…" />;
  }

  const total = questions.length;
  const q = questions[idx];

  // 문항이 없거나 idx가 범위를 벗어난 경우(예: 빈 응답) 안전하게 처리.
  if (!q) {
    return (
      <main>
        <h2>표시할 문항이 없어요</h2>
        <p className="muted">아직 등록된 테스트 문항이 없습니다. 잠시 후 다시 시도해 주세요.</p>
        <button className="btn btn-ghost" onClick={() => location.reload()}>
          다시 시도
        </button>
      </main>
    );
  }

  const answeredCount = Object.keys(answers).length;
  const selected = answers[q.id];

  function choose(choice: Choice) {
    const next = { ...answers, [q.id]: choice };
    setAnswers(next);
    saveAnswers(next);
    track("answer", { idx, question_id: q.id, choice });
    // 마지막 문항이 아니면 살짝 뒤 자동 진행.
    // 빠른 연타 시 타이머가 여러 개 쌓여 idx가 2칸 이상 점프(문항 건너뜀)하지 않도록,
    // 클릭 시점의 다음 문항으로만 이동하고 이미 넘어갔으면 무시한다.
    if (idx < total - 1) {
      const target = idx + 1;
      setTimeout(() => setIdx((i) => (i === idx ? target : i)), 220);
    }
  }

  async function finish() {
    setSubmitting(true);
    setError(null);
    try {
      const payload = (questions ?? []).map((qq) => ({
        question_id: qq.id,
        choice: answers[qq.id],
      }));
      const result = await submitResults(getSessionId(), payload);
      track("test_complete", {
        answered: result.answered,
        skipped: result.skipped,
      });
      stashResult(result);
      clearAnswers();
      router.push("/result");
    } catch (e) {
      setError(String(e));
      setSubmitting(false);
    }
  }

  const allAnswered = questions.every((qq) => qq.id in answers);
  const isLast = idx === total - 1;

  return (
    <main>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: 13,
          color: "var(--muted)",
        }}
      >
        <span>
          {idx + 1} / {total}
        </span>
        <span>{q.issue}</span>
      </div>
      <div className="progress" aria-hidden>
        <span style={{ width: `${((idx + 1) / total) * 100}%` }} />
      </div>

      <h2 style={{ fontSize: 21, lineHeight: 1.45, marginTop: 8 }}>{q.body}</h2>

      <ChoiceCard
        label={`Ⓐ ${q.option_a.label ?? ""}`}
        pro={q.option_a.pro}
        con={q.option_a.con}
        active={selected === "찬성"}
        onClick={() => choose("찬성")}
      />
      <ChoiceCard
        label={`Ⓑ ${q.option_b.label ?? ""}`}
        pro={q.option_b.pro}
        con={q.option_b.con}
        active={selected === "반대"}
        onClick={() => choose("반대")}
      />
      <button
        className={`choice${selected === "모름" ? " selected" : ""}`}
        onClick={() => choose("모름")}
        style={{ textAlign: "center" }}
      >
        <span className="choice-label" style={{ margin: 0 }}>
          잘 모르겠어요
        </span>
      </button>

      {q.source_note && (
        <details
          className="source"
          onToggle={(e) => {
            if ((e.target as HTMLDetailsElement).open)
              track("source_open", { question_id: q.id });
          }}
        >
          <summary>원래 어떤 법안인지 ▼</summary>
          <p style={{ marginBottom: 4 }}>{q.source_note}</p>
          {q.likms_url && (
            <a href={q.likms_url} target="_blank" rel="noreferrer">
              의안정보시스템에서 보기 ↗
            </a>
          )}
        </details>
      )}

      <div style={{ display: "flex", gap: 10, marginTop: 24 }}>
        <button
          className="btn btn-ghost"
          disabled={idx === 0}
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
        >
          ← 이전
        </button>
        {isLast ? (
          <button
            className="btn"
            style={{ flex: 1 }}
            disabled={!allAnswered || submitting}
            onClick={finish}
          >
            {submitting
              ? "계산 중…"
              : allAnswered
                ? "결과 보기 →"
                : `남은 문항 ${total - answeredCount}개`}
          </button>
        ) : (
          <button
            className="btn"
            style={{ flex: 1 }}
            disabled={!selected}
            onClick={() => setIdx((i) => Math.min(total - 1, i + 1))}
          >
            다음 →
          </button>
        )}
      </div>

      {notice && (
        <p style={{ marginTop: 18, fontSize: 12, color: "var(--muted)" }}>
          {notice}
        </p>
      )}
    </main>
  );
}

function ChoiceCard({
  label,
  pro,
  con,
  active,
  onClick,
}: {
  label: string;
  pro: string | null;
  con: string | null;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button className={`choice${active ? " selected" : ""}`} onClick={onClick}>
      <div className="choice-label">{label}</div>
      {pro && (
        <div className="choice-row">
          <b>좋은 점</b> · {pro}
        </div>
      )}
      {con && (
        <div className="choice-row">
          <b>아쉬운 점</b> · {con}
        </div>
      )}
    </button>
  );
}
