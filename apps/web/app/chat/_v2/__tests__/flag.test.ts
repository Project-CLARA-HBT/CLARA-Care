import { afterEach, describe, expect, it, vi } from "vitest";
import fc from "fast-check";

import { parseChatV2Flag, isChatV2Enabled } from "@/app/chat/_v2/flag";

/**
 * Feature: clara-chat-redesign, Property P1 (flag isolation).
 *
 * As of the production rollout (task 8.3) the redesign is the DEFAULT: the flag
 * resolves to ON unless `NEXT_PUBLIC_CHAT_V2` is explicitly set to an opt-out
 * value (`0`/`false`/`off`, case-insensitive), which restores the legacy page
 * for instant rollback (Requirement 8.1, 8.6).
 */

const OPT_OUT_VALUES = new Set(["0", "false", "off"]);

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("parseChatV2Flag", () => {
  it("treats explicit opt-in values as enabled", () => {
    for (const value of ["1", "true", "on", "TRUE", "On", " 1 ", "TrUe"]) {
      expect(parseChatV2Flag(value)).toBe(true);
    }
  });

  it("defaults to ON for unset / empty / unrelated values", () => {
    for (const value of [undefined, null, "", "yes", "legacy", "2"]) {
      expect(parseChatV2Flag(value)).toBe(true);
    }
  });

  it("resolves to OFF (legacy) only for explicit opt-out values", () => {
    for (const value of ["0", "false", "off", "OFF", "False", " off "]) {
      expect(parseChatV2Flag(value)).toBe(false);
    }
  });

  it("Property P1: only an explicit opt-out string resolves to legacy (OFF)", () => {
    fc.assert(
      fc.property(fc.string(), (raw) => {
        const expected = !OPT_OUT_VALUES.has(raw.trim().toLowerCase());
        return parseChatV2Flag(raw) === expected;
      }),
      { numRuns: 300 }
    );
  });
});

describe("isChatV2Enabled", () => {
  it("is ON by default (no env set)", () => {
    vi.stubEnv("NEXT_PUBLIC_CHAT_V2", "");
    expect(isChatV2Enabled()).toBe(true);
  });

  it("is OFF only when the env var is an explicit opt-out (rollback)", () => {
    vi.stubEnv("NEXT_PUBLIC_CHAT_V2", "false");
    expect(isChatV2Enabled()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_CHAT_V2", "nope");
    expect(isChatV2Enabled()).toBe(true);
  });
});
