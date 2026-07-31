import api from "@/lib/http-client";

export type CareguardAnalyzeRequest = {
  symptoms: string[];
  labs: Record<string, number | string>;
  medications: string[];
  locale?: "vi" | "en";
  /**
   * Optional bounded Vietnamese list/sentence. The server extracts exact
   * candidates only and returns a terminal clarification state if any named
   * medicine cannot be safely identified; it is never an LLM normalization.
   */
  medication_text?: string;
  allergies: string[];
};

export type CareguardDdiAlert = {
  title: string;
  severity?: string;
  details?: string;
};

export type CareguardAttributionSource = {
  id: string;
  name: string;
  category?: string;
  type?: string;
};

export type CareguardAttributionCitation = {
  source: string;
  url?: string;
};

export type CareguardAttribution = {
  channel?: string;
  mode?: string | null;
  sourceCount: number;
  citationCount: number;
  sources: CareguardAttributionSource[];
  citations: CareguardAttributionCitation[];
};

export type CareguardSourceErrors = Record<string, string[]>;

/**
 * A source-backed DrugBank identity offered only when the deterministic index
 * cannot safely select a medicine on the person's behalf.  It deliberately
 * carries no risk, recommendation, or model-generated confidence.
 */
export type CareguardMedicationClarificationCandidate = {
  drugbank_id: string;
  normalized_name: string;
  active_ingredients: string[];
  source_version: string;
};

/** A cabinet item which must be clarified before any DDI result is produced. */
export type CareguardMedicationClarification = {
  cabinet_item_id: number;
  input_alias: string;
  candidates: CareguardMedicationClarificationCandidate[];
};

export type CareguardAnalyzeRawResponse = {
  /**
   * Terminal fail-closed state.  When present, callers must not project or
   * cache this object as a DDI result.
   */
  status?: unknown;
  clarifications?: unknown;
  risk_tier?: string;
  riskTier?: string;
  tier?: string;
  risk?: string;
  risk_obj?: {
    level?: string;
  };
  ddi_alerts?: unknown;
  ddiAlerts?: unknown;
  recommendations?: unknown;
  recommendation?: unknown;
  metadata?: unknown;
  attribution?: unknown;
  attributions?: unknown;
  fallback_used?: unknown;
  fallbackUsed?: unknown;
  source_errors?: unknown;
  sourceErrors?: unknown;
  consumer_explanation?: unknown;
  consumerExplanation?: unknown;
  ddi_status?: unknown;
  ddiStatus?: unknown;
  mode?: unknown;
  [key: string]: unknown;
};

function asSafeClarificationCandidate(value: unknown): CareguardMedicationClarificationCandidate | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const drugbankId = typeof candidate.drugbank_id === "string" ? candidate.drugbank_id.trim() : "";
  const normalizedName = typeof candidate.normalized_name === "string" ? candidate.normalized_name.trim() : "";
  const sourceVersion = typeof candidate.source_version === "string" ? candidate.source_version.trim() : "";
  if (!drugbankId || !normalizedName || !sourceVersion) return null;
  return {
    drugbank_id: drugbankId,
    normalized_name: normalizedName,
    active_ingredients: Array.isArray(candidate.active_ingredients)
      ? candidate.active_ingredients.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
      : [],
    source_version: sourceVersion,
  };
}

/**
 * Parse only the additive, source-backed clarification terminal state.
 * Unknown/malformed payloads fail closed by returning no clarification rather
 * than manufacturing a choice in the browser.
 */
export function medicationClarifications(
  value: CareguardAnalyzeRawResponse,
): CareguardMedicationClarification[] | null {
  if (value.status !== "requires_medication_clarification") return null;
  if (!Array.isArray(value.clarifications)) return [];
  return value.clarifications.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const clarification = raw as Record<string, unknown>;
    const cabinetItemId = clarification.cabinet_item_id;
    const inputAlias = typeof clarification.input_alias === "string" ? clarification.input_alias.trim() : "";
    if (!Number.isSafeInteger(cabinetItemId) || (cabinetItemId as number) <= 0 || !inputAlias) return [];
    return [{
      cabinet_item_id: cabinetItemId as number,
      input_alias: inputAlias,
      candidates: Array.isArray(clarification.candidates)
        ? clarification.candidates.flatMap((candidate) => {
            const parsed = asSafeClarificationCandidate(candidate);
            return parsed ? [parsed] : [];
          })
        : [],
    }];
  });
}

export type CareguardAnalyzeResult = {
  riskTier: string | null;
  ddiAlerts: CareguardDdiAlert[];
  recommendations: string[];
  attribution: CareguardAttribution | null;
  mode: string | null;
  fallbackUsed: boolean;
  sourceErrors: CareguardSourceErrors;
  sourceUsed: string[];
};

/** Coarse, machine-readable DDI risk classification used by end-user views. */
export type DdiRiskLevel = "low" | "medium" | "high" | "critical" | "unknown";

/** A single end-user-facing DDI alert. Excludes telemetry/severity internals. */
export type DdiUserAlert = {
  message: string;
  details?: string;
  severity: DdiRiskLevel;
};

/** A reference source shown to the end user (label only, optional link). */
export type DdiUserSource = {
  label: string;
  url?: string;
};

/**
 * The projected DDI view shown to an End_User. It exposes only risk level,
 * alerts, recommendations, and reference sources. It intentionally omits
 * runtime `mode`, `fallback` flags, and `source_errors` (Requirements 3.1, 3.6).
 */
export type DdiUserView = {
  riskLevel: DdiRiskLevel;
  alerts: DdiUserAlert[];
  recommendations: string[];
  sources: DdiUserSource[];
};

/**
 * Bounded, verifier-approved wording generated from already released CareGuard
 * facts. It is presentation-only: no medication name, dose, risk score, or
 * source decision can be changed here.
 */
export type CareguardConsumerExplanation = {
  headline: string;
  summary: string;
  whyItMatters: string[];
  nextSteps: string[];
  uncertainty: string;
  safetyText?: string;
  sourceLabels: string[];
};

/** A non-technical disclosure of whether a DDI conclusion was available. */
export type CareguardDdiConclusion = {
  availability: "available" | "unavailable" | "unknown";
  authority: "drugbank" | "other" | null;
  sourceVersion: string | null;
  medicationAmbiguity: boolean;
};

/**
 * Consumer composition used by the Medicines safety surface. The existing
 * four-field DdiUserView remains the sole offline-cache projection.
 */
export type CareguardConsumerView = {
  ddi: DdiUserView;
  explanation: CareguardConsumerExplanation | null;
  conclusion: CareguardDdiConclusion;
};

/** Minimum number of medicines required before a DDI check may run (Requirement 3.5). */
export const MINIMUM_DDI_MEDICINES = 2;

const NORMALIZED_SOURCE_NAMES: Record<string, string> = {
  openfda: "OpenFDA",
  rxnav: "RxNav",
  dailymed: "DailyMed",
  fda: "FDA",
  local: "Nguồn cục bộ",
  localdb: "Nguồn cục bộ",
  localcache: "Nguồn cục bộ"
};

const TECHNICAL_COPY_MARKERS = [
  "source_errors",
  "source error",
  "openfda",
  "rxnav",
  "http_",
  "status=",
  "status_code",
  "traceback",
  "stack trace",
  "exception",
  "axioserror",
  "<html",
  "</html>",
  "\"detail\":",
  "{\"detail\"",
  "sqlstate",
  "validationerror"
];

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const next = value.trim();
  return next ? next : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") {
    if (value === 1) return true;
    if (value === 0) return false;
    return undefined;
  }
  if (typeof value !== "string") return undefined;
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes"].includes(normalized)) return true;
  if (["false", "0", "no"].includes(normalized)) return false;
  return undefined;
}

function normalizeUserFacingText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function normalizeSourceToken(value: string | null | undefined): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function normalizeSourceName(value: string): string {
  const key = normalizeSourceToken(value);
  if (key && NORMALIZED_SOURCE_NAMES[key]) {
    return NORMALIZED_SOURCE_NAMES[key];
  }
  return normalizeUserFacingText(value);
}

function shouldHideTechnicalCopy(value: string): boolean {
  const normalized = normalizeUserFacingText(value).toLowerCase();
  if (!normalized) return true;
  if (TECHNICAL_COPY_MARKERS.some((marker) => normalized.includes(marker))) return true;
  if (/\bhttps?:\/\//i.test(normalized)) return true;
  if (/\b(?:http|status)[\s:_-]*[45]\d{2}\b/i.test(normalized)) return true;
  return false;
}

function sanitizeReadableLine(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const normalized = normalizeUserFacingText(value);
  if (!normalized || shouldHideTechnicalCopy(normalized)) return undefined;
  return normalized;
}

function dedupeReadableLines(values: string[]): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const value of values) {
    const sanitized = sanitizeReadableLine(value);
    if (!sanitized) continue;
    const key = sanitized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(sanitized);
  }
  return output;
}

function dedupeAttributionSources(values: CareguardAttributionSource[]): CareguardAttributionSource[] {
  const output: CareguardAttributionSource[] = [];
  const seen = new Set<string>();
  for (const source of values) {
    const key = normalizeSourceToken(source.name) || normalizeSourceToken(source.id);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    output.push({
      ...source,
      name: normalizeSourceName(source.name)
    });
  }
  return output;
}

function dedupeStringList(values: string[]): string[] {
  const output: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const normalized = normalizeUserFacingText(value);
    if (!normalized) continue;
    const key = normalized.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(normalized);
  }
  return output;
}

function resolveErrorText(cause: unknown): string | undefined {
  if (typeof cause === "string") return cause;
  if (cause instanceof Error) return cause.message;
  const record = asRecord(cause);
  if (!record) return undefined;
  return asText(record.message) ?? asText(record.detail);
}

export function toCareguardUserMessage(cause: unknown, fallback: string): string {
  const resolved = sanitizeReadableLine(resolveErrorText(cause));
  if (!resolved || resolved.length > 220) {
    return fallback;
  }
  return resolved;
}

export function formatCareguardRiskLabel(value: string | null | undefined): string {
  const normalized = normalizeSourceToken(value);
  if (/(critical|severe|contra|major|high|red|danger)/.test(normalized)) return "Cao";
  if (/(moderate|medium|amber|intermediate)/.test(normalized)) return "Trung bình";
  if (/(minor|low|green|safe|none)/.test(normalized)) return "Thấp";
  return "Chưa xác định";
}

function parseStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => asText(item))
      .filter((item): item is string => Boolean(item));
  }

  const single = asText(value);
  return single ? [single] : [];
}

function parseDdiAlert(value: unknown): CareguardDdiAlert | null {
  if (typeof value === "string") {
    const text = sanitizeReadableLine(asText(value));
    return text ? { title: text } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const title =
    asText(item.title) ??
    asText(item.interaction) ??
    asText(item.pair) ??
    asText(item.summary) ??
    asText(item.message) ??
    asText(item.alert);

  const sanitizedTitle = sanitizeReadableLine(title);
  if (!sanitizedTitle) return null;

  const details = sanitizeReadableLine(
    asText(item.details) ??
      asText(item.description) ??
      asText(item.recommendation) ??
      asText(item.advice)
  );

  return {
    title: sanitizedTitle,
    severity: asText(item.severity) ?? asText(item.level) ?? asText(item.risk),
    details
  };
}

function parseDdiAlerts(value: unknown): CareguardDdiAlert[] {
  if (!Array.isArray(value)) {
    const single = parseDdiAlert(value);
    return single ? [single] : [];
  }

  return value
    .map((item) => parseDdiAlert(item))
    .filter((item): item is CareguardDdiAlert => Boolean(item));
}

function parseAttributionSource(value: unknown): CareguardAttributionSource | null {
  const record = asRecord(value);
  if (!record) return null;
  const id = asText(record.id);
  const name = asText(record.name);
  if (!id || !name) return null;
  return {
    id,
    name: normalizeSourceName(name),
    category: asText(record.category),
    type: asText(record.type)
  };
}

function parseAttributionCitation(value: unknown): CareguardAttributionCitation | null {
  const record = asRecord(value);
  if (!record) return null;
  const source = asText(record.source);
  if (!source) return null;
  return {
    source,
    url: asText(record.url)
  };
}

function parseAttribution(value: unknown): CareguardAttribution | null {
  const record = asRecord(value);
  if (!record) return null;

  const parsedSources = Array.isArray(record.sources)
    ? record.sources.map((item) => parseAttributionSource(item)).filter((item): item is CareguardAttributionSource => Boolean(item))
    : [];
  const sources = dedupeAttributionSources(parsedSources);
  const citations = Array.isArray(record.citations)
    ? record.citations
        .map((item) => parseAttributionCitation(item))
        .filter((item): item is CareguardAttributionCitation => Boolean(item))
    : [];

  const sourceCountRaw = record.source_count;
  const citationCountRaw = record.citation_count;
  const sourceCount =
    sources.length > 0
      ? sources.length
      : typeof sourceCountRaw === "number" && Number.isFinite(sourceCountRaw)
        ? sourceCountRaw
        : 0;
  const citationCount =
    typeof citationCountRaw === "number" && Number.isFinite(citationCountRaw) ? citationCountRaw : citations.length;

  return {
    channel: asText(record.channel),
    mode: asText(record.mode) ?? null,
    sourceCount,
    citationCount,
    sources,
    citations
  };
}

function parseSourceErrors(value: unknown): CareguardSourceErrors {
  const record = asRecord(value);
  if (!record) return {};
  const output: CareguardSourceErrors = {};
  for (const [key, next] of Object.entries(record)) {
    const values = parseStringList(next);
    if (!values.length) continue;
    output[key] = values;
  }
  return output;
}

function mergeSourceErrors(...values: CareguardSourceErrors[]): CareguardSourceErrors {
  const output: CareguardSourceErrors = {};
  for (const value of values) {
    for (const [key, messages] of Object.entries(value)) {
      if (!messages.length) continue;
      const existing = new Set(output[key] ?? []);
      messages.forEach((item) => existing.add(item));
      output[key] = Array.from(existing);
    }
  }
  return output;
}

export function parseFreeTextList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseLabsInput(value: string): Record<string, number | string> {
  const output: Record<string, number | string> = {};
  const tokens = parseFreeTextList(value);
  for (const token of tokens) {
    const [rawKey, rawValue] = token.split(/[:=]/, 2);
    if (!rawKey || !rawValue) continue;
    const key = rawKey.trim().toLowerCase();
    const valueText = rawValue.trim();
    if (!key || !valueText) continue;
    const numeric = Number(valueText);
    output[key] = Number.isFinite(numeric) ? numeric : valueText;
  }
  return output;
}

export async function analyzeCareguard(payload: CareguardAnalyzeRequest): Promise<CareguardAnalyzeRawResponse> {
  const response = await api.post<CareguardAnalyzeRawResponse>("/careguard/analyze", payload);
  return response.data;
}

export function normalizeCareguardResult(data: CareguardAnalyzeRawResponse): CareguardAnalyzeResult {
  const riskRecord = asRecord(data.risk);
  const metadata = asRecord(data.metadata);

  const riskTier =
    asText(data.risk_tier) ??
    asText(data.riskTier) ??
    asText(data.tier) ??
    asText(data.risk) ??
    asText(riskRecord?.level) ??
    null;

  const ddiAlerts = parseDdiAlerts(data.ddi_alerts ?? data.ddiAlerts);

  const recommendations = dedupeReadableLines([
    ...parseStringList(data.recommendations),
    ...parseStringList(data.recommendation)
  ]);

  const attribution =
    parseAttribution(data.attribution) ??
    (Array.isArray(data.attributions) ? parseAttribution(data.attributions[0]) : null);

  const mode =
    attribution?.mode ??
    asText(data.mode) ??
    asText(metadata?.mode) ??
    (asBoolean(metadata?.external_ddi_enabled) === false
      ? "local_only"
      : asBoolean(metadata?.external_ddi_enabled) === true
        ? "external_plus_local"
        : null);

  const fallbackUsed =
    asBoolean(data.fallback_used) ??
    asBoolean(data.fallbackUsed) ??
    asBoolean(metadata?.fallback_used) ??
    asBoolean(metadata?.fallbackUsed) ??
    false;

  const sourceErrors = mergeSourceErrors(
    parseSourceErrors(data.source_errors),
    parseSourceErrors(data.sourceErrors),
    parseSourceErrors(metadata?.source_errors),
    parseSourceErrors(metadata?.sourceErrors)
  );

  const sourceUsed = dedupeStringList([
    ...parseStringList((data as Record<string, unknown>).source_used),
    ...parseStringList((data as Record<string, unknown>).sourceUsed),
    ...parseStringList(metadata?.source_used),
    ...parseStringList(metadata?.sourceUsed)
  ]);

  return {
    riskTier,
    ddiAlerts,
    recommendations,
    attribution,
    mode,
    fallbackUsed,
    sourceErrors,
    sourceUsed
  };
}

function parseConsumerExplanation(value: unknown): CareguardConsumerExplanation | null {
  const record = asRecord(value);
  // The browser must not make a renderer's release decision. Only an explicit
  // independent verifier pass may reach the consumer surface.
  if (!record || asBoolean(record.verifier_passed) !== true) return null;

  const headline = sanitizeReadableLine(asText(record.headline));
  const summary = sanitizeReadableLine(asText(record.summary));
  const uncertainty = sanitizeReadableLine(asText(record.uncertainty_text));
  if (!headline || !summary || !uncertainty) return null;

  const safetyText = sanitizeReadableLine(asText(record.safety_text));
  const sourceLabels = dedupeReadableLines(parseStringList(record.source_labels)).slice(0, 3);
  const explanation: CareguardConsumerExplanation = {
    headline,
    summary,
    whyItMatters: dedupeReadableLines(parseStringList(record.why_it_matters)).slice(0, 3),
    nextSteps: dedupeReadableLines(parseStringList(record.next_steps)).slice(0, 3),
    uncertainty,
    sourceLabels
  };
  if (safetyText) explanation.safetyText = safetyText;
  return explanation;
}

function parseSourceVersion(value: unknown): string | null {
  const candidate = sanitizeReadableLine(asText(value));
  // Artifact versions are controlled identifiers, never raw upstream text.
  if (!candidate || candidate.length > 120 || !/^[a-zA-Z0-9._:+-]+$/.test(candidate)) {
    return null;
  }
  return candidate;
}

function careguardConclusion(
  data: CareguardAnalyzeRawResponse,
  normalized: CareguardAnalyzeResult
): CareguardDdiConclusion {
  const metadata = asRecord(data.metadata);
  const status = asRecord(data.ddi_status ?? data.ddiStatus) ?? asRecord(metadata?.ddi_status);
  const conclusionAvailable = asBoolean(status?.conclusion_available);
  const medicationAmbiguity = asBoolean(metadata?.normalization_pair_coverage_low) === true;

  if (conclusionAvailable === false) {
    return {
      availability: "unavailable",
      authority: null,
      sourceVersion: null,
      medicationAmbiguity
    };
  }

  const drugbank = asRecord(metadata?.drugbank);
  const drugbankReady =
    drugbank?.state === "ready" && normalized.sourceUsed.includes("drugbank");
  if (drugbankReady) {
    return {
      availability: "available",
      authority: "drugbank",
      sourceVersion: parseSourceVersion(drugbank?.version),
      medicationAmbiguity
    };
  }

  if (normalized.sourceUsed.length > 0 || conclusionAvailable === true) {
    return {
      availability: "available",
      authority: "other",
      sourceVersion: null,
      medicationAmbiguity
    };
  }
  return {
    availability: "unknown",
    authority: null,
    sourceVersion: null,
    medicationAmbiguity
  };
}

/**
 * Compose the task-first CareGuard view without leaking transport errors,
 * scores, normalization confidences, or raw provenance. The deterministic
 * DDI result remains authoritative; renderer output is accepted only after its
 * independent verifier reports success.
 */
export function toCareguardConsumerView(
  raw: CareguardAnalyzeRawResponse | CareguardAnalyzeResult
): CareguardConsumerView {
  const ddi = toDdiUserView(raw);
  const data = raw as CareguardAnalyzeRawResponse;
  const normalized = coerceCareguardResult(raw);
  return {
    ddi,
    explanation: parseConsumerExplanation(data.consumer_explanation ?? data.consumerExplanation),
    conclusion: careguardConclusion(data, normalized)
  };
}

/**
 * Classify any raw risk/severity token into a coarse DDI risk level.
 * `critical` is detected before `high` so the most severe match wins.
 */
export function classifyDdiRiskLevel(value: string | null | undefined): DdiRiskLevel {
  const normalized = normalizeSourceToken(value);
  if (!normalized) return "unknown";
  if (/(critical|contra|fatal|lifethreat)/.test(normalized)) return "critical";
  if (/(severe|major|high|red|danger)/.test(normalized)) return "high";
  if (/(moderate|medium|amber|intermediate)/.test(normalized)) return "medium";
  if (/(minor|low|green|safe|none)/.test(normalized)) return "low";
  return "unknown";
}

/** Common DDI risk groups recognized for Vietnamese localization (Requirement 3.4). */
export type DdiRiskGroup =
  | "bleeding"
  | "reducedClopidogrelEfficacy"
  | "drowsinessOrDizziness"
  | "hyperkalemia"
  | "myopathy";

/** Vietnamese alert message + recommendation shown for a recognized risk group. */
export type DdiRiskGroupCopy = {
  message: string;
  recommendation: string;
};

/**
 * Detection patterns per risk group. Each set matches both the English
 * passthrough markers emitted by the ML-layer `_localize_ddi_message`
 * (`services/ml/src/clara_ml/agents/careguard.py`) and the Vietnamese copy it
 * produces, so a group is recognized whether the upstream text arrived
 * localized or slipped through as an English passthrough (audit CG-6).
 */
const DDI_RISK_GROUP_PATTERNS: Record<DdiRiskGroup, RegExp[]> = {
  bleeding: [/\bbleed/, /h(?:a)?emorrhage/, /\bgi bleeding\b/, /blunt aspirin/, /\binr\b/, /chảy máu/],
  reducedClopidogrelEfficacy: [
    /clopidogrel/,
    /plavix/,
    /antiplatelet/,
    /cyp\s*2?c?19/,
    /cyp interaction/,
    /chống kết tập tiểu cầu/
  ],
  drowsinessOrDizziness: [
    /sedation/,
    /sedat/,
    /drowsi/,
    /somnolence/,
    /\bdizz/,
    /cns depress/,
    /buồn ngủ/,
    /chóng mặt/
  ],
  hyperkalemia: [/hyperkal(?:a|e)mia/, /potassium[-\s]?sparing/, /\bpotassium\b/, /kali máu/],
  myopathy: [
    /myopathy/,
    /rhabdomyolysis/,
    /myalgia/,
    /muscle (?:pain|ache|weakness|damage|injury)/,
    /đau cơ/,
    /tổn thương cơ/
  ]
};

/**
 * The canonical Vietnamese alert message and recommendation shown for each
 * common risk group (Requirement 3.4). The messages mirror the ML-layer copy
 * so localization is consistent across the ML aggregation and the web client.
 */
export const DDI_RISK_GROUP_LOCALIZATION: Record<DdiRiskGroup, DdiRiskGroupCopy> = {
  bleeding: {
    message: "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
    recommendation:
      "Không tự dùng kéo dài cùng nhau khi chưa được bác sĩ xác nhận. Đi khám ngay nếu nôn ra máu, " +
      "đi ngoài phân đen, chóng mặt nhiều hoặc chảy máu khó cầm."
  },
  reducedClopidogrelEfficacy: {
    message: "Thuốc này có thể làm giảm hiệu quả chống kết tập tiểu cầu của clopidogrel.",
    recommendation:
      "Hỏi bác sĩ hoặc dược sĩ để kiểm tra lại phối hợp này. Không tự đổi giờ uống hoặc kéo dài dùng cùng " +
      "nếu chưa được hướng dẫn."
  },
  drowsinessOrDizziness: {
    message: "Dùng cùng nhau có thể làm tăng buồn ngủ, chóng mặt và giảm tập trung.",
    recommendation:
      "Theo dõi buồn ngủ và chóng mặt. Tránh lái xe hoặc vận hành máy móc khi thấy lơ mơ, và hỏi bác sĩ " +
      "hoặc dược sĩ nếu cần dùng cùng trong nhiều ngày."
  },
  hyperkalemia: {
    message: "Phối hợp này có thể làm tăng kali máu, nhất là khi có bệnh thận.",
    recommendation:
      "Cần được bác sĩ hoặc dược sĩ kiểm tra sớm. Đi khám nếu mệt nhiều, yếu cơ, hồi hộp hoặc tiểu ít hơn " +
      "bình thường."
  },
  myopathy: {
    message: "Phối hợp này có thể làm tăng nguy cơ đau cơ, yếu cơ hoặc tổn thương cơ.",
    recommendation:
      "Liên hệ bác sĩ hoặc dược sĩ sớm để rà soát đơn thuốc. Đi khám ngay nếu đau cơ tăng nhanh, yếu cơ " +
      "nhiều hoặc nước tiểu sẫm màu."
  }
};

/**
 * Order used when more than one group could match the same text. Bleeding is
 * checked first because it is the most actionable signal; the drowsiness group
 * is checked last so a more specific organ-system match wins over generic CNS
 * wording.
 */
const DDI_RISK_GROUP_ORDER: DdiRiskGroup[] = [
  "bleeding",
  "reducedClopidogrelEfficacy",
  "hyperkalemia",
  "myopathy",
  "drowsinessOrDizziness"
];

/** Calm, generic Vietnamese fallback used when English passthrough cannot be mapped. */
const GENERIC_DDI_MESSAGE_VI =
  "Hai thuốc này có thể tương tác với nhau. Nên hỏi bác sĩ hoặc dược sĩ để kiểm tra lại.";

/** Mirrors the ML-layer Vietnamese-text check (`[À-ỹ]`). */
const VIETNAMESE_DIACRITIC_PATTERN = /[\u00C0-\u1EF9]/;

function containsVietnameseText(value: string): boolean {
  return VIETNAMESE_DIACRITIC_PATTERN.test(value);
}

/**
 * Classify free-text DDI copy into one of the common risk groups, or `null`
 * when no group matches. Matching is case-insensitive and recognizes both the
 * English passthrough markers and the Vietnamese copy.
 */
export function classifyDdiRiskGroup(text: string | null | undefined): DdiRiskGroup | null {
  const normalized = normalizeUserFacingText(String(text ?? "")).toLowerCase();
  if (!normalized) return null;
  for (const group of DDI_RISK_GROUP_ORDER) {
    if (DDI_RISK_GROUP_PATTERNS[group].some((pattern) => pattern.test(normalized))) {
      return group;
    }
  }
  return null;
}

/**
 * Localize a DDI alert message to Vietnamese. Mirrors the ML-layer
 * `_localize_ddi_message`: a recognized English passthrough maps to its
 * canonical Vietnamese copy, copy already in Vietnamese is preserved, and any
 * remaining English (audit CG-6) falls back to a calm generic Vietnamese line
 * so internal English never reaches the End_User.
 */
export function localizeDdiMessage(message: string | null | undefined): string {
  const normalized = normalizeUserFacingText(String(message ?? ""));
  if (!normalized) return GENERIC_DDI_MESSAGE_VI;
  if (containsVietnameseText(normalized)) return normalized;
  const group = classifyDdiRiskGroup(normalized);
  if (group) return DDI_RISK_GROUP_LOCALIZATION[group].message;
  return GENERIC_DDI_MESSAGE_VI;
}

/**
 * Return the Vietnamese recommendations for the supplied risk groups, in order.
 */
export function recommendationsForRiskGroups(groups: DdiRiskGroup[]): string[] {
  return groups.map((group) => DDI_RISK_GROUP_LOCALIZATION[group].recommendation);
}

/**
 * Collect the recognized risk groups present across DDI alert copy, preserving
 * first-seen order and de-duplicating repeats.
 */
function detectDdiRiskGroups(texts: (string | null | undefined)[]): DdiRiskGroup[] {
  const seen = new Set<DdiRiskGroup>();
  const output: DdiRiskGroup[] = [];
  for (const text of texts) {
    const group = classifyDdiRiskGroup(text);
    if (group && !seen.has(group)) {
      seen.add(group);
      output.push(group);
    }
  }
  return output;
}

/**
 * Localize an optional alert detail line. Vietnamese detail is preserved; an
 * English passthrough that maps to a risk group becomes that group's Vietnamese
 * copy (when it differs from the primary message); unmapped English detail is
 * dropped so internal English never leaks to the End_User.
 */
function localizeDdiDetail(detail: string | undefined, message: string): string | undefined {
  const sanitized = sanitizeReadableLine(detail);
  if (!sanitized) return undefined;
  if (containsVietnameseText(sanitized)) return sanitized;
  const group = classifyDdiRiskGroup(sanitized);
  if (group) {
    const localized = DDI_RISK_GROUP_LOCALIZATION[group].message;
    return localized === message ? undefined : localized;
  }
  return undefined;
}

/**
 * Count distinct, non-empty medicine names. A drug-drug interaction requires
 * two *different* medicines, so case-insensitive duplicates collapse to one.
 */
function countDistinctMedicines(medicines: string[] | null | undefined): number {
  if (!Array.isArray(medicines)) return 0;
  const seen = new Set<string>();
  for (const medicine of medicines) {
    const normalized = normalizeUserFacingText(String(medicine ?? "")).toLowerCase();
    if (!normalized) continue;
    seen.add(normalized);
  }
  return seen.size;
}

/**
 * Returns true when a DDI check must NOT run because the input has fewer than
 * two distinct medicines. The caller should prompt the user to add at least
 * two medicines and SHALL NOT call the DDI analysis (Requirement 3.5).
 */
export function requiresTwoMedicines(medicines: string[] | null | undefined): boolean {
  return countDistinctMedicines(medicines) < MINIMUM_DDI_MEDICINES;
}

function coerceCareguardResult(
  input: CareguardAnalyzeRawResponse | CareguardAnalyzeResult
): CareguardAnalyzeResult {
  const candidate = input as CareguardAnalyzeResult;
  if (Array.isArray(candidate.ddiAlerts) && Array.isArray(candidate.recommendations)) {
    return candidate;
  }
  return normalizeCareguardResult(input as CareguardAnalyzeRawResponse);
}

function toDdiUserSources(attribution: CareguardAttribution | null): DdiUserSource[] {
  if (!attribution) return [];
  const citationByLabel = new Map<string, string>();
  for (const citation of attribution.citations) {
    const key = normalizeSourceToken(citation.source);
    if (key && citation.url && !citationByLabel.has(key)) {
      citationByLabel.set(key, citation.url);
    }
  }
  return attribution.sources.map((source) => {
    const url = citationByLabel.get(normalizeSourceToken(source.name));
    return url ? { label: source.name, url } : { label: source.name };
  });
}

/**
 * Project a CareGuard payload (raw response or normalized result) into the
 * End_User DDI view. Exposes only risk level, alerts, recommendations, and
 * reference sources. Runtime `mode`, `fallback` flags, and `source_errors`
 * are intentionally dropped, so connector errors are never surfaced to the
 * end user while a valid signal remains (Requirements 3.1, 3.6).
 */
export function toDdiUserView(
  raw: CareguardAnalyzeRawResponse | CareguardAnalyzeResult
): DdiUserView {
  const result = coerceCareguardResult(raw);

  // Re-run the readable-text guard so the projection is self-contained: even
  // when a caller hands in a manually constructed result, alert copy and
  // recommendations stay free of connector identifiers, HTTP status detail,
  // and `source_errors` fragments (Requirements 3.1, 3.6).
  const alerts: DdiUserAlert[] = result.ddiAlerts
    .map((alert): DdiUserAlert | null => {
      const sanitizedTitle = sanitizeReadableLine(alert.title);
      if (!sanitizedTitle) return null;
      // Map any English passthrough for a recognized risk group to Vietnamese
      // before display, complementing the ML-layer localization (Requirement 3.4).
      const message = localizeDdiMessage(sanitizedTitle);
      const details = localizeDdiDetail(alert.details, message);
      const userAlert: DdiUserAlert = {
        message,
        severity: classifyDdiRiskLevel(alert.severity ?? result.riskTier)
      };
      // `details` is optional: only attach it when a readable line survives.
      if (details) userAlert.details = details;
      return userAlert;
    })
    .filter((alert): alert is DdiUserAlert => alert !== null);

  // Risk-group-aware Vietnamese recommendations (Requirement 3.4): derive them
  // from the recognized groups in the alert copy and merge with any upstream
  // recommendations, dropping duplicates and English passthrough.
  const riskGroups = detectDdiRiskGroups([
    ...alerts.map((alert) => alert.message),
    ...result.ddiAlerts.map((alert) => alert.details)
  ]);
  const recommendations = dedupeReadableLines([
    ...recommendationsForRiskGroups(riskGroups),
    ...result.recommendations
  ]);

  return {
    riskLevel: classifyDdiRiskLevel(result.riskTier),
    alerts,
    recommendations,
    sources: toDdiUserSources(result.attribution)
  };
}
