import { describe, expect, it } from "vitest";

import { SocialUnavailableError, isSocialModerationBlock } from "@/lib/social";

// CLARA Health Social platform web-client unit tests. These lock the two
// fail-safe classifiers the UI relies on: the feature-off signal and the
// moderation-block signal. Both must be precise so the surface degrades
// gracefully (feature off ⇒ hidden) and communicates moderation refusals
// clearly (blocked ⇒ edit-and-retry copy) without leaking internals.

describe("SocialUnavailableError", () => {
  it("is a named Error subclass", () => {
    const err = new SocialUnavailableError();
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("SocialUnavailableError");
  });
});

describe("isSocialModerationBlock", () => {
  it("is true for a 422 (moderation refusal / emergency escalation)", () => {
    expect(isSocialModerationBlock({ response: { status: 422 } })).toBe(true);
  });

  it("is false for other statuses", () => {
    expect(isSocialModerationBlock({ response: { status: 404 } })).toBe(false);
    expect(isSocialModerationBlock({ response: { status: 500 } })).toBe(false);
    expect(isSocialModerationBlock({ response: { status: 200 } })).toBe(false);
  });

  it("is false for a non-axios error shape", () => {
    expect(isSocialModerationBlock(new Error("boom"))).toBe(false);
    expect(isSocialModerationBlock(null)).toBe(false);
    expect(isSocialModerationBlock(undefined)).toBe(false);
    expect(isSocialModerationBlock("nope")).toBe(false);
  });
});
