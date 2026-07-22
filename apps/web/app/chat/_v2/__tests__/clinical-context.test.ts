import { describe, expect, it } from "vitest";

import {
  buildContextualMedicalQuery,
  EMPTY_CLINICAL_CONTEXT,
} from "@/app/chat/_v2/lib/clinical-context";

describe("buildContextualMedicalQuery", () => {
  it("leaves a question unchanged when no structured context was supplied", () => {
    expect(
      buildContextualMedicalQuery(
        "  What should I do?  ",
        EMPTY_CLINICAL_CONTEXT,
        "normal",
        "en",
      ),
    ).toBe("What should I do?");
  });

  it("creates a visible no-inference medical context envelope for the existing API", () => {
    const result = buildContextualMedicalQuery(
      "Assess this symptom",
      {
        ...EMPTY_CLINICAL_CONTEXT,
        person: "42-year-old",
        medicines: "warfarin 5 mg",
      },
      "doctor",
      "en",
    );
    expect(result).toContain("[Structured medical context]");
    expect(result).toContain("Audience: doctor");
    expect(result).toContain("warfarin 5 mg");
    expect(result).toContain("do not infer absent facts");
  });
});
