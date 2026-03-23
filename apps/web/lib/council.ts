import api from "@/lib/http-client";

export type CouncilRunRequest = {
  symptoms: string[];
  labs: Record<string, number | string>;
  medications: string[];
  history: string;
  specialistCount: number;
  specialists: string[];
};

export type CouncilReasoningLog = {
  specialist: string;
  reasoning: string;
  recommendation?: string;
  confidence?: string;
};

export type CouncilRunRawResponse = {
  [key: string]: unknown;
};

export type CouncilRunResult = {
  specialistReasoningLogs: CouncilReasoningLog[];
  conflicts: string[];
  consensus: string;
  divergence: string[];
  finalRecommendation: string;
  isEmergency: boolean;
  escalationReason: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | undefined {
  if (typeof value === "string") {
    const next = value.trim();
    return next ? next : undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return undefined;
}

function objectToText(value: Record<string, unknown>): string {
  const lines: string[] = [];
  for (const [key, item] of Object.entries(value)) {
    if (item == null) continue;
    if (Array.isArray(item)) {
      const values = item
        .map((entry) => asText(entry))
        .filter((entry): entry is string => Boolean(entry));
      if (values.length) lines.push(`${key}: ${values.join("; ")}`);
      continue;
    }
    const direct = asText(item);
    if (direct) {
      lines.push(`${key}: ${direct}`);
      continue;
    }
    const nested = asRecord(item);
    if (nested) {
      const nestedValues = Object.entries(nested)
        .map(([nestedKey, nestedValue]) => {
          const text = asText(nestedValue);
          return text ? `${nestedKey}=${text}` : "";
        })
        .filter(Boolean);
      if (nestedValues.length) lines.push(`${key}: ${nestedValues.join(", ")}`);
    }
  }
  return lines.join("\n").trim();
}

function parseText(value: unknown): string {
  const direct = asText(value);
  if (direct) return direct;
  const record = asRecord(value);
  if (!record) return "";
  return objectToText(record);
}

function parseTextList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseText(item))
      .map((item) => item.trim())
      .filter(Boolean);
  }

  const single = parseText(value);
  return single ? [single] : [];
}

function parseReasoningLog(value: unknown, fallbackSpecialist?: string): CouncilReasoningLog | null {
  if (typeof value === "string") {
    const reasoning = value.trim();
    if (!reasoning) return null;
    return {
      specialist: fallbackSpecialist ?? "Specialist",
      reasoning
    };
  }

  const record = asRecord(value);
  if (!record) return null;

  const specialist =
    asText(record.specialist) ??
    asText(record.specialist_name) ??
    asText(record.name) ??
    asText(record.agent) ??
    asText(record.domain) ??
    fallbackSpecialist ??
    "Specialist";

  const reasoningLogList = Array.isArray(record.reasoning_log)
    ? record.reasoning_log
        .map((item) => asText(item))
        .filter((item): item is string => Boolean(item))
    : [];

  const reasoning =
    (reasoningLogList.length ? reasoningLogList.join("\n") : undefined) ??
    asText(record.reasoning) ??
    asText(record.analysis) ??
    asText(record.rationale) ??
    asText(record.log) ??
    asText(record.notes) ??
    asText(record.summary) ??
    asText(record.opinion) ??
    objectToText(record);

  const recommendation =
    asText(record.recommendation) ??
    asText(record.suggested_action) ??
    asText(record.plan) ??
    asText(record.next_step);

  const confidence = asText(record.confidence) ?? asText(record.score);

  if (!reasoning && !recommendation) return null;

  return {
    specialist,
    reasoning: reasoning || recommendation || "No reasoning details provided.",
    recommendation,
    confidence
  };
}

function parseReasoningLogs(value: unknown): CouncilReasoningLog[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseReasoningLog(item))
      .filter((item): item is CouncilReasoningLog => Boolean(item));
  }

  const record = asRecord(value);
  if (!record) {
    const single = parseReasoningLog(value);
    return single ? [single] : [];
  }

  return Object.entries(record)
    .map(([key, item]) => parseReasoningLog(item, key))
    .filter((item): item is CouncilReasoningLog => Boolean(item));
}

function pickUnknown(
  candidates: Array<Record<string, unknown> | null>,
  keys: string[]
): unknown {
  for (const candidate of candidates) {
    if (!candidate) continue;
    for (const key of keys) {
      if (candidate[key] !== undefined && candidate[key] !== null) {
        return candidate[key];
      }
    }
  }
  return undefined;
}

function parseBoolean(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  if (typeof value !== "string") return false;

  const normalized = value.trim().toLowerCase();
  if (!normalized) return false;
  return ["true", "1", "yes", "y", "emergency", "urgent", "escalate", "escalated"].includes(normalized);
}

export async function runCouncil(payload: CouncilRunRequest): Promise<CouncilRunRawResponse> {
  const response = await api.post<CouncilRunRawResponse>("/council/run", {
    symptoms: payload.symptoms,
    labs: payload.labs,
    medications: payload.medications,
    history: payload.history,
    specialist_count: payload.specialistCount,
    specialists: payload.specialists
  });

  return response.data;
}

export function normalizeCouncilRunResult(data: CouncilRunRawResponse): CouncilRunResult {
  const root = asRecord(data) ?? {};
  const candidates: Array<Record<string, unknown> | null> = [
    root,
    asRecord(root.data),
    asRecord(root.result),
    asRecord(root.output),
    asRecord(root.council),
    asRecord(root.response),
    asRecord(root.payload),
    asRecord(root.policy)
  ];

  const specialistReasoningLogs = parseReasoningLogs(
    pickUnknown(candidates, [
      "per_specialist_reasoning_logs",
      "specialist_reasoning_logs",
      "specialist_logs",
      "reasoning_logs",
      "logs",
      "specialists",
      "agents",
      "deliberation"
    ])
  );

  const conflicts = parseTextList(
    pickUnknown(candidates, ["conflict_list", "conflicts", "conflict_notes", "conflictNotes", "disagreements"])
  );

  const consensus = parseText(
    pickUnknown(candidates, ["consensus", "consensus_summary", "consensusSummary", "agreement"])
  );

  const divergence = parseTextList(
    pickUnknown(candidates, ["divergence_notes", "divergence", "dissent", "divergent_points", "differences"])
  );

  const finalRecommendation =
    parseText(
      pickUnknown(candidates, [
        "final_recommendation",
        "finalRecommendation",
        "recommendation",
        "final_decision",
        "decision",
        "summary"
      ])
    ) || "";

  const emergencyRecord = asRecord(pickUnknown(candidates, ["emergency_escalation", "emergency"]));
  const policyAction = parseText(pickUnknown(candidates, ["policy_action", "action"])).toLowerCase();
  const explicitEmergencyFlag = parseBoolean(
    pickUnknown(candidates, ["is_emergency", "escalated", "needs_escalation", "should_escalate"])
  );
  const nestedEmergency = parseBoolean(
    emergencyRecord?.triggered ?? emergencyRecord?.escalated ?? emergencyRecord?.emergency
  );
  const nestedAction = parseText(emergencyRecord?.action).toLowerCase();
  const isEmergency =
    explicitEmergencyFlag ||
    nestedEmergency ||
    policyAction.includes("escalat") ||
    policyAction.includes("urgent") ||
    nestedAction.includes("escalat") ||
    nestedAction.includes("urgent");

  const escalationReason =
    parseText(
      pickUnknown(candidates, ["emergency_reason", "escalation_reason", "escalationReason", "alert_reason"])
    ) ||
    parseTextList(emergencyRecord?.red_flags).join(", ") ||
    "";

  return {
    specialistReasoningLogs,
    conflicts,
    consensus,
    divergence,
    finalRecommendation,
    isEmergency,
    escalationReason
  };
}
