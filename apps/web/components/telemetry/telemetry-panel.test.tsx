import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  isTelemetryVisible,
  shouldShowTelemetry,
  telemetryVisibility,
} from "@/components/telemetry/telemetry-panel";
import type { UserRole } from "@/lib/auth-store";

/**
 * Feature: product-polish-analytics, Property 11
 * Telemetry panel visibility equals admin role.
 *
 * Validates: Requirements 4.3
 *
 * Detailed telemetry panels are visible if and only if the requesting role is
 * `admin`. The decision is payload-independent: for any role and any view
 * payload, `isTelemetryVisible(role)` returns `true` iff `role === "admin"`,
 * and the `telemetryVisibility(role, payload)` split (detailed vs summary) is a
 * pure function of the role alone.
 */

const ALL_ROLES: UserRole[] = ["normal", "researcher", "doctor", "admin"];
const NON_ADMIN_ROLES: UserRole[] = ["normal", "researcher", "doctor"];

// A generator for arbitrary view payloads — the visibility decision must not
// depend on any of these.
const arbitraryPayload = fc.oneof(
  fc.constant(undefined),
  fc.constant(null),
  fc.string(),
  fc.integer(),
  fc.boolean(),
  fc.array(fc.string()),
  fc.object(),
  fc.record({
    mode: fc.string(),
    fallback: fc.boolean(),
    source_errors: fc.array(fc.string()),
  })
);

describe("isTelemetryVisible (Feature: product-polish-analytics, Property 11)", () => {
  // ---- Unit/example tests: pin the exact mapping ----
  it("is true only for the admin role", () => {
    expect(isTelemetryVisible("admin")).toBe(true);
  });

  it("is false for every non-admin role", () => {
    for (const role of NON_ADMIN_ROLES) {
      expect(isTelemetryVisible(role)).toBe(false);
    }
  });

  it("exposes a backwards-compatible alias with identical behavior", () => {
    for (const role of ALL_ROLES) {
      expect(shouldShowTelemetry(role)).toBe(isTelemetryVisible(role));
    }
  });

  // ---- Property: visibility === (role is admin), for any role ----
  it("Property 11: detailed telemetry is visible iff role is admin", () => {
    fc.assert(
      fc.property(fc.constantFrom<UserRole>(...ALL_ROLES), (role) => {
        return isTelemetryVisible(role) === (role === "admin");
      }),
      { numRuns: 200 }
    );
  });

  // ---- Property: payload-independence ----
  it("Property 11: visibility is independent of the view payload", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<UserRole>(...ALL_ROLES),
        arbitraryPayload,
        (role, payload) => {
          const { showDetailed, showSummary } = telemetryVisibility(role, payload);
          // Detailed iff admin, regardless of payload.
          if (showDetailed !== (role === "admin")) {
            return false;
          }
          // Detailed and summary are mutually exclusive (exactly one is shown).
          return showDetailed !== showSummary;
        }
      ),
      { numRuns: 300 }
    );
  });

  it("Property 11: non-admin roles never see detailed telemetry for any payload", () => {
    fc.assert(
      fc.property(
        fc.constantFrom<UserRole>(...NON_ADMIN_ROLES),
        arbitraryPayload,
        (role, payload) => {
          return telemetryVisibility(role, payload).showDetailed === false;
        }
      ),
      { numRuns: 200 }
    );
  });

  it("Property 11: the admin role always sees detailed telemetry for any payload", () => {
    fc.assert(
      fc.property(arbitraryPayload, (payload) => {
        return telemetryVisibility("admin", payload).showDetailed === true;
      }),
      { numRuns: 200 }
    );
  });
});
