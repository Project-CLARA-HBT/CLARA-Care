import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  resolveChatTransport,
  orderDisclosedResearchFlowStages,
  normalizeResearchTier2JobProgress,
  normalizeResearchTier2,
  citationRegistryAnchorId,
  injectTracedClaimAnchors,
  CANONICAL_RESEARCH_STAGE_ORDER,
  type ChatTransport,
  type ResearchExecutionMode,
  type ResearchFlowStage,
  type ResearchFlowStageStatus
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

/**
 * Feature: clara-research, Requirement 13 (Progressive Disclosure)
 *
 * `orderDisclosedResearchFlowStages` enforces that the canonical research
 * pipeline phases (plan → retrieval → synthesis → verification) are disclosed
 * as an ordered subsequence and that an earlier phase reads as `completed`
 * before a later phase is disclosed (R13.1, R13.3). Disclosure operates on the
 * canonical `FLOW_STAGE_ALIAS_MAP` stage ids (R13.2).
 *
 * Validates: Requirements 13.1, 13.2, 13.3
 */

const CANONICAL_ORDER = [...CANONICAL_RESEARCH_STAGE_ORDER];

function stage(
  id: string,
  status: ResearchFlowStageStatus,
  extra: Partial<ResearchFlowStage> = {}
): ResearchFlowStage {
  return {
    id,
    label: id,
    status,
    source: "flow_events",
    ...extra
  };
}

function canonicalSubsequence(stages: ResearchFlowStage[]): string[] {
  return stages
    .map((item) => item.id)
    .filter((id) => CANONICAL_ORDER.includes(id));
}

function isOrderedSubsequence(observed: string[], canonical: string[]): boolean {
  let cursor = 0;
  for (const id of observed) {
    const at = canonical.indexOf(id, cursor);
    if (at < 0) return false;
    cursor = at + 1;
  }
  return true;
}

describe("orderDisclosedResearchFlowStages (Feature: clara-research, Requirement 13)", () => {
  it("orders canonical phases into plan → retrieval → synthesis → verification", () => {
    const out = orderDisclosedResearchFlowStages([
      stage("verification", "pending"),
      stage("synthesis", "pending"),
      stage("retrieval_orchestrator", "pending"),
      stage("planner", "pending")
    ]);
    expect(out.map((item) => item.id)).toEqual([
      "planner",
      "retrieval_orchestrator",
      "synthesis",
      "verification"
    ]);
  });

  it("marks earlier canonical phases complete before disclosing a later in-progress phase", () => {
    const out = orderDisclosedResearchFlowStages([
      stage("planner", "in_progress"),
      stage("retrieval_orchestrator", "pending"),
      stage("synthesis", "in_progress")
    ]);
    const byId = new Map(out.map((item) => [item.id, item.status]));
    // synthesis is in progress, so planner and retrieval must read complete.
    expect(byId.get("planner")).toBe("completed");
    expect(byId.get("retrieval_orchestrator")).toBe("completed");
    expect(byId.get("synthesis")).toBe("in_progress");
  });

  it("preserves a terminal-negative earlier phase (failed) instead of forcing complete", () => {
    const out = orderDisclosedResearchFlowStages([
      stage("planner", "failed"),
      stage("verification", "in_progress")
    ]);
    const byId = new Map(out.map((item) => [item.id, item.status]));
    expect(byId.get("planner")).toBe("failed");
  });

  it("keeps non-canonical stages anchored to the phase they followed", () => {
    const out = orderDisclosedResearchFlowStages([
      stage("input_gateway", "completed"),
      stage("planner", "completed"),
      stage("query_decomposition", "completed"),
      stage("retrieval_orchestrator", "in_progress")
    ]);
    const ids = out.map((item) => item.id);
    // query_decomposition followed planner, so it stays between planner and retrieval.
    expect(ids.indexOf("planner")).toBeLessThan(ids.indexOf("query_decomposition"));
    expect(ids.indexOf("query_decomposition")).toBeLessThan(
      ids.indexOf("retrieval_orchestrator")
    );
    // input_gateway preceded any canonical phase, so it stays at the front.
    expect(ids[0]).toBe("input_gateway");
  });

  it("Requirement 13.1/13.2/13.3: disclosed canonical phases are always an ordered subsequence", () => {
    const stageStatuses: ResearchFlowStageStatus[] = [
      "pending",
      "in_progress",
      "completed",
      "warning",
      "failed",
      "skipped"
    ];
    fc.assert(
      fc.property(
        fc.shuffledSubarray(CANONICAL_ORDER, { minLength: 0, maxLength: 4 }),
        fc.array(fc.constantFrom(...stageStatuses), { minLength: 4, maxLength: 4 }),
        (presentCanonical, statuses) => {
          const input = presentCanonical.map((id, i) => stage(id, statuses[i] ?? "pending"));
          const out = orderDisclosedResearchFlowStages(input);
          // Canonical phases appear as an ordered subsequence of the canonical order.
          return isOrderedSubsequence(canonicalSubsequence(out), CANONICAL_ORDER);
        }
      ),
      { numRuns: 200 }
    );
  });
});

describe("normalizeResearchTier2JobProgress ordered disclosure (Feature: clara-research, Requirement 13)", () => {
  it("orders flow_events-derived stages and maps active_stage through the alias map", () => {
    const progress = normalizeResearchTier2JobProgress({
      active_stage: "query_plan",
      flow_events: [
        { stage: "verification", status: "in_progress" },
        { stage: "answer_synthesis", status: "in_progress" },
        { stage: "query_plan", status: "in_progress" },
        { stage: "retrieval_orchestrator", status: "in_progress" }
      ]
    });
    const canonical = canonicalSubsequence(progress.flowStages);
    expect(isOrderedSubsequence(canonical, CANONICAL_ORDER)).toBe(true);
    // active_stage "query_plan" maps to the canonical "planner" id.
    expect(progress.activeStage).toBe("planner");
  });
});

describe("GRADE certainty display gating (Feature: clara-research, Requirement 8.4)", () => {
  function matrixByClaim(data: Parameters<typeof normalizeResearchTier2>[0]) {
    const entries = normalizeResearchTier2(data).telemetry.verificationMatrix;
    return new Map(entries.map((entry) => [entry.claim, entry] as const));
  }

  it("attaches a certainty label only to claims that have an assigned GRADE label", () => {
    const byClaim = matrixByClaim({
      verification_matrix: [
        { claim: "Claim A", verdict: "supported" },
        { claim: "Claim B", verdict: "supported" }
      ],
      grade: [{ claim: "Claim A", certainty: "moderate" }]
    } as never);

    // Claim A has an assigned label -> certainty is surfaced.
    expect(byClaim.get("Claim A")?.certainty).toBe("moderate");
    // Claim B has no assigned label -> no certainty is surfaced (R8.4).
    expect(byClaim.get("Claim B")?.certainty).toBeUndefined();
  });

  it("surfaces a certainty label carried inline on the matrix row", () => {
    const byClaim = matrixByClaim({
      verification_matrix: [{ claim: "Claim C", verdict: "supported", certainty: "High" }]
    } as never);
    expect(byClaim.get("Claim C")?.certainty).toBe("high");
  });

  it("never surfaces an out-of-set certainty value", () => {
    const byClaim = matrixByClaim({
      verification_matrix: [{ claim: "Claim D", verdict: "supported" }],
      grade: [{ claim: "Claim D", certainty: "definitely" }]
    } as never);
    expect(byClaim.get("Claim D")?.certainty).toBeUndefined();
  });

  it("produces no certainty labels when GRADE data is absent (flag-off shape)", () => {
    const byClaim = matrixByClaim({
      verification_matrix: [{ claim: "Claim E", verdict: "supported" }]
    } as never);
    expect(byClaim.get("Claim E")?.certainty).toBeUndefined();
  });

  it("reads certainty from traced_claims when grade array is absent", () => {
    const byClaim = matrixByClaim({
      verification_matrix: [{ claim: "Claim F", verdict: "supported" }],
      traced_claims: [{ claim: "Claim F", certainty: "very_low" }]
    } as never);
    expect(byClaim.get("Claim F")?.certainty).toBe("very_low");
  });
});

describe("Claim-to-study traceability + Citation Registry (Feature: clara-research, Requirement 11.3, 11.4)", () => {
  it("parses traced_claims and citation_registry from the result payload", () => {
    const result = normalizeResearchTier2({
      answer: "Metformin lowers HbA1c in type 2 diabetes.",
      traced_claims: [
        {
          claim: "Metformin lowers HbA1c in type 2 diabetes",
          citation_ids: ["c1", "c2"],
          verdict: "supported",
          certainty: "moderate"
        }
      ],
      citation_registry: [
        {
          citation_id: "c1",
          study_id: "PMID:12345",
          source_type: "rct",
          trust_tier: 1,
          published_at: "2021-03",
          title: "Metformin RCT",
          url: "https://pubmed.ncbi.nlm.nih.gov/12345"
        },
        { citation_id: "c2", doi: "10.1000/xyz", source_type: "cohort" }
      ]
    } as never);

    expect(result.tracedClaims).toHaveLength(1);
    expect(result.tracedClaims[0].citationIds).toEqual(["c1", "c2"]);
    expect(result.tracedClaims[0].certainty).toBe("moderate");
    expect(result.citationRegistry).toHaveLength(2);
    expect(result.citationRegistry[0].studyId).toBe("PMID:12345");
    expect(result.citationRegistry[0].trustTier).toBe(1);
    // Bare `doi` is normalized to studyId.
    expect(result.citationRegistry[1].studyId).toBe("10.1000/xyz");
  });

  it("produces empty traceability fields when the payload omits them (legacy shape)", () => {
    const result = normalizeResearchTier2({ answer: "Plain answer." } as never);
    expect(result.tracedClaims).toEqual([]);
    expect(result.citationRegistry).toEqual([]);
  });

  it("derives a deterministic, slug-safe anchor id for a citation id", () => {
    expect(citationRegistryAnchorId("c1")).toBe("citation-c1");
    expect(citationRegistryAnchorId("PMID:12345")).toBe("citation-pmid-12345");
    expect(citationRegistryAnchorId("c1")).toBe(citationRegistryAnchorId("c1"));
  });

  it("injects inline anchors after a matched claim that resolve into the registry (R11.3, R11.4)", () => {
    const answer = "Metformin lowers HbA1c in type 2 diabetes.";
    const tracedClaims = [
      { claim: "Metformin lowers HbA1c in type 2 diabetes", citationIds: ["c1", "c2"] }
    ];
    const registry = [
      { citationId: "c1" },
      { citationId: "c2" }
    ];

    const out = injectTracedClaimAnchors(answer, tracedClaims, registry);
    // Anchors are appended to the matched sentence and point into the appendix.
    expect(out).toContain("[[1]](#citation-c1)");
    expect(out).toContain("[[2]](#citation-c2)");
  });

  it("never emits an anchor for a citation id absent from the registry (no dangling anchors)", () => {
    const answer = "Drug X reduces mortality significantly across trials.";
    const tracedClaims = [
      { claim: "Drug X reduces mortality significantly across trials", citationIds: ["c1", "ghost"] }
    ];
    const registry = [{ citationId: "c1" }];

    const out = injectTracedClaimAnchors(answer, tracedClaims, registry);
    expect(out).toContain("[[1]](#citation-c1)");
    expect(out).not.toContain("ghost");
  });

  it("leaves the answer unchanged when no claim matches or inputs are empty", () => {
    const answer = "Completely unrelated narrative paragraph.";
    const tracedClaims = [
      { claim: "Metformin lowers HbA1c in type 2 diabetes", citationIds: ["c1"] }
    ];
    const registry = [{ citationId: "c1" }];

    expect(injectTracedClaimAnchors(answer, tracedClaims, registry)).toBe(answer);
    expect(injectTracedClaimAnchors(answer, [], registry)).toBe(answer);
    expect(injectTracedClaimAnchors(answer, tracedClaims, [])).toBe(answer);
  });

  it("does not inject anchors inside fenced code blocks", () => {
    const answer = [
      "```",
      "Metformin lowers HbA1c in type 2 diabetes",
      "```"
    ].join("\n");
    const tracedClaims = [
      { claim: "Metformin lowers HbA1c in type 2 diabetes", citationIds: ["c1"] }
    ];
    const registry = [{ citationId: "c1" }];

    expect(injectTracedClaimAnchors(answer, tracedClaims, registry)).toBe(answer);
  });
});
