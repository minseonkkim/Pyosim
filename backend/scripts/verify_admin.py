"""어드민 검토 end-to-end 검증 — Phase 2-3 (SQLite + TestClient).

backend 디렉터리에서: python scripts/verify_admin.py
스키마 생성 → 시드 → 어드민 토큰/인증 → 검토 큐 → 전이(승인 후 공개 노출) →
수정→재검토 → 반려 검증.
LLM generate 는 키가 없으면 503 을 기대(중립성 안전선: 키 없으면 자동 생성 비활성).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_DB = _BACKEND / "scripts" / ".verify_admin.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["ANTHROPIC_API_KEY"] = ""  # 키 없음 → generate 비활성 확인

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app import seed, seed_demo, seed_questions  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Question, QuestionStatus  # noqa: E402

AUTH = {"X-Admin-Token": "test-admin-token"}


def main() -> int:
    if _DB.exists():
        _DB.unlink()
    Base.metadata.create_all(engine)
    seed.run()
    seed_demo.run()
    seed_questions.run()

    client = TestClient(app)

    print("\n── 인증: 토큰 없음 → 401 ──")
    r = client.get("/admin/questions")
    assert r.status_code == 401, r.text
    r = client.get("/admin/questions", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401, r.text
    print("  토큰 미제공/오류 모두 401 ✅")

    print("\n── 검토 큐: 초안 목록 ──")
    r = client.get("/admin/questions", headers=AUTH)
    assert r.status_code == 200, r.text
    qs = r.json()
    print(f"  전체 문항 {len(qs)}개 (전부 초안)")
    assert qs and all(q["status"] == "초안" for q in qs)
    qid = qs[0]["id"]

    print("\n── 공개 API: 승인 0건이라 비노출 ──")
    pub = client.get("/api/questions").json()["questions"]
    assert len(pub) == 0, pub
    print("  공개(승인) 0건 ✅")

    print("\n── 전이: 잘못된 전이 차단(승인 상태에서 승인 불가 등) ──")
    # 초안 → 아카이브 직행은 규칙에 없음(아카이브는 승인에서만) → 409
    r = client.post(f"/admin/questions/{qid}/transition", headers=AUTH, json={"action": "아카이브"})
    assert r.status_code == 409, r.text
    # 반려는 사유 필수
    r = client.post(f"/admin/questions/{qid}/transition", headers=AUTH, json={"action": "반려"})
    assert r.status_code == 400, r.text
    print("  잘못된 전이 409 / 반려 사유 누락 400 ✅")

    print("\n── 전이: 검토시작 → 승인 ──")
    r = client.post(f"/admin/questions/{qid}/transition", headers=AUTH, json={"action": "검토시작"})
    assert r.status_code == 200 and r.json()["status"] == "검토중", r.text
    r = client.post(
        f"/admin/questions/{qid}/transition",
        headers=AUTH,
        json={"action": "승인", "by": "검수자A"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "승인" and body["approved_by"] == "검수자A", body
    print(f"  문항 #{qid} 승인(approved_by={body['approved_by']}) ✅")

    print("\n── 공개 API: 승인 1건 노출 ──")
    pub = client.get("/api/questions").json()["questions"]
    assert len(pub) == 1 and pub[0]["id"] == qid, pub
    print("  승인 문항만 공개됨 ✅")

    print("\n── 수정 → 승인 해제(재검토 강제) ──")
    r = client.patch(
        f"/admin/questions/{qid}", headers=AUTH, json={"body": "수정된 질문 본문?"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["body"] == "수정된 질문 본문?" and body["status"] == "검토중", body
    assert body["approved_by"] is None
    pub = client.get("/api/questions").json()["questions"]
    assert len(pub) == 0, pub  # 다시 비공개
    print("  승인 문항 수정 시 검토중으로 환원 + 비공개 ✅")

    print("\n── 반려(사유) → 아카이브 + review_note ──")
    qid2 = qs[1]["id"]
    r = client.post(
        f"/admin/questions/{qid2}/transition",
        headers=AUTH,
        json={"action": "반려", "note": "한쪽 선택지가 우월하게 들림"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "아카이브" and body["review_note"].startswith("[반려]"), body
    print(f"  문항 #{qid2} 반려: {body['review_note']} ✅")

    print("\n── LLM generate: 키 없으면 503(자동 생성 비활성) ──")
    bill_id = next((q["bill_id"] for q in qs if q["bill_id"]), None)
    if bill_id:
        r = client.post("/admin/questions/generate", headers=AUTH, json={"bill_id": bill_id})
        assert r.status_code == 503, r.text
        print(f"  generate 503: {r.json()['detail'][:40]}… ✅")

    with SessionLocal() as s:
        approved = s.scalars(
            select(Question).where(Question.status == QuestionStatus.승인)
        ).all()
        print(f"\n  최종 승인 문항 수: {len(approved)} (수정으로 0이 정상)")

    print("\n✅ 어드민 검토 end-to-end 검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
