"""시드 데이터 — 정당(+color_hex), 쟁점 7축.

실행: python -m app.seed
멱등(이미 있으면 건너뜀).
"""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Issue, Party

# 22대 국회 주요 원내정당 (color_hex 는 각 당 공식/통용 색, 추후 검증·갱신)
PARTIES: list[tuple[str, str]] = [
    ("더불어민주당", "#152484"),
    ("국민의힘", "#E61E2B"),
    ("조국혁신당", "#0073CF"),
    ("개혁신당", "#FF7920"),
    ("진보당", "#D6001C"),
    ("기본소득당", "#00D2C3"),
    ("사회민주당", "#F58400"),
    ("무소속", "#777777"),
]

# 기획서 3-3 쟁점 7축
ISSUES: list[str] = [
    "노동",
    "복지·분배",
    "경제·시장",
    "안보·외교",
    "환경·기후",
    "젠더·가족",
    "사회질서·치안",
]


def run() -> None:
    db = SessionLocal()
    try:
        for name, color in PARTIES:
            exists = db.scalar(select(Party).where(Party.name == name))
            if not exists:
                db.add(Party(name=name, color_hex=color))

        for name in ISSUES:
            exists = db.scalar(select(Issue).where(Issue.name == name))
            if not exists:
                db.add(Issue(name=name))

        db.commit()
        n_party = db.scalar(select(Party).where(Party.id.isnot(None))) is not None
        print(f"seed 완료: 정당 {len(PARTIES)}개, 쟁점 {len(ISSUES)}축 (멱등)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
