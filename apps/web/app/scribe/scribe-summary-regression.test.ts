import { readFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { getScribeAnalyticsSummary } from "@/lib/scribe";

/**
 * Feature: product-polish-analytics — scribe-summary regression (task 6.3)
 *
 * Validates: Requirements 8.5
 *
 * The new Clinical_Analytics dashboard must be rendered SEPARATELY from the
 * existing scribe analytics summary and must NOT remove it. This is a
 * lightweight content/wiring check:
 *
 *   1. The scribe analytics summary data source (`getScribeAnalyticsSummary`,
 *      hitting `/scribe/analytics/summary`) still exists in `lib/scribe.ts`.
 *   2. The scribe page still consumes that summary (imports it, sets analytics
 *      state, and renders the summary KPIs).
 *   3. IF a clinical dashboard page exists, it is a distinct route from the
 *      scribe summary and does not hijack the scribe `/analytics/summary`
 *      endpoint.
 */

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..", "..");

const scribeLib = readFileSync(resolve(webRoot, "lib/scribe.ts"), "utf8");
const scribePage = readFileSync(resolve(here, "page.tsx"), "utf8");

describe("scribe analytics summary regression (Feature: product-polish-analytics, Req 8.5)", () => {
  it("keeps the scribe analytics summary data source and endpoint", () => {
    expect(typeof getScribeAnalyticsSummary).toBe("function");
    expect(scribeLib).toContain("getScribeAnalyticsSummary");
    expect(scribeLib).toContain("/scribe/analytics/summary");
  });

  it("keeps the scribe page consuming and rendering the summary", () => {
    expect(scribePage).toContain("getScribeAnalyticsSummary");
    expect(scribePage).toContain("ScribeAnalyticsSummary");
    // The summary KPIs (driven by the summary payload) remain rendered.
    expect(scribePage).toContain("total_sessions");
    expect(scribePage).toContain("completed_sessions");
  });

  it("does not let any clinical dashboard replace the scribe summary endpoint", () => {
    const clinicalPage = resolve(webRoot, "app/admin/analytics/clinical/page.tsx");
    if (!existsSync(clinicalPage)) {
      // Clinical dashboard not built yet in this surface — nothing to regress.
      expect(true).toBe(true);
      return;
    }
    const clinical = readFileSync(clinicalPage, "utf8");
    // The clinical dashboard surface must use its own endpoint, not the scribe
    // summary. The page is a thin wrapper that delegates to the panel, so the
    // endpoint reference may live in the imported panel/client rather than the
    // page file itself. Gather the page plus its local component imports and
    // assert the clinical endpoint is reached and the scribe summary is not.
    const clinicalPanel = resolve(webRoot, "components/admin/clinical-analytics-panel.tsx");
    const analyticsClient = resolve(webRoot, "lib/analytics-dashboard.ts");
    const surface = [clinicalPage, clinicalPanel, analyticsClient]
      .filter((file) => existsSync(file))
      .map((file) => readFileSync(file, "utf8"))
      .join("\n");

    expect(surface).not.toContain("/scribe/analytics/summary");
    expect(surface).toContain("/system/analytics/clinical");
  });
});
