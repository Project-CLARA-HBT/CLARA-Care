import { describe, expect, it } from "vitest";
import sitemap, { SITEMAP_ROUTES } from "./sitemap";

describe("sitemap.ts metadata route", () => {
  it("exports a valid sitemap with all required public and feature landing pages", () => {
    const entries = sitemap();

    expect(entries).toBeDefined();
    expect(entries.length).toBe(19);

    // Map for easy lookup
    const entriesByUrl = new Map(entries.map((entry) => [entry.url, entry]));

    // 1. Root
    const root = entriesByUrl.get("https://theclaracare.com");
    expect(root).toBeDefined();
    expect(root?.priority).toBe(1.0);
    expect(root?.changeFrequency).toBe("daily");
    expect(root?.lastModified).toBeInstanceOf(Date);
    expect(root?.alternates?.languages).toEqual({
      vi: "https://theclaracare.com",
      en: "https://theclaracare.com",
      "x-default": "https://theclaracare.com",
    });

    // 2. Primary Feature Hubs
    const primaryHubs = [
      { path: "/chat", priority: 0.9, changeFrequency: "daily" },
      { path: "/lifemap", priority: 0.9, changeFrequency: "daily" },
      { path: "/medicines", priority: 0.9, changeFrequency: "daily" },
      { path: "/council", priority: 0.9, changeFrequency: "daily" },
      { path: "/scribe", priority: 0.9, changeFrequency: "daily" },
      { path: "/evidence", priority: 0.9, changeFrequency: "daily" },
    ];

    for (const hub of primaryHubs) {
      const url = `https://theclaracare.com${hub.path}`;
      const entry = entriesByUrl.get(url);
      expect(entry, `Expected entry for ${url}`).toBeDefined();
      expect(entry?.priority).toBe(hub.priority);
      expect(entry?.changeFrequency).toBe(hub.changeFrequency);
      expect(entry?.lastModified).toBeInstanceOf(Date);
      expect(entry?.alternates?.languages).toEqual({
        vi: url,
        en: url,
        "x-default": url,
      });
    }

    // 3. Safety, Trust & Guide Surfaces
    const trustSurfaces = [
      { path: "/huong-dan", priority: 0.85, changeFrequency: "weekly" },
      { path: "/safety", priority: 0.85, changeFrequency: "weekly" },
      { path: "/privacy", priority: 0.85, changeFrequency: "weekly" },
      { path: "/sources", priority: 0.8, changeFrequency: "weekly" },
      { path: "/clinical-standards", priority: 0.8, changeFrequency: "weekly" },
    ];

    for (const surface of trustSurfaces) {
      const url = `https://theclaracare.com${surface.path}`;
      const entry = entriesByUrl.get(url);
      expect(entry, `Expected entry for ${url}`).toBeDefined();
      expect(entry?.priority).toBe(surface.priority);
      expect(entry?.changeFrequency).toBe(surface.changeFrequency);
      expect(entry?.lastModified).toBeInstanceOf(Date);
      expect(entry?.alternates?.languages).toEqual({
        vi: url,
        en: url,
        "x-default": url,
      });
    }

    // 4. Utility & Legal
    const utilityAndLegal = [
      { path: "/login", priority: 0.7, changeFrequency: "monthly" },
      { path: "/register", priority: 0.7, changeFrequency: "monthly" },
      { path: "/contact", priority: 0.7, changeFrequency: "monthly" },
      { path: "/legal/privacy", priority: 0.6, changeFrequency: "monthly" },
      { path: "/legal/terms", priority: 0.6, changeFrequency: "monthly" },
      { path: "/legal/consent", priority: 0.6, changeFrequency: "monthly" },
      { path: "/legal/cookies", priority: 0.6, changeFrequency: "monthly" },
    ];

    for (const item of utilityAndLegal) {
      const url = `https://theclaracare.com${item.path}`;
      const entry = entriesByUrl.get(url);
      expect(entry, `Expected entry for ${url}`).toBeDefined();
      expect(entry?.priority).toBe(item.priority);
      expect(entry?.changeFrequency).toBe(item.changeFrequency);
      expect(entry?.lastModified).toBeInstanceOf(Date);
      expect(entry?.alternates?.languages).toEqual({
        vi: url,
        en: url,
        "x-default": url,
      });
    }
  });

  it("exports exact SITEMAP_ROUTES definitions matching product specifications", () => {
    expect(SITEMAP_ROUTES).toHaveLength(19);
    expect(SITEMAP_ROUTES.map((r) => r.path)).toEqual([
      "",
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
      "/login",
      "/register",
      "/contact",
      "/legal/privacy",
      "/legal/terms",
      "/legal/consent",
      "/legal/cookies",
    ]);
  });
});
