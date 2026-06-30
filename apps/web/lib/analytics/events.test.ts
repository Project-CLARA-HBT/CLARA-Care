import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Feature: product-polish-analytics
 *
 * Unit tests for the named product-event emitters (Req 9.1). These verify the
 * canonical event names and that emitters only ever attach coarse,
 * non-identifying props (no PII) — focusing on the Admin surface emitters added
 * for task 9.6 while covering the shared emitter contract.
 *
 * The shared `getAnalyticsClient` singleton is mocked with a recording client
 * so we can assert the exact `(name, props)` passed through the facade without
 * needing configured credentials or consent.
 */

const trackMock = vi.fn();

vi.mock("@/lib/analytics", () => ({
  getAnalyticsClient: () => ({ track: trackMock })
}));

// Imported after the mock is registered so `emit` binds to the mocked client.
import {
  ANALYTICS_EVENTS,
  trackAdminSurfaceViewed,
  trackChatMessageSent,
  trackCareguardDdiChecked,
  trackCouncilRun,
  trackCouncilViewed,
  trackResearchSourcesSynced,
  trackResearchViewed
} from "@/lib/analytics/events";

beforeEach(() => {
  trackMock.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Admin surface events (Feature: product-polish-analytics, Req 9.1)", () => {
  it("declares dedicated named events for each primary Admin surface", () => {
    expect(ANALYTICS_EVENTS.adminOverviewViewed).toBe("admin_overview_viewed");
    expect(ANALYTICS_EVENTS.adminKnowledgeSourcesViewed).toBe("admin_knowledge_sources_viewed");
    expect(ANALYTICS_EVENTS.adminAnswerFlowViewed).toBe("admin_answer_flow_viewed");
    expect(ANALYTICS_EVENTS.adminObservabilityViewed).toBe("admin_observability_viewed");
    expect(ANALYTICS_EVENTS.adminAnalyticsViewed).toBe("admin_analytics_viewed");
    expect(ANALYTICS_EVENTS.adminClinicalAnalyticsViewed).toBe("admin_clinical_analytics_viewed");
  });

  it("emits the dedicated overview event plus the coarse roll-up event", () => {
    trackAdminSurfaceViewed({ view: "overview" });

    expect(trackMock).toHaveBeenCalledTimes(2);
    expect(trackMock).toHaveBeenNthCalledWith(1, "admin_overview_viewed", {
      surface: "admin",
      view: "overview"
    });
    expect(trackMock).toHaveBeenNthCalledWith(2, "admin_surface_viewed", {
      surface: "admin",
      view: "overview"
    });
  });

  it("maps the product analytics view to admin_analytics_viewed", () => {
    trackAdminSurfaceViewed({ view: "product_analytics" });

    expect(trackMock).toHaveBeenNthCalledWith(1, "admin_analytics_viewed", {
      surface: "admin",
      view: "product_analytics"
    });
  });

  it("maps the clinical analytics view to admin_clinical_analytics_viewed", () => {
    trackAdminSurfaceViewed({ view: "clinical_analytics" });

    expect(trackMock).toHaveBeenNthCalledWith(1, "admin_clinical_analytics_viewed", {
      surface: "admin",
      view: "clinical_analytics"
    });
  });

  it("only ever attaches coarse, non-identifying props (no PII)", () => {
    const views = [
      "overview",
      "knowledge_sources",
      "answer_flow",
      "observability",
      "product_analytics",
      "clinical_analytics"
    ] as const;

    for (const view of views) {
      trackMock.mockReset();
      trackAdminSurfaceViewed({ view });
      for (const call of trackMock.mock.calls) {
        const props = (call[1] ?? {}) as Record<string, unknown>;
        expect(Object.keys(props).sort()).toEqual(["surface", "view"]);
        expect(props.surface).toBe("admin");
        expect(props.view).toBe(view);
      }
    }
  });

  // Hardening (Req 11.5): every prop emitted from an Admin surface must be a
  // coarse, non-identifying signal. Beyond the key allowlist above, assert that
  // each emitted prop NAME is allowlisted and each emitted VALUE is a coarse
  // token (a short snake_case label or a number) — never a PII-shaped value
  // such as an email, a name with whitespace, free-text, or a long identifier.
  it("restricts admin event props to an allowlist of coarse keys and coarse values", () => {
    const ADMIN_PROP_ALLOWLIST = new Set(["surface", "view"]);
    // A coarse label: lowercase snake_case token, no PII characters
    // (no '@', no spaces, no punctuation) and short enough to be an enum, not
    // free-text or an opaque id.
    const COARSE_TOKEN = /^[a-z][a-z0-9_]{0,40}$/;
    const views = [
      "overview",
      "knowledge_sources",
      "answer_flow",
      "observability",
      "product_analytics",
      "clinical_analytics"
    ] as const;

    for (const view of views) {
      trackMock.mockReset();
      trackAdminSurfaceViewed({ view });
      expect(trackMock).toHaveBeenCalled();
      for (const [name, props] of trackMock.mock.calls as Array<
        [string, Record<string, unknown> | undefined]
      >) {
        // Event name is a coarse admin_*_viewed label.
        expect(name).toMatch(/^admin_[a-z_]+_viewed$/);
        for (const [key, value] of Object.entries(props ?? {})) {
          expect(ADMIN_PROP_ALLOWLIST.has(key)).toBe(true);
          if (typeof value === "string") {
            expect(value).toMatch(COARSE_TOKEN);
            expect(value).not.toContain("@");
            expect(value).not.toContain(" ");
          } else {
            expect(typeof value).toBe("number");
          }
        }
      }
    }
  });
});

describe("Shared emitter contract (Feature: product-polish-analytics, Req 9.1)", () => {
  it("emits chat_message_sent with coarse mode/transport only", () => {
    trackChatMessageSent({ mode: "fast", transport: "tier1_chat" });
    expect(trackMock).toHaveBeenCalledWith("chat_message_sent", {
      surface: "chat",
      mode: "fast",
      transport: "tier1_chat"
    });
  });

  it("emits careguard_ddi_checked with aggregate signals only", () => {
    trackCareguardDdiChecked({ riskLevel: "medium", alertCount: 2, medicineCount: 3 });
    expect(trackMock).toHaveBeenCalledWith("careguard_ddi_checked", {
      surface: "careguard",
      risk_level: "medium",
      alert_count: 2,
      medicine_count: 3
    });
  });
});

describe("Research surface events (Feature: product-polish-analytics, Req 9.1)", () => {
  it("declares the research source-sync named event", () => {
    expect(ANALYTICS_EVENTS.researchViewed).toBe("research_viewed");
    expect(ANALYTICS_EVENTS.researchSourcesSynced).toBe("research_sources_synced");
  });

  it("emits research_viewed with the surface label only (no PII)", () => {
    trackResearchViewed();
    expect(trackMock).toHaveBeenCalledWith("research_viewed", {
      surface: "research"
    });
  });

  it("emits research_sources_synced with coarse source key + counts only", () => {
    trackResearchSourcesSynced({ source: "pubmed", fetched: 12, stored: 9 });
    expect(trackMock).toHaveBeenCalledWith("research_sources_synced", {
      surface: "research",
      source: "pubmed",
      fetched: 12,
      stored: 9
    });
  });

  it("never attaches query text or record content to research sync events", () => {
    trackResearchSourcesSynced({ source: "openfda", fetched: 5, stored: 5 });
    for (const call of trackMock.mock.calls) {
      const props = (call[1] ?? {}) as Record<string, unknown>;
      expect(Object.keys(props).sort()).toEqual(["fetched", "source", "stored", "surface"]);
    }
  });
});

describe("Council surface events (Feature: product-polish-analytics, Req 9.1)", () => {
  it("declares the council named events", () => {
    expect(ANALYTICS_EVENTS.councilViewed).toBe("council_viewed");
    expect(ANALYTICS_EVENTS.councilRun).toBe("council_run");
  });

  it("emits council_viewed with the surface label only (no PII)", () => {
    trackCouncilViewed();
    expect(trackMock).toHaveBeenCalledWith("council_viewed", {
      surface: "council"
    });
  });

  it("emits council_viewed with a coarse view label when provided", () => {
    trackCouncilViewed({ view: "result" });
    expect(trackMock).toHaveBeenCalledWith("council_viewed", {
      surface: "council",
      view: "result"
    });
  });

  it("emits council_run with the coarse specialist count only", () => {
    trackCouncilRun({ specialistCount: 3 });
    expect(trackMock).toHaveBeenCalledWith("council_run", {
      surface: "council",
      specialist_count: 3
    });
  });

  it("never attaches case or patient content to council events", () => {
    trackCouncilViewed({ view: "landing" });
    trackCouncilRun({ specialistCount: 4 });
    for (const call of trackMock.mock.calls) {
      const props = (call[1] ?? {}) as Record<string, unknown>;
      for (const key of Object.keys(props)) {
        expect(["surface", "view", "specialist_count"]).toContain(key);
      }
      expect(props.surface).toBe("council");
    }
  });
});
