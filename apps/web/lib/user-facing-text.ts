/**
 * User-facing text boundary.
 *
 * This module is the single place that governs every string that crosses the
 * boundary from internal/back-end land into an End_User view. It keeps internal
 * jargon, stack traces, connector identifiers, and raw upstream errors out of
 * the UI and presents calm Vietnamese copy and friendly mode labels instead.
 *
 * All functions here are pure and side-effect free so they can be reused on the
 * server and the client and exercised directly by property tests.
 *
 * Design: `.kiro/specs/product-polish-analytics/design.md` section 2
 * Requirements: 4.1 (telemetry labels), 4.2 (sanitized upstream errors),
 *               4.4 (Vietnamese mode labels), 2.5 (sanitized timeout message).
 */

/** Calm Vietnamese copy shown when an upstream error must be hidden. */
export const GENERIC_ERROR_MESSAGE = "Hệ thống đang bận, vui lòng thử lại.";

/** Calm Vietnamese copy shown when a request timed out and can be retried. */
export const TIMEOUT_RETRY_MESSAGE =
  "Hệ thống phản hồi lâu hơn dự kiến, vui lòng thử lại sau giây lát.";

/** Longest clean upstream message we are willing to surface verbatim. */
const MAX_SAFE_MESSAGE_LENGTH = 220;

/**
 * Internal telemetry labels that must never appear in an End_User view.
 * Matched case-insensitively. Keep the most specific phrasings here; the
 * stripper applies them repeatedly until the string is stable.
 * Requirement 4.1.
 */
const TELEMETRY_LABEL_PATTERNS: RegExp[] = [
  /research\s+mode/gi,
  /rag\s+mode/gi,
  /fallback\s+mode/gi,
  /retrieval/gi,
  /policy:\s*warn(?:\s*\/\s*allow)?/gi,
  /policy:\s*allow(?:\s*\/\s*warn)?/gi
];

/**
 * Markers that signal a string carries internal/technical content which must
 * not reach an End_User. Mirrors the denylist already used in
 * `careguard.ts` so the two boundaries stay consistent.
 */
const TECHNICAL_CONTENT_MARKERS = [
  "traceback",
  "stack trace",
  "stacktrace",
  "exception",
  "sqlstate",
  "econnrefused",
  "econnaborted",
  "econnreset",
  "status_code",
  "status=",
  "http_",
  "<html",
  "</html>",
  '"detail"',
  '{"detail"',
  "openfda",
  "rxnav",
  "dailymed"
];

/**
 * Regular expressions that detect internal/technical content:
 * internal URLs, exception class names, HTTP status detail tokens,
 * connector ids, and stack-trace frames.
 */
const TECHNICAL_CONTENT_PATTERNS: RegExp[] = [
  /\bhttps?:\/\//i, // internal URLs
  /\b[a-z][\w.-]*:\/\//i, // any scheme://host (e.g. ws://, internal://)
  /\blocalhost\b/i,
  /\b\d{1,3}(?:\.\d{1,3}){3}\b/, // raw IPv4 addresses
  /\b\w*(?:Error|Exception)\b/, // exception class names (TypeError, AxiosError, ...)
  /\b(?:http|status)[\s:_-]*[1-5]\d{2}\b/i, // HTTP status detail tokens
  /\bhttp_\d{3}\b/i, // connector status ids such as openfda http_400
  /\bat\s+\S+\s+\(/, // JS stack frame: "at fn (file:line)"
  /\bFile\s+".*",\s*line\s+\d+/i, // Python stack frame
  /[{[]\s*"[^"]+"\s*:/ // raw JSON payloads
];

/** Markers that indicate the underlying failure was a timeout. */
const TIMEOUT_PATTERNS: RegExp[] = [
  /timed?\s*out/i,
  /\btimeout\b/i,
  /etimedout/i,
  /econnaborted/i,
  /deadline\s+exceeded/i,
  /\b504\b/
];

/**
 * Vietnamese labels presented to End_Users for each internal mode.
 * Requirement 4.4.
 */
const MODE_LABELS: Record<string, string> = {
  fast: "Nhanh",
  deep: "Tư duy",
  deep_beta: "Pro",
  auto: "Tự chọn",
  full: "Đầy đủ"
};

/** Safe default mode label for unknown/empty internal modes. */
const DEFAULT_MODE_LABEL = "Tự chọn";

function normalizeWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function looksLikeTimeout(value: string): boolean {
  return TIMEOUT_PATTERNS.some((pattern) => pattern.test(value));
}

function containsTechnicalContent(value: string): boolean {
  const lowered = value.toLowerCase();
  if (TECHNICAL_CONTENT_MARKERS.some((marker) => lowered.includes(marker))) {
    return true;
  }
  return TECHNICAL_CONTENT_PATTERNS.some((pattern) => pattern.test(value));
}

/**
 * Convert any raw upstream error or timeout payload into calm Vietnamese copy.
 *
 * Internal URLs, connector ids, HTTP status detail tokens, exception class
 * names, and stack traces are never surfaced: when the raw text carries any
 * technical content (or is empty, or unreasonably long) the function returns
 * the appropriate calm fallback message. A clean, short, human-readable string
 * with no technical content is passed through unchanged.
 *
 * Requirements 2.5, 4.2.
 */
export function sanitizeUpstreamError(raw: string): string {
  if (typeof raw !== "string") {
    return GENERIC_ERROR_MESSAGE;
  }

  const normalized = normalizeWhitespace(raw);
  if (!normalized) {
    return GENERIC_ERROR_MESSAGE;
  }

  if (looksLikeTimeout(normalized)) {
    return TIMEOUT_RETRY_MESSAGE;
  }

  if (normalized.length > MAX_SAFE_MESSAGE_LENGTH) {
    return GENERIC_ERROR_MESSAGE;
  }

  if (containsTechnicalContent(normalized)) {
    return GENERIC_ERROR_MESSAGE;
  }

  return normalized;
}

/**
 * Remove internal telemetry labels (`research mode`, `retrieval`, `RAG mode`,
 * `Fallback mode`, `Policy: Warn`, `Policy: Allow`) from any user-facing
 * string, case-insensitively. The labels are stripped repeatedly until the
 * string is stable so that overlapping or adjacent labels cannot leave a
 * residual match, then surrounding whitespace and orphaned separators are
 * tidied up.
 *
 * Requirement 4.1.
 */
export function stripTelemetryLabels(text: string): string {
  if (typeof text !== "string" || !text) {
    return "";
  }

  let current = text;
  // Apply removals to a fixpoint (bounded) so adjacent labels can't survive.
  for (let pass = 0; pass < 8; pass += 1) {
    const next = TELEMETRY_LABEL_PATTERNS.reduce(
      (acc, pattern) => acc.replace(pattern, " "),
      current
    );
    if (next === current) {
      break;
    }
    current = next;
  }

  return current
    .replace(/\(\s*\)/g, " ") // drop emptied parentheses
    .replace(/\[\s*\]/g, " ") // drop emptied brackets
    .replace(/\s+([,.;:])/g, "$1") // pull punctuation back to the word
    .replace(/([•·|/–—-])\s*(?=[•·|/–—-]|$)/g, " ") // collapse orphaned separators
    .replace(/\s+/g, " ")
    .replace(/^[\s,.;:•·|/–—-]+/, "")
    .replace(/[\s,.;:•·|/–—-]+$/, "")
    .trim();
}

/**
 * Map an internal mode string to its Vietnamese End_User label.
 * Known modes map to `Nhanh` / `Tư duy` / `Pro` / `Tự chọn` / `Đầy đủ`;
 * unknown or empty input falls back to a safe neutral label so internal
 * mode strings never leak into the UI.
 *
 * Requirement 4.4.
 */
export function toModeLabel(internalMode: string): string {
  if (typeof internalMode !== "string") {
    return DEFAULT_MODE_LABEL;
  }
  const key = internalMode.trim().toLowerCase();
  return MODE_LABELS[key] ?? DEFAULT_MODE_LABEL;
}
