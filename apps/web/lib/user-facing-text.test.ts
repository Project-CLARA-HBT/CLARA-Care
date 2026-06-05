import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  GENERIC_ERROR_MESSAGE,
  TIMEOUT_RETRY_MESSAGE,
  sanitizeUpstreamError,
  stripTelemetryLabels,
  toModeLabel
} from "@/lib/user-facing-text";

/**
 * Feature: product-polish-analytics
 *  - Property 4  : User-facing error messages are sanitized (Req 2.5, 4.2)
 *  - Property 10 : Internal telemetry labels excluded from End_User views (Req 4.1)
 *  - Mode labels : Vietnamese mode-label mapping (Req 4.4)
 */

// Tokens that must never appear in a sanitized user-facing error string.
const STACK_TRACE_MARKERS = [
  "Traceback (most recent call last):",
  'at handler (server.js:42:13)',
  'File "app.py", line 88, in run'
];
const EXCEPTION_CLASS_NAMES = ["TypeError", "AxiosError", "ValueError", "RuntimeError"];
const HTTP_STATUS_TOKENS = ["status 500", "HTTP 404", "status_code=502", "http_400"];
const INTERNAL_URLS = ["http://api:8000/api/v1/chat", "https://internal.svc/health", "localhost:8100"];
const CONNECTOR_IDS = ["openfda http_400", "rxnav status=503", "dailymed timeout"];

const LEAKY_INPUTS = [
  ...STACK_TRACE_MARKERS,
  ...EXCEPTION_CLASS_NAMES,
  ...HTTP_STATUS_TOKENS,
  ...INTERNAL_URLS,
  ...CONNECTOR_IDS
];

const SANITIZED_OUTPUTS = new Set([GENERIC_ERROR_MESSAGE, TIMEOUT_RETRY_MESSAGE]);

// Lowercase fragments that must never survive in a sanitized error message.
const FORBIDDEN_FRAGMENTS = [
  "traceback",
  "exception",
  "error",
  "http",
  "status",
  "://",
  "localhost",
  "openfda",
  "rxnav",
  "dailymed",
  "{",
  "}"
];

function isCleanUserCopy(value: string): boolean {
  const lowered = value.toLowerCase();
  return !FORBIDDEN_FRAGMENTS.some((fragment) => lowered.includes(fragment));
}

describe("sanitizeUpstreamError (Feature: product-polish-analytics, Property 4)", () => {
  it("returns the calm generic copy for raw stack traces and exceptions", () => {
    for (const raw of [...STACK_TRACE_MARKERS, ...EXCEPTION_CLASS_NAMES]) {
      expect(sanitizeUpstreamError(raw)).toBe(GENERIC_ERROR_MESSAGE);
    }
  });

  it("hides internal URLs, connector ids, and HTTP status detail", () => {
    for (const raw of [...INTERNAL_URLS, ...CONNECTOR_IDS, ...HTTP_STATUS_TOKENS]) {
      const out = sanitizeUpstreamError(raw);
      expect(SANITIZED_OUTPUTS.has(out)).toBe(true);
    }
  });

  it("maps timeout-flavored errors to the retry copy", () => {
    for (const raw of ["Request timed out", "ETIMEDOUT", "deadline exceeded", "gateway 504"]) {
      expect(sanitizeUpstreamError(raw)).toBe(TIMEOUT_RETRY_MESSAGE);
    }
  });

  it("passes a clean short human-readable message through unchanged", () => {
    const clean = "Vui lòng thử lại sau giây lát.";
    expect(sanitizeUpstreamError(clean)).toBe(clean);
  });

  it("Property 4: any leaky payload yields a calm message free of technical content", () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...LEAKY_INPUTS),
        // Wrap the leaky token in arbitrary surrounding noise to mimic real
        // upstream error envelopes.
        fc.string(),
        fc.string(),
        (leak, prefix, suffix) => {
          const raw = `${prefix} ${leak} ${suffix}`;
          const out = sanitizeUpstreamError(raw);
          // The output must be one of the calm fallbacks, OR (if it happened to
          // be reduced to clean copy) it must contain no technical content.
          return SANITIZED_OUTPUTS.has(out) || isCleanUserCopy(out);
        }
      ),
      { numRuns: 300 }
    );
  });

  it("Property 4: output never contains stack frames, exception names, URLs or status tokens", () => {
    fc.assert(
      fc.property(fc.constantFrom(...LEAKY_INPUTS), (leak) => {
        const out = sanitizeUpstreamError(leak);
        return isCleanUserCopy(out);
      }),
      { numRuns: 200 }
    );
  });

  it("Property 4: non-string and empty input degrade to the generic message", () => {
    expect(sanitizeUpstreamError("")).toBe(GENERIC_ERROR_MESSAGE);
    expect(sanitizeUpstreamError("   ")).toBe(GENERIC_ERROR_MESSAGE);
    // @ts-expect-error exercising the runtime guard against non-string input
    expect(sanitizeUpstreamError(null)).toBe(GENERIC_ERROR_MESSAGE);
  });
});

const TELEMETRY_LABELS = [
  "research mode",
  "retrieval",
  "RAG mode",
  "Fallback mode",
  "Policy: Warn",
  "Policy: Allow",
  "Policy: Warn/Allow"
];

// Case/spacing variants that must also be stripped.
const TELEMETRY_VARIANTS = [
  "Research Mode",
  "RETRIEVAL",
  "rag mode",
  "fallback mode",
  "policy: warn / allow"
];

function containsTelemetryLabel(value: string): boolean {
  const lowered = value.toLowerCase();
  return [
    "research mode",
    "rag mode",
    "fallback mode",
    "retrieval",
    "policy: warn",
    "policy: allow"
  ].some((label) => lowered.includes(label));
}

describe("stripTelemetryLabels (Feature: product-polish-analytics, Property 10)", () => {
  it("removes each known telemetry label", () => {
    for (const label of [...TELEMETRY_LABELS, ...TELEMETRY_VARIANTS]) {
      expect(containsTelemetryLabel(stripTelemetryLabels(label))).toBe(false);
    }
  });

  it("preserves surrounding user-facing copy", () => {
    const out = stripTelemetryLabels("Kết quả (research mode) đã sẵn sàng");
    expect(out).toContain("Kết quả");
    expect(out).toContain("đã sẵn sàng");
    expect(containsTelemetryLabel(out)).toBe(false);
  });

  it("Property 10: no telemetry label survives in the output, even when embedded", () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...TELEMETRY_LABELS, ...TELEMETRY_VARIANTS), {
          minLength: 1,
          maxLength: 5
        }),
        // Interleave with benign words that contain none of the labels.
        fc.array(fc.constantFrom("kết quả", "báo cáo", "đã xong", "thông tin", "tóm tắt"), {
          maxLength: 5
        }),
        (labels, fillers) => {
          const parts: string[] = [];
          const max = Math.max(labels.length, fillers.length);
          for (let i = 0; i < max; i += 1) {
            if (fillers[i]) parts.push(fillers[i]);
            if (labels[i]) parts.push(labels[i]);
          }
          const text = parts.join(" ");
          return !containsTelemetryLabel(stripTelemetryLabels(text));
        }
      ),
      { numRuns: 300 }
    );
  });

  it("Property 10: adjacent/repeated labels are fully removed (fixpoint)", () => {
    fc.assert(
      fc.property(
        fc.array(fc.constantFrom(...TELEMETRY_LABELS), { minLength: 2, maxLength: 8 }),
        (labels) => {
          const text = labels.join(" ");
          return !containsTelemetryLabel(stripTelemetryLabels(text));
        }
      ),
      { numRuns: 200 }
    );
  });

  it("returns an empty string for empty/non-string input", () => {
    expect(stripTelemetryLabels("")).toBe("");
    // @ts-expect-error exercising the runtime guard
    expect(stripTelemetryLabels(undefined)).toBe("");
  });
});

describe("toModeLabel (Feature: product-polish-analytics, Req 4.4)", () => {
  const EXPECTED: Record<string, string> = {
    fast: "Nhanh",
    deep: "Tư duy",
    deep_beta: "Pro",
    auto: "Tự chọn",
    full: "Đầy đủ"
  };

  it("maps every internal mode to its Vietnamese End_User label", () => {
    for (const [mode, label] of Object.entries(EXPECTED)) {
      expect(toModeLabel(mode)).toBe(label);
    }
  });

  it("is case-insensitive and trims whitespace", () => {
    expect(toModeLabel("  FAST ")).toBe("Nhanh");
    expect(toModeLabel("Deep_Beta")).toBe("Pro");
  });

  it("falls back to a safe neutral label and never leaks raw mode strings", () => {
    const VIETNAMESE_LABELS = new Set(Object.values(EXPECTED));
    fc.assert(
      fc.property(fc.string(), (raw) => {
        const label = toModeLabel(raw);
        const key = raw.trim().toLowerCase();
        if (key in EXPECTED) {
          return label === EXPECTED[key];
        }
        // Unknown modes must resolve to a known Vietnamese label (never the raw input).
        return VIETNAMESE_LABELS.has(label);
      }),
      { numRuns: 300 }
    );
  });
});
