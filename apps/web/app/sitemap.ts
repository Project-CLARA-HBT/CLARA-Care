import type { MetadataRoute } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://theclaracare.com").replace(/\/+$/, "");

export type SitemapRoute = {
  path: string;
  changeFrequency: "always" | "hourly" | "daily" | "weekly" | "monthly" | "yearly" | "never";
  priority: number;
};

export const SITEMAP_ROUTES: readonly SitemapRoute[] = [
  // 1. Root
  { path: "", priority: 1.0, changeFrequency: "daily" },

  // 2. Primary Feature Hubs
  { path: "/chat", priority: 0.9, changeFrequency: "daily" },
  { path: "/lifemap", priority: 0.9, changeFrequency: "daily" },
  { path: "/medicines", priority: 0.9, changeFrequency: "daily" },
  { path: "/council", priority: 0.9, changeFrequency: "daily" },
  { path: "/scribe", priority: 0.9, changeFrequency: "daily" },
  { path: "/evidence", priority: 0.9, changeFrequency: "daily" },

  // 3. Safety, Trust & Guide Surfaces
  { path: "/huong-dan", priority: 0.85, changeFrequency: "weekly" },
  { path: "/safety", priority: 0.85, changeFrequency: "weekly" },
  { path: "/privacy", priority: 0.85, changeFrequency: "weekly" },
  { path: "/sources", priority: 0.8, changeFrequency: "weekly" },
  { path: "/clinical-standards", priority: 0.8, changeFrequency: "weekly" },

  // 4. Utility & Legal
  { path: "/login", priority: 0.7, changeFrequency: "monthly" },
  { path: "/register", priority: 0.7, changeFrequency: "monthly" },
  { path: "/contact", priority: 0.7, changeFrequency: "monthly" },
  { path: "/legal/privacy", priority: 0.6, changeFrequency: "monthly" },
  { path: "/legal/terms", priority: 0.6, changeFrequency: "monthly" },
  { path: "/legal/consent", priority: 0.6, changeFrequency: "monthly" },
  { path: "/legal/cookies", priority: 0.6, changeFrequency: "monthly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  return SITEMAP_ROUTES.map((route) => {
    const url = `${SITE_URL}${route.path}`;
    return {
      url,
      lastModified: now,
      changeFrequency: route.changeFrequency,
      priority: route.priority,
      alternates: {
        languages: {
          vi: url,
          en: url,
          "x-default": url,
        },
      },
    };
  });
}

