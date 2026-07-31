import { describe, expect, it } from "vitest";

import { normalizeResearchTier2 } from "@/lib/research";

describe("Research verified presentation", () => {
  it("uses professional chrome only with a passed release and complete citation binding", () => {
    const result = normalizeResearchTier2({
      answer_markdown: "Released answer.",
      citations: [{ source_id: "pmid:1", title: "Source" }],
      quality_gate: { passed: true, reasons: [] },
      presentation: {
        mode: "professional",
        answer_markdown: "Released answer.",
        citation_ids: ["pmid:1"],
        citation_visibility: "expanded",
      },
    });

    expect(result.presentation?.mode).toBe("professional");
    expect(result.answer).toBe("Released answer.");
  });

  it("does not trust a presentation body without a passed release", () => {
    const result = normalizeResearchTier2({
      answer_markdown: "Safe abstention.",
      citations: [{ source_id: "pmid:1", title: "Source" }],
      quality_gate: { passed: false, reasons: ["unsupported_claims"] },
      presentation: {
        mode: "professional",
        answer_markdown: "Unreleased prose.",
        citation_ids: ["pmid:1"],
        citation_visibility: "expanded",
      },
    });

    expect(result.presentation).toBeUndefined();
    expect(result.answer).toBe("Safe abstention.");
  });
});
