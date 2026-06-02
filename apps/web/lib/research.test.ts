import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  resolveChatTransport,
  type ChatTransport,
  type ResearchExecutionMode
} from "@/lib/research";

/**
 * Feature: product-polish-analytics, Property 1
 * Mode dispatch routes fast to tier1 and deep modes to tier2.
 *
 * Validates: Requirements 2.1, 2.2
 *
 * `resolveChatTransport` is the pure routing unit: `fast` must reach the tier1
 * chat transport and `deep`/`deep_beta` must reach the tier2 research job
 * pipeline. The critical safety invariant is that a `fast` query NEVER reaches
 * the long tier2 job pipeline (that was the original "spinner" bug).
 */

const DEEP_MODES: ResearchExecutionMode[] = ["deep", "deep_beta"];
const ALL_MODES: ResearchExecutionMode[] = ["fast", "deep", "deep_beta"];

describe("resolveChatTransport (Feature: product-polish-analytics, Property 1)", () => {
  // ---- Unit/example tests: pin the exact mapping ----
  it("maps fast to the tier1 chat transport", () => {
    expect(resolveChatTransport("fast")).toBe<ChatTransport>("tier1_chat");
  });

  it("maps deep to the tier2 job pipeline", () => {
    expect(resolveChatTransport("deep")).toBe<ChatTransport>("tier2_job");
  });

  it("maps deep_beta to the tier2 job pipeline", () => {
    expect(resolveChatTransport("deep_beta")).toBe<ChatTransport>("tier2_job");
  });

  it("normalizes unknown/undefined modes to the fast tier1 transport", () => {
    expect(resolveChatTransport(undefined)).toBe<ChatTransport>("tier1_chat");
    // Defensive: any out-of-enum string must still route to tier1, never tier2.
    expect(resolveChatTransport("nonsense" as ResearchExecutionMode)).toBe<ChatTransport>(
      "tier1_chat"
    );
  });

  // ---- Property: fast => tier1, deep/deep_beta => tier2, never the reverse ----
  it("Property 1: fast => tier1_chat and deep modes => tier2_job", () => {
    fc.assert(
      fc.property(fc.constantFrom<ResearchExecutionMode>(...ALL_MODES), (mode) => {
        const transport = resolveChatTransport(mode);
        if (mode === "fast") {
          return transport === "tier1_chat";
        }
        return transport === "tier2_job";
      }),
      { numRuns: 200 }
    );
  });

  it("Property 1: no fast query ever reaches the tier2 job pipeline", () => {
    fc.assert(
      fc.property(fc.constant<ResearchExecutionMode>("fast"), (mode) => {
        return resolveChatTransport(mode) !== "tier2_job";
      }),
      { numRuns: 200 }
    );
  });

  it("Property 1: every deep mode reaches the tier2 job pipeline", () => {
    fc.assert(
      fc.property(fc.constantFrom<ResearchExecutionMode>(...DEEP_MODES), (mode) => {
        return resolveChatTransport(mode) === "tier2_job";
      }),
      { numRuns: 200 }
    );
  });

  it("Property 1: arbitrary/unknown mode strings never route to tier2", () => {
    fc.assert(
      fc.property(fc.string(), (raw) => {
        // Unknown strings are normalized to fast, so they must route to tier1.
        // Only the exact deep enum values may produce tier2.
        const transport = resolveChatTransport(raw as ResearchExecutionMode);
        if (raw === "deep" || raw === "deep_beta") {
          return transport === "tier2_job";
        }
        return transport === "tier1_chat";
      }),
      { numRuns: 300 }
    );
  });
});
