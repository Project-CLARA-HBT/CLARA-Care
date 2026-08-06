/**
 * Pure telemetry-formatting utilities for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Logic-flow node mapping, source-intel aggregation, and confidence derivation
 * extracted from the legacy page so they can be unit/property tested without
 * React (Requirement 1.2, 1.3, 6.6; design Property P7, P8). No PII is ever
 * read or emitted here — these operate only on coarse telemetry shapes.
 */

import type { UILanguage } from "@/lib/ui-language";
import type { ResearchTier2Result } from "@/lib/research";

export type LogicFlowNodeStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "warning"
  | "failed"
  | "skipped";

export type LogicFlowNode = {
  id: string;
  label: string;
  status: LogicFlowNodeStatus;
  detail?: string;
};

export type SourceIntelStatus = "active" | "connecting" | "error";

export const LOGIC_FLOW_BLUEPRINT: Array<{
  id: string;
  label: string;
  stageIds: string[];
}> = [
  {
    id: "semantic_parsing",
    label: "Semantic Parsing",
    stageIds: [
      "input_gateway",
      "session_guard",
      "safety_ingress",
      "legal_guard",
      "role_router",
      "intent_router",
      "query_canonicalizer",
      "query_decomposition",
      "planner",
      "llm_query_planner",
      "keyword_filter",
      "query_plan",
      "deep_beta_scope",
      "deep_beta_hypothesis_map",
      "deep_beta_claim_graph",
      "deep_beta_parallel_reasoning",
    ],
  },
  {
    id: "evidence_retrieval",
    label: "Evidence Retrieval",
    stageIds: [
      "hybrid_retrieval",
      "retrieval_orchestrator",
      "retrieval_internal",
      "retrieval_scientific",
      "retrieval_web",
      "retrieval_file",
      "evidence_index",
      "contradiction_miner",
      "collect_evidence",
      "source_attempts",
      "deep_retrieval_pass",
      "deep_research",
      "deep_beta_consensus",
      "deep_beta_retrieval_budget",
      "deep_beta_multi_pass_retrieval",
      "deep_beta_retrieval_pass",
      "deep_beta_gap_fill",
      "deep_beta_evidence_audit",
    ],
  },
  {
    id: "synthesis_engine",
    label: "Synthesis Engine",
    stageIds: [
      "synthesis",
      "answer_synthesis",
      "llm_generation",
      "llm_generation_retry",
      "deep_report_synthesis",
      "deep_beta_chain_synthesis",
      "deep_beta_chain_verification",
      "deep_beta_report_synthesis",
      "deep_beta_quality_gate",
      "verification",
      "verification_matrix",
      "citation_selection",
      "responder",
      "final_response",
    ],
  },
];

export const LOGIC_FLOW_LABELS: Record<string, Record<UILanguage, string>> = {
  semantic_parsing: { vi: "Phân tích ngữ nghĩa", en: "Semantic Parsing" },
  evidence_retrieval: { vi: "Truy xuất bằng chứng", en: "Evidence Retrieval" },
  synthesis_engine: { vi: "Bộ tổng hợp", en: "Synthesis Engine" },
};

export const LOGIC_FLOW_STATUS_LABELS: Record<
  LogicFlowNodeStatus,
  Record<UILanguage, string>
> = {
  pending: { vi: "đang chờ", en: "pending" },
  in_progress: { vi: "đang xử lý", en: "in progress" },
  completed: { vi: "hoàn tất", en: "completed" },
  warning: { vi: "cảnh báo", en: "warning" },
  failed: { vi: "thất bại", en: "failed" },
  skipped: { vi: "bỏ qua", en: "skipped" },
};

export function localizeLogicFlowLabel(
  nodeId: string,
  language: UILanguage,
): string {
  return (
    LOGIC_FLOW_LABELS[nodeId]?.[language] ??
    LOGIC_FLOW_LABELS[nodeId]?.en ??
    nodeId
  );
}

export function localizeLogicFlowStatus(
  status: LogicFlowNodeStatus,
  language: UILanguage,
): string {
  return LOGIC_FLOW_STATUS_LABELS[status][language];
}

/** Maps an arbitrary backend status string into a canonical flow node status. */
export function normalizeLogicFlowStatus(status?: string): LogicFlowNodeStatus {
  const text = (status ?? "").trim().toLowerCase();
  if (!text) return "pending";
  if (
    text.includes("failed") ||
    text.includes("error") ||
    text.includes("deny") ||
    text.includes("reject") ||
    text.includes("timeout")
  ) {
    return "failed";
  }
  if (
    text.includes("warning") ||
    text.includes("warn") ||
    text.includes("degraded")
  ) {
    return "warning";
  }
  if (
    text.includes("running") ||
    text.includes("in_progress") ||
    text.includes("active") ||
    text.includes("processing") ||
    text.includes("started") ||
    text.includes("streaming")
  ) {
    return "in_progress";
  }
  if (
    text.includes("completed") ||
    text.includes("complete") ||
    text.includes("done") ||
    text.includes("success") ||
    text.includes("verified") ||
    text.includes("pass") ||
    text.includes("allow")
  ) {
    return "completed";
  }
  if (text.includes("skip") || text.includes("cancel")) {
    return "skipped";
  }
  return "pending";
}

/** Reduces a set of node statuses into the most salient single status. */
export function pickLogicFlowStatus(
  statuses: LogicFlowNodeStatus[],
): LogicFlowNodeStatus {
  if (!statuses.length) return "pending";
  if (statuses.includes("failed")) return "failed";
  if (statuses.includes("in_progress")) return "in_progress";
  if (statuses.includes("warning")) return "warning";
  if (statuses.includes("completed")) return "completed";
  if (statuses.includes("skipped")) return "skipped";
  return "pending";
}

/** Builds the three-stage logic-flow timeline from a tier2 result. */
export function buildLogicFlowNodes(
  result: ResearchTier2Result | null,
): LogicFlowNode[] {
  const flowStages = result?.flowStages ?? [];
  const normalizedStages = flowStages.map((stage) => ({
    ...stage,
    normalizedId: stage.id
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_"),
    normalizedStatus: normalizeLogicFlowStatus(stage.status),
  }));

  const answerText = (result?.answer ?? "").trim();
  const hasAnswer = answerText.length > 0;
  const keywordCount = result?.telemetry.keywords.length ?? 0;
  const sourceAttemptCount = result?.telemetry.sourceAttempts.length ?? 0;
  const docCount = result?.telemetry.docs.length ?? 0;
  const citationCount = result?.citations.length ?? 0;
  const telemetryErrorCount = result?.telemetry.errors.length ?? 0;

  const fallbackStatusForNode = (nodeId: string): LogicFlowNodeStatus => {
    if (!result) return "pending";
    if (nodeId === "semantic_parsing") {
      if (keywordCount > 0 || result.steps.length > 0 || hasAnswer)
        return "completed";
      return "pending";
    }
    if (nodeId === "evidence_retrieval") {
      if (docCount > 0 || citationCount > 0) {
        return telemetryErrorCount > 0 ? "warning" : "completed";
      }
      if (sourceAttemptCount > 0) return "in_progress";
      if (telemetryErrorCount > 0) return "failed";
      return hasAnswer ? "completed" : "pending";
    }
    if (nodeId === "synthesis_engine") {
      if (hasAnswer) return "completed";
      if (docCount > 0 || citationCount > 0) return "in_progress";
      return "pending";
    }
    return "pending";
  };

  const fallbackDetailForNode = (nodeId: string): string | undefined => {
    if (!result) return undefined;
    if (nodeId === "semantic_parsing" && keywordCount > 0) {
      return `keyword filter: ${keywordCount} terms`;
    }
    if (
      nodeId === "evidence_retrieval" &&
      (docCount > 0 || sourceAttemptCount > 0)
    ) {
      return `${docCount} docs · ${sourceAttemptCount} source attempts`;
    }
    if (nodeId === "synthesis_engine" && hasAnswer) {
      return "Answer generated";
    }
    return undefined;
  };

  return LOGIC_FLOW_BLUEPRINT.map((node) => {
    const stageIdSet = new Set(node.stageIds);
    const matchedStages = normalizedStages.filter((stage) =>
      stageIdSet.has(stage.normalizedId),
    );
    const matchedStatuses = matchedStages.map(
      (stage) => stage.normalizedStatus,
    );
    const status = matchedStatuses.length
      ? pickLogicFlowStatus(matchedStatuses)
      : fallbackStatusForNode(node.id);
    const detail =
      matchedStages
        .slice()
        .reverse()
        .find((stage) => stage.detail)?.detail ??
      fallbackDetailForNode(node.id);
    return { id: node.id, label: node.label, status, detail };
  });
}

/** Normalizes a source attempt status into a coarse source-intel status. */
export function normalizeSourceStatus(
  status?: string,
  hasError?: boolean,
): SourceIntelStatus {
  if (hasError) return "error";
  const text = (status ?? "").trim().toLowerCase();
  if (!text) return "active";
  if (
    text.includes("fail") ||
    text.includes("error") ||
    text.includes("timeout") ||
    text.includes("denied") ||
    text.includes("rejected")
  ) {
    return "error";
  }
  if (
    text.includes("pending") ||
    text.includes("queue") ||
    text.includes("running") ||
    text.includes("connect") ||
    text.includes("in_progress")
  ) {
    return "connecting";
  }
  return "active";
}

/** Heuristic: is this source name a Vietnamese MoH / local medical source? */
export function isVietnamMedicalSource(name: string): boolean {
  const normalized = name.toLowerCase();
  return (
    normalized.includes("dav") ||
    normalized.includes("kcb") ||
    normalized.includes(".vn") ||
    normalized.includes("vietnam")
  );
}

export type SourceIntelItem = {
  name: string;
  status: SourceIntelStatus;
  query?: string;
  attempts: number;
};

export type SourceIntelSummary = {
  activeCount: number;
  all: SourceIntelItem[];
  global: SourceIntelItem[];
  vietnam: SourceIntelItem[];
};

/** Aggregates source attempts + citations into a deduplicated source-intel view. */
export function buildSourceIntel(
  result: ResearchTier2Result | null,
): SourceIntelSummary {
  const merged = new Map<string, SourceIntelItem>();

  for (const attempt of result?.telemetry.sourceAttempts ?? []) {
    const sourceName = (attempt.source || "unknown").trim() || "unknown";
    const key = sourceName.toLowerCase();
    const nextStatus = normalizeSourceStatus(
      attempt.status,
      Boolean(attempt.error),
    );
    const current = merged.get(key);
    const status: SourceIntelStatus =
      current?.status === "error" || nextStatus === "error"
        ? "error"
        : current?.status === "connecting" || nextStatus === "connecting"
          ? "connecting"
          : "active";
    merged.set(key, {
      name: current?.name ?? sourceName,
      status,
      query: current?.query ?? attempt.query ?? attempt.subquery,
      attempts: (current?.attempts ?? 0) + 1,
    });
  }

  for (const citation of result?.citations ?? []) {
    const sourceName = (citation.source || citation.title || "").trim();
    if (!sourceName) continue;
    const key = sourceName.toLowerCase();
    if (!merged.has(key)) {
      merged.set(key, {
        name: sourceName,
        status: "active",
        query: undefined,
        attempts: 0,
      });
    }
  }

  const items = Array.from(merged.values()).sort((left, right) => {
    const severity = (value: SourceIntelStatus) =>
      value === "error" ? 0 : value === "connecting" ? 1 : 2;
    const diff = severity(left.status) - severity(right.status);
    if (diff !== 0) return diff;
    return right.attempts - left.attempts;
  });

  return {
    activeCount: items.filter((item) => item.status === "active").length,
    all: items,
    global: items.filter((item) => !isVietnamMedicalSource(item.name)),
    vietnam: items.filter((item) => isVietnamMedicalSource(item.name)),
  };
}

/** Normalizes a raw confidence value (0..1, 0..100, or undefined) to a ratio. */
export function normalizeConfidenceRatio(
  value: number | undefined,
): number | undefined {
  if (value === undefined || !Number.isFinite(value) || value < 0)
    return undefined;
  if (value <= 1) return value;
  if (value <= 100) return value / 100;
  return undefined;
}

/**
 * Confidence is intentionally not rendered until the API contract carries a
 * calibration/version marker. Raw provider, routing, retrieval, and verifier
 * scores are not interchangeable probabilities and must not be averaged into
 * a patient-facing percentage.
 */
export function resolveTelemetryConfidence(
  _result: ResearchTier2Result | null,
): number | undefined {
  return undefined;
}
