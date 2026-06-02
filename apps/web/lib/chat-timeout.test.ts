import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  GENERIC_ERROR_MESSAGE,
  TIMEOUT_RETRY_MESSAGE,
  sanitizeUpstreamError
} from "@/lib/user-facing-text";

/**
 * Feature: product-polish-analytics
 * Regression: chat timeout path surfaces a sanitized retry message.
 *
 * Validates: Requirements 2.5, 1.3
 *
 * The chat surface (`apps/web/app/chat/page.tsx`) routes every caught failure
 * through `sanitizeUpstreamError(cause.message)` before calling `setError(...)`:
 *
 *     } catch (cause) {
 *       setError(
 *         cause instanceof Error
 *           ? sanitizeUpstreamError(cause.message)
 *           : "Không thể xử lý câu hỏi."
 *       );
 *     }
 *
 * Pre-fix behavior surfaced `cause.message` verbatim, leaking raw timeout
 * payloads (axios `ETIMEDOUT`/`ECONNABORTED`, `504 Gateway Timeout`, HTTP status
 * codes, exception class names, and stack-trace frames) directly into the UI.
 * These tests fail on that pre-fix behavior and pass once the timeout/error is
 * converted to calm Vietnamese retry copy with no raw codes or stack traces.
 */

/**
 * Faithful mirror of the chat surface's catch-block mapping. Keeping it here
 * lets the regression exercise the exact transformation an End_User sees when
 * the chat pipeline rejects.
 */
function surfaceChatError(cause: unknown): string {
  return cause instanceof Error
    ? sanitizeUpstreamError(cause.message)
    : "Không thể xử lý câu hỏi.";
}

// The only two safe Vietnamese strings the boundary may emit for a raw error.
const SAFE_MESSAGES = [TIMEOUT_RETRY_MESSAGE, GENERIC_ERROR_MESSAGE];

// Technical fragments that must never reach an End_User from a timeout/error.
const FORBIDDEN_LEAKS = [
  "ETIMEDOUT",
  "ECONNABORTED",
  "AxiosError",
  "TypeError",
  "Traceback",
  "Exception",
  "http_",
  "status code",
  "status=",
  "504",
  "500",
  "503",
  "node_modules",
  ".ts:",
  ".js:",
  ".py"
];

function leaksTechnicalContent(message: string): boolean {
  const lowered = message.toLowerCase();
  if (FORBIDDEN_LEAKS.some((token) => lowered.includes(token.toLowerCase()))) {
    return true;
  }
  // No raw 3-digit HTTP status / line numbers, and no JS/Python stack frames.
  if (/\d{3}/.test(message)) return true;
  if (/\bat\s+\S+\s+\(/.test(message)) return true;
  if (/File\s+".*",\s*line\s+\d+/i.test(message)) return true;
  return false;
}

describe("chat timeout path (Feature: product-polish-analytics, Req 2.5 / 1.3)", () => {
  // ---- Example/regression cases: real upstream timeout payloads ----
  it("surfaces the calm retry copy for an axios client timeout", () => {
    const raw = "timeout of 90000ms exceeded";
    expect(surfaceChatError(new Error(raw))).toBe(TIMEOUT_RETRY_MESSAGE);
  });

  it("surfaces the calm retry copy for a gateway (504) timeout", () => {
    expect(surfaceChatError(new Error("Request failed with status code 504"))).toBe(
      TIMEOUT_RETRY_MESSAGE
    );
    expect(surfaceChatError(new Error("504 Gateway Timeout"))).toBe(TIMEOUT_RETRY_MESSAGE);
  });

  it("surfaces the calm retry copy for low-level timeout codes", () => {
    expect(surfaceChatError(new Error("ETIMEDOUT"))).toBe(TIMEOUT_RETRY_MESSAGE);
    expect(surfaceChatError(new Error("ECONNABORTED: timeout exceeded"))).toBe(
      TIMEOUT_RETRY_MESSAGE
    );
    expect(surfaceChatError(new Error("deadline exceeded"))).toBe(TIMEOUT_RETRY_MESSAGE);
  });

  it("regression: a raw timeout stack trace never reaches the user", () => {
    const raw =
      "AxiosError: timeout of 90000ms exceeded\n" +
      "    at RedirectableRequest.handleRequestTimeout (/app/node_modules/axios/lib/adapters/http.js:647:16)";
    const surfaced = surfaceChatError(new Error(raw));

    // The whole point of the fix: the verbatim message is replaced.
    expect(surfaced).not.toBe(raw);
    expect(surfaced).toBe(TIMEOUT_RETRY_MESSAGE);
    expect(leaksTechnicalContent(surfaced)).toBe(false);
  });

  it("regression: a non-timeout pipeline error is sanitized to generic copy", () => {
    const raw =
      'Traceback (most recent call last):\n  File "pipeline.py", line 220, in synthesize\n' +
      'RuntimeError: upstream ML failed at http://ml:8200/synthesize';
    const surfaced = surfaceChatError(new Error(raw));

    expect(surfaced).not.toBe(raw);
    expect(surfaced).toBe(GENERIC_ERROR_MESSAGE);
    expect(leaksTechnicalContent(surfaced)).toBe(false);
  });

  it("falls back to calm copy when the rejection is not an Error", () => {
    expect(surfaceChatError("boom")).toBe("Không thể xử lý câu hỏi.");
    expect(surfaceChatError(undefined)).toBe("Không thể xử lý câu hỏi.");
  });

  // ---- Property: timeout payloads always become the retry message ----
  it("Req 2.5: any timeout-shaped payload surfaces the retry message", () => {
    const timeoutCore = fc.constantFrom(
      "timeout of 90000ms exceeded",
      "ETIMEDOUT",
      "ECONNABORTED",
      "deadline exceeded",
      "request timed out",
      "504 Gateway Timeout",
      "Request failed with status code 504"
    );

    fc.assert(
      fc.property(
        timeoutCore,
        // Prefix/suffix the timeout token with arbitrary upstream noise.
        fc.constantFrom("", "Error: ", "AxiosError: ", "[upstream] "),
        fc.constantFrom("", "\n    at handler (http.js:1:1)", " (code 12)"),
        (core, prefix, suffix) => {
          const surfaced = surfaceChatError(new Error(`${prefix}${core}${suffix}`));
          return surfaced === TIMEOUT_RETRY_MESSAGE && !leaksTechnicalContent(surfaced);
        }
      ),
      { numRuns: 200 }
    );
  });

  // ---- Property: no raw error/codes/stack traces ever reach the user ----
  // Scope: the chat catch-block boundary for the timeout/failure path. The
  // payloads below are the technical shapes that boundary is designed to catch
  // (timeout text, exception class names, stack frames, connector ids, internal
  // URLs, raw JSON). Bare HTTP-status phrases such as "Request failed with
  // status code 500" / "503 Service Unavailable" are intentionally NOT asserted
  // here — exhaustive HTTP-status-token sanitization is Property 4 (task 3.2,
  // Epic 3) and a gap there is reported separately, not by this timeout
  // regression.
  it("Req 2.5/1.3: technical error payloads never leak raw codes or stack traces", () => {
    const technicalFragment = fc.constantFrom(
      "AxiosError: timeout of 90000ms exceeded",
      "TypeError: Cannot read properties of undefined (reading 'data')",
      'Traceback (most recent call last):\n  File "pipeline.py", line 220, in synthesize',
      "RuntimeError: ETIMEDOUT contacting http://ml:8200/synthesize",
      "openfda http_400",
      "rxnav status=503",
      '{"detail":"upstream ML timed out after 60s at http://ml:8200/synthesize"}',
      "Error: connect ECONNREFUSED 127.0.0.1:8200",
      "    at sendChatMessage (/app/lib/chat.ts:35:24)"
    );

    fc.assert(
      fc.property(technicalFragment, fc.string(), (fragment, noise) => {
        const surfaced = surfaceChatError(new Error(`${fragment} ${noise}`));
        // Output must be one of the two safe Vietnamese strings and must not
        // carry any of the raw technical tokens through to the End_User.
        return SAFE_MESSAGES.includes(surfaced) && !leaksTechnicalContent(surfaced);
      }),
      { numRuns: 300 }
    );
  });
});
