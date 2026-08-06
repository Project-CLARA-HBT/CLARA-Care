import { describe, expect, it } from "vitest";
import { shouldRetryCsrfFailure } from "./http-client";

describe("CSRF recovery guard", () => {
  const csrfError = { response: { status: 403, data: { detail: "CSRF validation failed" } } };

  it("retries only one unsafe request rejected by the CSRF guard", () => {
    expect(shouldRetryCsrfFailure(csrfError, { method: "post" }, false)).toBe(true);
  });

  it("does not retry reads, bypass auth routes, a second attempt, or other 403 responses", () => {
    expect(shouldRetryCsrfFailure(csrfError, { method: "get" }, false)).toBe(false);
    expect(shouldRetryCsrfFailure(csrfError, { method: "post" }, true)).toBe(false);
    expect(shouldRetryCsrfFailure(csrfError, { method: "post", _csrfRetry: true }, false)).toBe(false);
    expect(shouldRetryCsrfFailure({ response: { status: 403, data: { detail: "Forbidden" } } }, { method: "post" }, false)).toBe(false);
  });
});
