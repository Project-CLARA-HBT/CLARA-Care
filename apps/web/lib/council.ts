import api from "@/lib/http-client";
import { getAccessToken, getCsrfToken } from "@/lib/auth-store";

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
  missingFields?: string[];
  councilPayload?: {
    symptoms: string[];
    labs: Record<string, number>;
    medications: string[];
    history: string[];
  };
};

/** Clinician-facing specialist conclusion; never a model reasoning trace. */
export type CouncilSpecialistSummary = {
  specialist: string;
  findings: string[];
  recommendation?: string;
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
};

export type CouncilRuleShadow = {
  enabled: boolean;
  shadowMode: boolean;
  modelVersion: string;
  riskBand: string;
  recommendedTriage: string;
  topContributors: Array<{
    feature: string;
    impact: number | null;
    direction: string;
  }>;
};

export type CouncilAiDisclosure = {
  modelFamily: string;
  modelVersion: string;
  isFallback: boolean;
};

/** Sanitized deterministic Council → CareGuard safety projection only. */
export type CouncilMedicationSafety = {
  state: "checked" | "unavailable" | "requires_clarification";
  drugbankState: "ready" | "unavailable" | "disabled" | "unknown";
  drugbankVersion: string;
  alertIds: string[];
  triageFloor: "routine_follow_up" | "same_day_review" | "emergency_escalation" | null;
  reviewRequired: boolean;
};

export type CouncilRunRawResponse = {
  [key: string]: unknown;
};

export type CouncilRunResult = {
  specialistReasoningLogs: CouncilSpecialistSummary[];
  conflicts: string[];
  consensus: string;
  divergence: string[];
  finalRecommendation: string;
  isEmergency: boolean;
  escalationReason: string;
  missingInfoQuestions: string[];
  uncertaintyNotes: string[];
  citations: CouncilCitation[];
  consensusMetadata: CouncilConsensusMetadata | null;
  escalationMetadata: CouncilEscalationMetadata | null;
  citationQuality: CouncilCitationQuality | null;
  reasoningTimeline: CouncilReasoningTimelineStep[];
  ruleShadow: CouncilRuleShadow | null;
  aiDisclosure: CouncilAiDisclosure | null;
  medicationSafety: CouncilMedicationSafety | null;
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

let councilDraftMemory: CouncilCaseDraft | null = null;
let councilSnapshotMemory: CouncilRunSnapshot | null = null;
const ACTIVE_COUNCIL_CASE_KEY = "clara_active_council_case_id";

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

function parseSpecialistSummary(value: unknown, fallbackSpecialist?: string): CouncilSpecialistSummary | null {
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

  // Do not accept free-text fields such as `reasoning`, `rationale`, `log`,
  // or legacy `reasoning_log`. Those fields can contain implementation traces
  // or a model's private reasoning. Only render stable, structured findings.
  const findings = parseTextList(record.key_findings ?? record.supported_findings)
    .slice(0, 10);

  const recommendation =
    asText(record.recommendation) ??
    asText(record.suggested_action) ??
    asText(record.plan) ??
    asText(record.next_step);

  if (!findings.length && !recommendation) return null;

  return {
    specialist,
    findings,
    recommendation,
  };
}

function parseSpecialistSummaries(value: unknown): CouncilSpecialistSummary[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseSpecialistSummary(item))
      .filter((item): item is CouncilSpecialistSummary => Boolean(item));
  }

  const record = asRecord(value);
  if (!record) return [];

  return Object.entries(record)
    .map(([key, item]) => parseSpecialistSummary(item, key))
    .filter((item): item is CouncilSpecialistSummary => Boolean(item));
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
      if (!step) return null;
      return {
        sequence,
        step,
      } satisfies CouncilReasoningTimelineStep;
    })
    .filter((item): item is CouncilReasoningTimelineStep => Boolean(item))
    .sort((a, b) => a.sequence - b.sequence);
}

function parseRuleShadow(value: unknown): CouncilRuleShadow | null {
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
    riskBand: asText(record.risk_band) ?? asText(record.riskBand) ?? "",
    recommendedTriage:
      asText(record.recommended_triage) ?? asText(record.recommendedTriage) ?? "",
    topContributors,
  };
}

// ---------------------------------------------------------------------------
// Model & fallback disclosure (Req 6.1, 6.2, 6.3, 6.4)
//
// `parseCouncilDisclosure` reads the additive `ai_disclosure` block
// (`{ model_family, model_version, is_fallback }`) attached to the run/intake
// envelope by the ML tier when `COUNCIL_MODEL_DISCLOSURE_ENABLED` is on (design
// §E). With the flag off the block is absent, so this returns `null` and the
// surfaces render byte-identically to today. `is_fallback` is true IFF a
// degraded/heuristic path produced the output (Property P10). Mirrors the
// `parseRuleShadow` style above.
// ---------------------------------------------------------------------------
function parseCouncilDisclosure(value: unknown): CouncilAiDisclosure | null {
  const record = asRecord(value);
  if (!record) return null;
  const modelFamily = asText(record.model_family ?? record.modelFamily) ?? "";
  const modelVersion = asText(record.model_version ?? record.modelVersion) ?? "";
  if (!modelFamily && !modelVersion) return null;
  return {
    modelFamily,
    modelVersion,
    isFallback: parseBoolean(record.is_fallback ?? record.isFallback),
  };
}

function parseCouncilMedicationSafety(value: unknown): CouncilMedicationSafety | null {
  const record = asRecord(value);
  if (!record) return null;

  const state = asText(record.state);
  if (state !== "checked" && state !== "unavailable" && state !== "requires_clarification") {
    return null;
  }
  const rawDrugbankState = asText(record.drugbank_state ?? record.drugbankState);
  const drugbankState =
    rawDrugbankState === "ready" ||
    rawDrugbankState === "unavailable" ||
    rawDrugbankState === "disabled"
      ? rawDrugbankState
      : "unknown";
  const version = asText(record.drugbank_version ?? record.drugbankVersion) ?? "";
  const drugbankVersion =
    version.includes("/") || version.includes("\\") || /[\r\n]/.test(version)
      ? ""
      : version.slice(0, 160);
  const alertIds = parseStringArray(record.alert_ids ?? record.alertIds)
    .filter((item) => /^council-ddi-alert-\d+$/.test(item))
    .slice(0, 12);
  const triageFloorRaw = asText(record.triage_floor ?? record.triageFloor);
  const triageFloor =
    triageFloorRaw === "routine_follow_up" ||
    triageFloorRaw === "same_day_review" ||
    triageFloorRaw === "emergency_escalation"
      ? triageFloorRaw
      : null;

  return {
    state,
    drugbankState,
    drugbankVersion,
    alertIds,
    triageFloor,
    reviewRequired: parseBoolean(record.review_required ?? record.reviewRequired),
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
    modelUsed: asText(root.model_used) ?? "deepseek-v4-pro",
    warnings: parseStringArray(root.warnings),
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

  const specialistReasoningLogs = parseSpecialistSummaries(
    pickUnknown(candidates, [
      "per_specialist_assessments",
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
  const ruleShadow = parseRuleShadow(pickUnknown(candidates, ["rule_shadow"]));
  const aiDisclosure = parseCouncilDisclosure(pickUnknown(candidates, ["ai_disclosure", "aiDisclosure"]));
  const medicationSafety = parseCouncilMedicationSafety(
    pickUnknown(candidates, ["medication_safety", "medicationSafety"])
  );

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
    missingInfoQuestions,
    uncertaintyNotes,
    citations,
    consensusMetadata,
    escalationMetadata,
    citationQuality,
    reasoningTimeline,
    ruleShadow,
    aiDisclosure,
    medicationSafety,
    analysisSections
  };
}

function cloneSnapshot<T>(value: T): T {
  try {
    return JSON.parse(JSON.stringify(value)) as T;
  } catch {
    return value;
  }
}

export function loadCouncilDraft(): CouncilCaseDraft | null {
  return councilDraftMemory ? cloneSnapshot(councilDraftMemory) : null;
}

export function saveCouncilDraft(draft: CouncilCaseDraft): void {
  councilDraftMemory = cloneSnapshot(draft);
}

export function clearCouncilDraft(): void {
  councilDraftMemory = null;
}

export function loadCouncilSnapshot(): CouncilRunSnapshot | null {
  return councilSnapshotMemory ? cloneSnapshot(councilSnapshotMemory) : null;
}

export function saveCouncilSnapshot(snapshot: CouncilRunSnapshot): void {
  councilSnapshotMemory = cloneSnapshot(snapshot);
}

export function clearCouncilSnapshot(): void {
  councilSnapshotMemory = null;
}

export function setActiveCouncilCaseId(caseId: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ACTIVE_COUNCIL_CASE_KEY, String(caseId));
}

export function getActiveCouncilCaseId(): number | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ACTIVE_COUNCIL_CASE_KEY);
  const parsed = Number(raw);
  if (!Number.isFinite(parsed) || parsed <= 0) return null;
  return Math.trunc(parsed);
}

export function clearActiveCouncilCaseId(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ACTIVE_COUNCIL_CASE_KEY);
}

export type CouncilCaseRecord = {
  id: number;
  title: string;
  status: string;
  intake_mode: string;
  transcript: string;
  intake?: Record<string, unknown> | null;
  request?: Record<string, unknown> | null;
  result?: CouncilRunRawResponse | null;
  raw_result?: CouncilRunRawResponse | null;
  last_run_at?: string | null;
  // Additive oversight column (Req 3.2). Present only when the server has the
  // oversight feature; `paused` drives the "not yet confirmed" render. Optional
  // so flags-off / pre-feature payloads remain shape-compatible.
  oversight_state?: string | null;
  created_at: string;
  updated_at: string;
};

export type CouncilCaseListResponse = {
  items: CouncilCaseRecord[];
  total: number;
};

/** A completed Research snapshot that is eligible for Council shadow review. */
export type CouncilEvidenceSnapshotOption = {
  job_id: string;
  captured_at?: string | null;
  evidence_count: number;
  categories: string[];
};

/** Append-only, non-clinical projection of an attached shadow packet. */
export type CouncilEvidenceAttachment = {
  id: number;
  case_id: number;
  research_job_id: string;
  retrieval_snapshot_id: string;
  evidence_count: number;
  categories: string[];
  created_at: string;
};

export type CouncilCaseCreatePayload = {
  title?: string;
  intake_mode?: string;
  transcript?: string;
  request?: Record<string, unknown>;
};

export type CouncilCaseUpdatePayload = {
  title?: string;
  status?: string;
  intake_mode?: string;
  transcript?: string;
  intake?: Record<string, unknown>;
  request?: Record<string, unknown>;
  result?: Record<string, unknown>;
  raw_result?: Record<string, unknown>;
};

export async function listCouncilCases(limit = 20, offset = 0): Promise<CouncilCaseListResponse> {
  const response = await api.get<CouncilCaseListResponse>("/council/cases", {
    params: { limit, offset },
  });
  return response.data;
}

export async function getLatestCouncilCase(): Promise<CouncilCaseRecord> {
  const response = await api.get<CouncilCaseRecord>("/council/cases/latest");
  return response.data;
}

export async function getCouncilCase(caseId: number): Promise<CouncilCaseRecord> {
  const response = await api.get<CouncilCaseRecord>(`/council/cases/${caseId}`);
  return response.data;
}

export async function listCouncilEvidenceSnapshotOptions(
  caseId: number
): Promise<CouncilEvidenceSnapshotOption[]> {
  const response = await api.get<{ items?: CouncilEvidenceSnapshotOption[] }>(
    `/council/cases/${caseId}/evidence-snapshots`
  );
  return Array.isArray(response.data.items) ? response.data.items : [];
}

export async function listCouncilEvidenceAttachments(
  caseId: number
): Promise<CouncilEvidenceAttachment[]> {
  const response = await api.get<{ items?: CouncilEvidenceAttachment[] }>(
    `/council/cases/${caseId}/evidence-attachments`
  );
  return Array.isArray(response.data.items) ? response.data.items : [];
}

/**
 * The API accepts only an owner-scoped job ID and constructs the opaque packet
 * itself. No research prose, citation text, URL, score, or packet object is
 * ever accepted from the browser.
 */
export async function attachCouncilEvidenceSnapshot(
  caseId: number,
  jobId: string
): Promise<CouncilEvidenceAttachment> {
  const response = await api.post<CouncilEvidenceAttachment>(
    `/council/cases/${caseId}/evidence-snapshots/${encodeURIComponent(jobId)}/attach`
  );
  return response.data;
}

export async function createCouncilCase(payload: CouncilCaseCreatePayload): Promise<CouncilCaseRecord> {
  const response = await api.post<CouncilCaseRecord>("/council/cases", payload);
  return response.data;
}

export async function updateCouncilCase(
  caseId: number,
  payload: CouncilCaseUpdatePayload
): Promise<CouncilCaseRecord> {
  const response = await api.patch<CouncilCaseRecord>(`/council/cases/${caseId}`, payload);
  return response.data;
}

export async function runCouncilCaseIntake(
  caseId: number,
  payload: CouncilIntakeRequest
): Promise<CouncilCaseRecord> {
  const formData = new FormData();
  const transcript = (payload.transcript ?? "").trim();
  if (transcript) {
    formData.append("transcript", transcript);
  }
  if (payload.audioFile) {
    formData.append("audio_file", payload.audioFile);
  }
  const response = await api.post<CouncilCaseRecord>(`/council/cases/${caseId}/intake`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function runCouncilCaseById(
  caseId: number,
  payload: { request?: Record<string, unknown>; specialist_count?: number; specialists?: string[] } = {}
): Promise<CouncilCaseRecord> {
  const response = await api.post<CouncilCaseRecord>(`/council/cases/${caseId}/run`, payload);
  return response.data;
}

// ---------------------------------------------------------------------------
// Run history & versioning (Req 2.4)
//
// `getCouncilRuns` fetches the owner-isolated, newest-first run history for a
// case (`GET /council/cases/{id}/runs`). Owner isolation is enforced
// server-side; the client only renders what it is given. The endpoint is only
// mounted when `COUNCIL_RUN_HISTORY_ENABLED` is on, so callers treat an absent
// endpoint / empty payload as "no history" and degrade gracefully (no-op).
// ---------------------------------------------------------------------------

/** One immutable Council run-history record (a single `run_council` snapshot). */
export type CouncilRunRecord = {
  id: number;
  caseId: number | null;
  modelVersion: string;
  emergencyTriggered: boolean;
  createdAt: string;
  result: CouncilRunRawResponse | null;
  request: Record<string, unknown> | null;
};

function parseCouncilRunRecord(value: unknown): CouncilRunRecord | null {
  const record = asRecord(value);
  if (!record) return null;
  const id = parseNumber(record.id);
  if (id == null) return null;
  const result = asRecord(record.result ?? record.result_json) as CouncilRunRawResponse | null;
  const request = asRecord(record.request ?? record.request_json);
  return {
    id,
    caseId: parseNumber(record.case_id ?? record.caseId),
    modelVersion: asText(record.model_version ?? record.modelVersion) ?? "",
    emergencyTriggered: parseBoolean(record.emergency_triggered ?? record.emergencyTriggered),
    createdAt:
      asText(record.created_at ?? record.createdAt) ?? "",
    result,
    request,
  };
}

/**
 * Fetch the newest-first run history for a case. Server enforces owner
 * isolation; this returns whatever the server permits. The list is sorted
 * newest-first defensively (by `createdAt` desc, then `id` desc) so the render
 * order is stable regardless of server ordering. Throws on transport errors so
 * callers can decide to no-op (e.g. when run history is disabled and the
 * endpoint is not mounted).
 */
export async function getCouncilRuns(
  caseId: number,
  limit = 20,
  offset = 0
): Promise<CouncilRunRecord[]> {
  const response = await api.get<unknown>(`/council/cases/${caseId}/runs`, {
    params: { limit, offset },
  });
  const root = asRecord(response.data);
  const rawItems = Array.isArray(response.data)
    ? response.data
    : Array.isArray(root?.items)
      ? (root?.items as unknown[])
      : Array.isArray(root?.runs)
        ? (root?.runs as unknown[])
        : [];
  return rawItems
    .map((item) => parseCouncilRunRecord(item))
    .filter((item): item is CouncilRunRecord => Boolean(item))
    .sort((a, b) => {
      const aTime = Date.parse(a.createdAt);
      const bTime = Date.parse(b.createdAt);
      if (Number.isFinite(aTime) && Number.isFinite(bTime) && aTime !== bTime) {
        return bTime - aTime;
      }
      return b.id - a.id;
    });
}

// ---------------------------------------------------------------------------
// Streaming / progressive deliberation (Req 1.3)
//
// `streamCouncilRun` opens the additive SSE deliberation stream
// (`POST /council/cases/{id}/run/stream`) and dispatches one `onStage` callback
// per pipeline stage, then exactly one terminal `onResult` (the full
// `run_council` envelope — same shape as the blocking `/run`) or `onError`.
// It mirrors the `streamScribe`/`streamChatMessage` SSE conventions (same
// bearer + CSRF + credentials and the same `\n\n`-delimited frame parsing).
//
// The streaming endpoint only exists when the server flag
// `COUNCIL_STREAMING_ENABLED` is on; callers gate the streaming path on the
// client-readable `NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED` flag (default off) via
// `isCouncilStreamingEnabled()` and fall back to the blocking run when off.
// ---------------------------------------------------------------------------

/** One streamed Council processing state (no clinical text or reasoning trace). */
export type CouncilStreamStage = {
  sequence: number;
  step: string;
};

export type CouncilStreamRunPayload = {
  request?: Record<string, unknown>;
  specialist_count?: number;
  specialists?: string[];
};

export type CouncilStreamHandlers = {
  /** Fired once per ordered pipeline stage as the deliberation progresses. */
  onStage?: (stage: CouncilStreamStage) => void;
  /** Fired once with the terminal result envelope (equals the blocking `/run`). */
  onResult?: (raw: CouncilRunRawResponse) => void;
  /** Fired on a terminal error; ``message`` names the failure class (no PII). */
  onError?: (message: string) => void;
  signal?: AbortSignal;
};

/**
 * Client-readable gate for the streaming deliberation path. Defaults to OFF so
 * the blocking `/run` path is used unless the environment opts in. The server
 * remains the source of truth (the stream endpoint is only mounted when
 * `COUNCIL_STREAMING_ENABLED` is on); this only decides which path the web
 * client attempts first.
 */
export function isCouncilStreamingEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED ?? "").trim().toLowerCase();
  return raw === "true" || raw === "1" || raw === "yes" || raw === "on";
}

/**
 * Client-readable gate for the model/fallback disclosure surface (Req 6.4,
 * 6.5). Defaults to OFF so nothing about disclosure renders unless the
 * environment opts in — byte-identical to today. The server/ML tier remains
 * the source of truth (the `ai_disclosure` block is only attached when
 * `COUNCIL_MODEL_DISCLOSURE_ENABLED` is on); this only decides whether the web
 * client renders the disclosure when the block is present. Mirrors
 * `isCouncilStreamingEnabled()`.
 */
export function isCouncilModelDisclosureEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_COUNCIL_MODEL_DISCLOSURE_ENABLED ?? "").trim().toLowerCase();
  return raw === "true" || raw === "1" || raw === "yes" || raw === "on";
}

function councilStreamUrl(caseId: number): string {
  const base = (process.env.NEXT_PUBLIC_API_URL ?? "/api/v1").replace(/\/$/, "");
  return `${base}/council/cases/${caseId}/run/stream`;
}

function parseCouncilSseFrame(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

function parseCouncilStreamStage(value: unknown): CouncilStreamStage {
  const record = asRecord(value) ?? {};
  return {
    sequence: parseNumber(record.sequence) ?? 0,
    step: asText(record.step) ?? asText(record.stage) ?? "",
  };
}

/**
 * Open the SSE Council deliberation stream for a case and dispatch
 * stage/result/error callbacks. Resolves once a terminal `result`/`error`
 * event is seen; throws on a transport failure or if the stream ends without a
 * terminal event (so callers can fall back to the blocking run path).
 */
export async function streamCouncilRun(
  caseId: number,
  payload: CouncilStreamRunPayload,
  handlers: CouncilStreamHandlers = {}
): Promise<void> {
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
    "Content-Type": "application/json",
  };
  const accessToken = getAccessToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const csrfToken = getCsrfToken();
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const response = await fetch(councilStreamUrl(caseId), {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(payload ?? {}),
    signal: handlers.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`council stream failed (status=${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawTerminal = false;

  const dispatch = (event: string, data: string) => {
    let parsed: unknown = data;
    try {
      parsed = JSON.parse(data);
    } catch {
      parsed = data;
    }
    if (event === "stage") {
      handlers.onStage?.(parseCouncilStreamStage(parsed));
    } else if (event === "result") {
      sawTerminal = true;
      handlers.onResult?.((parsed ?? {}) as CouncilRunRawResponse);
    } else if (event === "error") {
      sawTerminal = true;
      const message = (parsed as { message?: string; error?: string })?.message
        ?? (parsed as { error?: string })?.error
        ?? "council stream error";
      handlers.onError?.(message);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const frameBlock = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const frame = parseCouncilSseFrame(frameBlock);
        if (frame) dispatch(frame.event, frame.data);
        idx = buffer.indexOf("\n\n");
      }
    }
    const tail = parseCouncilSseFrame(buffer);
    if (tail) dispatch(tail.event, tail.data);
  } finally {
    reader.releaseLock();
  }

  if (!sawTerminal) throw new Error("council stream ended without a terminal event");
}

export function buildSnapshotFromCouncilCase(caseItem: CouncilCaseRecord): CouncilRunSnapshot | null {
  const raw = (caseItem.raw_result ?? caseItem.result) as CouncilRunRawResponse | null;
  const requestRaw = (caseItem.request ?? {}) as Record<string, unknown>;
  if (!raw) return null;

  const historyValue = requestRaw.history;
  const history =
    typeof historyValue === "string"
      ? historyValue
      : Array.isArray(historyValue)
        ? historyValue.map((item) => String(item).trim()).filter(Boolean).join("\n")
        : asRecord(historyValue)
          ? objectToText(asRecord(historyValue) as Record<string, unknown>)
          : "";
  const specialistCount =
    typeof requestRaw.specialist_count === "number" && Number.isFinite(requestRaw.specialist_count)
      ? Math.min(5, Math.max(2, Math.trunc(requestRaw.specialist_count)))
      : 3;
  const request: CouncilRunRequest = {
    symptoms: Array.isArray(requestRaw.symptoms) ? parseStringArray(requestRaw.symptoms) : [],
    labs:
      typeof requestRaw.labs === "object" && requestRaw.labs && !Array.isArray(requestRaw.labs)
        ? (requestRaw.labs as Record<string, number | string>)
        : {},
    medications: Array.isArray(requestRaw.medications) ? parseStringArray(requestRaw.medications) : [],
    history,
    specialistCount,
    specialists: Array.isArray(requestRaw.specialists) ? parseStringArray(requestRaw.specialists) : [],
  };

  return {
    request: {
      symptoms: request.symptoms,
      labs: request.labs,
      medications: request.medications,
      history: request.history,
      specialistCount: request.specialistCount,
      specialists: request.specialists,
    },
    result: normalizeCouncilRunResult(raw),
    raw,
    createdAt: caseItem.last_run_at ?? caseItem.updated_at ?? caseItem.created_at,
  };
}

// ---------------------------------------------------------------------------
// Human oversight actions (Req 3.2, 3.6)
//
// `submitCouncilOversight` records a clinician/admin governance action against a
// case (`POST /council/cases/{id}/oversight`). It reuses the shared `api` axios
// instance, so the existing bearer + CSRF + credentials interceptors apply
// exactly as they do for `runCouncilCaseById` (no bespoke header handling).
//
// The endpoint is only mounted when the server flag `COUNCIL_OVERSIGHT_ENABLED`
// is on. Callers gate the real call behind the client-readable
// `NEXT_PUBLIC_COUNCIL_OVERSIGHT_ENABLED` flag (default OFF) via
// `isCouncilOversightEnabled()`; when the flag is off they keep the existing
// browser-only local-notice behavior and write nothing (Req 3.6). When on, a
// `pause` flips the case `oversight_state` so the final recommendation renders
// as "chưa được xác nhận" / not yet confirmed (Req 3.2). The call is defensive:
// if the endpoint is absent/unavailable (e.g. the server flag is still off) the
// caller falls back to the local notice.
// ---------------------------------------------------------------------------

/** The three governance action kinds (mirrors the server `kind` enum). */
export type CouncilOversightActionKind = "handoff" | "override" | "pause";

/** Client-side oversight request; `action` maps to the server `kind` field. */
export type CouncilOversightRequest = {
  action: CouncilOversightActionKind;
  reason?: string;
  /** For `handoff`: the invited attending specialty. */
  handoffSpecialty?: string;
  /** For `override`: the human decision recorded alongside the AI output. */
  overrideDecision?: string;
  /** Optional target run id; the server defaults to the case's latest run. */
  runId?: number;
};

/** Normalized oversight response (server is the source of truth). */
export type CouncilOversightResult = {
  id: number | null;
  caseId: number | null;
  kind: CouncilOversightActionKind | string;
  reason: string;
  /** `none` / `paused` — `paused` drives the "not yet confirmed" render. */
  oversightState: string;
  handoffSpecialty: string;
  overrideDecision: string;
  /** Retained original AI recommendation for an `override` (never discarded). */
  overrideOriginal: string;
  createdAt: string;
};

/**
 * Client-readable gate for the real oversight path. Defaults to OFF so the
 * existing browser-only local-notice behavior is preserved unless the
 * environment opts in. The server remains the source of truth (the oversight
 * endpoint is only mounted + authorized when `COUNCIL_OVERSIGHT_ENABLED` is on);
 * this only decides whether the web client attempts the real call.
 */
export function isCouncilOversightEnabled(): boolean {
  const raw = (process.env.NEXT_PUBLIC_COUNCIL_OVERSIGHT_ENABLED ?? "").trim().toLowerCase();
  return raw === "true" || raw === "1" || raw === "yes" || raw === "on";
}

function parseCouncilOversightResult(
  value: unknown,
  fallbackKind: CouncilOversightActionKind
): CouncilOversightResult {
  const record = asRecord(value) ?? {};
  return {
    id: parseNumber(record.id),
    caseId: parseNumber(record.case_id ?? record.caseId),
    kind: asText(record.kind ?? record.action) ?? fallbackKind,
    reason: asText(record.reason) ?? "",
    oversightState:
      asText(record.oversight_state ?? record.oversightState) ??
      (fallbackKind === "pause" ? "paused" : "none"),
    handoffSpecialty: asText(record.handoff_specialty ?? record.handoffSpecialty) ?? "",
    overrideDecision: asText(record.override_decision ?? record.overrideDecision) ?? "",
    overrideOriginal: asText(record.override_original ?? record.overrideOriginal) ?? "",
    createdAt: asText(record.created_at ?? record.createdAt) ?? "",
  };
}

/**
 * Persist a Council oversight action (`handoff` / `override` / `pause`) for a
 * case. Sends both `kind` and `action` for forward/back compatibility with the
 * server contract. Throws on transport errors (including the endpoint being
 * absent) so callers can fall back to the local-notice behavior.
 */
export async function submitCouncilOversight(
  caseId: number,
  payload: CouncilOversightRequest
): Promise<CouncilOversightResult> {
  const body: Record<string, unknown> = {
    kind: payload.action,
    action: payload.action,
  };
  const reason = (payload.reason ?? "").trim();
  if (reason) body.reason = reason;
  const handoffSpecialty = (payload.handoffSpecialty ?? "").trim();
  if (handoffSpecialty) body.handoff_specialty = handoffSpecialty;
  const overrideDecision = (payload.overrideDecision ?? "").trim();
  if (overrideDecision) body.override_decision = overrideDecision;
  if (typeof payload.runId === "number" && Number.isFinite(payload.runId)) {
    body.run_id = Math.trunc(payload.runId);
  }

  const response = await api.post<unknown>(`/council/cases/${caseId}/oversight`, body);
  return parseCouncilOversightResult(response.data, payload.action);
}
