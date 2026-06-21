# 표심 · Pyosim — _Where do you stand?_

실제 국회 표결 데이터로 내 정치 성향을 확인하고, 지금 진행 중인 법안에 직접 의견까지 낼 수 있는 정치 정보 서비스.

> **가장 큰 목적: 정치를 잘 모르는 사람이 정치에 관심을 가지게 하는 것.**
> 모든 설계 결정의 최우선 기준 — "모르는 사람이 이탈하지 않고 한 단계 더 들어오는가."

기획·설계 문서는 [docs/](docs/)에 있다.

- [기획서](docs/기획서.md)
- [개발 로드맵(체크리스트)](docs/로드맵.md)
- [데이터 출처·고지 정책](docs/데이터_출처_고지_정책.md) 🟡
- [자동 갱신 스케줄링](infra/스케줄링.md) 🤖 — 1일 1회 `--job daily`(감시견 알림 자동 점등)
- [커밋 컨벤션](docs/커밋_컨벤션.md)

## 모노레포 구조

```
pyosim/
├─ frontend/   # Next.js + TypeScript (테스트·결과·공유 카드)
├─ backend/    # FastAPI (REST + 어드민 문항 검토 API)
├─ etl/        # 데이터 수집·정규화 잡 (열린국회/선관위/공공데이터)
├─ infra/      # docker-compose, 배포 설정
└─ docs/       # 기획·설계 문서
```

**스택**: Next.js+TS / FastAPI / PostgreSQL / Cloud Run(또는 Vercel+Cloud Run).
API rate limit 대응을 위해 자체 DB 캐싱.

## 로컬 실행법

### 0. 사전 준비

- Node.js 20+ / npm
- Python 3.10+
- PostgreSQL 15+ (Docker 권장 — 미설치 시 로컬 Postgres 직접 사용)
- 외부 API Key 발급 (아래 "외부 API" 참조)

### 1. 환경변수

각 디렉터리의 `.env.example`를 복사해 `.env`로 채운다.

```bash
cp backend/.env.example backend/.env
cp etl/.env.example etl/.env
cp frontend/.env.example frontend/.env.local
```

### 2. 데이터베이스

Docker가 있으면:

```bash
docker compose -f infra/docker-compose.yml up -d db
```

Docker가 없으면 로컬 PostgreSQL에 `pyosim` DB를 만들고 `backend/.env`의 `DATABASE_URL`을 맞춘다.

### 3. 백엔드

```bash
cd backend
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# bash:                source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head        # 스키마 생성
python -m app.seed          # 정당 시드 데이터
uvicorn app.main:app --reload
```

→ http://localhost:8000/docs (Swagger)

### 4. ETL (데이터 수집)

```bash
cd etl
pip install -r requirements.txt
python -m jobs.run --job bills   # 예: 의안 수집 (구현 진행 중)
```

### 5. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

→ http://localhost:3000

## 외부 API (🔴 발급 필요)

| 소스                                  | 용도              | 발급처                  |
| ------------------------------------- | ----------------- | ----------------------- |
| 열린국회정보 (open.assembly.go.kr)    | 표결·법안·의원    | open.assembly.go.kr     |
| 선관위 (info.nec.go.kr)               | 후보자 전과·재산  | data.go.kr (선관위)     |
| 공공데이터포털 (data.go.kr)           | 선거구·정치자금   | data.go.kr              |

발급한 키는 각 `.env`에 넣는다. 키 동작 확인: `python etl/scripts/check_api_keys.py`

## 개발 현황

[로드맵](docs/로드맵.md) 참조. 현재 **Phase 0 (기반 공사)** 진행 중.
