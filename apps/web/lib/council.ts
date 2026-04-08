import api from "@/lib/http-client";

export type CouncilRunRequest = {
  symptoms: string[];
  labs: Record<string, number | string>;
  medications: string[];
  history: string;
  specialistCount: number;
  specialists: string[];
};

export type CouncilIntakeRequest = {
  transcript?: string;
  audioFile?: File | null;
};

export type CouncilConsultRequest = {
  transcript?: string;
  symptoms?: string[];
  labs?: Record<string, number | string>;
  medications?: string[];
  history?: string;
  specialists?: string[];
  specialistCount?: number;
};

export type CouncilIntakeResult = {
  transcript: string;
  symptomsInput: string;
  labsInput: string;
  medicationsInput: string;
  historyInput: string;
  modelUsed: string;
  warnings: string[];
  fieldConfidence?: Record<string, number>;
  missingFields?: string[];
  councilPayload?: {
    symptoms: string[];
    labs: Record<string, number>;
    medications: string[];
    history: string[];
  };
};

export type CouncilReasoningLog = {
  specialist: string;
  reasoning: string;
  recommendation?: string;
  confidence?: string;
};

export type CouncilCitation = {
  source: string;
  title: string;
  url?: string;
  summary?: string;
  specialist?: string;
};

export type CouncilConsensusMetadata = {
  winningTriage: string;
  voteBreakdown: Record<string, number>;
  supportRatio: number | null;
  disagreementIndex: number | null;
  conflictCount: number | null;
  strongestDissent: string;
  strongestDissentVotes: number | null;
};

export type CouncilEscalationMetadata = {
  priority: string;
  recommendedSlaMinutes: number | null;
  requiresHumanHandoff: boolean;
  generatedAtUtc?: string;
};

export type CouncilCitationQuality = {
  totalCitations: number | null;
  averageEvidenceStrength: number | null;
  highSignalCount: number | null;
  supportingSignalCount: number | null;
  contextOnlyCount: number | null;
  negatedContextCount: number | null;
};

export type CouncilReasoningTimelineStep = {
  sequence: number;
  step: string;
  detail: string;
  metadata: Record<string, unknown>;
};

export type CouncilNeuralRisk = {
  enabled: boolean;
  shadowMode: boolean;
  modelVersion: string;
  riskProbability: number | null;
  riskBand: string;
  recommendedTriage: string;
  topContributors: Array<{
    feature: string;
    impact: number | null;
    direction: string;
  }>;
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
  confidenceScore: number | null;
  dataQualityScore: number | null;
  missingInfoQuestions: string[];
  uncertaintyNotes: string[];
  citations: CouncilCitation[];
  consensusMetadata: CouncilConsensusMetadata | null;
  escalationMetadata: CouncilEscalationMetadata | null;
  citationQuality: CouncilCitationQuality | null;
  reasoningTimeline: CouncilReasoningTimelineStep[];
  neuralRisk: CouncilNeuralRisk | null;
  analysisSections: {
    analyze: string[];
    details: string[];
    research: string[];
    deepdive: string[];
    citations: string[];
  };
};

export type CouncilCaseDraft = {
  symptomsInput: string;
  labsInput: string;
  medicationsInput: string;
  historyInput: string;
  specialistCount: number;
  selectedSpecialists: string[];
};

export type CouncilRunSnapshot = {
  request: CouncilRunRequest;
  result: CouncilRunResult;
  raw: CouncilRunRawResponse;
  createdAt: string;
};

const COUNCIL_DRAFT_KEY = "clara.council.draft.v1";
const COUNCIL_RESULT_KEY = "clara.council.result.v1";

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

function parseNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const parsed = Number(value.trim());
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => asText(item))
    .filter((item): item is string => Boolean(item));
}

function parseCitationList(value: unknown): CouncilCitation[] {
  if (!Array.isArray(value)) return [];
  const citations: CouncilCitation[] = [];
  for (const item of value) {
    const row = asRecord(item);
    if (!row) continue;
    const source = asText(row.source) ?? asText(row.journal) ?? asText(row.publisher) ?? "Clinical source";
    const title = asText(row.title) ?? asText(row.label) ?? source;
    const url = asText(row.url);
    const summary = asText(row.summary) ?? asText(row.note);
    const specialist = asText(row.specialist);
    citations.push({
      source,
      title,
      url,
      summary,
      specialist
    });
  }
  return citations;
}

function parseAnalysisSection(value: unknown): string[] {
  if (Array.isArray(value)) return parseStringArray(value);
  const text = parseText(value);
  return text ? [text] : [];
}

function parseConsensusMetadata(value: unknown): CouncilConsensusMetadata | null {
  const record = asRecord(value);
  if (!record) return null;

  const voteBreakdownRaw = asRecord(record.vote_breakdown) ?? asRecord(record.voteBreakdown) ?? {};
  const voteBreakdown: Record<string, number> = {};
  for (const [key, item] of Object.entries(voteBreakdownRaw)) {
    const parsed = parseNumber(item);
    voteBreakdown[key] = parsed ?? 0;
  }

  return {
    winningTriage: asText(record.winning_triage) ?? asText(record.winningTriage) ?? "",
    voteBreakdown,
    supportRatio: parseNumber(record.support_ratio ?? record.supportRatio),
    disagreementIndex: parseNumber(record.disagreement_index ?? record.disagreementIndex),
    conflictCount: parseNumber(record.conflict_count ?? record.conflictCount),
    strongestDissent: asText(record.strongest_dissent) ?? asText(record.strongestDissent) ?? "",
    strongestDissentVotes: parseNumber(record.strongest_dissent_votes ?? record.strongestDissentVotes)
  };
}

function parseEscalationMetadata(value: unknown): CouncilEscalationMetadata | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    priority: asText(record.priority) ?? "",
    recommendedSlaMinutes: parseNumber(record.recommended_sla_minutes ?? record.recommendedSlaMinutes),
    requiresHumanHandoff: parseBoolean(record.requires_human_handoff ?? record.requiresHumanHandoff),
    generatedAtUtc: asText(record.generated_at_utc) ?? asText(record.generatedAtUtc)
  };
}

function parseCitationQuality(value: unknown): CouncilCitationQuality | null {
  const record = asRecord(value);
  if (!record) return null;
  return {
    totalCitations: parseNumber(record.total_citations ?? record.totalCitations),
    averageEvidenceStrength: parseNumber(record.average_evidence_strength ?? record.averageEvidenceStrength),
    highSignalCount: parseNumber(record.high_signal_count ?? record.highSignalCount),
    supportingSignalCount: parseNumber(record.supporting_signal_count ?? record.supportingSignalCount),
    contextOnlyCount: parseNumber(record.context_only_count ?? record.contextOnlyCount),
    negatedContextCount: parseNumber(record.negated_context_count ?? record.negatedContextCount),
  };
}

function parseReasoningTimeline(value: unknown): CouncilReasoningTimelineStep[] {
  if (!Array.isArray(value)) return [];

  return value
    .map((item) => {
      const record = asRecord(item);
      if (!record) return null;
      const sequence = parseNumber(record.sequence) ?? 0;
      const step = asText(record.step) ?? "";
      const detail = asText(record.detail) ?? "";
      const metadata = asRecord(record.metadata) ?? {};
      if (!step && !detail) return null;
      return {
        sequence,
        step,
        detail,
        metadata
      } satisfies CouncilReasoningTimelineStep;
    })
    .filter((item): item is CouncilReasoningTimelineStep => Boolean(item))
    .sort((a, b) => a.sequence - b.sequence);
}

function parseNeuralRisk(value: unknown): CouncilNeuralRisk | null {
  const record = asRecord(value);
  if (!record) return null;
  const contributorsRaw = Array.isArray(record.top_contributors) ? record.top_contributors : [];
  const topContributors = contributorsRaw
    .map((item) => {
      const row = asRecord(item);
      if (!row) return null;
      return {
        feature: asText(row.feature) ?? "",
        impact: parseNumber(row.impact),
        direction: asText(row.direction) ?? "",
      };
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item));

  return {
    enabled: parseBoolean(record.enabled),
    shadowMode: parseBoolean(record.shadow_mode ?? record.shadowMode),
    modelVersion: asText(record.model_version) ?? asText(record.modelVersion) ?? "",
    riskProbability: parseNumber(record.risk_probability ?? record.riskProbability),
    riskBand: asText(record.risk_band) ?? asText(record.riskBand) ?? "",
    recommendedTriage:
      asText(record.recommended_triage) ?? asText(record.recommendedTriage) ?? "",
    topContributors,
  };
}

function formatLabsInput(value: unknown): string {
  const rows = Array.isArray(value) ? value : [];
  const formattedRows = rows
    .map((item) => {
      const record = asRecord(item);
      if (!record) return "";
      const name = asText(record.name) ?? asText(record.key) ?? asText(record.lab) ?? "";
      const val = asText(record.value) ?? asText(record.result) ?? "";
      const unit = asText(record.unit) ?? "";
      const raw = asText(record.raw) ?? "";
      if (name && val) {
        return unit ? `${name}=${val} ${unit}` : `${name}=${val}`;
      }
      if (name && raw) return `${name}: ${raw}`;
      if (raw) return raw;
      return "";
    })
    .filter(Boolean);
  return formattedRows.join("\n");
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

export async function runCouncilConsult(payload: CouncilConsultRequest): Promise<CouncilRunRawResponse> {
  const response = await api.post<CouncilRunRawResponse>("/council/consult", {
    transcript: payload.transcript,
    symptoms: payload.symptoms,
    labs: payload.labs,
    medications: payload.medications,
    history: payload.history,
    specialists: payload.specialists,
    specialist_count: payload.specialistCount
  });
  return response.data;
}

export async function extractCouncilIntake(payload: CouncilIntakeRequest): Promise<CouncilIntakeResult> {
  const formData = new FormData();
  const transcript = (payload.transcript ?? "").trim();
  if (transcript) {
    formData.append("transcript", transcript);
  }
  if (payload.audioFile) {
    formData.append("audio_file", payload.audioFile);
  }

  const response = await api.post<unknown>("/council/intake", formData, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  const root = asRecord(response.data) ?? {};
  const textFields = asRecord(root.text_fields);

  const symptomsInput =
    asText(textFields?.symptoms_input) ??
    parseStringArray(root.symptoms).join("\n");
  const labsInput =
    asText(textFields?.labs_input) ??
    formatLabsInput(root.labs);
  const medicationsInput =
    asText(textFields?.medications_input) ??
    parseStringArray(root.medications).join("\n");
  const historyInput =
    asText(textFields?.history_input) ??
    parseStringArray(root.history).join("\n");

  return {
    transcript: asText(root.transcript) ?? transcript,
    symptomsInput,
    labsInput,
    medicationsInput,
    historyInput,
    modelUsed: asText(root.model_used) ?? "deepseek-v3.2",
    warnings: parseStringArray(root.warnings),
    fieldConfidence: asRecord(root.field_confidence) as Record<string, number> | undefined,
    missingFields: parseStringArray(root.missing_fields),
    councilPayload: asRecord(root.council_payload) as CouncilIntakeResult["councilPayload"] | undefined
  };
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
  const detailsRecord = asRecord(pickUnknown(candidates, ["details"]));
  const consensusMetadata =
    parseConsensusMetadata(pickUnknown(candidates, ["council_consensus", "consensus_metadata"])) ??
    parseConsensusMetadata(detailsRecord?.consensus);
  const escalationMetadata = parseEscalationMetadata(
    emergencyRecord?.metadata ?? pickUnknown(candidates, ["escalation_metadata"])
  );
  const citationQuality = parseCitationQuality(pickUnknown(candidates, ["citation_quality"]));
  const reasoningTimeline = parseReasoningTimeline(pickUnknown(candidates, ["reasoning_timeline"]));
  const neuralRisk = parseNeuralRisk(pickUnknown(candidates, ["neural_risk"]));

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

  const confidenceScore = parseNumber(
    pickUnknown(candidates, ["confidence", "overall_confidence", "confidence_score"])
  );

  const dataQualityRecord = asRecord(pickUnknown(candidates, ["data_quality", "quality", "input_quality"]));
  const dataQualityScore = parseNumber(
    dataQualityRecord?.score ?? dataQualityRecord?.quality_score ?? pickUnknown(candidates, ["data_quality_score"])
  );

  const uncertaintyNotes = parseTextList(
    pickUnknown(candidates, ["uncertainty_notes", "uncertainties", "uncertain_points"])
  );

  const missingInfoQuestions = parseTextList(
    pickUnknown(candidates, [
      "follow_up_questions",
      "missing_information_questions",
      "needs_more_info_questions",
      "missing_info_questions"
    ])
  );

  const citations = parseCitationList(
    pickUnknown(candidates, ["citations", "evidence_citations", "references", "sources"])
  );

  const analysisSectionsRecord = asRecord(
    pickUnknown(candidates, ["analysis_sections", "sections", "workspace_sections"])
  );
  const analysisSections = {
    analyze: parseAnalysisSection(analysisSectionsRecord?.analyze),
    details: parseAnalysisSection(analysisSectionsRecord?.details),
    research: parseAnalysisSection(analysisSectionsRecord?.research),
    deepdive: parseAnalysisSection(analysisSectionsRecord?.deepdive),
    citations: parseAnalysisSection(analysisSectionsRecord?.citations)
  };

  return {
    specialistReasoningLogs,
    conflicts,
    consensus,
    divergence,
    finalRecommendation,
    isEmergency,
    escalationReason,
    confidenceScore,
    dataQualityScore,
    missingInfoQuestions,
    uncertaintyNotes,
    citations,
    consensusMetadata,
    escalationMetadata,
    citationQuality,
    reasoningTimeline,
    neuralRisk,
    analysisSections
  };
}

function readStorageJson<T>(key: string): T | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeStorageJson<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(key, JSON.stringify(value));
}

export function loadCouncilDraft(): CouncilCaseDraft | null {
  return readStorageJson<CouncilCaseDraft>(COUNCIL_DRAFT_KEY);
}

export function saveCouncilDraft(draft: CouncilCaseDraft): void {
  writeStorageJson(COUNCIL_DRAFT_KEY, draft);
}

export function clearCouncilDraft(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(COUNCIL_DRAFT_KEY);
}

export function loadCouncilSnapshot(): CouncilRunSnapshot | null {
  return readStorageJson<CouncilRunSnapshot>(COUNCIL_RESULT_KEY);
}

export function saveCouncilSnapshot(snapshot: CouncilRunSnapshot): void {
  writeStorageJson(COUNCIL_RESULT_KEY, snapshot);
}

export function clearCouncilSnapshot(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(COUNCIL_RESULT_KEY);
}
