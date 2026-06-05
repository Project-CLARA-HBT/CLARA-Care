import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  AnalyticsClient,
  isPiiKey,
  pseudonymousId,
  stripPii,
  type AnalyticsConfig,
  type AnalyticsEvent,
  type AnalyticsProps,
  type AnalyticsTransport,
  type SessionUser
} from "@/lib/analytics";

/**
 * Feature: product-polish-analytics
 *  - Property 16 : Analytics transmission suppressed without consent (Req 9.3)
 *  - Property 17 : Analytics is a safe no-op without credentials (Req 9.5)
 *  - Property 18 : Users identified by an opaque pseudonymous id (Req 9.6)
 *  - Property 13 : Outward SDK payloads contain no PII (Req 9.4)
 */

/** A transport spy that records every identify/capture call. */
class RecordingTransport implements AnalyticsTransport {
  initCalls = 0;

  identified: string[] = [];

  captured: AnalyticsEvent[] = [];

  init(): void {
    this.initCalls += 1;
  }

  identify(distinctId: string): void {
    this.identified.push(distinctId);
  }

  capture(event: AnalyticsEvent): void {
    this.captured.push(event);
  }

  get totalTransmissions(): number {
    return this.identified.length + this.captured.length;
  }
}

const CONFIGURED: AnalyticsConfig = { provider: "posthog", key: "phc_test_key" };
const UNCONFIGURED: AnalyticsConfig = { provider: "none" };
const MISSING_CREDENTIALS: AnalyticsConfig = { provider: "posthog" };

const sampleEvent: AnalyticsEvent = {
  name: "chat_message_sent",
  props: { surface: "chat", mode: "fast" }
};

const sampleUser: SessionUser = {
  userId: 42,
  email: "patient@example.com",
  fullName: "Nguyen Van A"
};

describe("AnalyticsClient consent suppression (Feature: product-polish-analytics, Property 16)", () => {
  it("suppresses all transmission while consent is not granted", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: CONFIGURED, transport, consent: false });
    client.identify(sampleUser);
    client.capture(sampleEvent);
    client.track("research_started", { surface: "research" });
    expect(transport.totalTransmissions).toBe(0);
    expect(transport.initCalls).toBe(0);
  });

  it("transmits only after consent is granted", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: CONFIGURED, transport, consent: false });
    client.capture(sampleEvent);
    expect(transport.captured.length).toBe(0);

    client.setConsent(true);
    client.capture(sampleEvent);
    expect(transport.captured.length).toBe(1);
  });

  it("Property 16: configured-but-no-consent yields zero transmissions for any event stream", () => {
    const eventArb: fc.Arbitrary<AnalyticsEvent> = fc.record(
      {
        name: fc.constantFrom("chat_message_sent", "research_started", "careguard_ddi_checked"),
        props: fc.dictionary(fc.string(), fc.oneof(fc.string(), fc.integer(), fc.boolean()))
      },
      { requiredKeys: ["name"] }
    );

    fc.assert(
      fc.property(fc.array(eventArb, { maxLength: 12 }), (events) => {
        const transport = new RecordingTransport();
        const client = new AnalyticsClient({ config: CONFIGURED, transport, consent: false });
        for (const event of events) {
          client.capture(event);
          client.identify(sampleUser);
        }
        return transport.totalTransmissions === 0;
      }),
      { numRuns: 200 }
    );
  });
});

describe("AnalyticsClient safe no-op without credentials (Feature: product-polish-analytics, Property 17)", () => {
  it("never transmits and never throws when unconfigured, even with consent granted", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: UNCONFIGURED, transport, consent: true });
    expect(() => {
      client.init();
      client.identify(sampleUser);
      client.capture(sampleEvent);
      client.track("anything", { a: 1 });
    }).not.toThrow();
    expect(transport.totalTransmissions).toBe(0);
    expect(client.configured).toBe(false);
  });

  it("treats a provider with no key as unconfigured", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: MISSING_CREDENTIALS, transport, consent: true });
    client.capture(sampleEvent);
    expect(transport.totalTransmissions).toBe(0);
    expect(client.configured).toBe(false);
  });

  it("Property 17: unconfigured client is a safe no-op for any event stream and consent state", () => {
    const eventArb: fc.Arbitrary<AnalyticsEvent> = fc.record(
      {
        name: fc.string({ minLength: 1 }),
        props: fc.dictionary(fc.string(), fc.oneof(fc.string(), fc.integer(), fc.boolean()))
      },
      { requiredKeys: ["name"] }
    );

    fc.assert(
      fc.property(fc.array(eventArb, { maxLength: 10 }), fc.boolean(), (events, consent) => {
        const transport = new RecordingTransport();
        const client = new AnalyticsClient({ config: UNCONFIGURED, transport, consent });
        let threw = false;
        try {
          for (const event of events) {
            client.capture(event);
            client.identify(sampleUser);
          }
        } catch {
          threw = true;
        }
        return !threw && transport.totalTransmissions === 0;
      }),
      { numRuns: 200 }
    );
  });
});

describe("pseudonymousId (Feature: product-polish-analytics, Property 18)", () => {
  it("is deterministic for the same user and opaque (no email/name)", () => {
    const id1 = pseudonymousId(sampleUser);
    const id2 = pseudonymousId({ userId: 42, email: "different@x.com", fullName: "Other Name" });
    expect(id1).toBe(id2); // determined by stable user id only
    expect(id1).not.toContain("patient@example.com");
    expect(id1).not.toContain("Nguyen Van A");
  });

  it("Property 18: id never equals or contains the email or name, and is deterministic per user", () => {
    const userArb: fc.Arbitrary<SessionUser> = fc.record({
      userId: fc.oneof(fc.integer({ min: 1, max: 1_000_000 }), fc.uuid()),
      email: fc.emailAddress(),
      // Names must contain at least one non-hex character so the substring-
      // containment assertion below is meaningful. A pseudonymous id is
      // `anon_` + a lowercase hex digest, so any string consisting only of
      // [0-9a-f] (e.g. a single-letter "a") can appear in the digest by
      // coincidence without representing a real PII leak.
      fullName: fc.string({ minLength: 1, maxLength: 40 }).filter((value) => /[g-z]/i.test(value))
    });

    fc.assert(
      fc.property(userArb, (user) => {
        const id = pseudonymousId(user);
        const idLower = id.toLowerCase();

        // Opaque: never equals or contains the email or name. For very short
        // strings (< 3 chars), substring coincidence in a 69-char hex id is
        // statistically inevitable and doesn't constitute a PII leak, so we
        // only assert non-containment for names/emails >= 3 chars.
        const emailLower = (user.email ?? "").toLowerCase();
        const nameLower = (user.fullName ?? "").toLowerCase();
        const opaque =
          id !== user.email &&
          id !== user.fullName &&
          (emailLower.length < 3 || !idLower.includes(emailLower)) &&
          (nameLower.length < 3 || !idLower.includes(nameLower));

        // Deterministic: re-deriving from the SAME stable id (ignoring PII fields)
        // yields the identical pseudonymous id.
        const reDerived = pseudonymousId({ userId: user.userId });
        const deterministic = pseudonymousId(user) === id && reDerived === id;

        return opaque && deterministic;
      }),
      { numRuns: 300 }
    );
  });

  it("Property 18: different stable user ids produce different pseudonymous ids", () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5000 }),
        fc.integer({ min: 5001, max: 10000 }),
        (a, b) => {
          return pseudonymousId({ userId: a }) !== pseudonymousId({ userId: b });
        }
      ),
      { numRuns: 200 }
    );
  });
});

describe("stripPii (Feature: product-polish-analytics, Property 13 / SDK)", () => {
  const PII_KEYS = [
    "name",
    "fullName",
    "email",
    "patient_email",
    "query",
    "search_query",
    "free_text_query",
    "drug",
    "drugs",
    "drug_list",
    "medications",
    "symptoms",
    "allergies",
    "prompt",
    "message"
  ];

  it("identifies known PII keys", () => {
    for (const key of PII_KEYS) {
      expect(isPiiKey(key)).toBe(true);
    }
  });

  it("keeps coarse, non-identifying keys", () => {
    for (const key of ["surface", "mode", "transport", "risk_level", "alert_count", "count"]) {
      expect(isPiiKey(key)).toBe(false);
    }
  });

  it("removes PII keys at the top level and preserves safe keys", () => {
    const event: AnalyticsEvent = {
      name: "careguard_ddi_checked",
      props: {
        surface: "careguard",
        risk_level: "medium",
        email: "patient@example.com",
        drug_list: ["aspirin", "warfarin"],
        query: "tôi bị đau đầu"
      }
    };
    const stripped = stripPii(event);
    expect(stripped.name).toBe("careguard_ddi_checked");
    expect(stripped.props).toEqual({ surface: "careguard", risk_level: "medium" });
  });

  it("Property 13: no PII key survives stripPii, recursively through nested objects/arrays", () => {
    const piiKeyArb = fc.constantFrom(...PII_KEYS);
    const safeKeyArb = fc.constantFrom("surface", "mode", "count", "risk_level", "transport");
    const valueArb = fc.oneof(fc.string(), fc.integer(), fc.boolean());

    const nestedProps: fc.Arbitrary<AnalyticsProps> = fc.dictionary(
      fc.oneof(piiKeyArb, safeKeyArb),
      fc.oneof(
        valueArb,
        fc.array(valueArb, { maxLength: 3 }),
        fc.dictionary(fc.oneof(piiKeyArb, safeKeyArb), valueArb, { maxKeys: 4 })
      ),
      { maxKeys: 8 }
    );

    function hasPiiKey(value: unknown): boolean {
      if (Array.isArray(value)) {
        return value.some((item) => hasPiiKey(item));
      }
      if (value && typeof value === "object") {
        return Object.entries(value as Record<string, unknown>).some(
          ([key, child]) => isPiiKey(key) || hasPiiKey(child)
        );
      }
      return false;
    }

    fc.assert(
      fc.property(fc.string({ minLength: 1 }), nestedProps, (name, props) => {
        const stripped = stripPii({ name, props });
        return !hasPiiKey(stripped.props ?? {});
      }),
      { numRuns: 300 }
    );
  });

  it("Property 13: capture transmits a PII-free payload through the transport", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: CONFIGURED, transport, consent: true });
    client.capture({
      name: "careguard_ddi_checked",
      props: { surface: "careguard", email: "x@y.com", drugs: ["aspirin"] }
    });
    expect(transport.captured).toHaveLength(1);
    const props = transport.captured[0].props ?? {};
    expect(Object.keys(props)).not.toContain("email");
    expect(Object.keys(props)).not.toContain("drugs");
    expect(props.surface).toBe("careguard");
  });

  it("Property 18 + 13: identify transmits only the opaque pseudonymous id", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({ config: CONFIGURED, transport, consent: true });
    client.identify(sampleUser);
    expect(transport.identified).toHaveLength(1);
    const id = transport.identified[0];
    expect(id).toBe(pseudonymousId(sampleUser));
    expect(id).not.toContain("patient@example.com");
    expect(id).not.toContain("Nguyen Van A");
  });
});
