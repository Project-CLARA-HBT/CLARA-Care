import { describe, expect, it } from "vitest";
import robots from "./robots";

describe("robots.ts metadata route", () => {
  it("configures robots rules for AI crawlers and default search engines with allowed and disallowed routes", () => {
    const config = robots();

    expect(config).toBeDefined();
    expect(config.sitemap).toBe("https://theclaracare.com/sitemap.xml");

    const rules = Array.isArray(config.rules) ? config.rules : [config.rules];
    expect(rules.length).toBeGreaterThanOrEqual(2);

    const [aiCrawlerRule, generalRule] = rules;

    // AI search crawlers
    expect(aiCrawlerRule.userAgent).toEqual([
      "GPTBot",
      "ChatGPT-User",
      "PerplexityBot",
      "ClaudeBot",
      "anthropic-ai",
      "Google-Extended",
      "Bingbot",
      "Applebot-Extended",
      "Meta-ExternalAgent",
    ]);

    const expectedAllowedRoutes = [
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
      "/legal/*",
    ];

    const expectedDisallowedRoutes = [
      "/api/*",
      "/admin/*",
      "/dashboard/*",
      "/account/*",
      "/today/tasks/*",
      "/phr/shared/*",
    ];

    expect(aiCrawlerRule.allow).toEqual(expectedAllowedRoutes);
    expect(aiCrawlerRule.disallow).toEqual(expectedDisallowedRoutes);

    // General user agent
    expect(generalRule.userAgent).toBe("*");
    expect(generalRule.allow).toEqual(expectedAllowedRoutes);
    expect(generalRule.disallow).toEqual(expectedDisallowedRoutes);
  });
});
