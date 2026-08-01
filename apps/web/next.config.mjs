const defaultProxyTarget =
  process.env.NODE_ENV === "development"
    ? "http://localhost:8000/api/v1"
    : "http://api:8000/api/v1";
const proxyTarget = (
  process.env.NEXT_SERVER_API_PROXY || defaultProxyTarget
).replace(/\/+$/, "");

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "form-action 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "img-src 'self' data: blob: https://hitechcloud.vn https://www.hitechcloud.vn https://bnix.vn https://www.bnix.vn",
      "font-src 'self' data: https://fonts.gstatic.com",
      "connect-src 'self'",
      "media-src 'self' blob:",
      "worker-src 'self' blob:",
      "frame-src 'none'",
      "upgrade-insecure-requests",
    ].join("; "),
  },
  {
    key: "Strict-Transport-Security",
    value: "max-age=31536000; includeSubDomains",
  },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value:
      "accelerometer=(), autoplay=(), camera=(self), geolocation=(), gyroscope=(), magnetometer=(), microphone=(self), payment=(), usb=()",
  },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  poweredByHeader: false,
  eslint: {
    // Keep lint in a separate CI/local step to reduce production build cost.
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Skip heavyweight type checking on constrained builders.
    ignoreBuildErrors: true,
  },
  experimental: {
    cpus: 1,
    // Keep build artifacts in the main process; the build worker can leave an
    // incomplete .next directory on this environment before prerender starts.
    webpackBuildWorker: false,
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
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
};

export default nextConfig;
