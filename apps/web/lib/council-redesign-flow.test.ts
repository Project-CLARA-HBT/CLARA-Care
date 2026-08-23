import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { COUNCIL_FLOW_STEPS } from "@/components/council/council-flow-stepper";

describe("Council Redesign Flow and Result Hierarchy", () => {
  it("defines the exact 6-step Council workflow sequence: Case -> Question -> Context -> Review -> Run -> Result", () => {
    expect(COUNCIL_FLOW_STEPS).toHaveLength(6);
    expect(COUNCIL_FLOW_STEPS.map((s) => s.id)).toEqual([
      "case",
      "question",
      "context",
      "review",
      "run",
      "result",
    ]);
  });

  it("enforces the exact 7-tier Result Hierarchy in council/result/page.tsx", () => {
    const resultSource = readFileSync(
      resolve(__dirname, "../app/council/result/page.tsx"),
      "utf8",
    );

    // 1. Escalation / Red Flags
    expect(resultSource).toContain("hierarchy-escalation-heading");
    expect(resultSource).toContain("council.result.hierarchy.escalation");

    // 2. Recommendation
    expect(resultSource).toContain("hierarchy-recommendation-heading");
    expect(resultSource).toContain("council.result.hierarchy.recommendation");

    // 3. Consensus / Agreement
    expect(resultSource).toContain("hierarchy-consensus-heading");
    expect(resultSource).toContain("council.result.hierarchy.consensus");

    // 4. Uncertainty
    expect(resultSource).toContain("hierarchy-uncertainty-heading");
    expect(resultSource).toContain("council.result.hierarchy.uncertainty");

    // 5. Evidence
    expect(resultSource).toContain("hierarchy-evidence-heading");
    expect(resultSource).toContain("council.result.hierarchy.evidence");

    // 6. Clinician Action
    expect(resultSource).toContain("hierarchy-action-heading");
    expect(resultSource).toContain("council.result.hierarchy.clinicianAction");

    // 7. Technical Details
    expect(resultSource).toContain("council.result.hierarchy.technicalDetails");

    // Check strict relative order of sections in the source code
    const pos1 = resultSource.indexOf("hierarchy-escalation-heading");
    const pos2 = resultSource.indexOf("hierarchy-recommendation-heading");
    const pos3 = resultSource.indexOf("hierarchy-consensus-heading");
    const pos4 = resultSource.indexOf("hierarchy-uncertainty-heading");
    const pos5 = resultSource.indexOf("hierarchy-evidence-heading");
    const pos6 = resultSource.indexOf("hierarchy-action-heading");
    const pos7 = resultSource.indexOf("council.result.hierarchy.technicalDetails");

    expect(pos1).toBeLessThan(pos2);
    expect(pos2).toBeLessThan(pos3);
    expect(pos3).toBeLessThan(pos4);
    expect(pos4).toBeLessThan(pos5);
    expect(pos5).toBeLessThan(pos6);
    expect(pos6).toBeLessThan(pos7);
  });

  it("verifies opaque surface styling on clinical output surfaces", () => {
    const resultSource = readFileSync(
      resolve(__dirname, "../app/council/result/page.tsx"),
      "utf8",
    );

    expect(resultSource).toContain("bg-[var(--surface-panel)]");
    expect(resultSource).toContain("bg-[var(--surface-muted)]");
    expect(resultSource).toContain("border-[color:var(--shell-border)]");
    expect(resultSource).toContain("border-t-[color:var(--card-top-border)]");
  });
});
