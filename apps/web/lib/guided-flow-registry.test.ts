import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  GUIDED_FLOW_REGISTRY,
  adjacentGuidedFlowStep,
  guidedFlowPath,
  guidedFlowSteps,
  isGuidedFlowStep,
  isGuidedFlowStepAhead,
  makeGuidedFlowAnalyticsEvent,
} from "@/lib/guided-flow-registry";

describe("guided-flow registry", () => {
  it("keeps localized labels and URL paths aligned with the typed order", () => {
    const flow = GUIDED_FLOW_REGISTRY.welcome;
    expect(guidedFlowSteps("welcome", "vi")).toHaveLength(flow.stepIds.length);
    expect(guidedFlowSteps("welcome", "en")).toHaveLength(flow.stepIds.length);
    expect(guidedFlowPath("welcome", "review")).toBe("/welcome/review");
    expect(guidedFlowPath("lifemapEpisode", "goal")).toBe(
      "/lifemap/new/goal",
    );
    expect(guidedFlowSteps("lifemapEpisode", "vi")).toHaveLength(4);
    expect(isGuidedFlowStep("lifemapEpisode", "priority")).toBe(true);
    expect(isGuidedFlowStep("welcome", "body")).toBe(true);
    expect(isGuidedFlowStep("welcome", "not-a-step")).toBe(false);
    expect(isGuidedFlowStepAhead("lifemapEpisode", "review", "goal")).toBe(true);
    expect(isGuidedFlowStepAhead("lifemapEpisode", "title", "goal")).toBe(false);
  });

  it("never moves outside the ordered flow", () => {
    const steps = GUIDED_FLOW_REGISTRY.welcome.stepIds;
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: steps.length - 1 }),
        (index) => {
          const step = steps[index];
          expect(adjacentGuidedFlowStep("welcome", step, "previous")).toBe(
            index === 0 ? null : steps[index - 1],
          );
          expect(adjacentGuidedFlowStep("welcome", step, "next")).toBe(
            index === steps.length - 1 ? null : steps[index + 1],
          );
        },
      ),
    );
  });

  it("produces a stable content-free analytics shape", () => {
    const event = makeGuidedFlowAnalyticsEvent(
      "welcome",
      "personalization",
      "step_viewed",
    );
    expect(event).toEqual({
      schemaVersion: 1,
      event: "step_viewed",
      surface: "web",
      flowId: "welcome",
      stepId: "personalization",
      stepIndex: 6,
      totalSteps: 8,
    });
    expect(JSON.stringify(event)).not.toMatch(
      /name|birth|blood|height|weight|consent|draft|user/i,
    );
  });
});
