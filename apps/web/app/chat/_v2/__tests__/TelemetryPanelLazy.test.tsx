import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import TelemetryPanelLazy from "@/app/chat/_v2/components/TelemetryPanelLazy";
import type { Tier2Result } from "@/components/research/lib/research-page-types";
import type { ResearchTier2Result } from "@/lib/research";

/**
 * Feature: clara-chat-redesign, task 4.4 — lazily-loaded, admin-only detailed
 * telemetry. Validates Requirement 6.6, 7.3 and design Property P7
 * (non-admin roles never see — or even load — detailed telemetry).
 */

function emptyTelemetry(): ResearchTier2Result["telemetry"] {
  return {
    keywords: [],
    scores: [],
    docs: [],
    sourceReasoning: [],
    sourceAttempts: [],
    verificationMatrix: [],
    stageSpans: [],
    errors: [],
    traceMetadata: {},
  } as unknown as ResearchTier2Result["telemetry"];
}

function makeTier2(): Tier2Result {
  return {
    tier: "tier2",
    answer: "x",
    citations: [],
    steps: [],
    flowStages: [],
    flowEvents: [],
    telemetry: emptyTelemetry(),
    visualAssets: [],
    chartSpecs: [],
    reasoningDigest: {
      items: [],
    } as unknown as ResearchTier2Result["reasoningDigest"],
    tracedClaims: [],
    citationRegistry: [],
    debug: {
      stageCount: 0,
      flowEventCount: 0,
      telemetryKeywordCount: 0,
      telemetryDocCount: 0,
      telemetrySourceAttemptCount: 0,
      telemetryErrorCount: 0,
      crawlDomainCount: 0,
    } as unknown as ResearchTier2Result["debug"],
  } as Tier2Result;
}

describe("TelemetryPanelLazy (lazy + admin-only, Property P7)", () => {
  it("lazily loads and renders detailed telemetry for an admin", async () => {
    render(<TelemetryPanelLazy role="admin" result={makeTier2()} uiLanguage="en" />);
    // The panel is code-split via next/dynamic, so it resolves asynchronously.
    expect(
      await screen.findByRole("complementary", { name: /telemetry/i }),
    ).toBeInTheDocument();
  });

  it.each(["normal", "researcher", "doctor"] as const)(
    "renders nothing and never loads the chunk for role=%s",
    async (role) => {
      const { container } = render(
        <TelemetryPanelLazy role={role} result={makeTier2()} uiLanguage="en" />,
      );
      // Non-admins get a synchronous null — the chunk is never even requested.
      expect(container).toBeEmptyDOMElement();
      // Give any (incorrect) async import a chance to surface, then re-assert.
      await waitFor(() => {
        expect(
          screen.queryByRole("complementary", { name: /telemetry/i }),
        ).not.toBeInTheDocument();
      });
    },
  );
});
