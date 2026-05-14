import api from "@/lib/http-client";

export type CareguardAnalyzeRequest = {
  symptoms: string[];
  labs: Record<string, number | string>;
  medications: string[];
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

export type CareguardAnalyzeRawResponse = {
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
  mode?: unknown;
  [key: string]: unknown;
};

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
