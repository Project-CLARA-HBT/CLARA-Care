import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Council Archetype and Route Recomposition (Spec v5 Section 6.43–6.53)", () => {
  it("verifies apps/web/app/council/page.tsx adheres to Case Library archetype", () => {
    const source = readFileSync(
      resolve(__dirname, "../app/council/page.tsx"),
      "utf8",
    );

    // 1. Case Library Archetype & Heading
    expect(source).toContain("Case Library");
    expect(source).toContain("Tạo ca mới");
    expect(source).toContain("/council/new");

    // 2. Resumable Active Case HeroObject
    expect(source).toContain('aria-label="Active resumable case"');
    expect(source).toContain("Ca đang thực hiện");

    // 3. Recent cases list as rows with status chips
    expect(source).toContain("Danh sách ca gần đây");
    expect(source).toContain("getCaseStatusMeta");
  });

  it("verifies wizard pages use clean FOCUS layout without redundant nav chrome", () => {
    const newSource = readFileSync(
      resolve(__dirname, "../app/council/new/page.tsx"),
      "utf8",
    );
    const intakeSource = readFileSync(
      resolve(__dirname, "../app/council/new/intake/page.tsx"),
      "utf8",
    );
    const specialistsSource = readFileSync(
      resolve(__dirname, "../app/council/new/specialists/page.tsx"),
      "utf8",
    );
    const reviewSource = readFileSync(
      resolve(__dirname, "../app/council/new/review/page.tsx"),
      "utf8",
    );

    // No redundant CouncilWorkspaceNav in FOCUS wizard steps
    expect(newSource).not.toContain("CouncilWorkspaceNav");
    expect(intakeSource).not.toContain("CouncilWorkspaceNav");
    expect(specialistsSource).not.toContain("CouncilWorkspaceNav");
    expect(reviewSource).not.toContain("CouncilWorkspaceNav");

    // Step progress maintained
    expect(newSource).toContain("CouncilFlowStepper");
    expect(intakeSource).toContain("CouncilFlowStepper");
    expect(specialistsSource).toContain("CouncilFlowStepper");
    expect(reviewSource).toContain("CouncilFlowStepper");

    // Clean focus container with max-w-3xl/4xl
    expect(newSource).toContain("max-w-3xl");
    expect(intakeSource).toContain("max-w-4xl");
    expect(specialistsSource).toContain("max-w-4xl");
    expect(reviewSource).toContain("max-w-4xl");
  });

  it("verifies apps/web/app/council/result/page.tsx satisfies 7-tier decision review hierarchy", () => {
    const resultSource = readFileSync(
      resolve(__dirname, "../app/council/result/page.tsx"),
      "utf8",
    );

    // 1. Red flags -> 2. Recommendation -> 3. Consensus -> 4. Uncertainty -> 5. Clinician Action -> 6. Evidence -> 7. Technical Details
    const headings = [
      "hierarchy-escalation-heading",
      "hierarchy-recommendation-heading",
      "hierarchy-consensus-heading",
      "hierarchy-uncertainty-heading",
      "hierarchy-action-heading",
      "hierarchy-evidence-heading",
      "council.result.hierarchy.technicalDetails",
    ];

    headings.forEach((heading) => {
      expect(resultSource).toContain(heading);
    });

    for (let i = 0; i < headings.length - 1; i++) {
      const currentPos = resultSource.indexOf(headings[i]);
      const nextPos = resultSource.indexOf(headings[i + 1]);
      expect(currentPos).toBeGreaterThan(-1);
      expect(nextPos).toBeGreaterThan(-1);
      expect(currentPos).toBeLessThan(nextPos);
    }
  });

  it("verifies document sub-views unify under canonical tab anchors and retain decision context", () => {
    const workspaceSource = readFileSync(
      resolve(__dirname, "../components/council/council-workspace-screen.tsx"),
      "utf8",
    );

    // Retained decision context header
    expect(workspaceSource).toContain("Council Decision Context");
    expect(workspaceSource).toContain("COUNCIL_SUB_TABS");

    // Canonical sub-views
    expect(workspaceSource).toContain("tab === \"analyze\"");
    expect(workspaceSource).toContain("tab === \"details\"");
    expect(workspaceSource).toContain("tab === \"citations\"");
    expect(workspaceSource).toContain("tab === \"research\"");
    expect(workspaceSource).toContain("tab === \"deepdive\"");
  });
});
