const defaultProxyTarget =
  process.env.NODE_ENV === "development"
    ? "http://localhost:8000/api/v1"
    : "http://api:8000/api/v1";
const proxyTarget = (process.env.NEXT_SERVER_API_PROXY || defaultProxyTarget).replace(/\/+$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  eslint: {
    // Keep lint in a separate CI/local step to reduce production build cost.
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Skip heavyweight type checking on constrained builders.
    ignoreBuildErrors: true,
  },
  experimental: {
    // Next.js documents this as a low-risk way to lower peak webpack memory.
    webpackMemoryOptimizations: true,
    // Dev rewrite proxy defaults to 30s; chat with deepseek-v4-pro can take 30-58s
    // (API gateway timeout is ML_SERVICE_TIMEOUT_SECONDS=150). Keep above that.
    proxyTimeout: 180_000,
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "hitechcloud.vn" },
      { protocol: "https", hostname: "www.hitechcloud.vn" },
      { protocol: "https", hostname: "bnix.vn" },
      { protocol: "https", hostname: "www.bnix.vn" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${proxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
