import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it, vi } from "vitest";

/**
 * Feature: product-polish-analytics — Scribe surface integration (task 9.5)
 *
 * Validates: Requirements 4.1 (no telemetry labels in End_User views),
 *            9.1 (named product events for primary Surface interactions).
 *
 * Task 9.5 integrates the Scribe surface with the shared boundary primitives:
 *   1. user-facing strings are passed through `stripTelemetryLabels` so
 *      internal telemetry jargon never reaches the End_User view (Req 4.1);
 *   2. detailed/raw telemetry (raw pipeline timing) is wrapped in the
 *      role-gated `TelemetryPanel` so it stays admin-only (Req 4.3);
 *   3. named Scribe product events are emitted through the consent/PII-guarded
 *      analytics facade (Req 9.1).
 *
 * The first two are static wiring checks on the page (mirroring the existing
 * `scribe-summary-regression.test.ts` convention, since the page is a large
 * client component). The third is a behavioral check on the named emitters
 * through a recording analytics client.
 */

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..", "..");
const scribePage = readFileSync(resolve(here, "page.tsx"), "utf8");

describe("scribe surface integration (Feature: product-polish-analytics, Req 4.1)", () => {
  it("imports and applies the telemetry-label stripper to user-facing text", () => {
    expect(scribePage).toContain('from "@/lib/user-facing-text"');
    expect(scribePage).toContain("stripTelemetryLabels");
    // SOAP content rendered to the End_User is sanitized.
    expect(scribePage).toContain("stripTelemetryLabels(safeText(selectedSoap[item.valueKey]))");
  });

  it("wraps detailed pipeline telemetry in the role-gated TelemetryPanel", () => {
    expect(scribePage).toContain('from "@/components/telemetry/telemetry-panel"');
    expect(scribePage).toContain("<TelemetryPanel role={role}");
    // Role is sourced from the auth store, defaulting to a non-admin role.
    expect(scribePage).toContain('useState<UserRole>("normal")');
    expect(scribePage).toContain("setRole(getRole())");
  });

  it("emits named Scribe product events through the analytics facade", () => {
    expect(scribePage).toContain('from "@/lib/analytics/events"');
    expect(scribePage).toContain("trackScribeViewed()");
    expect(scribePage).toContain('trackScribeGenerated({ action: "regenerate" })');
    expect(scribePage).toContain('trackScribeGenerated({ action: "finalize" })');
  });
});

describe("scribe named events emit coarse, non-PII props (Req 9.1, 9.4)", () => {
  it("emits scribe_viewed and scribe_generated with safe props only", async () => {
    const trackMock = vi.fn();
    vi.resetModules();
    vi.doMock("@/lib/analytics", () => ({
      getAnalyticsClient: () => ({ track: trackMock })
    }));

    const events = await import("@/lib/analytics/events");

    events.trackScribeViewed();
    expect(trackMock).toHaveBeenCalledWith("scribe_viewed", { surface: "scribe" });

    trackMock.mockReset();
    events.trackScribeGenerated({ action: "regenerate" });
    expect(trackMock).toHaveBeenCalledWith("scribe_generated", {
      surface: "scribe",
      action: "regenerate"
    });

    trackMock.mockReset();
    events.trackScribeGenerated({ action: "finalize" });
    expect(trackMock).toHaveBeenCalledWith("scribe_generated", {
      surface: "scribe",
      action: "finalize"
    });

    // No PII / free-text keys ever attached.
    for (const call of trackMock.mock.calls) {
      const props = (call[1] ?? {}) as Record<string, unknown>;
      expect(Object.keys(props).sort()).toEqual(["action", "surface"]);
    }

    vi.doUnmock("@/lib/analytics");
  });
});
