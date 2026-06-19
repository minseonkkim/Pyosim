"""API end-to-end 검증 — SQLite + FastAPI TestClient (Postgres 불필요).

backend 디렉터리에서: python scripts/verify_api.py
스키마 생성 → 시드(정당·쟁점·앵커법안·문항) → /api/questions·/api/results 호출 검증.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_DB = _BACKEND / "scripts" / ".verify.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app import seed, seed_demo, seed_questions  # noqa: E402
from app.main import app  # noqa: E402


def main() -> int:
    if _DB.exists():
        _DB.unlink()
    Base.metadata.create_all(engine)
    seed.run()
    seed_demo.run()
    seed_questions.run()

    client = TestClient(app)

    print("\n── GET /api/parties ──")
    r = client.get("/api/parties")
    assert r.status_code == 200, r.text
    print(" ", [(p["name"], p["color_hex"]) for p in r.json()])

    print("\n── GET /api/questions (preview) ──")
    r = client.get("/api/questions", params={"preview": True})
    assert r.status_code == 200, r.text
    qs = r.json()["questions"]
    print(f"  문항 {len(qs)}개, notice={r.json()['notice']!r}")
    assert len(qs) == 8, f"문항 8개 기대, 실제 {len(qs)}"
    q0 = qs[0]
    print(f"  예시 #{q0['id']} [{q0['issue']}] {q0['body']}")
    print(f"    Ⓐ {q0['option_a']['label']}  /  Ⓑ {q0['option_b']['label']}")
    print(f"    출처: {q0['source_note']}")

    print("\n── GET /api/questions (공개=승인만) ──")
    r = client.get("/api/questions")
    pub = r.json()["questions"]
    print(f"  공개(승인) 문항 {len(pub)}개 (초안뿐이라 0이 정상)")
    assert len(pub) == 0

    print("\n── POST /api/results (전부 Ⓐ=찬성) ──")
    answers = [{"question_id": q["id"], "choice": "찬성"} for q in qs]
    r = client.post("/api/results", json={"session_id": "verify-sess", "answers": answers})
    assert r.status_code == 200, r.text
    res = r.json()
    print(f"  답함 {res['answered']} / 모름 {res['skipped']}")
    for m in res["party_match"]:
        bar = "█" * round(m["match_rate"] * 20)
        print(f"    {m['party']:8} {m['match_rate']*100:5.1f}%  {bar} ({m['matched']}/{m['total']})")
    print(f"  고지문: {res['disclaimer'][:40]}…")

    # 검증: '전부 찬성'이면 진보 성향(민/혁/진)이 높고 국민의힘이 낮아야 함(채점 방향 sanity)
    by = {m["party"]: m["match_rate"] for m in res["party_match"]}
    assert by["더불어민주당"] == 1.0, by
    assert by["국민의힘"] < by["더불어민주당"], by

    print("\n── POST /api/results (혼합 + 모름) ──")
    mixed = []
    for i, q in enumerate(qs):
        mixed.append({"question_id": q["id"], "choice": ["찬성", "반대", "모름"][i % 3]})
    r = client.post("/api/results", json={"session_id": "verify-sess2", "answers": mixed})
    res = r.json()
    print(f"  답함 {res['answered']} / 모름 {res['skipped']} / 정당 {len(res['party_match'])}개")
    assert res["skipped"] == sum(1 for m in mixed if m["choice"] == "모름")

    print("\n── POST /api/events (퍼널 로깅) ──")
    payload = {
        "session_id": "verify-sess",
        "events": [
            {"name": "landing"},
            {"name": "test_start", "props": {"total": 8}},
            {"name": "answer", "props": {"idx": 0, "choice": "찬성"}},
            {"name": "result_view", "props": {"answered": 6, "skipped": 2}},
            {"name": "삭제하라는_임의이벤트"},  # 화이트리스트 밖 → 버려져야 함
        ],
    }
    r = client.post("/api/events", content=json.dumps(payload), headers={"Content-Type": "text/plain"})
    assert r.status_code == 200, r.text
    accepted = r.json()["accepted"]
    print(f"  accepted={accepted} (화이트리스트 밖 1건 제외 → 4 기대)")
    assert accepted == 4, accepted

    from app.models import Event  # noqa: E402

    with SessionLocal() as s:
        names = sorted(e.name for e in s.scalars(select(Event)).all())
        print(f"  적재된 이벤트: {names}")
        assert "삭제하라는_임의이벤트" not in names
        assert len(names) == 4

    # ── 정치인 프로필 (Phase 1-2) ──
    print("\n── GET /api/persons (목록) ──")
    r = client.get("/api/persons")
    assert r.status_code == 200, r.text
    persons = r.json()
    print(f"  의원 {len(persons)}명 (데모 가상 4명 기대)")
    assert len(persons) >= 4, persons
    assert all(p["name"].startswith("[데모]") for p in persons)  # 데모 환경: 가상 인물만

    print("\n── GET /api/persons?q=이두리 ──")
    r = client.get("/api/persons", params={"q": "이두리"})
    hit = r.json()
    assert len(hit) == 1, hit
    pid = hit[0]["id"]

    print("\n── GET /api/persons/{id} (프로필 상세) ──")
    r = client.get(f"/api/persons/{pid}")
    assert r.status_code == 200, r.text
    prof = r.json()
    print(f"  {prof['name']} · {prof['party']['name']} · {prof['district']}")
    print(f"    출석률={prof['attendance_rate']} 대표발의={len(prof['proposed_bills'])}건 "
          f"전과={len(prof['criminal_records'])}건")
    assert prof["notice"], "🟡 중립 고지 동봉 필요"
    assert prof["criminal_records"], "데모 이두리에 가상 전과 1건 기대"
    # 🟡 전과는 동일 양식 필드를 갖춰야(출처 필드 포함)
    assert "source_url" in prof["criminal_records"][0]
    assert "vote_summary" in prof and prof["vote_summary"]["total"] == 0  # 데모: 표결기록 없음

    print("\n── 404 (없는 의원) ──")
    assert client.get("/api/persons/999999").status_code == 404

    # ── 법안 상세 (Phase 1-3) ──
    print("\n── GET /api/bills/{id} (법안 상세) ──")
    bid = prof["proposed_bills"][0]["id"]  # 이두리 대표발의 데모 법안
    r = client.get(f"/api/bills/{bid}")
    assert r.status_code == 200, r.text
    bill = r.json()
    print(f"  [{bill['bill_no']}] {bill['title'][:30]}")
    print(f"    대표발의={bill['proposer']['name'] if bill['proposer'] else None} "
          f"funnel={[s['label'] for s in bill['funnel'] if s['done']]}")
    assert bill["proposer"] and bill["proposer"]["name"] == "[데모] 이두리", bill["proposer"]
    assert len(bill["funnel"]) == 4 and bill["funnel"][0]["done"]  # 발의 done
    assert bill["notice"], "🟡 중립 고지 동봉 필요"
    assert bill["vote"] is None  # 데모: 본회의 표결 없음
    assert client.get("/api/bills/999999").status_code == 404

    print("\n✅ API end-to-end 검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
