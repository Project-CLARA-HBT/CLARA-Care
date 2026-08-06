import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  buildLogicFlowNodes,
  buildSourceIntel,
  isVietnamMedicalSource,
  localizeLogicFlowLabel,
  localizeLogicFlowStatus,
  normalizeConfidenceRatio,
  normalizeLogicFlowStatus,
  normalizeSourceStatus,
  pickLogicFlowStatus,
  resolveTelemetryConfidence,
  type LogicFlowNodeStatus,
} from "@/app/chat/_v2/lib/telemetry-format";
import type { ResearchTier2Result } from "@/lib/research";

/**
 * Feature: clara-chat-redesign, Property P5 (flow status mapping) + P7
 * (telemetry derivation). Validates Requirement 2.3, 3.2, 6.6.
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

function makeResult(overrides: Partial<ResearchTier2Result> = {}): ResearchTier2Result {
  return {
    answer: "",
    citations: [],
    steps: [],
    flowStages: [],
    flowEvents: [],
    telemetry: emptyTelemetry(),
    visualAssets: [],
    chartSpecs: [],
    reasoningDigest: { items: [] } as unknown as ResearchTier2Result["reasoningDigest"],
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
    },
    ...overrides,
  };
}

describe("normalizeLogicFlowStatus", () => {
  it("maps backend status strings to canonical statuses", () => {
    expect(normalizeLogicFlowStatus("failed")).toBe("failed");
    expect(normalizeLogicFlowStatus("timeout")).toBe("failed");
    expect(normalizeLogicFlowStatus("degraded")).toBe("warning");
    expect(normalizeLogicFlowStatus("running")).toBe("in_progress");
    expect(normalizeLogicFlowStatus("completed")).toBe("completed");
    expect(normalizeLogicFlowStatus("skipped")).toBe("skipped");
    expect(normalizeLogicFlowStatus("")).toBe("pending");
    expect(normalizeLogicFlowStatus(undefined)).toBe("pending");
  });

  it("Property: always returns a valid status", () => {
    const valid: LogicFlowNodeStatus[] = [
      "pending",
      "in_progress",
      "completed",
      "warning",
      "failed",
      "skipped",
    ];
    fc.assert(fc.property(fc.string(), (s) => valid.includes(normalizeLogicFlowStatus(s))));
  });
});

describe("pickLogicFlowStatus", () => {
  it("prioritizes failed > in_progress > warning > completed > skipped", () => {
    expect(pickLogicFlowStatus(["completed", "failed", "in_progress"])).toBe("failed");
    expect(pickLogicFlowStatus(["completed", "in_progress"])).toBe("in_progress");
    expect(pickLogicFlowStatus(["completed", "warning"])).toBe("warning");
    expect(pickLogicFlowStatus(["completed", "skipped"])).toBe("completed");
    expect(pickLogicFlowStatus([])).toBe("pending");
  });
});

describe("buildLogicFlowNodes", () => {
  it("returns three blueprint nodes", () => {
    const nodes = buildLogicFlowNodes(makeResult());
    expect(nodes.map((n) => n.id)).toEqual([
      "semantic_parsing",
      "evidence_retrieval",
      "synthesis_engine",
    ]);
  });

  it("marks synthesis completed when an answer exists", () => {
    const nodes = buildLogicFlowNodes(makeResult({ answer: "done" }));
    const synth = nodes.find((n) => n.id === "synthesis_engine");
    expect(synth?.status).toBe("completed");
  });

  it("maps explicit flow stages into the matching node", () => {
    const result = makeResult({
      flowStages: [
        { id: "llm_generation", label: "Gen", status: "completed", source: "ml" },
      ] as unknown as ResearchTier2Result["flowStages"],
    });
    const nodes = buildLogicFlowNodes(result);
    expect(nodes.find((n) => n.id === "synthesis_engine")?.status).toBe("completed");
  });

  it("returns pending nodes for a null result", () => {
    const nodes = buildLogicFlowNodes(null);
    expect(nodes.every((n) => n.status === "pending")).toBe(true);
  });
});

describe("localize helpers", () => {
  it("localizes labels and statuses", () => {
    expect(localizeLogicFlowLabel("synthesis_engine", "vi")).toBe("Bộ tổng hợp");
    expect(localizeLogicFlowLabel("unknown_node", "vi")).toBe("unknown_node");
    expect(localizeLogicFlowStatus("completed", "vi")).toBe("hoàn tất");
    expect(localizeLogicFlowStatus("completed", "en")).toBe("completed");
  });
});

describe("normalizeSourceStatus", () => {
  it("maps to active / connecting / error", () => {
    expect(normalizeSourceStatus(undefined, true)).toBe("error");
    expect(normalizeSourceStatus("timeout")).toBe("error");
    expect(normalizeSourceStatus("pending")).toBe("connecting");
    expect(normalizeSourceStatus("ok")).toBe("active");
    expect(normalizeSourceStatus("")).toBe("active");
  });
});

describe("isVietnamMedicalSource", () => {
  it("detects VN medical sources", () => {
    expect(isVietnamMedicalSource("DAV Vietnam")).toBe(true);
    expect(isVietnamMedicalSource("kcb.vn")).toBe(true);
    expect(isVietnamMedicalSource("PubMed")).toBe(false);
  });
});

describe("buildSourceIntel", () => {
  it("aggregates and dedupes source attempts, counting active", () => {
    const result = makeResult({
      telemetry: {
        ...emptyTelemetry(),
        sourceAttempts: [
          { source: "PubMed", status: "ok" },
          { source: "pubmed", status: "ok" },
          { source: "DailyMed", status: "timeout", error: "x" },
        ],
      } as unknown as ResearchTier2Result["telemetry"],
    });
    const intel = buildSourceIntel(result);
    expect(intel.all).toHaveLength(2);
    const pubmed = intel.all.find((s) => s.name === "PubMed");
    expect(pubmed?.attempts).toBe(2);
    expect(intel.all[0].status).toBe("error"); // errors sorted first
    expect(intel.activeCount).toBe(1);
  });

  it("handles a null result", () => {
    const intel = buildSourceIntel(null);
    expect(intel.all).toEqual([]);
    expect(intel.activeCount).toBe(0);
  });
});

describe("normalizeConfidenceRatio", () => {
  it("normalizes 0..1 and 0..100 ranges", () => {
    expect(normalizeConfidenceRatio(0.5)).toBe(0.5);
    expect(normalizeConfidenceRatio(80)).toBe(0.8);
    expect(normalizeConfidenceRatio(-1)).toBeUndefined();
    expect(normalizeConfidenceRatio(200)).toBeUndefined();
    expect(normalizeConfidenceRatio(undefined)).toBeUndefined();
  });

  it("Property: output is within [0,1] or undefined", () => {
    fc.assert(
      fc.property(fc.double({ noNaN: true }), (v) => {
        const r = normalizeConfidenceRatio(v);
        return r === undefined || (r >= 0 && r <= 1);
      })
    );
  });
});

describe("resolveTelemetryConfidence", () => {
  it("does not expose an uncalibrated verifier score as confidence", () => {
    const result = makeResult({ verificationStatus: { confidence: 0.9 } });
    expect(resolveTelemetryConfidence(result)).toBeUndefined();
  });

  it("returns undefined when there is no signal", () => {
    expect(resolveTelemetryConfidence(makeResult())).toBeUndefined();
    expect(resolveTelemetryConfidence(null)).toBeUndefined();
  });

  it("Property: any returned confidence is in [0,1]", () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 12 }), fc.boolean(), (citations, hasAnswer) => {
        const result = makeResult({
          answer: hasAnswer ? "x" : "",
          citations: Array.from({ length: citations }, () => ({
            title: "t",
          })) as unknown as ResearchTier2Result["citations"],
        });
        const c = resolveTelemetryConfidence(result);
        return c === undefined || (c >= 0 && c <= 1);
      })
    );
  });
});
