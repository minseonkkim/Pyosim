# 표심 · Pyosim — _Where do you stand?_

국회 데이터로 민심과 국회 사이의 거리를 보여주는 정치 정보 서비스.
정치인, 법안, 청원, 입법예고, 세금을 한데 모아 흩어진 공식 데이터를 한 화면에서 본다.

🔗 바로가기: https://pyosim-web-785567251954.asia-northeast3.run.app

기획·설계 문서는 [docs/](docs/)에 있다.

- [기획서](docs/기획서.md)
- [개발 로드맵(체크리스트)](docs/로드맵.md)
- [외부 API 카탈로그](docs/외부_API.md)
- [데이터 출처·고지 정책](docs/데이터_출처_고지_정책.md)
- [디자인 시스템](docs/디자인_시스템.md)
- [배포 가이드](infra/배포_가이드.md) · [자동 갱신 스케줄링](infra/스케줄링.md)
- [커밋 컨벤션](docs/커밋_컨벤션.md)

## 주요 기능

사람·법안·민심 세 축을 연결 키로 묶었다. 모든 화면에는 공식 1차 출처 링크와 중립 고지를 같이 붙인다(사실만 보여주고 판정은 하지 않음).

- **정치인 프로필** (`/persons`, `/person/[id]`) — 현역 300명 전수. 정당·지역구·사진·나이·선수·위원회 경력, 대표발의 법안 타임라인, 표결 요약.
- **법안** (`/bills`, `/bill/[id]`) — 논쟁이 있었던 정책 법안만 추려서 보여주는 피드(생활 카테고리 12개로 필터). 상세에는 제안이유·주요내용 원문, 처리 단계 타임라인, 정당별 찬반, AI가 정리한 좋은 점/문제점(원문과 분리, 양쪽 대칭으로 생성).
- **국민청원 추적** (`/petitions`, `/petition/[id]`) — 접수→회부→심사→처리 단계로 "그 청원 지금 어디?"를 따라간다.
- **입법예고 시민 찬반** — 법안 상세 안에 통합. 시민 찬반 집계와 국회 처리 결과를 한 화면에서 비교한다.
- **감시견 알림** (`/watch`) — 청원·법안·의원을 구독하면 상태가 바뀔 때 앱 안 받은함으로 알려준다. 익명 세션 기반(계정·개인정보 없음)이라, 하루 한 번 자동 갱신으로 점등된다.
- **세금 계산기** (`/tax`) — 월급을 넣으면 세금을 추정하고 분야별 쓰임을 도넛으로 보여준다. 본예산(계획)과 결산(실제)의 차이도 같이 보여준다(열린재정 연동).
- **성향 매칭 테스트** (`/test` → `/result` → `/share`) — 정당·의원 일치율과 공유 카드.

## 모노레포 구조

```
pyosim/
├─ frontend/   # Next.js 15 (App Router) + TS — SSR 상세 페이지·OG·sitemap·GA4
├─ backend/    # FastAPI — REST API (persons/bills/petitions/watch/budget/health)
├─ etl/        # 데이터 수집·정규화 잡 (열린국회·열린재정·pal·likms)
├─ infra/      # docker-compose, Cloud Run 배포 스크립트·문서
└─ docs/       # 기획·설계 문서
```

**스택**: Next.js 15 + React 19 + Recharts / FastAPI + SQLAlchemy + Alembic / PostgreSQL.
법안 AI 요약은 로컬 Ollama(기본)나 Gemini를 쓴다. 운영은 GCP Cloud Run(API·Web·ETL Job·Cloud SQL).
외부 API rate limit 때문에 자체 DB에 캐싱해 둔다.

## 로컬 실행법

### 0. 사전 준비

- Node.js 20+ / npm
- Python 3.10+
- PostgreSQL 15+ (Docker 권장)
- (선택) AI 요약용 [Ollama](https://ollama.com) — `ollama pull qwen2.5:7b`
- 외부 API Key 발급 (아래 "외부 API" 참조)

### 1. 환경변수

각 디렉터리의 `.env.example`를 복사해 채운다.

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

없으면 로컬 PostgreSQL에 `pyosim` DB를 만들고 `.env`의 `DATABASE_URL`을 맞춘다.

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
python -m jobs.run --job ping              # 동작 확인
python -m jobs.run --job members           # 현역 의원 300명
python -m jobs.run --job bills             # 법안
python -m jobs.run --job daily             # 하루 한 번 자동 갱신 세트
```

주요 잡: `members` · `photos` · `bills` · `vote_records` · `proposers` · `committees` ·
`bill_stages` · `petitions` · `lawnotices` · `lawnotice_opinions` ·
`bill_content` · `bill_summary` · `categorize` · `budget` · `daily`.
전체 목록과 설명은 [etl/jobs/run.py](etl/jobs/run.py) 맨 위 docstring에 있다.

### 5. 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

→ http://localhost:3000

## 외부 API (발급 필요)

| 소스                                  | 용도                          | 환경변수            | 발급처               |
| ------------------------------------- | ----------------------------- | ------------------- | -------------------- |
| 열린국회정보 (open.assembly.go.kr)    | 의원·법안·표결·위원회·청원    | `ASSEMBLY_API_KEY`  | open.assembly.go.kr  |
| 열린재정 (openfiscaldata.go.kr)       | 분야별 결산·예산 (세금 도구)  | `OFD_API_KEY`       | openfiscaldata.go.kr |
| 선관위 / 공공데이터포털 (data.go.kr)  | 후보자 전과·재산 (Phase 2~3)  | `NEC_API_KEY` 등    | data.go.kr           |

열린국회 키 하나로 위원회·청원·입법예고·공동발의 등 여러 서비스를 호출할 수 있다. 자세한 건 [docs/외부_API.md](docs/외부_API.md) 참조.

발급한 키는 각 `.env`에 넣는다. 동작 확인: `python etl/scripts/check_api_keys.py`

AI 요약은 `SUMMARY_PROVIDER`로 고른다 — `ollama`(기본, 로컬·무료)나 `gemini`(`GEMINI_API_KEY` 필요).

## 배포

`main`에 push하면 GitHub Actions가 GCP Cloud Run으로 자동 배포한다(Workload Identity Federation, 장기 키 없음).
수동 배포나 아키텍처, 자동 갱신 스케줄링은 [infra/배포_가이드.md](infra/배포_가이드.md), [infra/스케줄링.md](infra/스케줄링.md)에 정리해 뒀다.

- **Cloud Run**: `pyosim-api`(FastAPI) · `pyosim-web`(Next.js) · Job `pyosim-daily`(ETL)·`pyosim-migrate`
- **Cloud SQL**: `pyosim-db`(PostgreSQL 16)
- **Cloud Scheduler**: `pyosim-daily-trigger` — 매일 04:10 KST에 `--job daily` 실행

## 개발 현황

[로드맵](docs/로드맵.md) 참조. Phase 1(그물망 뼈대)과 Phase 2(민심 레이어) 핵심은 구현됐고, Phase 3(비교 대시보드)이 진행 중.
아직 안 들어온 데이터: 후보자 전과·재산(선관위 키 필요), 지역구(District) 정규화.
