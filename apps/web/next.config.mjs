const proxyTarget = (process.env.NEXT_SERVER_API_PROXY || "http://api:8000/api/v1").replace(/\/+$/, "");

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
