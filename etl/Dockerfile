# 표심 ETL (일 1회 배치) — Cloud Run Job 용
# ⚠️ 빌드 컨텍스트는 "레포 루트"여야 한다.
#    etl/jobs/db.py 가 ../backend(app.models)를 import 경로로 끌어쓰므로
#    backend/ 와 etl/ 디렉터리 구조를 그대로 유지해 함께 담는다.
#    빌드 예: docker build -f etl/Dockerfile -t <IMAGE> .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 의존성 먼저 (backend 모델 재사용 → backend 의존성도 필요)
COPY backend/requirements.txt backend/requirements.txt
COPY etl/requirements.txt etl/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r etl/requirements.txt

# 코드 (디렉터리 구조 유지: /app/backend, /app/etl)
COPY backend/ backend/
COPY etl/ etl/

# jobs.run 은 etl/ 에서 실행
WORKDIR /app/etl

# 기본 엔트리포인트 = 일일 자동 갱신. Job 정의에서 --args 로 덮어쓸 수 있음.
CMD ["python", "-m", "jobs.run", "--job", "daily", "--trigger", "scheduler"]
