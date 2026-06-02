import { CouncilReasoningLog, CouncilRunSnapshot } from "@/lib/council";

type UnknownRecord = Record<string, unknown>;

export type CouncilCitation = {
  title: string;
  source?: string;
  url?: string;
  snippet?: string;
  publishedAt?: string;
};

export type CouncilDeepDiveSection = {
  title: string;
  items: string[];
};

export type CouncilViewModel = {
  snapshot: CouncilRunSnapshot;
  createdAtLabel: string;
  urgencyTone: "stable" | "emergency";
  urgencyLabel: string;
  requestSummary: {
    symptoms: string[];
    labs: Array<{ name: string; value: string }>;
    medications: string[];
    history: string;
    specialists: string[];
  };
  summary: {
    finalRecommendation: string;
    consensus: string;
    conflicts: string[];
    divergence: string[];
    escalationReason: string;
  };
  quality: {
    supportRatio: number | null;
    disagreementIndex: number | null;
    conflictCount: number | null;
    strongestDissent: string;
    strongestDissentVotes: number | null;
    escalationPriority: string;
    recommendedSlaMinutes: number | null;
    requiresHumanHandoff: boolean;
    citationAverageStrength: number | null;
    citationTotal: number | null;
    neuralEnabled: boolean;
    neuralProbability: number | null;
    neuralBand: string;
    neuralRecommendedTriage: string;
  };
  analyze: {
    keySignals: string[];
    riskDrivers: string[];
    actionItems: string[];
  };
  details: {
    specialistLogs: CouncilReasoningLog[];
  };
  citations: CouncilCitation[];
  research: {
    highlights: string[];
    openQuestions: string[];
    nextSteps: string[];
  };
  deepDive: {
    sections: CouncilDeepDiveSection[];
    rawPreview: string;
  };
  timeline: {
    steps: Array<{
      sequence: number;
      step: string;
      detail: string;
    }>;
  };
};

function asRecord(value: unknown): UnknownRecord | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as UnknownRecord;
}

function asText(value: unknown): string | undefined {
  if (typeof value === "string") {
    const text = value.trim();
    return text || undefined;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  return undefined;
}

function recordToText(record: UnknownRecord): string {
  const chunks: string[] = [];
  for (const [key, value] of Object.entries(record)) {
    if (value == null) continue;

    if (Array.isArray(value)) {
      const rows = value.map((item) => asText(item)).filter((item): item is string => Boolean(item));
      if (rows.length) chunks.push(`${key}: ${rows.join("; ")}`);
      continue;
    }

    const direct = asText(value);
    if (direct) {
      chunks.push(`${key}: ${direct}`);
      continue;
    }

    const nested = asRecord(value);
    if (nested) {
      const nestedText = Object.entries(nested)
        .map(([nestedKey, nestedValue]) => {
          const text = asText(nestedValue);
          return text ? `${nestedKey}=${text}` : "";
        })
        .filter(Boolean)
        .join(", ");
      if (nestedText) chunks.push(`${key}: ${nestedText}`);
    }
  }
  return chunks.join("\n").trim();
}

function parseText(value: unknown): string {
  const direct = asText(value);
  if (direct) return direct;
  const record = asRecord(value);
  if (record) return recordToText(record);
  return "";
}

function splitBySentence(value: string): string[] {
  return value
    .split(/\n|\r|\.|;|\u2022|\-/g)
    .map((item) => item.trim())
    .filter((item) => item.length >= 4);
}

function uniqueStrings(values: string[], maxItems = 24): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];

  for (const item of values) {
    const text = item.trim();
    if (!text) continue;
    const key = text.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    normalized.push(text);
    if (normalized.length >= maxItems) break;
  }

  return normalized;
}

function parseTextList(value: unknown, maxItems = 24): string[] {
  if (Array.isArray(value)) {
    const rows = value
      .flatMap((item) => {
        const text = parseText(item);
        if (!text) return [];
        return splitBySentence(text).length > 1 ? splitBySentence(text) : [text];
      })
      .filter(Boolean);
    return uniqueStrings(rows, maxItems);
  }

  const single = parseText(value);
  if (!single) return [];
  const chunks = splitBySentence(single);
  if (chunks.length > 1) return uniqueStrings(chunks, maxItems);
  return [single];
}

function pickUnknown(candidates: Array<UnknownRecord | null>, keys: string[]): unknown {
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

function collectFromKeys(candidates: Array<UnknownRecord | null>, keys: string[], maxItems = 24): string[] {
  const values: string[] = [];
  for (const candidate of candidates) {
    if (!candidate) continue;
    for (const key of keys) {
      if (candidate[key] === undefined || candidate[key] === null) continue;
      values.push(...parseTextList(candidate[key], maxItems));
    }
  }
  return uniqueStrings(values, maxItems);
}

function parseCitation(value: unknown): CouncilCitation | null {
  if (typeof value === "string") {
    const text = value.trim();
    if (!text) return null;
    return { title: text };
  }

  const record = asRecord(value);
  if (!record) return null;

  const title =
    asText(record.title) ??
    asText(record.paper) ??
    asText(record.name) ??
    asText(record.label) ??
    asText(record.citation) ??
    asText(record.reference) ??
    parseText(record);

  if (!title) return null;

  const source =
    asText(record.source) ??
    asText(record.journal) ??
    asText(record.publisher) ??
    asText(record.domain) ??
    asText(record.database);

  const url = asText(record.url) ?? asText(record.href) ?? asText(record.link);
  const snippet = asText(record.snippet) ?? asText(record.summary) ?? asText(record.excerpt) ?? asText(record.quote);
  const publishedAt =
    asText(record.published_at) ??
    asText(record.publishedAt) ??
    asText(record.date) ??
    asText(record.year);

  return {
    title,
    source,
    url,
    snippet,
    publishedAt,
  };
}

function parseCitationList(value: unknown): CouncilCitation[] {
  if (Array.isArray(value)) {
    return value.map((item) => parseCitation(item)).filter((item): item is CouncilCitation => Boolean(item));
  }

  const record = asRecord(value);
  if (!record) {
    const single = parseCitation(value);
    return single ? [single] : [];
  }

  if (Array.isArray(record.citations)) return parseCitationList(record.citations);
  if (Array.isArray(record.sources)) return parseCitationList(record.sources);
  if (Array.isArray(record.references)) return parseCitationList(record.references);

  return Object.values(record)
    .map((item) => parseCitation(item))
    .filter((item): item is CouncilCitation => Boolean(item));
}

function extractCitations(candidates: Array<UnknownRecord | null>): CouncilCitation[] {
  const lists: CouncilCitation[] = [];

  const attribution = pickUnknown(candidates, ["attribution"]);
  const attributionRecord = asRecord(attribution);
  if (attributionRecord?.citations) {
    lists.push(...parseCitationList(attributionRecord.citations));
  }

  const citationKeys = [
    "citations",
    "references",
    "source_documents",
    "sources",
    "evidence",
    "supporting_evidence",
    "bibliography",
  ];

  for (const key of citationKeys) {
    const value = pickUnknown(candidates, [key]);
    if (!value) continue;
    lists.push(...parseCitationList(value));
  }

  const deduped = new Map<string, CouncilCitation>();
  for (const item of lists) {
    const key = `${item.title}|${item.url ?? ""}`.toLowerCase();
    if (!deduped.has(key)) deduped.set(key, item);
  }

  return Array.from(deduped.values()).slice(0, 24);
}

function buildDeepDiveSections(candidates: Array<UnknownRecord | null>, snapshot: CouncilRunSnapshot): CouncilDeepDiveSection[] {
  const definitions = [
    {
      title: "Differential Diagnosis",
      keys: ["differential_diagnosis", "differentials", "diagnostic_hypotheses", "working_diagnosis"],
    },
    {
      title: "Risk Stratification",
      keys: ["risk_stratification", "risk_profile", "red_flags", "high_risk_features"],
    },
    {
      title: "Recommended Tests",
      keys: ["recommended_tests", "test_plan", "diagnostic_plan", "additional_tests"],
    },
    {
      title: "Monitoring & Follow-up",
      keys: ["monitoring_plan", "follow_up", "followup", "reassessment_plan", "next_steps"],
    },
    {
      title: "Policy & Guardrail Trace",
      keys: ["policy", "policy_notes", "guardrails", "safety_checks", "safety"],
    },
  ] as const;

  const sections = definitions
    .map((definition) => ({
      title: definition.title,
      items: collectFromKeys(candidates, definition.keys as unknown as string[], 12),
    }))
    .filter((section) => section.items.length > 0);

  if (sections.length > 0) return sections;

  if (!snapshot.result.specialistReasoningLogs.length) return [];

  return snapshot.result.specialistReasoningLogs.slice(0, 5).map((log) => ({
    title: log.specialist,
    items: uniqueStrings([log.reasoning, log.recommendation ?? ""].filter(Boolean), 6),
  }));
}

function stringifyRawPreview(raw: unknown): string {
  try {
    const json = JSON.stringify(raw, null, 2);
    if (!json) return "{}";
    if (json.length <= 8000) return json;
    return `${json.slice(0, 8000)}\n... (truncated)`;
  } catch {
    return "{}";
  }
}

function formatLabs(labs: Record<string, number | string>): Array<{ name: string; value: string }> {
  return Object.entries(labs)
    .map(([name, value]) => {
      const text = asText(value) ?? "";
      return { name, value: text };
    })
    .filter((row) => row.name.trim() && row.value.trim())
    .slice(0, 80);
}

function resolveActionItems(candidates: Array<UnknownRecord | null>, fallback: string): string[] {
  const direct = collectFromKeys(
    candidates,
    [
      "action_items",
      "recommended_actions",
      "next_steps",
      "care_plan",
      "treatment_plan",
      "monitoring_plan",
      "follow_up_plan",
    ],
    16
  );

  if (direct.length > 0) return direct;

  if (!fallback.trim()) return [];
  return uniqueStrings(splitBySentence(fallback), 12);
}

export function formatCouncilDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN", { hour12: false });
}

export function buildCouncilView(snapshot: CouncilRunSnapshot): CouncilViewModel {
  const rawRoot = asRecord(snapshot.raw) ?? {};
  const resultRecord = asRecord(snapshot.result as unknown) ?? {};
  const candidates: Array<UnknownRecord | null> = [
    rawRoot,
    asRecord(rawRoot.data),
    asRecord(rawRoot.result),
    asRecord(rawRoot.output),
    asRecord(rawRoot.council),
    asRecord(rawRoot.response),
    asRecord(rawRoot.payload),
    asRecord(rawRoot.policy),
    resultRecord,
  ];

  const keySignals = collectFromKeys(
    candidates,
    ["key_findings", "critical_findings", "signals", "red_flags", "alerts", "highlights"],
    16
  );

  const riskDrivers = uniqueStrings(
    [
      ...collectFromKeys(
        candidates,
        ["risk_factors", "risk_drivers", "danger_signals", "escalation_triggers", "red_flags"],
        16
      ),
      ...snapshot.result.conflicts,
      ...snapshot.result.divergence,
      snapshot.result.escalationReason,
    ],
    16
  );

  const actionItems = resolveActionItems(candidates, snapshot.result.finalRecommendation);

  const researchHighlights = collectFromKeys(
    candidates,
    ["research_summary", "research_highlights", "insights", "key_insights", "evidence_summary"],
    14
  );

  const openQuestions = collectFromKeys(
    candidates,
    ["open_questions", "unanswered_questions", "knowledge_gaps", "uncertainties", "pending_questions"],
    14
  );

  const nextSteps = collectFromKeys(
    candidates,
    ["next_steps", "follow_up", "followup", "recommended_tests", "monitoring_plan", "care_plan"],
    14
  );

  const defaultHighlights = snapshot.result.consensus ? [snapshot.result.consensus] : [];

  return {
    snapshot,
    createdAtLabel: formatCouncilDate(snapshot.createdAt),
    urgencyTone: snapshot.result.isEmergency ? "emergency" : "stable",
    urgencyLabel: snapshot.result.isEmergency ? "Cần leo thang khẩn" : "Tạm ổn định",
    requestSummary: {
      symptoms: snapshot.request.symptoms,
      labs: formatLabs(snapshot.request.labs),
      medications: snapshot.request.medications,
      history: snapshot.request.history,
      specialists: snapshot.request.specialists,
    },
    summary: {
      finalRecommendation: snapshot.result.finalRecommendation,
      consensus: snapshot.result.consensus,
      conflicts: snapshot.result.conflicts,
      divergence: snapshot.result.divergence,
      escalationReason: snapshot.result.escalationReason,
    },
    quality: {
      supportRatio: snapshot.result.consensusMetadata?.supportRatio ?? null,
      disagreementIndex: snapshot.result.consensusMetadata?.disagreementIndex ?? null,
      conflictCount: snapshot.result.consensusMetadata?.conflictCount ?? null,
      strongestDissent: snapshot.result.consensusMetadata?.strongestDissent ?? "",
      strongestDissentVotes: snapshot.result.consensusMetadata?.strongestDissentVotes ?? null,
      escalationPriority: snapshot.result.escalationMetadata?.priority ?? "",
      recommendedSlaMinutes: snapshot.result.escalationMetadata?.recommendedSlaMinutes ?? null,
      requiresHumanHandoff: snapshot.result.escalationMetadata?.requiresHumanHandoff ?? false,
      citationAverageStrength: snapshot.result.citationQuality?.averageEvidenceStrength ?? null,
      citationTotal: snapshot.result.citationQuality?.totalCitations ?? null,
      neuralEnabled: snapshot.result.neuralRisk?.enabled ?? false,
      neuralProbability: snapshot.result.neuralRisk?.riskProbability ?? null,
      neuralBand: snapshot.result.neuralRisk?.riskBand ?? "",
      neuralRecommendedTriage: snapshot.result.neuralRisk?.recommendedTriage ?? "",
    },
    analyze: {
      keySignals,
      riskDrivers,
      actionItems,
    },
    details: {
      specialistLogs: snapshot.result.specialistReasoningLogs,
    },
    citations: extractCitations(candidates),
    research: {
      highlights: researchHighlights.length ? researchHighlights : defaultHighlights,
      openQuestions: openQuestions.length ? openQuestions : snapshot.result.divergence,
      nextSteps: nextSteps.length ? nextSteps : actionItems,
    },
    deepDive: {
      sections: buildDeepDiveSections(candidates, snapshot),
      rawPreview: stringifyRawPreview(snapshot.raw),
    },
    timeline: {
      steps: snapshot.result.reasoningTimeline.map((item) => ({
        sequence: item.sequence,
        step: item.step,
        detail: item.detail,
      })),
    },
  };
}
