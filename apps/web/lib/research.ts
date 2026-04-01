import api from "@/lib/http-client";
import { getAccessToken } from "@/lib/auth-store";

export type ResearchTier = "tier1" | "tier2";
export type ResearchExecutionMode = "fast" | "deep" | "deep_beta";

export const RESEARCH_UPLOAD_TIMEOUT_MS = 60000;
export const RESEARCH_TIER2_TIMEOUT_MS = 120000;
export const RESEARCH_TIER2_JOB_POLL_MS = 1800;
export const RESEARCH_TIER2_STREAM_MAX_WAIT_MS = 30 * 60 * 1000;

export type Tier2Citation = {
  title: string;
  source?: string;
  url?: string;
  snippet?: string;
  year?: string;
};

export type Tier2Step = {
  title: string;
  detail?: string;
};

export type ResearchFlowStageStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "warning"
  | "failed"
  | "skipped";

export type ResearchFlowStage = {
  id: string;
  label: string;
  detail?: string;
  status: ResearchFlowStageStatus;
  source: "metadata" | "flow_events" | "local";
};

export type ResearchFlowEvent = {
  id: string;
  stageId: string;
  label: string;
  detail?: string;
  status: ResearchFlowStageStatus;
  timestamp?: string;
  component?: string;
  payload?: Record<string, unknown>;
};

export type ResearchTier2RoutingHint = {
  role?: string;
  intent?: string;
  confidence?: number;
  emergency?: boolean;
};

export type ResearchTier2DebugMeta = {
  pipeline?: string;
  responseStyle?: string;
  sourceMode?: string;
  researchMode?: string;
  deepPassCount?: number;
  stageCount: number;
  flowEventCount: number;
  telemetryKeywordCount: number;
  telemetryDocCount: number;
  telemetrySourceAttemptCount: number;
  telemetryErrorCount: number;
  crawlDomainCount: number;
  routing?: ResearchTier2RoutingHint;
};

export type ResearchTier2TelemetryScore = {
  label: string;
  value: number | string;
};

export type ResearchTier2TelemetryDocument = {
  id?: string;
  title: string;
  source?: string;
  score?: number;
  reasoning?: string;
  snippet?: string;
  url?: string;
  error?: string;
};

export type ResearchTier2SourceReasoning = {
  source: string;
  reasoning?: string;
  score?: number;
  error?: string;
};

export type ResearchTier2VerificationMatrixEntry = {
  claim: string;
  verdict?: string;
  confidence?: number;
  note?: string;
  source?: string;
  evidence: string[];
};

export type ResearchTier2ContradictionSummary = {
  hasContradiction?: boolean;
  count?: number;
  severity?: string;
  status?: string;
  summary?: string;
};

export type ResearchTier2TraceMetadataValue = string | number | boolean;
export type ResearchTier2TraceMetadata = Record<string, ResearchTier2TraceMetadataValue>;

export type ResearchTier2SearchPlan = {
  query?: string;
  researchMode?: string;
  topK?: number;
  totalCandidates?: number;
  durationMs?: number;
  keywords: string[];
  subqueries: string[];
  connectors: string[];
};

export type ResearchTier2SourceAttempt = {
  source: string;
  status?: string;
  documents?: number;
  error?: string;
  durationMs?: number;
  query?: string;
  subquery?: string;
  passIndex?: number;
};

export type ResearchTier2IndexSummary = {
  retrievedCount?: number;
  sourceCounts?: Record<string, number>;
  beforeDedupe?: number;
  afterDedupe?: number;
  selectedCount?: number;
  durationMs?: number;
};

export type ResearchTier2CrawlSummary = {
  enabled?: boolean;
  attempted?: number;
  success?: number;
  domains: string[];
  durationMs?: number;
};

export type ResearchTier2Telemetry = {
  keywords: string[];
  searchPlan: ResearchTier2SearchPlan;
  sourceAttempts: ResearchTier2SourceAttempt[];
  indexSummary: ResearchTier2IndexSummary;
  crawlSummary: ResearchTier2CrawlSummary;
  docs: ResearchTier2TelemetryDocument[];
  scores: ResearchTier2TelemetryScore[];
  sourceReasoning: ResearchTier2SourceReasoning[];
  verificationMatrix: ResearchTier2VerificationMatrixEntry[];
  contradictionSummary?: ResearchTier2ContradictionSummary;
  traceMetadata: ResearchTier2TraceMetadata;
  errors: string[];
  fallbackInfo: string[];
};

export type ResearchTier2VisualAsset = {
  id?: string;
  title: string;
  url?: string;
  caption?: string;
  source?: string;
  provider?: string;
  mimeType?: string;
  width?: number;
  height?: number;
};

export type ResearchTier2ChartSpec = {
  id?: string;
  title: string;
  format?: string;
  spec: string;
  description?: string;
};

export type ResearchTier2ReasoningDigestItem = {
  title: string;
  detail?: string;
  confidence?: number;
  status?: string;
};

export type ResearchTier2ReasoningDigest = {
  summary?: string;
  items: ResearchTier2ReasoningDigestItem[];
};

export type ResearchTier2RawResponse = {
  answer?: string;
  answer_markdown?: string;
  answer_md?: string;
  summary?: string;
  message?: string;
  answer_format?: string;
  render_hints?: unknown;
  citations?: unknown;
  sources?: unknown;
  steps?: unknown;
  workflow_steps?: unknown;
  plan_steps?: unknown;
  metadata?: unknown;
  flow_events?: unknown;
  events?: unknown;
  context_debug?: unknown;
  telemetry?: unknown;
  visual_assets?: unknown;
  visualAssets?: unknown;
  images?: unknown;
  chart_specs?: unknown;
  chartSpecs?: unknown;
  reasoning_digest?: unknown;
  reasoningDigest?: unknown;
  debug?: unknown;
  source_errors?: unknown;
  fallback_reason?: unknown;
  [key: string]: unknown;
};

export type ResearchTier2Result = {
  answer: string;
  citations: Tier2Citation[];
  steps: Tier2Step[];
  flowStages: ResearchFlowStage[];
  flowEvents: ResearchFlowEvent[];
  telemetry: ResearchTier2Telemetry;
  visualAssets: ResearchTier2VisualAsset[];
  chartSpecs: ResearchTier2ChartSpec[];
  reasoningDigest: ResearchTier2ReasoningDigest;
  debug: ResearchTier2DebugMeta;
  verificationStatus?: {
    verdict?: string;
    confidence?: number;
    severity?: string;
    note?: string;
    evidenceCount?: number;
  };
  policyAction?: "allow" | "warn";
  fallbackUsed?: boolean;
  researchMode?: string;
  deepPassCount?: number;
};

export type ResearchTier2JobStatus = "queued" | "running" | "completed" | "failed";

export type ResearchTier2JobProgress = {
  flowStages: ResearchFlowStage[];
  flowEvents: ResearchFlowEvent[];
  activeStage?: string;
  statusNote?: string;
  reasoningNotes: string[];
};

export type ResearchTier2JobResponse = {
  job_id: string;
  status: ResearchTier2JobStatus;
  query: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
  progress?: unknown;
  result?: ResearchTier2RawResponse | null;
  error?: string | null;
};

export type ResearchTier2JobStreamEventType = "progress" | "done" | "error";

export type ResearchTier2JobStreamEvent = {
  event: ResearchTier2JobStreamEventType;
  payload: ResearchTier2JobResponse | { message?: string };
};

export type UploadedResearchFile = {
  id: string;
  name: string;
  size?: number;
};

export type ResearchUploadRawResponse = {
  id?: unknown;
  file_id?: unknown;
  uploaded_file_id?: unknown;
  uploaded_file_ids?: unknown;
  file_ids?: unknown;
  file?: unknown;
  files?: unknown;
  uploaded_files?: unknown;
  [key: string]: unknown;
};

export type ResearchUploadResult = {
  uploadedFileIds: string[];
  files: UploadedResearchFile[];
};

export type KnowledgeSource = {
  id: number;
  name: string;
  description: string;
  is_active: boolean;
  documents_count: number;
};

export type KnowledgeSourceDocument = {
  id: number;
  source_id: number;
  filename: string;
  content_type: string;
  size: number;
  preview: string;
  token_count: number;
  is_active: boolean;
};

export type SourceHubSourceKey =
  | "pubmed"
  | "rxnorm"
  | "openfda"
  | "dailymed"
  | "clinicaltrials"
  | "europepmc"
  | "semantic_scholar"
  | "vn_moh"
  | "vn_kcb"
  | "vn_canhgiacduoc"
  | "vn_vbpl_byt"
  | "vn_dav"
  | "davidrug";

export type SourceHubCatalogEntry = {
  key: SourceHubSourceKey;
  label: string;
  description: string;
  docs_url?: string;
  default_query?: string;
  supports_live_sync: boolean;
};

export type SourceHubRecord = {
  id: string;
  source: SourceHubSourceKey;
  title: string;
  url?: string;
  snippet?: string;
  external_id?: string;
  query?: string;
  published_at?: string;
  synced_at?: string;
  metadata: Record<string, unknown>;
};

export type SourceHubSyncResult = {
  source: SourceHubSourceKey;
  query: string;
  fetched: number;
  stored: number;
  records: SourceHubRecord[];
  warnings: string[];
};

export type PersistedResearchConversation = {
  id: string;
  queryId?: string;
  query: string;
  result: Record<string, unknown>;
  tier: ResearchTier;
  createdAt: number;
};

export type PersistedResearchMessage = {
  queryId?: string;
  query: string;
  result: Record<string, unknown>;
  tier: ResearchTier;
  createdAt: number;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const next = value.trim();
  return next ? next : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (value === 1) return true;
    if (value === 0) return false;
    return undefined;
  }
  const text = asText(value)?.toLowerCase();
  if (!text) return undefined;
  if (["true", "1", "yes", "y", "on"].includes(text)) return true;
  if (["false", "0", "no", "n", "off"].includes(text)) return false;
  return undefined;
}

function asId(value: unknown): string | undefined {
  const text = asText(value);
  if (text) return text;
  const numeric = asNumber(value);
  return numeric !== undefined ? String(numeric) : undefined;
}

function asTimestampMs(value: unknown): number | undefined {
  const numeric = asNumber(value);
  if (numeric !== undefined) return numeric > 1e12 ? numeric : numeric * 1000;
  const text = asText(value);
  if (!text) return undefined;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function uniqueIds(ids: string[]): string[] {
  return Array.from(new Set(ids));
}

function uniqueText(values: string[]): string[] {
  return Array.from(
    new Set(
      values
        .map((value) => value.trim())
        .filter(Boolean)
    )
  );
}

function normalizeResearchExecutionMode(mode?: ResearchExecutionMode): ResearchExecutionMode {
  if (mode === "deep" || mode === "deep_beta" || mode === "fast") return mode;
  return "fast";
}

function resolveApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api/v1`;
  }
  return "http://localhost:8100/api/v1";
}

function parseSseBlocks(chunkBuffer: string): { blocks: string[]; tail: string } {
  const normalized = chunkBuffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  if (parts.length <= 1) {
    return { blocks: [], tail: normalized };
  }
  return {
    blocks: parts.slice(0, -1).filter((item) => item.trim().length > 0),
    tail: parts[parts.length - 1] ?? "",
  };
}

function parseSseEventBlock(
  block: string
): { event: string; data: string } | null {
  const lines = block.split("\n");
  let eventName = "message";
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim() || "message";
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) return null;
  return { event: eventName, data: dataLines.join("\n") };
}

function pickFromRecords(
  records: Array<Record<string, unknown> | null>,
  keys: string[]
): unknown {
  for (const record of records) {
    if (!record) continue;
    for (const key of keys) {
      const candidate = record[key];
      if (candidate !== undefined && candidate !== null) {
        return candidate;
      }
    }
  }
  return undefined;
}

function parseIdList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return uniqueIds(
      value
        .map((item) => {
          if (typeof item === "string" || typeof item === "number") {
            return asId(item);
          }

          const record = asRecord(item);
          if (!record) return undefined;
          return asId(record.id) ?? asId(record.file_id) ?? asId(record.uploaded_file_id);
        })
        .filter((item): item is string => Boolean(item))
    );
  }

  const single = asId(value);
  return single ? [single] : [];
}

function parseCitation(value: unknown): Tier2Citation | null {
  if (typeof value === "string") {
    const title = asText(value);
    return title ? { title } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const title =
    asText(item.title) ??
    asText(item.name) ??
    asText(item.source) ??
    asText(item.url) ??
    asText(item.id);

  if (!title) return null;

  return {
    title,
    source: asText(item.source) ?? asText(item.publisher) ?? asText(item.source_id),
    url: asText(item.url),
    snippet: asText(item.snippet) ?? asText(item.summary) ?? asText(item.relevance),
    year: asText(item.year)
  };
}

function parseStep(value: unknown): Tier2Step | null {
  if (typeof value === "string") {
    const title = asText(value);
    return title ? { title } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const title =
    asText(item.title) ??
    asText(item.name) ??
    asText(item.label) ??
    asText(item.action) ??
    asText(item.step) ??
    asText(item.stage) ??
    asText(item.objective);

  if (!title) return null;

  return {
    title,
    detail:
      asText(item.detail) ??
      asText(item.description) ??
      asText(item.result) ??
      asText(item.notes) ??
      asText(item.objective) ??
      asText(item.output)
  };
}

function normalizeFlowStatus(value: unknown): ResearchFlowStageStatus {
  const text = (asText(value) ?? "").toLowerCase();

  if (!text) return "pending";
  if (["in_progress", "running", "active", "processing", "started", "streaming"].some((token) => text.includes(token))) {
    return "in_progress";
  }
  if (["completed", "complete", "done", "success", "verified", "pass", "allow"].some((token) => text.includes(token))) {
    return "completed";
  }
  if (["warning", "warn", "degraded"].some((token) => text.includes(token))) {
    return "warning";
  }
  if (["failed", "error", "blocked", "deny", "reject", "timeout"].some((token) => text.includes(token))) {
    return "failed";
  }
  if (["skip", "skipped", "cancelled", "canceled"].some((token) => text.includes(token))) {
    return "skipped";
  }

  return "pending";
}

function toFlowKey(value: string): string {
  const normalized = value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
  return normalized.replace(/^_+|_+$/g, "") || "stage";
}

function toFlowLabel(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

const FLOW_STAGE_ALIAS_MAP: Record<string, { stageId: string; label: string }> = {
  input_gateway: { stageId: "input_gateway", label: "Input Gateway" },
  dispatch_ml: { stageId: "input_gateway", label: "Input Gateway" },
  session_guard: { stageId: "session_guard", label: "Session Guard" },
  safety_ingress: { stageId: "safety_ingress", label: "Safety Ingress" },
  legal_guard: { stageId: "legal_guard", label: "Legal Hard Guard" },
  legal_hard_guard: { stageId: "legal_guard", label: "Legal Hard Guard" },
  role_router: { stageId: "role_router", label: "Role Router" },
  intent_router: { stageId: "intent_router", label: "Intent Router" },
  query_canonicalizer: { stageId: "query_canonicalizer", label: "Query Canonicalizer" },
  query_canonicalization: { stageId: "query_canonicalizer", label: "Query Canonicalizer" },
  query_rewrite: { stageId: "query_canonicalizer", label: "Query Canonicalizer" },
  query_decomposition: { stageId: "query_decomposition", label: "Query Decomposition" },
  query_plan: { stageId: "planner", label: "Research Planner" },
  planner: { stageId: "planner", label: "Research Planner" },
  planner_v1: { stageId: "planner", label: "Research Planner" },
  retrieval_v2: { stageId: "retrieval_orchestrator", label: "Retrieval Orchestrator" },
  collect_evidence: { stageId: "retrieval_orchestrator", label: "Retrieval Orchestrator" },
  source_attempts: { stageId: "retrieval_orchestrator", label: "Retrieval Orchestrator" },
  retrieval_orchestrator: { stageId: "retrieval_orchestrator", label: "Retrieval Orchestrator" },
  deep_research: { stageId: "deep_research", label: "Deep Research Loop" },
  deep_retrieval_pass: { stageId: "deep_research", label: "Deep Research Loop" },
  deep_beta: { stageId: "deep_beta_router", label: "Deep Beta Router" },
  deep_beta_router: { stageId: "deep_beta_router", label: "Deep Beta Router" },
  deep_beta_gate: { stageId: "deep_beta_router", label: "Deep Beta Router" },
  deep_beta_planner: { stageId: "deep_beta_router", label: "Deep Beta Router" },
  deep_beta_loop: { stageId: "deep_beta_hypothesis", label: "Deep Beta Hypothesis Graph" },
  beta_hypothesis_graph: { stageId: "deep_beta_hypothesis", label: "Deep Beta Hypothesis Graph" },
  hypothesis_graph: { stageId: "deep_beta_hypothesis", label: "Deep Beta Hypothesis Graph" },
  deep_beta_hypothesis: { stageId: "deep_beta_hypothesis", label: "Deep Beta Hypothesis Graph" },
  deep_beta_debate: { stageId: "deep_beta_critic", label: "Deep Beta Critic Loop" },
  cross_source_debate: { stageId: "deep_beta_critic", label: "Deep Beta Critic Loop" },
  debate_refiner: { stageId: "deep_beta_critic", label: "Deep Beta Critic Loop" },
  uncertainty_probe: { stageId: "deep_beta_critic", label: "Deep Beta Critic Loop" },
  deep_beta_critic: { stageId: "deep_beta_critic", label: "Deep Beta Critic Loop" },
  deep_beta_consensus: { stageId: "deep_beta_consensus", label: "Deep Beta Consensus" },
  consensus_builder: { stageId: "deep_beta_consensus", label: "Deep Beta Consensus" },
  evidence_consensus: { stageId: "deep_beta_consensus", label: "Deep Beta Consensus" },
  retrieval_internal: { stageId: "retrieval_internal", label: "Internal Corpus" },
  internal_retrieval: { stageId: "retrieval_internal", label: "Internal Corpus" },
  retrieval_scientific: { stageId: "retrieval_scientific", label: "Scientific Retrieval" },
  external_scientific_retrieval: { stageId: "retrieval_scientific", label: "Scientific Retrieval" },
  retrieval_web: { stageId: "retrieval_web", label: "Web Retrieval" },
  retrieval_file: { stageId: "retrieval_file", label: "File Retrieval" },
  evidence_search: { stageId: "retrieval_orchestrator", label: "Retrieval Orchestrator" },
  evidence_index: { stageId: "evidence_index", label: "Evidence Index + Rerank" },
  contradiction_miner: { stageId: "contradiction_miner", label: "Contradiction Miner" },
  synthesis: { stageId: "synthesis", label: "Answer Synthesis" },
  answer_synthesis: { stageId: "synthesis", label: "Answer Synthesis" },
  rag_generation: { stageId: "synthesis", label: "Answer Synthesis" },
  verification: { stageId: "verification", label: "FIDES Verification" },
  verifier_v1: { stageId: "verification", label: "FIDES Verification" },
  verification_matrix: { stageId: "verification_matrix", label: "Claim Matrix" },
  citation_selection: { stageId: "citation_selection", label: "Citation Selection" },
  policy_gate: { stageId: "policy_gate", label: "Policy Gate" },
  policy_action: { stageId: "policy_gate", label: "Policy Gate" },
  deepseek_fallback: { stageId: "deepseek_fallback", label: "DeepSeek Fallback" },
  fallback_response: { stageId: "deepseek_fallback", label: "DeepSeek Fallback" },
  responder: { stageId: "responder", label: "Responder" },
  final_response: { stageId: "responder", label: "Responder" },
  evaluation_feedback: { stageId: "evaluation_feedback", label: "Eval + Feedback Loop" },
};

function resolveFlowStageIdentity(rawStage?: string, rawLabel?: string): { stageId: string; label?: string } {
  const candidates = [rawStage, rawLabel]
    .map((item) => (typeof item === "string" ? toFlowKey(item) : ""))
    .filter(Boolean);

  for (const candidate of candidates) {
    const alias = FLOW_STAGE_ALIAS_MAP[candidate];
    if (alias) {
      return alias;
    }
  }

  if (rawStage) {
    return { stageId: toFlowKey(rawStage) };
  }
  if (rawLabel) {
    return { stageId: toFlowKey(rawLabel) };
  }

  return { stageId: "stage" };
}

function parseFlowStage(value: unknown, index: number): ResearchFlowStage | null {
  const item = asRecord(value);
  if (!item) return null;

  const rawStage =
    asText(item.stage) ??
    asText(item.name) ??
    asText(item.step) ??
    asText(item.id) ??
    asText(item.key) ??
    asText(item.title);

  const rawLabel = asText(item.label) ?? asText(item.title) ?? rawStage;
  if (!rawStage && !rawLabel) return null;

  const { stageId, label: stageLabel } = resolveFlowStageIdentity(
    rawStage ?? `stage_${index + 1}`,
    rawLabel
  );
  const label = stageLabel ?? (rawLabel ? toFlowLabel(rawLabel) : toFlowLabel(stageId));
  const detail =
    asText(item.detail) ??
    asText(item.description) ??
    asText(item.note) ??
    asText(item.message) ??
    asText(item.objective) ??
    asText(item.output);

  return {
    id: stageId,
    label,
    detail,
    status: normalizeFlowStatus(item.status ?? item.state ?? item.result),
    source: "metadata"
  };
}

function parseFlowEvent(value: unknown, index: number): ResearchFlowEvent | null {
  const item = asRecord(value);
  if (!item) return null;

  const rawStage =
    asText(item.stage) ??
    asText(item.stage_id) ??
    asText(item.step) ??
    asText(item.name) ??
    asText(item.event) ??
    asText(item.id);
  if (!rawStage) return null;

  const rawLabel = asText(item.label) ?? asText(item.title) ?? rawStage;
  const { stageId, label: stageLabel } = resolveFlowStageIdentity(rawStage, rawLabel);
  const label = stageLabel ?? toFlowLabel(rawLabel);
  const detail = asText(item.detail) ?? asText(item.message) ?? asText(item.note) ?? asText(item.description);
  const timestamp =
    asText(item.timestamp) ??
    asText(item.ts) ??
    asText(item.time) ??
    asText(item.created_at) ??
    asText(item.at);

  return {
    id: `${stageId}-${index + 1}`,
    stageId,
    label,
    detail,
    status: normalizeFlowStatus(item.status ?? item.state ?? item.event_type ?? item.type),
    timestamp,
    component: asText(item.component),
    payload: asRecord(item.payload) ?? undefined
  };
}

function parseFlowStages(value: unknown): ResearchFlowStage[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => parseFlowStage(item, index))
    .filter((item): item is ResearchFlowStage => Boolean(item));
}

function parseFlowEvents(value: unknown): ResearchFlowEvent[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item, index) => parseFlowEvent(item, index))
    .filter((item): item is ResearchFlowEvent => Boolean(item));
}

function deriveStagesFromFlowEvents(events: ResearchFlowEvent[]): ResearchFlowStage[] {
  if (!events.length) return [];

  const stageMap = new Map<string, ResearchFlowStage>();
  const stageOrder: string[] = [];

  events.forEach((event) => {
    const existing = stageMap.get(event.stageId);
    if (!existing) {
      stageOrder.push(event.stageId);
      stageMap.set(event.stageId, {
        id: event.stageId,
        label: event.label,
        detail: event.detail,
        status: event.status,
        source: "flow_events"
      });
      return;
    }

    stageMap.set(event.stageId, {
      ...existing,
      label: event.label || existing.label,
      detail: event.detail ?? existing.detail,
      status: event.status
    });
  });

  return stageOrder
    .map((stageId) => stageMap.get(stageId))
    .filter((item): item is ResearchFlowStage => Boolean(item));
}

function parseRoutingHint(value: unknown): ResearchTier2RoutingHint | undefined {
  const record = asRecord(value);
  if (!record) return undefined;

  const hint: ResearchTier2RoutingHint = {
    role: asText(record.role),
    intent: asText(record.intent),
    confidence: asNumber(record.confidence),
    emergency: typeof record.emergency === "boolean" ? record.emergency : undefined
  };

  if (!hint.role && !hint.intent && hint.confidence === undefined && hint.emergency === undefined) {
    return undefined;
  }

  return hint;
}

function parseUploadedFile(value: unknown): UploadedResearchFile | null {
  if (typeof value === "string" || typeof value === "number") {
    const id = asId(value);
    return id ? { id, name: `File #${id}` } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const id = asId(item.id) ?? asId(item.file_id) ?? asId(item.uploaded_file_id);
  if (!id) return null;

  const name = asText(item.file_name) ?? asText(item.filename) ?? asText(item.name) ?? `File #${id}`;
  const size = asNumber(item.file_size) ?? asNumber(item.size);

  return { id, name, size };
}

function parseList<T>(value: unknown, parser: (item: unknown) => T | null): T[] {
  if (!Array.isArray(value)) {
    const single = parser(value);
    return single ? [single] : [];
  }

  return value.map((item) => parser(item)).filter((item): item is T => Boolean(item));
}

function parseKeywordList(value: unknown): string[] {
  if (typeof value === "string") {
    return uniqueText(value.split(/[,\n;|]/g).map((item) => item.trim()));
  }

  if (Array.isArray(value)) {
    return uniqueText(
      value
        .map((item) => {
          if (typeof item === "string" || typeof item === "number") {
            return String(item);
          }
          const record = asRecord(item);
          if (!record) return "";
          return asText(record.keyword) ?? asText(record.term) ?? asText(record.name) ?? asText(record.value) ?? "";
        })
        .filter(Boolean)
    );
  }

  const record = asRecord(value);
  if (!record) return [];

  return uniqueText(
    Object.entries(record).flatMap(([key, raw]) => {
      if (typeof raw === "boolean") return raw ? [key] : [];
      if (typeof raw === "number") return raw > 0 ? [key] : [];
      return asText(raw) ? [key] : [];
    })
  );
}

function parseTelemetryDocument(value: unknown): ResearchTier2TelemetryDocument | null {
  const item = asRecord(value);
  if (!item) return null;

  const id =
    asId(item.id) ??
    asId(item.doc_id) ??
    asId(item.document_id) ??
    asId(item.source_id) ??
    asId(item.file_id);
  const source =
    asText(item.source) ??
    asText(item.source_name) ??
    asText(item.provider) ??
    asText(item.channel) ??
    asText(item.publisher);
  const title =
    asText(item.title) ??
    asText(item.name) ??
    asText(item.document_title) ??
    asText(item.filename) ??
    asText(item.file_name) ??
    id;
  const snippet =
    asText(item.snippet) ??
    asText(item.summary) ??
    asText(item.preview) ??
    asText(item.excerpt) ??
    asText(item.text);
  const score =
    asNumber(item.score) ??
    asNumber(item.relevance) ??
    asNumber(item.relevance_score) ??
    asNumber(item.rerank_score) ??
    asNumber(item.similarity) ??
    asNumber(item.confidence);
  const reasoning =
    asText(item.reasoning) ??
    asText(item.rationale) ??
    asText(item.match_reason) ??
    asText(item.explanation) ??
    asText(item.note) ??
    asText(item.source_reasoning);
  const url = asText(item.url) ?? asText(item.link);
  const error =
    asText(item.error) ??
    asText(item.error_code) ??
    asText(item.error_message) ??
    asText(item.failure_reason);

  const resolvedTitle = title ?? snippet ?? (source ? `${source} context` : "Context document");
  if (!resolvedTitle) return null;

  return {
    id,
    title: resolvedTitle,
    source,
    score,
    reasoning,
    snippet,
    url,
    error
  };
}

function dedupeTelemetryDocs(items: ResearchTier2TelemetryDocument[]): ResearchTier2TelemetryDocument[] {
  const seen = new Set<string>();
  const results: ResearchTier2TelemetryDocument[] = [];

  items.forEach((item) => {
    const key = `${item.id ?? ""}|${item.title}|${item.source ?? ""}|${item.score ?? ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    results.push(item);
  });

  return results;
}

function metricLabel(value: string): string {
  return value.replace(/[_-]+/g, " ").trim();
}

function parseTelemetryScores(value: unknown): ResearchTier2TelemetryScore[] {
  if (typeof value === "number") {
    return [{ label: "score", value }];
  }

  if (typeof value === "string") {
    const text = asText(value);
    return text ? [{ label: "score", value: text }] : [];
  }

  if (Array.isArray(value)) {
    return value.flatMap<ResearchTier2TelemetryScore>((item, index) => {
      if (typeof item === "number") {
        return [{ label: `score_${index + 1}`, value: item }];
      }
      if (typeof item === "string") {
        const text = asText(item);
        return text ? [{ label: `score_${index + 1}`, value: text }] : [];
      }

      const record = asRecord(item);
      if (!record) return [];
      const label =
        asText(record.label) ??
        asText(record.metric) ??
        asText(record.name) ??
        asText(record.key) ??
        asText(record.source);
      const numericValue =
        asNumber(record.value) ??
        asNumber(record.score) ??
        asNumber(record.confidence) ??
        asNumber(record.relevance);
      const textValue =
        asText(record.value) ??
        asText(record.score) ??
        asText(record.confidence) ??
        asText(record.relevance);
      if (label && numericValue !== undefined) {
        return [{ label: metricLabel(label), value: numericValue }];
      }
      if (label && textValue) {
        return [{ label: metricLabel(label), value: textValue }];
      }

      const primitiveEntries = Object.entries(record).filter(
        ([, raw]) => asNumber(raw) !== undefined || Boolean(asText(raw))
      );
      if (primitiveEntries.length === 1) {
        const [entryKey, raw] = primitiveEntries[0];
        const numeric = asNumber(raw);
        const text = asText(raw);
        if (numeric !== undefined) return [{ label: metricLabel(entryKey), value: numeric }];
        if (text) return [{ label: metricLabel(entryKey), value: text }];
      }
      return [];
    });
  }

  const record = asRecord(value);
  if (!record) return [];

  const scores: ResearchTier2TelemetryScore[] = [];
  Object.entries(record).forEach(([key, raw]) => {
    const numeric = asNumber(raw);
    if (numeric !== undefined) {
      scores.push({ label: metricLabel(key), value: numeric });
      return;
    }
    const text = asText(raw);
    if (text) {
      scores.push({ label: metricLabel(key), value: text });
      return;
    }

    const nested = asRecord(raw);
    if (!nested) return;
    const nestedNumeric =
      asNumber(nested.value) ??
      asNumber(nested.score) ??
      asNumber(nested.confidence) ??
      asNumber(nested.relevance);
    const nestedText =
      asText(nested.value) ??
      asText(nested.score) ??
      asText(nested.confidence) ??
      asText(nested.relevance);
    if (nestedNumeric !== undefined) {
      scores.push({ label: metricLabel(key), value: nestedNumeric });
      return;
    }
    if (nestedText) {
      scores.push({ label: metricLabel(key), value: nestedText });
    }
  });

  return scores;
}

function dedupeTelemetryScores(items: ResearchTier2TelemetryScore[]): ResearchTier2TelemetryScore[] {
  const seen = new Set<string>();
  const results: ResearchTier2TelemetryScore[] = [];

  items.forEach((item) => {
    const key = `${item.label.toLowerCase()}|${String(item.value)}`;
    if (seen.has(key)) return;
    seen.add(key);
    results.push(item);
  });

  return results;
}

function parseTelemetrySourceReasoningItem(
  value: unknown,
  sourceHint?: string
): ResearchTier2SourceReasoning | null {
  if (typeof value === "string") {
    const reasoning = asText(value);
    if (!reasoning) return null;
    return { source: sourceHint ?? "general", reasoning };
  }

  if (typeof value === "number" && Number.isFinite(value) && sourceHint) {
    return { source: sourceHint, score: value };
  }

  const item = asRecord(value);
  if (!item) return null;

  const source =
    asText(item.source) ??
    asText(item.source_name) ??
    asText(item.provider) ??
    asText(item.channel) ??
    sourceHint;
  const reasoning =
    asText(item.reasoning) ??
    asText(item.rationale) ??
    asText(item.explanation) ??
    asText(item.note) ??
    asText(item.detail) ??
    asText(item.summary);
  const score =
    asNumber(item.score) ??
    asNumber(item.relevance) ??
    asNumber(item.confidence) ??
    asNumber(item.weight);
  const error =
    asText(item.error) ??
    asText(item.error_code) ??
    asText(item.error_message) ??
    asText(item.failure_reason);

  if (!source && !reasoning && score === undefined && !error) return null;

  return {
    source: source ?? "general",
    reasoning,
    score,
    error
  };
}

function parseTelemetrySourceReasoning(value: unknown): ResearchTier2SourceReasoning[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseTelemetrySourceReasoningItem(item))
      .filter((item): item is ResearchTier2SourceReasoning => Boolean(item));
  }

  const direct = parseTelemetrySourceReasoningItem(value);
  if (direct) return [direct];

  const record = asRecord(value);
  if (!record) return [];

  return Object.entries(record).flatMap(([source, raw]) => {
    if (Array.isArray(raw)) {
      return raw
        .map((item) => parseTelemetrySourceReasoningItem(item, source))
        .filter((item): item is ResearchTier2SourceReasoning => Boolean(item));
    }

    const parsed = parseTelemetrySourceReasoningItem(raw, source);
    return parsed ? [parsed] : [];
  });
}

function dedupeTelemetrySourceReasoning(items: ResearchTier2SourceReasoning[]): ResearchTier2SourceReasoning[] {
  const seen = new Set<string>();
  const results: ResearchTier2SourceReasoning[] = [];

  items.forEach((item) => {
    const key = `${item.source}|${item.reasoning ?? ""}|${item.score ?? ""}|${item.error ?? ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    results.push(item);
  });

  return results;
}

const TRACE_METADATA_CONTAINER_KEYS = [
  "trace_metadata",
  "trace_context",
  "otel_trace_metadata",
  "otel_trace_context",
  "otel_trace",
  "trace",
  "otel",
  "traceMetadata",
  "traceContext",
  "otelTraceMetadata",
  "otelTraceContext",
  "otelTrace"
] as const;

const TRACE_METADATA_SCALAR_KEYS = [
  "trace_id",
  "span_id",
  "parent_span_id",
  "trace_flags",
  "trace_state",
  "tracestate",
  "traceparent",
  "sampled",
  "service_name",
  "service",
  "component"
] as const;

function isTraceMetadataKey(key: string): boolean {
  const normalized = key.trim().toLowerCase();
  if (!normalized) return false;
  return (
    normalized.includes("trace") ||
    normalized.includes("span") ||
    normalized.includes("otel") ||
    normalized.includes("sampled") ||
    normalized.includes("service") ||
    normalized.includes("component")
  );
}

function normalizeTraceMetadataPrimitive(value: unknown): ResearchTier2TraceMetadataValue | undefined {
  if (typeof value === "string") {
    const text = asText(value);
    return text;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "boolean") {
    return value;
  }
  return undefined;
}

function collectTraceMetadataEntries(
  value: unknown,
  target: ResearchTier2TraceMetadata,
  prefix = "",
  depth = 0
): void {
  if (depth > 2) return;

  const record = asRecord(value);
  if (!record) return;

  Object.entries(record).forEach(([rawKey, rawValue]) => {
    const key = prefix ? `${prefix}.${rawKey}` : rawKey;
    const primitive = normalizeTraceMetadataPrimitive(rawValue);
    if (primitive !== undefined) {
      if (isTraceMetadataKey(key) && target[key] === undefined) {
        target[key] = primitive;
      }
      return;
    }

    if (Array.isArray(rawValue)) {
      const compact = rawValue
        .map((item) => normalizeTraceMetadataPrimitive(item))
        .filter((item): item is ResearchTier2TraceMetadataValue => item !== undefined)
        .slice(0, 8);
      if (compact.length && isTraceMetadataKey(key) && target[key] === undefined) {
        target[key] = compact.map((item) => String(item)).join(", ");
      }
      return;
    }

    collectTraceMetadataEntries(rawValue, target, key, depth + 1);
  });
}

function parseTraceMetadataFromRecords(
  records: Array<Record<string, unknown> | null>
): ResearchTier2TraceMetadata {
  const traceMetadata: ResearchTier2TraceMetadata = {};

  records.forEach((record) => {
    if (!record) return;

    TRACE_METADATA_CONTAINER_KEYS.forEach((key) => {
      collectTraceMetadataEntries(record[key], traceMetadata);
    });

    TRACE_METADATA_SCALAR_KEYS.forEach((key) => {
      const primitive = normalizeTraceMetadataPrimitive(record[key]);
      if (primitive !== undefined && traceMetadata[key] === undefined) {
        traceMetadata[key] = primitive;
      }
    });
  });

  return traceMetadata;
}

function parseEvidenceList(value: unknown): string[] {
  if (typeof value === "string") {
    const text = asText(value);
    return text ? [text] : [];
  }

  if (!Array.isArray(value)) {
    const record = asRecord(value);
    if (!record) return [];
    return parseEvidenceList(
      record.items ?? record.values ?? record.sources ?? record.citations ?? record.evidence
    );
  }

  return uniqueText(
    value
      .flatMap((item) => {
        if (typeof item === "string" || typeof item === "number") return [String(item)];
        const row = asRecord(item);
        if (!row) return [];
        const evidenceText =
          asText(row.title) ??
          asText(row.name) ??
          asText(row.id) ??
          asText(row.source) ??
          asText(row.url) ??
          asText(row.snippet) ??
          asText(row.detail);
        return evidenceText ? [evidenceText] : [];
      })
      .filter(Boolean)
  );
}

function parseVerificationMatrixEntry(value: unknown): ResearchTier2VerificationMatrixEntry | null {
  if (typeof value === "string") {
    const claim = asText(value);
    return claim ? { claim, evidence: [] } : null;
  }

  const row = asRecord(value);
  if (!row) return null;

  const claim =
    asText(row.claim) ??
    asText(row.statement) ??
    asText(row.assertion) ??
    asText(row.text) ??
    asText(row.title);
  const verdict =
    asText(row.verdict) ??
    asText(row.status) ??
    asText(row.result) ??
    asText(row.label);
  const confidence =
    asNumber(row.confidence) ??
    asNumber(row.score) ??
    asNumber(row.support_score) ??
    asNumber(row.probability);
  const note =
    asText(row.note) ??
    asText(row.reasoning) ??
    asText(row.rationale) ??
    asText(row.summary) ??
    asText(row.explanation);
  const source =
    asText(row.source) ??
    asText(row.source_name) ??
    asText(row.provider);
  const evidence = parseEvidenceList(
    row.evidence ??
    row.evidences ??
    row.supporting_evidence ??
    row.supportingEvidence ??
    row.citations ??
    row.sources
  );

  const resolvedClaim = claim ?? source ?? note;
  if (!resolvedClaim && !verdict && confidence === undefined && !evidence.length) {
    return null;
  }

  return {
    claim: resolvedClaim ?? "Claim",
    verdict,
    confidence,
    note,
    source,
    evidence
  };
}

function parseVerificationMatrix(value: unknown): ResearchTier2VerificationMatrixEntry[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseVerificationMatrixEntry(item))
      .filter((item): item is ResearchTier2VerificationMatrixEntry => Boolean(item));
  }

  const record = asRecord(value);
  if (!record) {
    const direct = parseVerificationMatrixEntry(value);
    return direct ? [direct] : [];
  }

  const nestedRows =
    record.rows ??
    record.items ??
    record.claims ??
    record.entries ??
    record.matrix ??
    record.verification_matrix;
  if (nestedRows !== undefined && nestedRows !== value) {
    const parsedNested = parseVerificationMatrix(nestedRows);
    if (parsedNested.length) return parsedNested;
  }

  const direct = parseVerificationMatrixEntry(record);
  return direct ? [direct] : [];
}

function dedupeVerificationMatrix(
  items: ResearchTier2VerificationMatrixEntry[]
): ResearchTier2VerificationMatrixEntry[] {
  const seen = new Set<string>();
  const results: ResearchTier2VerificationMatrixEntry[] = [];

  items.forEach((item) => {
    const key = `${item.claim}|${item.verdict ?? ""}|${item.confidence ?? ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    results.push(item);
  });

  return results;
}

function parseContradictionSummary(value: unknown): ResearchTier2ContradictionSummary | undefined {
  const text = asText(value);
  if (text) {
    return {
      hasContradiction: true,
      count: 1,
      summary: text
    };
  }

  if (Array.isArray(value)) {
    const entries = uniqueText(value.flatMap((item) => parseTelemetryErrors(item)));
    if (!entries.length) return undefined;
    return {
      hasContradiction: true,
      count: entries.length,
      summary: entries.slice(0, 2).join(" | ")
    };
  }

  const record = asRecord(value);
  if (!record) return undefined;

  const contradictions = Array.isArray(record.contradictions) ? record.contradictions : undefined;
  const count =
    asNumber(record.count) ??
    asNumber(record.total) ??
    asNumber(record.contradiction_count) ??
    asNumber(record.contradictions_count) ??
    (contradictions ? contradictions.length : undefined);
  const hasContradiction =
    asBoolean(record.has_contradiction) ??
    asBoolean(record.hasContradiction) ??
    asBoolean(record.contradiction_detected) ??
    asBoolean(record.contradictions_found) ??
    (count !== undefined ? count > 0 : undefined);
  const severity = asText(record.severity);
  const status = asText(record.status);
  const summary =
    asText(record.summary) ??
    asText(record.note) ??
    asText(record.message) ??
    asText(record.description);

  if (
    hasContradiction === undefined &&
    count === undefined &&
    !severity &&
    !status &&
    !summary
  ) {
    return undefined;
  }

  return {
    hasContradiction,
    count,
    severity,
    status,
    summary
  };
}

function parseSearchPlan(value: unknown): ResearchTier2SearchPlan {
  const text = asText(value);
  if (text) {
    return {
      query: text,
      keywords: [],
      subqueries: [],
      connectors: []
    };
  }

  if (Array.isArray(value)) {
    const subqueries = uniqueText(
      value
        .map((item) => {
          if (typeof item === "string" || typeof item === "number") return String(item);
          const row = asRecord(item);
          if (!row) return "";
          return (
            asText(row.subquery) ??
            asText(row.sub_query) ??
            asText(row.query) ??
            asText(row.term) ??
            asText(row.keyword) ??
            asText(row.name) ??
            asText(row.value) ??
            ""
          );
        })
        .filter(Boolean)
    );
    return {
      query: subqueries[0],
      keywords: [],
      subqueries,
      connectors: []
    };
  }

  const record = asRecord(value) ?? {};
  const rawConnectors =
    record.connectors ??
    record.connector_names ??
    record.connectorNameList ??
    record.connector_list ??
    record.connectorList ??
    record.sources ??
    record.provider_list ??
    record.providerList ??
    record.providers;
  const rawSubqueries =
    record.subqueries ??
    record.sub_queries ??
    record.subquery_list ??
    record.subqueryList ??
    record.query_list ??
    record.queries;
  return {
    query:
      asText(record.query) ??
      asText(record.query_text) ??
      asText(record.search_query) ??
      asText(record.topic),
    researchMode:
      asText(record.research_mode) ?? asText(record.researchMode) ?? asText(record.mode),
    topK: asNumber(record.top_k) ?? asNumber(record.topK) ?? asNumber(record.k),
    totalCandidates:
      asNumber(record.total_candidates) ??
      asNumber(record.totalCandidates) ??
      asNumber(record.candidate_count) ??
      asNumber(record.candidateCount),
    durationMs:
      asNumber(record.duration_ms) ??
      asNumber(record.durationMs) ??
      asNumber(record.latency_ms) ??
      asNumber(record.latencyMs),
    keywords: parseKeywordList(
      record.keywords ??
      record.query_keywords ??
      record.keyword_list ??
      record.keywordList ??
      record.query_terms ??
      record.terms
    ),
    subqueries: parseKeywordList(rawSubqueries),
    connectors: parseKeywordList(rawConnectors)
  };
}

function parseSourceAttempt(value: unknown): ResearchTier2SourceAttempt | null {
  const item = asRecord(value);
  if (!item) return null;
  const source =
    asText(item.source) ??
    asText(item.provider) ??
    asText(item.connector) ??
    asText(item.name) ??
    asText(item.source_name) ??
    asText(item.source_id);
  if (!source) return null;
  return {
    source,
    status: asText(item.status) ?? asText(item.state) ?? asText(item.result) ?? asText(item.outcome),
    documents:
      asNumber(item.documents) ??
      asNumber(item.doc_count) ??
      asNumber(item.document_count) ??
      asNumber(item.retrieved_count) ??
      asNumber(item.retrievedCount) ??
      asNumber(item.selected_count),
    error:
      asText(item.error) ??
      asText(item.error_code) ??
      asText(item.error_message) ??
      asText(item.failure_reason),
    durationMs: asNumber(item.duration_ms) ?? asNumber(item.durationMs),
    query: asText(item.query) ?? asText(item.search_query) ?? asText(item.query_text),
    subquery: asText(item.subquery) ?? asText(item.sub_query) ?? asText(item.query_focus),
    passIndex:
      asNumber(item.pass_index) ??
      asNumber(item.passIndex) ??
      asNumber(item.pass) ??
      asNumber(item.round)
  };
}

function parseSourceAttempts(value: unknown): ResearchTier2SourceAttempt[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => parseSourceAttempt(item))
      .filter((item): item is ResearchTier2SourceAttempt => Boolean(item));
  }

  const record = asRecord(value);
  if (record) {
    const direct = parseSourceAttempt(record);
    if (direct) return [direct];

    return Object.entries(record).flatMap(([sourceName, raw]) => {
      if (Array.isArray(raw)) {
        return raw
          .map((entry) => {
            const row = asRecord(entry);
            if (row) {
              return parseSourceAttempt({ source: sourceName, ...row });
            }
            const text = asText(entry);
            if (text) {
              return parseSourceAttempt({ source: sourceName, status: text });
            }
            return null;
          })
          .filter((item): item is ResearchTier2SourceAttempt => Boolean(item));
      }

      const nested = asRecord(raw);
      if (nested) {
        const parsed = parseSourceAttempt({ source: sourceName, ...nested });
        return parsed ? [parsed] : [];
      }

      const text = asText(raw);
      if (text) {
        const parsed = parseSourceAttempt({ source: sourceName, status: text });
        return parsed ? [parsed] : [];
      }

      const numeric = asNumber(raw);
      if (numeric !== undefined) {
        const parsed = parseSourceAttempt({ source: sourceName, documents: numeric });
        return parsed ? [parsed] : [];
      }

      return [];
    });
  }

  const single = parseSourceAttempt(value);
  return single ? [single] : [];
}

function parseDeepPassSourceAttempts(value: unknown): ResearchTier2SourceAttempt[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((item) => {
    const row = asRecord(item);
    if (!row) return [];
    const passIndex = asNumber(row.pass_index) ?? asNumber(row.passIndex);
    const attempts = parseSourceAttempts(row.source_attempts ?? row.sourceAttempts);
    if (passIndex === undefined) return attempts;
    return attempts.map((attempt) => ({
      ...attempt,
      passIndex: attempt.passIndex ?? passIndex
    }));
  });
}

function dedupeSourceAttempts(items: ResearchTier2SourceAttempt[]): ResearchTier2SourceAttempt[] {
  const seen = new Set<string>();
  const results: ResearchTier2SourceAttempt[] = [];
  items.forEach((item) => {
    const key = [
      item.source,
      item.status ?? "",
      item.query ?? "",
      item.subquery ?? "",
      String(item.passIndex ?? ""),
      String(item.documents ?? "")
    ].join("|");
    if (seen.has(key)) return;
    seen.add(key);
    results.push(item);
  });
  return results;
}

function parseIndexSummary(value: unknown): ResearchTier2IndexSummary {
  const item = asRecord(value) ?? {};
  const sourceCountsRecord = asRecord(item.source_counts) ?? asRecord(item.sourceCounts);
  const sourceCounts = sourceCountsRecord
    ? Object.fromEntries(
        Object.entries(sourceCountsRecord)
          .map(([key, raw]) => [key, asNumber(raw)])
          .filter(([, raw]) => raw !== undefined)
      )
    : undefined;
  return {
    retrievedCount:
      asNumber(item.retrieved_count) ??
      asNumber(item.retrievedCount),
    sourceCounts,
    beforeDedupe:
      asNumber(item.before_dedupe) ??
      asNumber(item.before_dedupe_count) ??
      asNumber(item.beforeDedupe),
    afterDedupe:
      asNumber(item.after_dedupe) ??
      asNumber(item.after_dedupe_count) ??
      asNumber(item.afterDedupe),
    selectedCount:
      asNumber(item.selected_count) ??
      asNumber(item.selected_documents_count) ??
      asNumber(item.selectedCount),
    durationMs: asNumber(item.duration_ms) ?? asNumber(item.durationMs)
  };
}

function parseCrawlSummary(value: unknown): ResearchTier2CrawlSummary {
  const item = asRecord(value) ?? {};
  return {
    enabled: typeof item.enabled === "boolean" ? item.enabled : undefined,
    attempted:
      asNumber(item.attempted) ??
      asNumber(item.pages_requested) ??
      asNumber(item.pages_attempted) ??
      asNumber(item.pagesAttempted),
    success:
      asNumber(item.success) ??
      asNumber(item.pages_crawled) ??
      asNumber(item.pagesCrawled),
    domains: parseKeywordList(item.domains ?? item.domain_list ?? item.hosts),
    durationMs: asNumber(item.duration_ms) ?? asNumber(item.durationMs)
  };
}

function parseTelemetryErrors(value: unknown): string[] {
  const text = asText(value);
  if (text) return [text];

  if (Array.isArray(value)) {
    return uniqueText(value.flatMap((item) => parseTelemetryErrors(item)));
  }

  const record = asRecord(value);
  if (!record) return [];

  const errors: string[] = [];
  Object.entries(record).forEach(([key, raw]) => {
    const nestedErrors = parseTelemetryErrors(raw);
    if (nestedErrors.length) {
      nestedErrors.forEach((entry) => errors.push(`${key}: ${entry}`));
      return;
    }

    if (typeof raw === "boolean" && raw) {
      errors.push(key);
      return;
    }

    const numeric = asNumber(raw);
    if (numeric !== undefined) {
      errors.push(`${key}: ${numeric}`);
    }
  });

  return uniqueText(errors);
}

function parseVisualAsset(value: unknown): ResearchTier2VisualAsset | null {
  const record = asRecord(value);
  if (!record) return null;
  const title = asText(record.title) ?? asText(record.caption) ?? asText(record.id);
  const url = asText(record.url) ?? asText(record.href);
  if (!title && !url) return null;
  return {
    id: asText(record.id),
    title: title ?? "Visual asset",
    url,
    caption: asText(record.caption),
    source: asText(record.source),
    provider: asText(record.provider),
    mimeType: asText(record.mime_type) ?? asText(record.mimeType),
    width: asNumber(record.width),
    height: asNumber(record.height),
  };
}

function parseChartSpec(value: unknown): ResearchTier2ChartSpec | null {
  const record = asRecord(value);
  if (!record) return null;
  const title = asText(record.title) ?? asText(record.name) ?? asText(record.id);
  const spec =
    asText(record.spec) ??
    asText(record.content) ??
    asText(record.code) ??
    asText(record.value);
  if (!title && !spec) return null;
  return {
    id: asText(record.id),
    title: title ?? "Chart spec",
    format: asText(record.format) ?? asText(record.type),
    spec: spec ?? "",
    description: asText(record.description) ?? asText(record.note),
  };
}

function parseReasoningDigest(value: unknown): ResearchTier2ReasoningDigest {
  const record = asRecord(value);
  if (!record) {
    const text = asText(value);
    return {
      summary: text,
      items: [],
    };
  }

  const items = parseList(
    record.items ?? record.steps ?? record.highlights,
    (item): ResearchTier2ReasoningDigestItem | null => {
      const row = asRecord(item);
      if (!row) return null;
      const title = asText(row.title) ?? asText(row.label);
      const detail = asText(row.detail) ?? asText(row.note) ?? asText(row.reasoning);
      if (!title && !detail) return null;
      return {
        title: title ?? "Reasoning step",
        detail,
        confidence: asNumber(row.confidence),
        status: asText(row.status),
      };
    }
  );

  return {
    summary: asText(record.summary) ?? asText(record.note),
    items,
  };
}

export async function uploadResearchFile(file: File): Promise<ResearchUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post<ResearchUploadRawResponse>("/research/upload-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: RESEARCH_UPLOAD_TIMEOUT_MS
  });

  const data = response.data;
  const files = parseList(data.files ?? data.uploaded_files ?? data.file, parseUploadedFile);
  const idsFromPayload = uniqueIds([
    ...parseIdList(data.uploaded_file_ids),
    ...parseIdList(data.file_ids),
    ...parseIdList(data.uploaded_file_id),
    ...parseIdList(data.file_id),
    ...parseIdList(data.id)
  ]);
  const idsFromFiles = files.map((item) => item.id);
  const uploadedFileIds = uniqueIds([...idsFromPayload, ...idsFromFiles]);

  if (!files.length && uploadedFileIds.length) {
    return {
      uploadedFileIds,
      files: uploadedFileIds.map((id, index) => ({
        id,
        name: index === 0 ? file.name : `${file.name} (${index + 1})`,
        size: file.size
      }))
    };
  }

  return { uploadedFileIds, files };
}

export async function runResearchTier2(
  query: string,
  options?: {
    uploadedFileIds?: string[];
    sourceIds?: number[];
    researchMode?: ResearchExecutionMode;
  }
): Promise<ResearchTier2RawResponse> {
  const uploadedFileIds = uniqueIds((options?.uploadedFileIds ?? []).map((item) => item.trim()).filter(Boolean));
  const sourceIds = Array.from(
    new Set((options?.sourceIds ?? []).filter((item) => Number.isFinite(item) && item > 0).map((item) => Math.trunc(item)))
  );
  const payload: Record<string, unknown> = { query, message: query };
  const researchMode = normalizeResearchExecutionMode(options?.researchMode);
  payload.research_mode = researchMode;
  payload.answer_format = "markdown";
  payload.response_format = "markdown";
  payload.render_hints = {
    markdown: true,
    tables: true,
    mermaid: true,
    chart_spec_fences: ["chart-spec", "vega-lite", "echarts-option", "json", "yaml"]
  };

  if (uploadedFileIds.length) {
    payload.uploaded_file_ids = uploadedFileIds;
  }
  if (sourceIds.length) {
    payload.source_ids = sourceIds;
  }

  const response = await api.post<ResearchTier2RawResponse>("/research/tier2", payload, {
    timeout: RESEARCH_TIER2_TIMEOUT_MS
  });
  return response.data;
}

export async function createResearchTier2Job(
  query: string,
  options?: {
    uploadedFileIds?: string[];
    sourceIds?: number[];
    sourceHubSources?: SourceHubSourceKey[];
    researchMode?: ResearchExecutionMode;
  }
): Promise<ResearchTier2JobResponse> {
  const uploadedFileIds = uniqueIds((options?.uploadedFileIds ?? []).map((item) => item.trim()).filter(Boolean));
  const sourceIds = Array.from(
    new Set((options?.sourceIds ?? []).filter((item) => Number.isFinite(item) && item > 0).map((item) => Math.trunc(item)))
  );
  const sourceHubSources = uniqueText((options?.sourceHubSources ?? []).map((item) => String(item))) as SourceHubSourceKey[];
  const researchMode = normalizeResearchExecutionMode(options?.researchMode);

  const payload: Record<string, unknown> = {
    query,
    message: query,
    research_mode: researchMode,
    answer_format: "markdown",
    response_format: "markdown",
    render_hints: {
      markdown: true,
      tables: true,
      mermaid: true,
      chart_spec_fences: ["chart-spec", "vega-lite", "echarts-option", "json", "yaml"]
    }
  };

  if (uploadedFileIds.length) payload.uploaded_file_ids = uploadedFileIds;
  if (sourceIds.length) payload.source_ids = sourceIds;
  if (sourceHubSources.length) payload.source_hub_sources = sourceHubSources;

  const response = await api.post<ResearchTier2JobResponse>("/research/tier2/jobs", payload, {
    timeout: 30000
  });
  return response.data;
}

export async function getResearchTier2Job(jobId: string): Promise<ResearchTier2JobResponse> {
  const response = await api.get<ResearchTier2JobResponse>(`/research/tier2/jobs/${jobId}`, {
    timeout: 30000
  });
  return response.data;
}

export async function streamResearchTier2Job(
  jobId: string,
  handlers: {
    onEvent: (event: ResearchTier2JobStreamEvent) => void;
    signal?: AbortSignal;
    maxWaitMs?: number;
  }
): Promise<void> {
  const accessToken = getAccessToken();
  if (!accessToken) {
    throw new Error("Thiếu access token để mở streaming research.");
  }

  const maxWaitMs = Math.max(30000, handlers.maxWaitMs ?? RESEARCH_TIER2_STREAM_MAX_WAIT_MS);
  const streamUrl = `${resolveApiBaseUrl().replace(/\/$/, "")}/research/tier2/jobs/${encodeURIComponent(jobId)}/stream?heartbeat_seconds=10&poll_interval_seconds=0.7`;
  const startedAt = Date.now();
  const response = await fetch(streamUrl, {
    method: "GET",
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${accessToken}`,
      "Cache-Control": "no-cache",
    },
    signal: handlers.signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Không thể mở stream research (status=${response.status}).`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    if (Date.now() - startedAt > maxWaitMs) {
      throw new Error("Streaming research vượt quá thời gian chờ.");
    }
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;

    buffer += decoder.decode(value, { stream: true });
    const { blocks, tail } = parseSseBlocks(buffer);
    buffer = tail;

    for (const block of blocks) {
      const parsed = parseSseEventBlock(block);
      if (!parsed) continue;
      if (parsed.event !== "progress" && parsed.event !== "done" && parsed.event !== "error") {
        continue;
      }
      let payload: unknown = {};
      try {
        payload = JSON.parse(parsed.data);
      } catch {
        payload = { message: parsed.data };
      }
      handlers.onEvent({
        event: parsed.event,
        payload: payload as ResearchTier2JobResponse | { message?: string },
      });
      if (parsed.event === "done" || parsed.event === "error") {
        return;
      }
    }
  }
}

export function normalizeResearchTier2JobProgress(value: unknown): ResearchTier2JobProgress {
  const record = asRecord(value) ?? {};
  const flowEvents = parseFlowEvents(record.flow_events ?? record.events);
  const metadataStages = parseFlowStages(record.flow_stages ?? record.stages);
  const flowStages = metadataStages.length ? metadataStages : deriveStagesFromFlowEvents(flowEvents);
  const reasoningSteps = parseList(
    pickFromRecords(
      [record],
      [
        "reasoning_steps",
        "reasoning_notes",
        "reasoning_log",
        "reasoning_timeline",
        "reasoning",
        "notes"
      ]
    ),
    (item) => {
      const direct = asText(item);
      if (direct) return direct;
      const row = asRecord(item);
      if (!row) return null;
      const note =
        asText(row.note) ??
        asText(row.detail) ??
        asText(row.message) ??
        asText(row.reasoning) ??
        asText(row.summary);
      return note ? note : null;
    }
  );
  const statusNote =
    asText(record.status_note) ??
    asText(record.status) ??
    asText(record.message);

  return {
    flowStages,
    flowEvents,
    activeStage: asText(record.active_stage),
    statusNote,
    reasoningNotes: uniqueText([...(statusNote ? [statusNote] : []), ...reasoningSteps]).slice(-40)
  };
}

export function normalizeResearchTier2(data: ResearchTier2RawResponse): ResearchTier2Result {
  const metadata = asRecord(data.metadata) ?? {};
  const answer =
    asText(data.answer_markdown) ??
    asText(data.answer_md) ??
    asText(metadata.answer_markdown) ??
    asText(data.answer) ??
    asText(data.summary) ??
    asText(data.message) ??
    "";
  const citations = parseList(data.citations ?? data.sources, parseCitation);
  const contextDebug = asRecord(data.context_debug) ?? asRecord(metadata.context_debug);
  const telemetryRecord =
    asRecord(data.telemetry) ??
    asRecord(metadata.telemetry) ??
    asRecord(contextDebug?.telemetry);
  const debugRecord = asRecord(data.debug) ?? asRecord(metadata.debug);
  const telemetryRecords: Array<Record<string, unknown> | null> = [
    telemetryRecord,
    contextDebug,
    debugRecord,
    metadata,
    asRecord(data)
  ];

  const keywords = parseKeywordList(
    pickFromRecords(telemetryRecords, [
      "keywords",
      "query_keywords",
      "keyword_list",
      "matched_keywords",
      "intent_keywords",
      "keyword_hits",
      "keyword_scores"
    ])
  );
  const searchPlan = parseSearchPlan(
    pickFromRecords(telemetryRecords, [
      "search_plan",
      "search_trace",
      "query_plan",
      "searchPlan",
      "queryPlan"
    ])
  );
  const sourceAttempts = dedupeSourceAttempts(
    [
      ...parseSourceAttempts(
        pickFromRecords(telemetryRecords, [
          "source_attempts",
          "connector_attempts",
          "provider_events",
          "retrieval_attempts",
          "sourceAttempts",
          "retrievalAttempts",
          "attempts_by_source",
          "attemptsBySource"
        ])
      ),
      ...parseDeepPassSourceAttempts(
        pickFromRecords(telemetryRecords, [
          "deep_pass_summaries",
          "deepPassSummaries"
        ])
      )
    ]
  );
  const indexSummary = parseIndexSummary(
    pickFromRecords(telemetryRecords, [
      "index_summary",
      "rerank_summary",
      "ranking_summary"
    ])
  );
  const crawlSummary = parseCrawlSummary(
    pickFromRecords(telemetryRecords, [
      "crawl_summary",
      "web_crawl_summary",
      "crawl_trace"
    ])
  );
  const docs = dedupeTelemetryDocs(
    parseList(
      pickFromRecords(telemetryRecords, [
        "docs",
        "documents",
        "retrieved_docs",
        "retrieved_context",
        "context_docs",
        "context_documents",
        "evidence_docs",
        "top_docs",
        "sources",
        "candidates"
      ]),
      parseTelemetryDocument
    )
  );
  const sourceReasoningFromDocs = docs
    .filter(
      (doc): doc is ResearchTier2TelemetryDocument & { source: string } =>
        Boolean(doc.source) && Boolean(doc.reasoning || doc.score !== undefined || doc.error)
    )
    .map((doc) => ({
      source: doc.source,
      reasoning: doc.reasoning,
      score: doc.score,
      error: doc.error
    }));
  const sourceReasoning = dedupeTelemetrySourceReasoning([
    ...parseTelemetrySourceReasoning(
      pickFromRecords(telemetryRecords, [
        "source_reasoning",
        "source_reasonings",
        "reasoning_by_source",
        "per_source_reasoning",
        "source_notes"
      ])
    ),
    ...sourceReasoningFromDocs
  ]);
  const scores = dedupeTelemetryScores([
    ...parseTelemetryScores(
      pickFromRecords(telemetryRecords, [
        "scores",
        "score_breakdown",
        "score_map",
        "metrics",
        "context_scores",
        "ranking_scores",
        "source_scores"
      ])
    ),
    ...parseTelemetryScores({
      relevance: pickFromRecords(telemetryRecords, ["relevance", "context_relevance", "retrieval_score"]),
      low_context_threshold: pickFromRecords(telemetryRecords, ["low_context_threshold", "threshold"])
    })
  ]);
  const docErrors = docs.map((doc) => doc.error).filter((item): item is string => Boolean(item));
  const sourceReasoningErrors = sourceReasoning
    .map((item) => item.error)
    .filter((item): item is string => Boolean(item));
  const verificationMatrix = dedupeVerificationMatrix(
    parseVerificationMatrix(
      pickFromRecords(telemetryRecords, [
        "verification_matrix",
        "claim_verification_matrix",
        "claim_matrix",
        "claims_matrix",
        "verificationMatrix",
        "claimMatrix"
      ])
    )
  );
  const contradictionSummary = parseContradictionSummary(
    pickFromRecords(telemetryRecords, [
      "contradiction_summary",
      "contradictions_summary",
      "contradiction_report",
      "contradiction_overview",
      "contradictionSummary"
    ])
  );
  const traceMetadata = parseTraceMetadataFromRecords(telemetryRecords);
  const errors = uniqueText([
    ...parseTelemetryErrors(
      pickFromRecords(telemetryRecords, [
        "errors",
        "error",
        "error_list",
        "source_errors",
        "retrieval_errors",
        "failed_sources",
        "errors_list",
        "sourceErrors",
        "retrievalErrors",
        "failedSources"
      ])
    ),
    ...parseTelemetryErrors(data.source_errors),
    ...parseTelemetryErrors(metadata.source_errors),
    ...parseTelemetryErrors(contextDebug?.source_errors),
    ...docErrors,
    ...sourceReasoningErrors
  ]);
  const fallbackInfo = uniqueText([
    ...parseTelemetryErrors(data.fallback_reason),
    ...parseTelemetryErrors(metadata.fallback_reason),
    ...parseTelemetryErrors(contextDebug?.fallback_reason)
  ]);
  const telemetry: ResearchTier2Telemetry = {
    keywords,
    searchPlan,
    sourceAttempts,
    indexSummary,
    crawlSummary,
    docs,
    scores,
    sourceReasoning,
    verificationMatrix,
    contradictionSummary,
    traceMetadata,
    errors,
    fallbackInfo
  };
  const visualAssets = parseList(
    data.visual_assets ?? data.visualAssets ?? data.images ?? metadata.visual_assets ?? metadata.visualAssets,
    parseVisualAsset
  );
  const chartSpecs = parseList(
    data.chart_specs ?? data.chartSpecs ?? metadata.chart_specs ?? metadata.chartSpecs,
    parseChartSpec
  );
  const reasoningDigest = parseReasoningDigest(
    data.reasoning_digest ??
      data.reasoningDigest ??
      metadata.reasoning_digest ??
      metadata.reasoningDigest
  );

  const flowEvents = parseFlowEvents(
    data.flow_events ??
      metadata.flow_events ??
      data.events ??
      metadata.events
  );
  const metadataStages = parseFlowStages(
    metadata.flow_stages ??
      data.flow_stages ??
      metadata.stages ??
      data.stages
  );
  const flowStages = metadataStages.length ? metadataStages : deriveStagesFromFlowEvents(flowEvents);
  const parsedSteps = parseList(data.steps ?? data.workflow_steps ?? data.plan_steps, parseStep);
  const steps = parsedSteps.length
    ? parsedSteps
    : flowStages.map((stage) => ({
        title: stage.label,
        detail: stage.detail
      }));
  const verification = asRecord(metadata.verification_status);
  const rawPolicy = (asText(metadata.policy_action) ?? asText(data.policy_action))?.toLowerCase();
  const policyAction = rawPolicy === "warn" ? "warn" : rawPolicy === "allow" ? "allow" : undefined;
  const fallbackUsed =
    typeof metadata.fallback_used === "boolean"
      ? metadata.fallback_used
      : typeof data.fallback_used === "boolean"
        ? data.fallback_used
        : undefined;
  const rawVerificationState = asText(metadata.verification_status);

  const verificationStatus = verification
    ? {
        verdict: asText(verification.verdict) ?? asText(verification.state),
        confidence: asNumber(verification.confidence),
        severity: asText(verification.severity),
        note: asText(verification.note),
        evidenceCount: asNumber(verification.evidence_count)
      }
    : rawVerificationState
      ? {
          verdict: rawVerificationState
        }
      : undefined;

  return {
    answer,
    citations,
    steps,
    flowStages,
    flowEvents,
    debug: {
      pipeline: asText(metadata.pipeline),
      responseStyle: asText(metadata.response_style),
      sourceMode: asText(metadata.source_mode),
      researchMode: asText(metadata.research_mode) ?? asText((data as Record<string, unknown>).research_mode),
      deepPassCount:
        asNumber(metadata.deep_pass_count) ??
        asNumber((data as Record<string, unknown>).deep_pass_count),
      stageCount: flowStages.length,
      flowEventCount: flowEvents.length,
      telemetryKeywordCount: telemetry.keywords.length,
      telemetryDocCount: telemetry.docs.length,
      telemetrySourceAttemptCount: telemetry.sourceAttempts.length,
      telemetryErrorCount: telemetry.errors.length,
      crawlDomainCount: telemetry.crawlSummary.domains.length,
      routing: parseRoutingHint(
        pickFromRecords(telemetryRecords, ["routing", "route_hint", "router"]) ?? metadata.routing
      )
    },
    telemetry,
    visualAssets,
    chartSpecs,
    reasoningDigest,
    verificationStatus,
    policyAction,
    fallbackUsed,
    researchMode:
      asText(metadata.research_mode) ??
      asText((data as Record<string, unknown>).research_mode),
    deepPassCount:
      asNumber(metadata.deep_pass_count) ??
      asNumber((data as Record<string, unknown>).deep_pass_count)
  };
}

function parseKnowledgeSource(item: unknown): KnowledgeSource | null {
  const value = asRecord(item);
  if (!value) return null;
  const id = asNumber(value.id);
  const name = asText(value.name);
  if (!id || !name) return null;
  return {
    id: Math.trunc(id),
    name,
    description: asText(value.description) ?? "",
    is_active: Boolean(value.is_active ?? true),
    documents_count: Math.trunc(asNumber(value.documents_count) ?? 0),
  };
}

function parseKnowledgeSourceDocument(item: unknown): KnowledgeSourceDocument | null {
  const value = asRecord(item);
  if (!value) return null;
  const id = asNumber(value.id);
  const sourceId = asNumber(value.source_id);
  const filename = asText(value.filename);
  if (!id || !sourceId || !filename) return null;
  return {
    id: Math.trunc(id),
    source_id: Math.trunc(sourceId),
    filename,
    content_type: asText(value.content_type) ?? "application/octet-stream",
    size: Math.trunc(asNumber(value.size) ?? 0),
    preview: asText(value.preview) ?? "",
    token_count: Math.trunc(asNumber(value.token_count) ?? 0),
    is_active: Boolean(value.is_active ?? true),
  };
}

function parseSourceHubKey(value: unknown): SourceHubSourceKey | null {
  const text = asText(value)?.toLowerCase();
  if (
    text === "pubmed" ||
    text === "rxnorm" ||
    text === "openfda" ||
    text === "dailymed" ||
    text === "clinicaltrials" ||
    text === "europepmc" ||
    text === "semantic_scholar" ||
    text === "vn_moh" ||
    text === "vn_kcb" ||
    text === "vn_canhgiacduoc" ||
    text === "vn_vbpl_byt" ||
    text === "vn_dav" ||
    text === "davidrug"
  ) {
    return text;
  }
  return null;
}

function parseSourceHubCatalogEntry(item: unknown): SourceHubCatalogEntry | null {
  const value = asRecord(item);
  if (!value) return null;
  const key = parseSourceHubKey(value.key);
  const label = asText(value.label);
  const description = asText(value.description);
  if (!key || !label || !description) return null;
  return {
    key,
    label,
    description,
    docs_url: asText(value.docs_url),
    default_query: asText(value.default_query),
    supports_live_sync: Boolean(value.supports_live_sync ?? true)
  };
}

function parseSourceHubRecord(item: unknown): SourceHubRecord | null {
  const value = asRecord(item);
  if (!value) return null;
  const id = asId(value.id);
  const source = parseSourceHubKey(value.source);
  const title = asText(value.title);
  if (!id || !source || !title) return null;
  return {
    id,
    source,
    title,
    url: asText(value.url),
    snippet: asText(value.snippet),
    external_id: asText(value.external_id),
    query: asText(value.query),
    published_at: asText(value.published_at),
    synced_at: asText(value.synced_at),
    metadata: asRecord(value.metadata) ?? {}
  };
}

function parseConversationResultPayload(value: unknown): Record<string, unknown> | null {
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parseConversationResultPayload(parsed);
    } catch {
      return { tier: "tier1", answer: value };
    }
  }

  const record = asRecord(value);
  if (!record) return null;
  const nestedResult = asRecord(record.result);
  const payload = nestedResult ?? record;

  const tierText = (asText(payload.tier) ?? "").toLowerCase();
  if (tierText === "tier1" || tierText === "tier2") {
    return { ...payload, tier: tierText };
  }

  if (payload.citations || payload.flowEvents || payload.flow_events || payload.telemetry) {
    return { ...payload, tier: "tier2" };
  }
  return { ...payload, tier: "tier1" };
}

function parsePersistedConversation(item: unknown): PersistedResearchConversation | null {
  const value = asRecord(item);
  if (!value) return null;

  const id = asId(value.id) ?? asId(value.session_id) ?? asId(value.conversation_id);
  const query = asText(value.query) ?? asText(value.user_input) ?? asText(value.message);
  const result = parseConversationResultPayload(value.result ?? value.response_text ?? value.response);
  const createdAt =
    asTimestampMs(value.created_at) ??
    asTimestampMs(value.createdAt) ??
    asTimestampMs(value.timestamp) ??
    Date.now();

  if (!id || !query || !result) return null;
  const tier = String(result.tier ?? value.tier ?? "tier1").toLowerCase() === "tier2" ? "tier2" : "tier1";

  return {
    id,
    queryId: asId(value.query_id),
    query,
    tier,
    result: { ...result, tier },
    createdAt
  };
}

function parsePersistedMessage(item: unknown): PersistedResearchMessage | null {
  const value = asRecord(item);
  if (!value) return null;

  const query = asText(value.query) ?? asText(value.user_input) ?? asText(value.message);
  const result = parseConversationResultPayload(value.result ?? value.response_text ?? value.response);
  const createdAt =
    asTimestampMs(value.created_at) ??
    asTimestampMs(value.createdAt) ??
    asTimestampMs(value.timestamp) ??
    Date.now();

  if (!query || !result) return null;
  const tier =
    String(result.tier ?? value.tier ?? "tier1").toLowerCase() === "tier2"
      ? "tier2"
      : "tier1";

  return {
    queryId: asId(value.query_id),
    query,
    tier,
    result: { ...result, tier },
    createdAt,
  };
}

export async function listKnowledgeSources(): Promise<KnowledgeSource[]> {
  const response = await api.get<{ items?: unknown }>("/research/knowledge-sources");
  const items = asRecord(response.data)?.items;
  return parseList(items, parseKnowledgeSource);
}

export async function createKnowledgeSource(name: string, description = ""): Promise<KnowledgeSource> {
  const response = await api.post<unknown>("/research/knowledge-sources", { name, description });
  const parsed = parseKnowledgeSource(response.data);
  if (!parsed) throw new Error("Không thể tạo knowledge source.");
  return parsed;
}

export async function updateKnowledgeSource(
  sourceId: number,
  payload: { is_active?: boolean; name?: string; description?: string }
): Promise<KnowledgeSource> {
  const response = await api.patch<unknown>(`/research/knowledge-sources/${sourceId}`, payload);
  const parsed = parseKnowledgeSource(response.data);
  if (!parsed) throw new Error("Không thể cập nhật knowledge source.");
  return parsed;
}

export async function listKnowledgeSourceDocuments(sourceId: number): Promise<KnowledgeSourceDocument[]> {
  const response = await api.get<{ items?: unknown }>(`/research/knowledge-sources/${sourceId}/documents`);
  const items = asRecord(response.data)?.items;
  return parseList(items, parseKnowledgeSourceDocument);
}

export async function uploadFileToKnowledgeSource(sourceId: number, file: File): Promise<KnowledgeSourceDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<unknown>(`/research/knowledge-sources/${sourceId}/upload-file`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: RESEARCH_UPLOAD_TIMEOUT_MS
  });
  const record = asRecord(response.data)?.document;
  const parsed = parseKnowledgeSourceDocument(record);
  if (!parsed) throw new Error("Không thể upload file vào knowledge source.");
  return parsed;
}

export async function setKnowledgeDocumentStatus(documentId: number, isActive: boolean): Promise<KnowledgeSourceDocument> {
  const response = await api.patch<unknown>(`/research/documents/${documentId}`, { is_active: isActive });
  const parsed = parseKnowledgeSourceDocument(response.data);
  if (!parsed) throw new Error("Không thể cập nhật trạng thái document.");
  return parsed;
}

export async function listSourceHubCatalog(): Promise<SourceHubCatalogEntry[]> {
  const response = await api.get<{ sources?: unknown }>("/research/source-hub/catalog");
  return parseList(asRecord(response.data)?.sources, parseSourceHubCatalogEntry);
}

export async function listSourceHubRecords(params?: {
  source?: SourceHubSourceKey | "all";
  query?: string;
  limit?: number;
}): Promise<SourceHubRecord[]> {
  const response = await api.get<{ records?: unknown }>("/research/source-hub/records", {
    params: {
      source: params?.source,
      query: params?.query,
      limit: params?.limit
    }
  });
  return parseList(asRecord(response.data)?.records, parseSourceHubRecord);
}

export async function syncSourceHub(payload: {
  source: SourceHubSourceKey;
  query: string;
  limit?: number;
}): Promise<SourceHubSyncResult> {
  const response = await api.post<unknown>("/research/source-hub/sync", payload);
  const data = asRecord(response.data);
  const source = parseSourceHubKey(data?.source);
  const query = asText(data?.query) ?? payload.query;
  if (!source) throw new Error("Không thể đồng bộ nguồn dữ liệu.");

  return {
    source,
    query,
    fetched: Math.trunc(asNumber(data?.fetched) ?? 0),
    stored: Math.trunc(asNumber(data?.stored) ?? 0),
    records: parseList(data?.records, parseSourceHubRecord),
    warnings: parseList(data?.warnings, (item) => {
      const text = asText(item);
      return text ? text : null;
    })
  };
}

export async function listResearchConversations(limit = 50): Promise<PersistedResearchConversation[]> {
  const response = await api.get<{ items?: unknown }>("/research/conversations", {
    params: { limit }
  });
  const root = asRecord(response.data);
  const items = root?.items ?? response.data;
  return parseList(items, parsePersistedConversation);
}

export async function createResearchConversation(
  query: string,
  result: Record<string, unknown>
): Promise<PersistedResearchConversation> {
  const response = await api.post<unknown>("/research/conversations", { query, result });
  const parsed = parsePersistedConversation(response.data);
  if (!parsed) throw new Error("Không thể lưu conversation vào database.");
  return parsed;
}

export async function appendResearchConversationMessage(
  conversationId: string | number,
  query: string,
  result: Record<string, unknown>
): Promise<PersistedResearchConversation> {
  const normalizedId =
    typeof conversationId === "number" ? conversationId : Math.trunc(Number(conversationId));
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) {
    throw new Error("conversationId không hợp lệ.");
  }
  const response = await api.post<unknown>(
    `/research/conversations/${normalizedId}/messages`,
    { query, result }
  );
  const parsed = parsePersistedConversation(response.data);
  if (!parsed) throw new Error("Không thể lưu message vào conversation.");
  return parsed;
}

export async function listResearchConversationMessages(
  conversationId: string | number,
  limit = 100
): Promise<PersistedResearchMessage[]> {
  const normalizedId =
    typeof conversationId === "number" ? conversationId : Math.trunc(Number(conversationId));
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) return [];
  const response = await api.get<{ items?: unknown }>(
    `/research/conversations/${normalizedId}/messages`,
    { params: { limit } }
  );
  const root = asRecord(response.data);
  const items = root?.items ?? response.data;
  return parseList(items, parsePersistedMessage);
}

export async function deleteResearchConversation(
  conversationId: string | number
): Promise<boolean> {
  const normalizedId =
    typeof conversationId === "number" ? conversationId : Math.trunc(Number(conversationId));
  if (!Number.isFinite(normalizedId) || normalizedId <= 0) return false;
  const response = await api.delete<{ deleted?: unknown }>(
    `/research/conversations/${normalizedId}`
  );
  return Boolean(asRecord(response.data)?.deleted);
}
