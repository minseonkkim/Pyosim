#!/usr/bin/env bash
# GitHub Actions(Workload Identity) → Cloud Run 자동배포 1회 설정.
# WIF 풀/프로바이더/배포 SA 는 이미 생성됨. 이 스크립트는 "권한 부여"만 한다.
# 실행: bash infra/setup-github-actions.sh
set -euo pipefail

PROJECT_ID="project-01308378-97ce-4b8a-8d1"
PROJECT_NUMBER="785567251954"
REPO="minseonkkim/Pyosim"
SA="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

echo "▶ 배포 SA 에 역할 부여 (run 배포 + 이미지 푸시 + 런타임 SA 위임)"
for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:${SA}" --role "$role" --condition=None >/dev/null
  echo "  부여: $role"
done

echo "▶ GitHub 저장소($REPO)가 배포 SA 를 가장(impersonate)하도록 허용"
gcloud iam service-accounts add-iam-policy-binding "$SA" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-pool/attribute.repository/${REPO}" \
  >/dev/null
echo "  허용 완료"

echo "✅ 설정 끝. 이제 main 에 push 하면 자동 배포된다."
