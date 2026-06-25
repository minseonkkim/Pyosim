# 표심 프론트엔드 (Next.js 15) — Cloud Run 서비스용 (standalone)
# ⚠️ NEXT_PUBLIC_API_BASE 는 빌드 시점에 번들에 박힌다.
#    백엔드 URL 을 먼저 확정한 뒤 --build-arg 로 주입할 것.
#    빌드 예: docker build -t <IMAGE> --build-arg NEXT_PUBLIC_API_BASE=https://api... ./frontend

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ARG NEXT_PUBLIC_GA_ID
ENV NEXT_PUBLIC_GA_ID=$NEXT_PUBLIC_GA_ID
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=8080 \
    HOSTNAME=0.0.0.0
# standalone 출력물 + 정적 자산
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 8080
CMD ["node", "server.js"]
