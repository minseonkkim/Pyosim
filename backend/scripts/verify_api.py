"""API end-to-end 검증 — SQLite + FastAPI TestClient (Postgres 불필요).

backend 디렉터리에서: python scripts/verify_api.py
스키마 생성 → 시드(정당·쟁점·앵커법안·문항) → /api/questions·/api/results 호출 검증.
"""
from __future__ import annotations

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

from app.db import Base, engine  # noqa: E402
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

    print("\n✅ API end-to-end 검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
