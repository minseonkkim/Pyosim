#!/usr/bin/env bash
# 프로덕션 DB에 '안 나오던' 기능들의 데이터를 1회 적재한다.
#   1) 설문 문항        (seed_questions)        → /test
#   2) 위원회 엔티티     (committees)            → /tax 분야 토글의 '소관 위원회', 의원 프로필
#   3) 입법예고 시민의견 (lawnotice_opinions)    → /bills?view=opinions
#   4) 의원 출석률       (attendance)            → 의원 프로필 출석률 (DB 표결기록에서 계산)
#
# 이 잡들은 daily 자동 갱신 세트에 없어 프로덕션에서 한 번도 안 돌았다(스케줄링.md 참조).
# 기존 pyosim-daily 잡과 동일한 Cloud SQL 연결·시크릿을 그대로 복제한 일회성 Job.
# 멱등(seed/upsert)하므로 재실행해도 안전하다.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-project-01308378-97ce-4b8a-8d1}"
REGION="${REGION:-asia-northeast3}"
REPO="${REPO:-pyosim}"
DB_INSTANCE="${DB_INSTANCE:-pyosim-db}"

AR="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"
API_IMAGE="${AR}/api:latest"
ETL_IMAGE="${AR}/etl:latest"
CONN_NAME="${PROJECT_ID}:${REGION}:${DB_INSTANCE}"

gcloud config set project "$PROJECT_ID" >/dev/null

# 일회성 Job 정의 헬퍼: 같은 이름이 있으면 args만 갱신, 없으면 생성. 그 뒤 즉시 실행(--wait).
run_job () {                # run_job <job-name> <image> <secrets> <command> <args...>
  local name="$1" image="$2" secrets="$3" cmd="$4"; shift 4
  local args; args="$(IFS=,; echo "$*")"
  if gcloud run jobs describe "$name" --region "$REGION" >/dev/null 2>&1; then
    gcloud run jobs update "$name" --region "$REGION" \
      --image "$image" --set-cloudsql-instances "$CONN_NAME" \
      --set-secrets "$secrets" --command "$cmd" --args="$args" \
      --task-timeout 3600 --max-retries 1
  else
    gcloud run jobs create "$name" --region "$REGION" \
      --image "$image" --set-cloudsql-instances "$CONN_NAME" \
      --set-secrets "$secrets" --command "$cmd" --args="$args" \
      --task-timeout 3600 --max-retries 1
  fi
  echo "▶ 실행: $name"
  gcloud run jobs execute "$name" --region "$REGION" --wait
}

# 1) 설문 문항 — 백엔드(api) 이미지에서 app.seed_questions (DB만 필요)
run_job pyosim-seed-questions "$API_IMAGE" \
  "DATABASE_URL=database-url:latest" \
  python -m app.seed_questions

# 2) 위원회 엔티티 + 의원 위원회경력 — ETL 이미지 (열린국회 API)
run_job pyosim-committees "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest" \
  python -m jobs.run --job committees

# 3-a) 입법예고 메타데이터 — ETL 이미지 (열린국회 API).
#      ⚠️ 시민의견(3-b)의 선행 잡: LawNotice 테이블이 비어 있으면 의견 집계가 0건이 된다.
run_job pyosim-lawnotices "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest" \
  python -m jobs.run --job lawnotices

# 3-b) 입법예고 시민 찬반 의견 집계 — ETL 이미지(pal 스크랩, 느림). 위 메타가 있어야 동작.
run_job pyosim-lawnotice-opinions "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest" \
  python -m jobs.run --job lawnotice_opinions --limit 50

# 4) 의원 출석률 — ETL 이미지 (이미 적재된 표결기록의 '불참' 비율로 계산, DB만 필요)
run_job pyosim-attendance "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest" \
  python -m jobs.run --job attendance

# 5) 청원 본문(취지·내용·분야) — ETL 이미지 (국민동의청원 API). 목록은 차지만 상세 본문이 빈다.
run_job pyosim-petition-content "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest" \
  python -m jobs.run --job petition_content

# 6) 의원 사진 — ETL 이미지 (ALLNAMEMBER NAAS_PIC). photo_url 이 비면 의원 카드/프로필 사진이 안 뜬다.
run_job pyosim-photos "$ETL_IMAGE" \
  "DATABASE_URL=database-url:latest,ASSEMBLY_API_KEY=assembly-key:latest" \
  python -m jobs.run --job photos

echo "✅ 완료. 확인:"
echo "  curl -s '${API_IMAGE%%/api*}'  # (아래 API URL로)"
echo "  curl -s -A Mozilla https://pyosim-api-785567251954.asia-northeast3.run.app/api/questions?preview=true"
