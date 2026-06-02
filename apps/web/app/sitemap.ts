import type { MetadataRoute } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://clara.thiennn.icu").replace(/\/+$/, "");

const ROUTES = [
  "",
  "/login",
  "/register",
  "/research",
  "/council",
  "/selfmed",
  "/careguard",
  "/scribe",
  "/admin",
  "/legal",
  "/legal/privacy",
  "/legal/terms",
  "/legal/consent",
  "/legal/cookies",
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return ROUTES.map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified: now,
    changeFrequency: path === "" ? "daily" : "weekly",
    priority: path === "" ? 1 : path.startsWith("/legal") ? 0.7 : 0.8,
  }));
}

