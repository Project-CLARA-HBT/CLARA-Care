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
  trackCareguardDdiChecked
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
