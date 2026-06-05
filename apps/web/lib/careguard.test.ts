import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  DDI_RISK_GROUP_LOCALIZATION,
  MINIMUM_DDI_MEDICINES,
  classifyDdiRiskGroup,
  localizeDdiMessage,
  requiresTwoMedicines,
  toDdiUserView,
  type CareguardAnalyzeRawResponse,
  type DdiRiskGroup
} from "@/lib/careguard";

/**
 * Feature: product-polish-analytics
 *  - Property 5 : DDI end-user projection excludes telemetry (Req 3.1)
 *  - Property 9 : Connector errors hidden while a valid signal remains (Req 3.6)
 *  - Property 8 : DDI checks require at least two medicines (Req 3.5)
 *  - Risk-group localization: VN message + recommendation per group (Req 3.4)
 */

// Keys that belong to the raw payload but must NEVER appear on the projection.
const FORBIDDEN_VIEW_KEYS = ["mode", "fallback", "fallbackUsed", "source_errors", "sourceErrors"];

// Connector-identifier / technical fragments that must never reach the view.
const CONNECTOR_FRAGMENTS = ["openfda", "rxnav", "dailymed", "http_", "status=", "source_errors"];

function viewJsonContainsConnectorLeak(view: unknown): boolean {
  const json = JSON.stringify(view).toLowerCase();
  return CONNECTOR_FRAGMENTS.some((fragment) => json.includes(fragment));
}

describe("toDdiUserView (Feature: product-polish-analytics, Property 5)", () => {
  it("exposes exactly the four user-facing keys and nothing else", () => {
    const raw: CareguardAnalyzeRawResponse = {
      risk: "moderate",
      ddi_alerts: [{ title: "Phối hợp này có thể làm tăng nguy cơ chảy máu." }],
      recommendations: ["Hỏi bác sĩ hoặc dược sĩ."],
      mode: "external_plus_local",
      fallback_used: true,
      source_errors: { openfda: ["openfda http_400"] }
    };
    const view = toDdiUserView(raw);
    expect(Object.keys(view).sort()).toEqual(
      ["alerts", "recommendations", "riskLevel", "sources"].sort()
    );
  });

  it("Property 5: projection never carries mode/fallback/source_errors keys", () => {
    const riskArb = fc.constantFrom("low", "medium", "moderate", "high", "critical", "minor");
    const rawArb: fc.Arbitrary<CareguardAnalyzeRawResponse> = fc.record(
      {
        risk: riskArb,
        ddi_alerts: fc.array(
          fc.record(
            {
              title: fc.constantFrom(
                "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
                "Dùng cùng nhau có thể làm tăng buồn ngủ, chóng mặt.",
                "Phối hợp này có thể làm tăng kali máu."
              ),
              severity: fc.constantFrom("low", "medium", "high", "critical")
            },
            { requiredKeys: ["title"] }
          ),
          { maxLength: 4 }
        ),
        recommendations: fc.array(fc.constantFrom("Hỏi bác sĩ.", "Theo dõi triệu chứng."), {
          maxLength: 3
        }),
        mode: fc.constantFrom("local_only", "external_plus_local", null),
        fallback_used: fc.boolean(),
        source_errors: fc.dictionary(
          fc.constantFrom("openfda", "rxnav", "dailymed"),
          fc.array(fc.constantFrom("openfda http_400", "rxnav status=503"), { maxLength: 2 })
        )
      },
      { requiredKeys: ["risk", "ddi_alerts"] }
    );

    fc.assert(
      fc.property(rawArb, (raw) => {
        const view = toDdiUserView(raw);
        const keys = Object.keys(view);
        return !FORBIDDEN_VIEW_KEYS.some((forbidden) => keys.includes(forbidden));
      }),
      { numRuns: 200 }
    );
  });

  it("Property 5: every alert message is Vietnamese-localized, never English passthrough", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.constantFrom(
            "increased bleeding risk",
            "reduced clopidogrel efficacy",
            "sedation and drowsiness",
            "hyperkalemia risk",
            "myopathy / rhabdomyolysis"
          ),
          { minLength: 1, maxLength: 5 }
        ),
        (titles) => {
          const raw: CareguardAnalyzeRawResponse = {
            risk: "medium",
            ddi_alerts: titles.map((title) => ({ title }))
          };
          const view = toDdiUserView(raw);
          // Vietnamese diacritic must be present in each projected alert message.
          return view.alerts.every((alert) => /[\u00C0-\u1EF9]/.test(alert.message));
        }
      ),
      { numRuns: 200 }
    );
  });
});

describe("toDdiUserView connector suppression (Feature: product-polish-analytics, Property 9)", () => {
  it("hides openfda http_400 while a valid local alert remains", () => {
    const raw: CareguardAnalyzeRawResponse = {
      risk: "medium",
      ddi_alerts: [{ title: "Phối hợp này có thể làm tăng nguy cơ chảy máu.", severity: "medium" }],
      source_errors: { openfda: ["openfda http_400"] },
      attribution: {
        sources: [{ id: "local", name: "local" }],
        citations: []
      }
    };
    const view = toDdiUserView(raw);
    expect(view.alerts.length).toBeGreaterThan(0);
    expect(viewJsonContainsConnectorLeak(view)).toBe(false);
  });

  it("Property 9: connector errors never appear in the view when a valid signal exists", () => {
    const connectorErrorArb = fc.dictionary(
      fc.constantFrom("openfda", "rxnav", "dailymed"),
      fc.array(
        fc.constantFrom("openfda http_400", "rxnav status=503", "dailymed timeout http_504"),
        { minLength: 1, maxLength: 3 }
      ),
      { minKeys: 1 }
    );

    fc.assert(
      fc.property(
        connectorErrorArb,
        fc.array(
          fc.constantFrom(
            "Phối hợp này có thể làm tăng nguy cơ chảy máu.",
            "Phối hợp này có thể làm tăng kali máu.",
            "Dùng cùng nhau có thể làm tăng buồn ngủ, chóng mặt."
          ),
          { minLength: 1, maxLength: 4 }
        ),
        (sourceErrors, alertTitles) => {
          const raw: CareguardAnalyzeRawResponse = {
            risk: "medium",
            ddi_alerts: alertTitles.map((title) => ({ title, severity: "medium" })),
            source_errors: sourceErrors
          };
          const view = toDdiUserView(raw);
          // A valid signal (at least one alert) remains, so no connector leak.
          return view.alerts.length > 0 && !viewJsonContainsConnectorLeak(view);
        }
      ),
      { numRuns: 200 }
    );
  });

  it("Property 9: technical connector titles are filtered out of the alert list", () => {
    const raw: CareguardAnalyzeRawResponse = {
      risk: "low",
      // A valid alert plus a leaked connector-error pseudo-alert.
      ddi_alerts: [
        { title: "Phối hợp này có thể làm tăng nguy cơ chảy máu." },
        { title: "openfda http_400 source_errors" }
      ]
    };
    const view = toDdiUserView(raw);
    expect(viewJsonContainsConnectorLeak(view)).toBe(false);
  });
});

describe("requiresTwoMedicines (Feature: product-polish-analytics, Property 8)", () => {
  it("requires at least two distinct medicines", () => {
    expect(MINIMUM_DDI_MEDICINES).toBe(2);
    expect(requiresTwoMedicines([])).toBe(true);
    expect(requiresTwoMedicines(["aspirin"])).toBe(true);
    expect(requiresTwoMedicines(["aspirin", "warfarin"])).toBe(false);
  });

  it("treats case-insensitive duplicates and blanks as a single distinct medicine", () => {
    expect(requiresTwoMedicines(["Aspirin", "aspirin", "  ASPIRIN "])).toBe(true);
    expect(requiresTwoMedicines(["aspirin", "", "   "])).toBe(true);
  });

  it("Property 8: fewer than two distinct medicines => prompt (true), >= two => proceed (false)", () => {
    const medicineArb = fc.constantFrom(
      "aspirin",
      "warfarin",
      "clopidogrel",
      "ibuprofen",
      "simvastatin",
      "lisinopril"
    );
    fc.assert(
      fc.property(fc.array(medicineArb, { maxLength: 8 }), (medicines) => {
        const distinct = new Set(
          medicines.map((m) => m.trim().toLowerCase()).filter(Boolean)
        ).size;
        const expected = distinct < 2;
        return requiresTwoMedicines(medicines) === expected;
      }),
      { numRuns: 300 }
    );
  });

  it("Property 8: blank-only or null-ish lists always require more medicines", () => {
    fc.assert(
      fc.property(fc.array(fc.constantFrom("", " ", "\t", "\n"), { maxLength: 6 }), (blanks) => {
        return requiresTwoMedicines(blanks) === true;
      }),
      { numRuns: 100 }
    );
    expect(requiresTwoMedicines(null)).toBe(true);
    expect(requiresTwoMedicines(undefined)).toBe(true);
  });
});

describe("DDI risk-group localization (Feature: product-polish-analytics, Req 3.4)", () => {
  const RISK_GROUPS: DdiRiskGroup[] = [
    "bleeding",
    "reducedClopidogrelEfficacy",
    "drowsinessOrDizziness",
    "hyperkalemia",
    "myopathy"
  ];

  // Representative English passthrough markers per group.
  const GROUP_MARKERS: Record<DdiRiskGroup, string[]> = {
    bleeding: ["increased bleeding risk", "GI bleeding", "hemorrhage"],
    reducedClopidogrelEfficacy: ["reduced clopidogrel efficacy", "antiplatelet CYP2C19"],
    drowsinessOrDizziness: ["sedation and drowsiness", "dizziness CNS depression"],
    hyperkalemia: ["hyperkalemia risk", "potassium-sparing"],
    myopathy: ["myopathy", "rhabdomyolysis muscle pain"]
  };

  it("provides a Vietnamese message AND recommendation for each common risk group", () => {
    for (const group of RISK_GROUPS) {
      const copy = DDI_RISK_GROUP_LOCALIZATION[group];
      expect(copy.message.length).toBeGreaterThan(0);
      expect(copy.recommendation.length).toBeGreaterThan(0);
      // Both strings must be Vietnamese (carry diacritics).
      expect(/[\u00C0-\u1EF9]/.test(copy.message)).toBe(true);
      expect(/[\u00C0-\u1EF9]/.test(copy.recommendation)).toBe(true);
    }
  });

  it("classifies each group's English markers to the correct group", () => {
    for (const group of RISK_GROUPS) {
      for (const marker of GROUP_MARKERS[group]) {
        expect(classifyDdiRiskGroup(marker)).toBe(group);
      }
    }
  });

  it("localizes each group's English passthrough to that group's Vietnamese message", () => {
    for (const group of RISK_GROUPS) {
      for (const marker of GROUP_MARKERS[group]) {
        expect(localizeDdiMessage(marker)).toBe(DDI_RISK_GROUP_LOCALIZATION[group].message);
      }
    }
  });

  it("Req 3.4: any recognized marker localizes to Vietnamese (never English passthrough)", () => {
    const allMarkers = RISK_GROUPS.flatMap((g) => GROUP_MARKERS[g]);
    fc.assert(
      fc.property(fc.constantFrom(...allMarkers), (marker) => {
        const localized = localizeDdiMessage(marker);
        return /[\u00C0-\u1EF9]/.test(localized);
      }),
      { numRuns: 200 }
    );
  });
});
