import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";

const nextConfig: NextConfig = {
  output: "standalone",
  // P12 (2026-04-25) — Next dev 가 127.0.0.1 origin 에서 _next/* 요청을 받을 때
  // 경고 (cross-origin) 띄우는 것을 명시적으로 허용. 미허용 시 future major Next 에서 차단됨.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  // Authoring AI (2026-05-05): Opus capability 호출이 30~40s 걸려서 default 30s
  // proxyTimeout 으로 ECONNRESET → 500 발생. 5분으로 확장.
  experimental: {
    proxyTimeout: 300_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
