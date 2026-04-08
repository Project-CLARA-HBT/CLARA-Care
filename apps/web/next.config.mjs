const proxyTarget = (process.env.NEXT_SERVER_API_PROXY || "http://api:8000/api/v1").replace(/\/+$/, "");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
