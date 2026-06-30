import { describe, expect, it } from "vitest";

import {
  DEFAULT_PHR_CAPABILITIES,
  parsePhrCapabilities,
  parsePhrCompleteness,
  type PhrAllergyItem,
  type PhrConditionItem,
  type PhrMedicationItem,
} from "@/lib/phr";

/**
 * Feature: personal-health-record, Requirement 18.1 (flags-off legacy
 * equivalence) and Requirement 6.5 (web exposes coded/provenance fields).
 *
 * These tests pin the capability-gating defaults so the web client fails closed
 * to the legacy PHR view, and confirm the new coded/provenance fields are
 * optional (legacy entries still type-check without them).
 */

describe("parsePhrCapabilities (Requirement 18.1)", () => {
  it("defaults every capability to OFF for an empty payload", () => {
    expect(parsePhrCapabilities({})).toEqual(DEFAULT_PHR_CAPABILITIES);
  });

  it("fails closed for null / malformed payloads", () => {
    expect(parsePhrCapabilities(null)).toEqual(DEFAULT_PHR_CAPABILITIES);
    expect(parsePhrCapabilities(undefined)).toEqual(DEFAULT_PHR_CAPABILITIES);
    expect(parsePhrCapabilities("nope")).toEqual(DEFAULT_PHR_CAPABILITIES);
    expect(parsePhrCapabilities(42)).toEqual(DEFAULT_PHR_CAPABILITIES);
  });

  it("reads flags from the wrapped { flags: {...} } envelope", () => {
    const result = parsePhrCapabilities({
      flags: { enhanced: true, export: true, sharing: true },
    });
    expect(result.enhanced).toBe(true);
    expect(result.export).toBe(true);
    expect(result.sharing).toBe(true);
    expect(result.reminders).toBe(false);
  });

  it("also tolerates a bare flags object (no envelope)", () => {
    const result = parsePhrCapabilities({ enhanced: true, observations: true });
    expect(result.enhanced).toBe(true);
    expect(result.observations).toBe(true);
  });

  it("forces every sub-capability OFF when enhanced is off (master AND sub)", () => {
    const result = parsePhrCapabilities({
      flags: {
        enhanced: false,
        consent_enforcement: true,
        reconciliation: true,
        allergy_aware_ddi: true,
        ocr_import: true,
        observations: true,
        export: true,
        sharing: true,
        reminders: true,
        completeness_meter: true,
      },
    });
    expect(result).toEqual(DEFAULT_PHR_CAPABILITIES);
  });

  it("coerces non-boolean flag values to false", () => {
    const result = parsePhrCapabilities({
      flags: { enhanced: true, export: "true", sharing: 1, reminders: null },
    });
    expect(result.enhanced).toBe(true);
    expect(result.export).toBe(false);
    expect(result.sharing).toBe(false);
    expect(result.reminders).toBe(false);
  });

  it("never mutates the shared default object", () => {
    const result = parsePhrCapabilities({ flags: { enhanced: true, export: true } });
    expect(result).not.toBe(DEFAULT_PHR_CAPABILITIES);
    expect(DEFAULT_PHR_CAPABILITIES.export).toBe(false);
  });
});

describe("coded/provenance entry fields are optional (Requirement 6.5, 18.1)", () => {
  it("accepts a legacy allergy without coded fields", () => {
    const legacy: PhrAllergyItem = {
      id: "a1",
      name: "Penicillin",
      reaction: "rash",
      severity: "moderate",
      note: "",
    };
    expect(legacy.substance).toBeUndefined();
    expect(legacy.is_coded).toBeUndefined();
  });

  it("accepts a fully coded allergy", () => {
    const coded: PhrAllergyItem = {
      id: "a2",
      name: "Penicillin",
      reaction: "rash",
      severity: "severe",
      note: "",
      substance: "penicillin",
      coded_substance_id: "7980",
      is_coded: true,
      information_source: "self-declared",
      verification_status: "unconfirmed",
    };
    expect(coded.coded_substance_id).toBe("7980");
  });

  it("accepts a legacy and a coded condition", () => {
    const legacy: PhrConditionItem = {
      id: "c1",
      name: "Diabetes",
      status: "active",
      note: "",
    };
    const coded: PhrConditionItem = {
      ...legacy,
      id: "c2",
      icd10_code: "E11",
      snomed_code: "44054006",
      is_coded: true,
    };
    expect(legacy.icd10_code).toBeUndefined();
    expect(coded.icd10_code).toBe("E11");
  });

  it("accepts a legacy and a structured medication", () => {
    const legacy: PhrMedicationItem = {
      id: "m1",
      name: "Panadol",
      dose: "500mg",
      frequency: "2x/day",
      is_current: true,
      note: "",
    };
    const structured: PhrMedicationItem = {
      ...legacy,
      id: "m2",
      dose_amount: 500,
      dose_unit: "mg",
      route: "oral",
      normalized_name: "paracetamol",
      rx_cui: "161",
      normalization_source: "db",
      is_normalized: true,
      duplicate_of: null,
      ocr_confidence: null,
    };
    expect(legacy.rx_cui).toBeUndefined();
    expect(structured.rx_cui).toBe("161");
  });
});

describe("parsePhrCompleteness (Requirement 16.2)", () => {
  it("parses a well-formed payload, keeping score and class names", () => {
    const result = parsePhrCompleteness({
      score: 0.4286,
      present: ["patient_demographics", "allergies", "medications"],
      missing: ["problems", "immunizations", "procedures", "labs"],
      telemetry: { phr_completeness_score: 0.4286 },
    });
    expect(result.score).toBeCloseTo(0.4286);
    expect(result.present).toEqual([
      "patient_demographics",
      "allergies",
      "medications",
    ]);
    expect(result.missing).toEqual([
      "problems",
      "immunizations",
      "procedures",
      "labs",
    ]);
  });

  it("clamps the score to [0, 1] and defaults non-numeric scores to 0", () => {
    expect(parsePhrCompleteness({ score: 1.5 }).score).toBe(1);
    expect(parsePhrCompleteness({ score: -2 }).score).toBe(0);
    expect(parsePhrCompleteness({ score: "nope" }).score).toBe(0);
    expect(parsePhrCompleteness({ score: NaN }).score).toBe(0);
  });

  it("drops unknown class names and tolerates malformed payloads", () => {
    const result = parsePhrCompleteness({
      score: 0.1,
      present: ["allergies", "bogus", 42],
      missing: "not-an-array",
    });
    expect(result.present).toEqual(["allergies"]);
    expect(result.missing).toEqual([]);
  });

  it("fails safe for null / non-object payloads", () => {
    expect(parsePhrCompleteness(null)).toEqual({
      score: 0,
      present: [],
      missing: [],
    });
    expect(parsePhrCompleteness("x")).toEqual({
      score: 0,
      present: [],
      missing: [],
    });
  });
});
