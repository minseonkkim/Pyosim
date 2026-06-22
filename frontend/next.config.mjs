/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Cloud Run 컨테이너 배포용 — .next/standalone 에 self-contained server.js 생성
  output: "standalone",
};

export default nextConfig;
