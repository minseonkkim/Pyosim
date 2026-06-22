# 표심 백엔드 (FastAPI) — Cloud Run 서비스용
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 의존성 먼저 (레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 코드 (alembic.ini · migrations · app 포함)
COPY . .

# Cloud Run 은 $PORT(기본 8080)로 트래픽을 보냄
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
