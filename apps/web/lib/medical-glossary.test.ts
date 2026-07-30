import { describe, expect, it } from "vitest";
import {
  MEDICAL_GLOSSARY,
  MEDICAL_GLOSSARY_VERSION,
  getMedicalGlossaryText,
  resolveMedicalConcept,
} from "@/lib/medical-glossary";

describe("versioned medical glossary", () => {
  it("keeps every concept complete for both supported locales and audiences", () => {
    expect(MEDICAL_GLOSSARY_VERSION).toBe("2026-07-30.v1");
    for (const entry of Object.values(MEDICAL_GLOSSARY)) {
      expect(entry.aliases.length).toBeGreaterThan(0);
      expect(entry.do_not_simplify_to.length).toBeGreaterThan(0);
      for (const locale of ["vi", "en"] as const) {
        for (const audience of ["lay", "expanded", "professional"] as const) {
          const text = getMedicalGlossaryText(entry.id, locale, audience);
          expect(text?.label).toBeTruthy();
          expect(text?.description).toBeTruthy();
        }
      }
    }
  });

  it("resolves only whole, explicit aliases without inferring from free text", () => {
    expect(resolveMedicalConcept("tương tác thuốc")).toBe("medication_interaction");
    expect(resolveMedicalConcept("TUONG TAC THUOC")).toBe("medication_interaction");
    expect(resolveMedicalConcept("tôi có thể bị tương tác thuốc không?")).toBeNull();
    expect(resolveMedicalConcept("unknown clinical label")).toBeNull();
  });
});
