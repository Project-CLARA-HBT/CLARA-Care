import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import robots from "./robots";
import sitemap, { SITEMAP_ROUTES } from "./sitemap";
import {
  getSeoJsonLdGraph,
  safeJsonLdStringify,
} from "@/components/landing/v7/seo-json-ld";

describe("AI Search Readiness & Discovery Suite", () => {
  const publicDir = path.resolve(__dirname, "../public");

  describe("1. robots.ts AI search crawlers and route gating", () => {
    it("includes required AI search crawlers in userAgent rules", () => {
      const config = robots();
      expect(config).toBeDefined();
      expect(config.sitemap).toBe("https://theclaracare.com/sitemap.xml");

      const rules = Array.isArray(config.rules) ? config.rules : [config.rules];
      expect(rules.length).toBeGreaterThanOrEqual(2);

      const aiCrawlerRule = rules.find((rule) => Array.isArray(rule.userAgent));
      expect(aiCrawlerRule).toBeDefined();

      const userAgents = (aiCrawlerRule?.userAgent as string[]) ?? [];

      const requiredCrawlers = [
        "GPTBot",
        "ChatGPT-User",
        "OAI-SearchBot",
        "Google-Extended",
        "PerplexityBot",
        "ClaudeBot",
        "anthropic-ai",
        "Bingbot",
        "Applebot-Extended",
        "Meta-ExternalAgent",
      ];

      for (const crawler of requiredCrawlers) {
        expect(
          userAgents,
          `Expected robots.ts to contain crawler rule for "${crawler}"`
        ).toContain(crawler);
      }
    });

    it("allows public feature hubs and disallows private/authenticated routes for AI crawlers", () => {
      const config = robots();
      const rules = Array.isArray(config.rules) ? config.rules : [config.rules];
      const aiCrawlerRule = rules.find((rule) => Array.isArray(rule.userAgent));

      expect(aiCrawlerRule).toBeDefined();

      const allowedRoutes = (aiCrawlerRule?.allow as string[]) ?? [];
      const disallowedRoutes = (aiCrawlerRule?.disallow as string[]) ?? [];

      const expectedAllowed = [
        "/",
        "/chat",
        "/lifemap",
        "/medicines",
        "/council",
        "/scribe",
        "/evidence",
      ];

      for (const route of expectedAllowed) {
        expect(
          allowedRoutes,
          `Expected robots.ts to allow public route "${route}"`
        ).toContain(route);
      }

      const expectedDisallowed = [
        "/api/*",
        "/admin/*",
        "/dashboard/*",
        "/account/*",
        "/phr/shared/*",
      ];

      for (const route of expectedDisallowed) {
        expect(
          disallowedRoutes,
          `Expected robots.ts to disallow private route "${route}"`
        ).toContain(route);
      }
    });
  });

  describe("2. sitemap.ts public feature hubs and alternate language links", () => {
    it("returns all public feature hubs with correct priority and changeFrequency", () => {
      const entries = sitemap();
      expect(entries).toBeDefined();
      expect(entries.length).toBeGreaterThanOrEqual(15);

      const entriesByUrl = new Map(entries.map((entry) => [entry.url, entry]));

      const publicFeatureHubs = [
        { path: "/chat", priority: 0.9, changeFrequency: "daily" },
        { path: "/lifemap", priority: 0.9, changeFrequency: "daily" },
        { path: "/medicines", priority: 0.9, changeFrequency: "daily" },
        { path: "/council", priority: 0.9, changeFrequency: "daily" },
        { path: "/scribe", priority: 0.9, changeFrequency: "daily" },
        { path: "/evidence", priority: 0.9, changeFrequency: "daily" },
      ];

      for (const hub of publicFeatureHubs) {
        const fullUrl = `https://theclaracare.com${hub.path}`;
        const entry = entriesByUrl.get(fullUrl);

        expect(entry, `Expected sitemap entry for ${fullUrl}`).toBeDefined();
        expect(entry?.priority).toBe(hub.priority);
        expect(entry?.changeFrequency).toBe(hub.changeFrequency);
        expect(entry?.lastModified).toBeInstanceOf(Date);
      }
    });

    it("provides alternate language links (vi, en, x-default) for all sitemap entries", () => {
      const entries = sitemap();
      expect(entries.length).toBeGreaterThan(0);

      for (const entry of entries) {
        expect(
          entry.alternates,
          `Entry ${entry.url} must contain alternates`
        ).toBeDefined();
        expect(
          entry.alternates?.languages,
          `Entry ${entry.url} must contain alternates.languages`
        ).toBeDefined();

        const languages = entry.alternates?.languages as Record<string, string>;
        expect(languages.vi, `Entry ${entry.url} missing "vi" language alternate`).toBe(entry.url);
        expect(languages.en, `Entry ${entry.url} missing "en" language alternate`).toBe(entry.url);
        expect(
          languages["x-default"],
          `Entry ${entry.url} missing "x-default" alternate`
        ).toBe(entry.url);
      }
    });

    it("verifies SITEMAP_ROUTES array contains all canonical public routes", () => {
      const paths = SITEMAP_ROUTES.map((r) => r.path);
      const expectedPaths = [
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
      ];

      for (const p of expectedPaths) {
        expect(paths).toContain(p);
      }
    });
  });

  describe("3. seo-json-ld.tsx structured data and Wikidata entity links", () => {
    it("generates valid JSON-LD graph with all 5 required schema types", () => {
      const graphData = getSeoJsonLdGraph();

      expect(graphData["@context"]).toBe("https://schema.org");
      expect(Array.isArray(graphData["@graph"])).toBe(true);

      const typesInGraph = graphData["@graph"].flatMap((item: Record<string, unknown>) => {
        const t = item["@type"] as string | string[] | undefined;
        return Array.isArray(t) ? t : t ? [t] : [];
      });

      expect(typesInGraph).toContain("MedicalOrganization");
      expect(typesInGraph).toContain("WebApplication");
      expect(typesInGraph).toContain("WebSite");
      expect(typesInGraph).toContain("FAQPage");
      expect(typesInGraph).toContain("MedicalWebPage");
    });

    it("embeds authoritative Wikidata entity URLs across the JSON-LD schema", () => {
      const graphData = getSeoJsonLdGraph();
      const serialized = JSON.stringify(graphData);

      // Verify that Wikidata entity links exist in the schema graph
      const wikidataUrlPattern = /https:\/\/www\.wikidata\.org\/wiki\/Q\d+/g;
      const wikidataMatches = serialized.match(wikidataUrlPattern);

      expect(
        wikidataMatches,
        "Expected JSON-LD graph to contain Wikidata entity URLs"
      ).not.toBeNull();
      expect((wikidataMatches ?? []).length).toBeGreaterThanOrEqual(5);

      // Verify MedicalOrganization sameAs or knowsAbout includes Wikidata URLs
      const org = graphData["@graph"].find((item: Record<string, unknown>) => {
        const t = item["@type"] as string | string[] | undefined;
        return Array.isArray(t)
          ? t.includes("MedicalOrganization")
          : t === "MedicalOrganization";
      });
      expect(org).toBeDefined();

      const orgSameAs = (org?.sameAs as string[]) ?? [];
      const orgWikidata = orgSameAs.filter((url) =>
        url.includes("wikidata.org/wiki/Q")
      );
      expect(
        orgWikidata.length,
        "MedicalOrganization must link to Wikidata entities"
      ).toBeGreaterThanOrEqual(3);

      // Verify knowsAbout contains medical entities with Wikidata sameAs
      const knowsAbout = (org?.knowsAbout as Array<Record<string, unknown>>) ?? [];
      expect(knowsAbout.length).toBeGreaterThanOrEqual(3);
      for (const entity of knowsAbout) {
        expect(entity["@type"]).toBe("MedicalEntity");
        const sameAsList = (entity.sameAs as string[]) ?? [];
        expect(
          sameAsList.some((url) => url.includes("wikidata.org/wiki/Q")),
          `MedicalEntity "${entity.name}" must contain Wikidata reference`
        ).toBe(true);
      }
    });

    it("verifies FAQPage has valid question and answer structures", () => {
      const graphData = getSeoJsonLdGraph();
      const faq = graphData["@graph"].find((item: Record<string, unknown>) => item["@type"] === "FAQPage");
      expect(faq).toBeDefined();

      const mainEntity = faq?.mainEntity as Array<{
        "@type": string;
        name: string;
        acceptedAnswer: { "@type": string; text: string };
      }>;
      expect(Array.isArray(mainEntity)).toBe(true);
      expect(mainEntity.length).toBeGreaterThanOrEqual(3);

      for (const q of mainEntity) {
        expect(q["@type"]).toBe("Question");
        expect(typeof q.name).toBe("string");
        expect(q.name.length).toBeGreaterThan(0);
        expect(q.acceptedAnswer["@type"]).toBe("Answer");
        expect(typeof q.acceptedAnswer.text).toBe("string");
        expect(q.acceptedAnswer.text.length).toBeGreaterThan(0);
      }
    });

    it("ensures safe serialization without script injection vulnerabilities", () => {
      const graphData = getSeoJsonLdGraph();
      const serialized = safeJsonLdStringify(graphData);

      expect(serialized).not.toContain("<script");
      expect(serialized).not.toContain("</script");

      // Verify it parses back to identical object structure
      const parsed = JSON.parse(serialized);
      expect(parsed["@context"]).toBe("https://schema.org");
      expect(parsed["@graph"].length).toBe(5);
    });
  });

  describe("4. AI & machine-readable discovery files in apps/web/public/", () => {
    it("verifies ai-plugin.json exists with valid manifest schema", () => {
      const pluginPath = path.join(publicDir, "ai-plugin.json");
      expect(
        fs.existsSync(pluginPath),
        `Expected ${pluginPath} to exist`
      ).toBe(true);

      const content = JSON.parse(fs.readFileSync(pluginPath, "utf-8"));
      expect(content.schema_version).toBe("v1");
      expect(typeof content.name_for_human).toBe("string");
      expect(typeof content.name_for_model).toBe("string");
      expect(typeof content.description_for_human).toBe("string");
      expect(typeof content.description_for_model).toBe("string");
      expect(content.auth).toBeDefined();
      expect(content.auth.type).toBeDefined();
      expect(content.api).toBeDefined();
      expect(content.api.type).toBe("openapi");
      expect(content.api.url).toBe("https://theclaracare.com/openapi.json");
      expect(typeof content.logo_url).toBe("string");
      expect(typeof content.contact_email).toBe("string");
      expect(typeof content.legal_info_url).toBe("string");
    });

    it("verifies mcp.json exists with valid Model Context Protocol manifest", () => {
      const mcpPath = path.join(publicDir, "mcp.json");
      expect(fs.existsSync(mcpPath), `Expected ${mcpPath} to exist`).toBe(true);

      const content = JSON.parse(fs.readFileSync(mcpPath, "utf-8"));
      expect(typeof content.name).toBe("string");
      expect(typeof content.version).toBe("string");
      expect(typeof content.description).toBe("string");
      expect(content.capabilities).toBeDefined();
      expect(Array.isArray(content.tools)).toBe(true);
      expect(content.tools.length).toBeGreaterThanOrEqual(2);

      for (const tool of content.tools) {
        expect(typeof tool.name).toBe("string");
        expect(typeof tool.description).toBe("string");
        expect(tool.inputSchema).toBeDefined();
        expect(tool.inputSchema.type).toBe("object");
      }
    });

    it("verifies openapi.json exists with valid OpenAPI 3.x schema", () => {
      const openapiPath = path.join(publicDir, "openapi.json");
      expect(
        fs.existsSync(openapiPath),
        `Expected ${openapiPath} to exist`
      ).toBe(true);

      const content = JSON.parse(fs.readFileSync(openapiPath, "utf-8"));
      expect(
        content.openapi.startsWith("3."),
        `OpenAPI version must be 3.x, got ${content.openapi}`
      ).toBe(true);
      expect(content.info).toBeDefined();
      expect(typeof content.info.title).toBe("string");
      expect(typeof content.info.version).toBe("string");
      expect(typeof content.info.description).toBe("string");
      expect(Array.isArray(content.servers)).toBe(true);
      expect(content.servers.length).toBeGreaterThanOrEqual(1);
      expect(content.paths).toBeDefined();
      expect(Object.keys(content.paths).length).toBeGreaterThanOrEqual(2);
      expect(content.components?.schemas).toBeDefined();
    });

    it("verifies llms.txt exists with structured markdown documentation", () => {
      const llmsPath = path.join(publicDir, "llms.txt");
      expect(fs.existsSync(llmsPath), `Expected ${llmsPath} to exist`).toBe(true);

      const content = fs.readFileSync(llmsPath, "utf-8");
      expect(content.length).toBeGreaterThan(100);

      // Must start with H1 title and have summary blockquote
      expect(content).toMatch(/^#\s+[^\n]+/m);
      expect(content).toMatch(/^>\s+[^\n]+/m);

      // Must contain instructions for LLMs & AI crawlers
      expect(content).toContain("Instructions for AI Search Engines");
      expect(content).toContain("Core Capabilities");
      expect(content).toContain("Canonical Safety Invariants");
      expect(content).toContain("Canonical URLs");

      // Must mention canonical website and features
      expect(content).toContain("https://theclaracare.com");
      expect(content).toContain("FIDES");
      expect(content).toContain("LifeMap");
    });

    it("verifies security.txt exists adhering to RFC 9116 specification", () => {
      const secPath = path.join(publicDir, "security.txt");
      expect(fs.existsSync(secPath), `Expected ${secPath} to exist`).toBe(true);

      const content = fs.readFileSync(secPath, "utf-8");
      expect(content.length).toBeGreaterThan(50);

      // Required RFC 9116 fields
      expect(content).toMatch(/^Contact:\s+mailto:\S+/m);
      expect(content).toMatch(/^Expires:\s+\S+/m);
      expect(content).toMatch(/^Canonical:\s+https:\/\/\S+/m);
      expect(content).toMatch(/^Policy:\s+https:\/\/\S+/m);
      expect(content).toMatch(/^Preferred-Languages:\s+\S+/m);
    });
  });
});
