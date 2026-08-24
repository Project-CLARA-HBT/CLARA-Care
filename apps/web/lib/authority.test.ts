import { describe, expect, it } from "vitest";

import {
  type AuthorityState,
  type DataEnvelope,
  wrapAuthoritative,
  wrapKnownEmpty,
  wrapUnavailable,
} from "@/lib/authority";

describe("authority module", () => {
  describe("AuthorityState types", () => {
    it("supports all required state literals", () => {
      const states: AuthorityState[] = [
        "authoritative",
        "known_empty",
        "unavailable",
        "degraded",
        "stale",
      ];
      expect(states).toHaveLength(5);
    });
  });

  describe("wrapAuthoritative", () => {
    it("wraps data with authoritative state and sets ISO generatedAt", () => {
      const data = { id: "123", name: "Nguyen Van A" };
      const envelope = wrapAuthoritative(data);

      expect(envelope.state).toBe("authoritative");
      expect(envelope.data).toEqual(data);
      expect(envelope.error).toBeUndefined();
      expect(envelope.resourceVersion).toBeUndefined();
      expect(envelope.provenance).toBeUndefined();
      expect(Date.parse(envelope.generatedAt)).not.toBeNaN();
    });

    it("attaches resourceVersion when provided", () => {
      const data = [1, 2, 3];
      const envelope = wrapAuthoritative(data, "v1.2.0");

      expect(envelope.state).toBe("authoritative");
      expect(envelope.data).toEqual([1, 2, 3]);
      expect(envelope.resourceVersion).toBe("v1.2.0");
      expect(envelope.provenance).toBeUndefined();
    });

    it("attaches provenance when provided", () => {
      const data = "clinical-payload";
      const provenance = {
        source: "clara_api/phr",
        policyVersion: "2026.1",
        digest: "sha256-abc123",
      };
      const envelope = wrapAuthoritative(data, undefined, provenance);

      expect(envelope.state).toBe("authoritative");
      expect(envelope.data).toBe("clinical-payload");
      expect(envelope.resourceVersion).toBeUndefined();
      expect(envelope.provenance).toEqual(provenance);
    });

    it("attaches both resourceVersion and provenance when provided", () => {
      const data = { count: 42 };
      const provenance = { source: "clara_api/audit" };
      const envelope = wrapAuthoritative(data, "rv-99", provenance);

      expect(envelope.state).toBe("authoritative");
      expect(envelope.data).toEqual({ count: 42 });
      expect(envelope.resourceVersion).toBe("rv-99");
      expect(envelope.provenance).toEqual(provenance);
    });

    it("handles null or primitive values correctly", () => {
      const nullEnvelope: DataEnvelope<string | null> = wrapAuthoritative(null);
      expect(nullEnvelope.state).toBe("authoritative");
      expect(nullEnvelope.data).toBeNull();

      const numEnvelope = wrapAuthoritative(0);
      expect(numEnvelope.state).toBe("authoritative");
      expect(numEnvelope.data).toBe(0);

      const boolEnvelope = wrapAuthoritative(false);
      expect(boolEnvelope.state).toBe("authoritative");
      expect(boolEnvelope.data).toBe(false);
    });
  });

  describe("wrapKnownEmpty", () => {
    it("wraps empty value with known_empty state", () => {
      const envelope = wrapKnownEmpty([]);

      expect(envelope.state).toBe("known_empty");
      expect(envelope.data).toEqual([]);
      expect(envelope.error).toBeUndefined();
      expect(envelope.provenance).toBeUndefined();
      expect(Date.parse(envelope.generatedAt)).not.toBeNaN();
    });

    it("wraps null emptyValue with known_empty state", () => {
      const envelope = wrapKnownEmpty<null>(null);

      expect(envelope.state).toBe("known_empty");
      expect(envelope.data).toBeNull();
      expect(envelope.error).toBeUndefined();
    });

    it("attaches provenance when provided", () => {
      const provenance = {
        source: "clara_api/medications",
        policyVersion: "v2",
      };
      const envelope = wrapKnownEmpty([], provenance);

      expect(envelope.state).toBe("known_empty");
      expect(envelope.data).toEqual([]);
      expect(envelope.provenance).toEqual(provenance);
    });
  });

  describe("wrapUnavailable", () => {
    it("creates an unavailable envelope with message only", () => {
      const envelope = wrapUnavailable("Service unreachable");

      expect(envelope.state).toBe("unavailable");
      expect(envelope.data).toBeNull();
      expect(envelope.error).toEqual({
        message: "Service unreachable",
      });
      expect(envelope.error?.correlationId).toBeUndefined();
      expect(envelope.error?.statusCode).toBeUndefined();
      expect(Date.parse(envelope.generatedAt)).not.toBeNaN();
    });

    it("attaches correlationId when provided", () => {
      const envelope = wrapUnavailable("Unauthorized access", "req-12345");

      expect(envelope.state).toBe("unavailable");
      expect(envelope.data).toBeNull();
      expect(envelope.error).toEqual({
        message: "Unauthorized access",
        correlationId: "req-12345",
      });
      expect(envelope.error?.statusCode).toBeUndefined();
    });

    it("attaches statusCode when provided with undefined correlationId", () => {
      const envelope = wrapUnavailable("Not Found", undefined, 404);

      expect(envelope.state).toBe("unavailable");
      expect(envelope.data).toBeNull();
      expect(envelope.error).toEqual({
        message: "Not Found",
        statusCode: 404,
      });
      expect(envelope.error?.correlationId).toBeUndefined();
    });

    it("attaches both correlationId and statusCode when provided", () => {
      const envelope = wrapUnavailable<string[]>(
        "Internal server error",
        "corr-999",
        500
      );

      expect(envelope.state).toBe("unavailable");
      expect(envelope.data).toBeNull();
      expect(envelope.error).toEqual({
        message: "Internal server error",
        correlationId: "corr-999",
        statusCode: 500,
      });
    });
  });
});
