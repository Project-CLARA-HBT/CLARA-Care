import type { MetadataRoute } from "next";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://theclaracare.com").replace(/\/+$/, "");

const AI_SEARCH_CRAWLERS = [
  "GPTBot",
  "ChatGPT-User",
  "OAI-SearchBot",
  "PerplexityBot",
  "ClaudeBot",
  "anthropic-ai",
  "Google-Extended",
  "GoogleOther",
  "Bingbot",
  "Applebot-Extended",
  "Meta-ExternalAgent",
  "cohere-ai",
  "Amazonbot",
  "Bytespider",
];

const PUBLIC_ROUTES = [
  "/",
  "/chat",
  "/lifemap",
  "/medicines",
  "/council",
  "/scribe",
  "/evidence",
  "/huong-dan",
  "/safety",
  "/privacy",
  "/sources",
  "/clinical-standards",
  "/contact",
  "/terms",
  "/legal/*",
  "/llms.txt",
  "/llms-full.txt",
  "/.well-known/*",
];

const DISALLOWED_ROUTES = [
  "/api/*",
  "/admin/*",
  "/dashboard/*",
  "/account/*",
  "/today/tasks/*",
  "/phr/shared/*",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: AI_SEARCH_CRAWLERS,
        allow: PUBLIC_ROUTES,
        disallow: DISALLOWED_ROUTES,
      },
      {
        userAgent: "*",
        allow: PUBLIC_ROUTES,
        disallow: DISALLOWED_ROUTES,
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}

