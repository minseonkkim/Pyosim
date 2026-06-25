#!/usr/bin/env bash
# 표심 · Pyosim — GCP(Cloud Run) 배포 스크립트
# ─────────────────────────────────────────────────────────────────────────────
# 전제: gcloud CLI 로그인(`gcloud auth login`) + Docker 설치.
# 처음이면 docs: infra/배포_가이드.md 를 먼저 읽을 것. 단계별로 끊어 실행 권장.
#
#   bash infra/deploy.sh setup      # 1) API 활성화 + Artifact Registry
#   bash infra/deploy.sh db         # 2) Cloud SQL 인스턴스/DB/유저
#   bash infra/deploy.sh secrets    # 3) Secret Manager (대화형 입력)
#   bash infra/deploy.sh backend    # 4) 백엔드 이미지 빌드·배포
#   bash infra/deploy.sh migrate    # 5) alembic upgrade + seed (1회성 Job)
#   bash infra/deploy.sh frontend   # 6) 프론트 이미지 빌드·배포(백엔드 URL 주입)
#   bash infra/deploy.sh etl        # 7) ETL Job + Cloud Scheduler(매일 04:10 KST)
#   bash infra/deploy.sh all        # 4→7 한 번에(setup/db/secrets 완료 후)
set -euo pipefail

# ───────── 설정(환경변수로 덮어쓰기 가능) ─────────
PROJECT_ID="${PROJECT_ID:?PROJECT_ID 를 설정하세요 (예: export PROJECT_ID=my-proj)}"
REGION="${REGION:-asia-northeast3}"              # 서울
REPO="${REPO:-pyosim}"                           # Artifact Registry repo
DB_INSTANCE="${DB_INSTANCE:-pyosim-db}"
DB_NAME="${DB_NAME:-pyosim}"
DB_USER="${DB_USER:-pyosim}"
DB_TIER="${DB_TIER:-db-f1-micro}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="${REGION}-docker.pkg.dev"
IMG_BASE="${HOST}/${PROJECT_ID}/${REPO}"
API_IMAGE="${IMG_BASE}/api:latest"
ETL_IMAGE="${IMG_BASE}/etl:latest"
WEB_IMAGE="${IMG_BASE}/web:latest"
CONN_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"   # Cloud SQL 연결 이름

log() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

setup() {
  log "API 활성화 + Artifact Registry"
  gcloud config set project "$PROJECT_ID"
  gcloud services enable \
    run.googleapis.com sqladmin.googleapis.com artifactregistry.googleapis.com \
    cloudscheduler.googleapis.com secretmanager.googleapis.com cloudbuild.googleapis.com
  gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 || \
    gcloud artifacts repositories create "$REPO" \
      --repository-format=docker --location "$REGION" \
      --description="표심 컨테이너 이미지"
  gcloud auth configure-docker "$HOST" --quiet
}

db() {
  log "Cloud SQL (Postgres 16) — 인스턴스 생성은 수 분 소요"
  gcloud sql instances describe "$DB_INSTANCE" >/dev/null 2>&1 || \
    gcloud sql instances create "$DB_INSTANCE" \
      --database-version=POSTGRES_16 --tier="$DB_TIER" --region="$REGION"
  gcloud sql databases describe "$DB_NAME" --instance="$DB_INSTANCE" >/dev/null 2>&1 || \
    gcloud sql databases create "$DB_NAME" --instance="$DB_INSTANCE"
  echo "DB 유저 비밀번호를 입력하세요 (Secret 에도 동일하게 넣을 값):"
  read -rs DB_PW; echo
  gcloud sql users create "$DB_USER" --instance="$DB_INSTANCE" --password="$DB_PW" 2>/dev/null || \
    gcloud sql users set-password "$DB_USER" --instance="$DB_INSTANCE" --password="$DB_PW"
  echo "→ 연결 이름: $CONN_NAME"
  echo "→ 이어서 'secrets' 단계에서 DATABASE_URL 에 이 비밀번호를 쓰세요."
}

_secret() {  # _secret <name> <value>
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=-
  else
    printf '%s' "$2" | gcloud secrets create "$1" --data-file=-
  fi
}

secrets() {
  log "Secret Manager — 값 입력(엔터 시 건너뜀)"
  read -rsp "DB 비밀번호(DATABASE_URL 조립용): " DB_PW; echo
  local url="postgresql+psycopg://${DB_USER}:${DB_PW}@/${DB_NAME}?host=/cloudsql/${CONN_NAME}"
  _secret database-url "$url"
  read -rp "ASSEMBLY_API_KEY (열린국회): " v; [ -n "$v" ] && _secret assembly-key "$v" || true
  read -rp "GEMINI_API_KEY (법안 요약, 운영 provider): " v; [ -n "$v" ] && _secret gemini-key "$v" || true
  read -rp "NEC_API_KEY (선택, 엔터=건너뜀): " v; [ -n "$v" ] && _secret nec-key "$v" || true
  read -rp "DATA_GO_KR_API_KEY (선택): " v; [ -n "$v" ] && _secret datagokr-key "$v" || true
  read -rp "OFD_API_KEY (열린재정, 선택): " v; [ -n "$v" ] && _secret ofd-key "$v" || true
  echo "→ Cloud Run/Job 서비스계정에 secretmanager.secretAccessor 권한이 필요(가이드 참조)."
}

backend() {
  log "백엔드 빌드·배포"
  gcloud builds submit "$REPO_ROOT/backend" --tag "$API_IMAGE"
  gcloud run deploy pyosim-api \
    --image "$API_IMAGE" --region "$REGION" \
    --add-cloudsql-instances "$CONN_NAME" \
    --set-secrets "DATABASE_URL=database-url:latest,GEMINI_API_KEY=gemini-key:latest" \
    --set-env-vars "ENV=prod,SUMMARY_PROVIDER=gemini" \
    --allow-unauthenticated --port 8080
  api_url
}

api_url() {
  API_URL="$(gcloud run services describe pyosim-api --region "$REGION" --format='value(status.url)')"
  echo "→ 백엔드 URL: $API_URL"
}

migrate() {
  log "DB 마이그레이션 + 시드 (백엔드 이미지로 1회성 Job)"
  gcloud run jobs describe pyosim-migrate --region "$REGION" >/dev/null 2>&1 && \
    gcloud run jobs delete pyosim-migrate --region "$REGION" --quiet || true
  gcloud run jobs create pyosim-migrate \
    --image "$API_IMAGE" --region "$REGION" \
    --set-cloudsql-instances "$CONN_NAME" \
    --set-secrets "DATABASE_URL=database-url:latest" \
    --command sh \
    --args="-c,alembic upgrade head && python -m app.seed"
  gcloud run jobs execute pyosim-migrate --region "$REGION" --wait
}

frontend() {
  log "프론트 빌드·배포 (백엔드 URL 주입)"
  api_url
  local cfg; cfg="$(mktemp)"
  cat >"$cfg" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build","-t","$WEB_IMAGE","--build-arg","NEXT_PUBLIC_API_BASE=$API_URL","--build-arg","NEXT_PUBLIC_GA_ID=${GA_ID:-G-H39S9GR8PY}","."]
images: ["$WEB_IMAGE"]
YAML
  gcloud builds submit "$REPO_ROOT/frontend" --config "$cfg"
  rm -f "$cfg"
  gcloud run deploy pyosim-web \
    --image "$WEB_IMAGE" --region "$REGION" \
    --allow-unauthenticated --port 8080
  WEB_URL="$(gcloud run services describe pyosim-web --region "$REGION" --format='value(status.url)')"
  echo "→ 프론트 URL: $WEB_URL"
  log "백엔드 CORS 에 프론트 URL 추가"
  gcloud run services update pyosim-api --region "$REGION" \
    --update-env-vars "CORS_ORIGINS=$WEB_URL"
}

etl() {
  log "ETL Cloud Run Job + Cloud Scheduler"
  local cfg; cfg="$(mktemp)"
  cat >"$cfg" <<YAML
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build","-f","etl/Dockerfile","-t","$ETL_IMAGE","."]
images: ["$ETL_IMAGE"]
YAML
  gcloud builds submit "$REPO_ROOT" --config "$cfg"
  rm -f "$cfg"
  gcloud run jobs describe pyosim-daily --region "$REGION" >/dev/null 2>&1 && \
    gcloud run jobs delete pyosim-daily --region "$REGION" --quiet || true
  gcloud run jobs create pyosim-daily \
    --image "$ETL_IMAGE" --region "$REGION" \
    --set-cloudsql-instances "$CONN_NAME" \
    --set-secrets "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest,GEMINI_API_KEY=gemini-key:latest" \
    --set-env-vars "SUMMARY_PROVIDER=gemini" \
    --task-timeout 3600 --max-retries 1

  # Cloud Run/Scheduler 호출용 서비스계정
  local sa="pyosim-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
  gcloud iam service-accounts describe "$sa" >/dev/null 2>&1 || \
    gcloud iam service-accounts create pyosim-scheduler --display-name "표심 스케줄러"
  gcloud run jobs add-iam-policy-binding pyosim-daily --region "$REGION" \
    --member "serviceAccount:$sa" --role roles/run.invoker

  local uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/pyosim-daily:run"
  gcloud scheduler jobs describe pyosim-daily-trigger --location "$REGION" >/dev/null 2>&1 && \
    gcloud scheduler jobs delete pyosim-daily-trigger --location "$REGION" --quiet || true
  gcloud scheduler jobs create http pyosim-daily-trigger \
    --location "$REGION" \
    --schedule "10 4 * * *" --time-zone "Asia/Seoul" \
    --uri "$uri" --http-method POST \
    --oauth-service-account-email "$sa"
  echo "→ 매일 04:10 KST 자동 갱신 설정 완료. 즉시 테스트: gcloud run jobs execute pyosim-daily --region $REGION --wait"
}

case "${1:-}" in
  setup)    setup ;;
  db)       db ;;
  secrets)  secrets ;;
  backend)  backend ;;
  migrate)  migrate ;;
  frontend) frontend ;;
  etl)      etl ;;
  all)      backend; migrate; frontend; etl ;;
  *) echo "사용: bash infra/deploy.sh {setup|db|secrets|backend|migrate|frontend|etl|all}"; exit 1 ;;
esac
