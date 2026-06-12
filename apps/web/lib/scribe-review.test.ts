import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  DEFAULT_SCRIBE_TEMPLATE_ID,
  SCRIBE_REVIEW_TEMPLATES,
  computePipelineStages,
  concatSegmentsText,
  getReviewTemplate,
  orderedNoteSections,
  parseContentDispositionFilename,
  speakerChip,
  type ScribeFlowState,
  type ScribeStageId,
} from "@/lib/scribe-review";
import type { ScribeStreamSegment } from "@/lib/scribe";

/**
 * Pure helpers backing the Clara Scribe enterprise review/sign/export UI
 * (spec `clara-scribe-enterprise`, task 2.7 — Requirements 1, 8, 9).
 *
 * Covers the bounded speaker-chip mapping (Req 3), the process-panel stage
 * derivation (consent → transcribe → generate → sign → export), template/section
 * ordering for the editor, transcript preservation (Req 3.4), and the export
 * Content-Disposition filename parsing (Req 9).
 */

const BOUNDED_SPEAKERS = ["clinician", "patient", "other", "unknown"] as const;
const STAGE_ORDER: ScribeStageId[] = ["consent", "transcribe", "generate", "sign", "export"];
const VALID_STATUSES = new Set(["pending", "in_progress", "completed", "failed", "warning"]);

function makeSegment(overrides: Partial<ScribeStreamSegment> = {}): ScribeStreamSegment {
  return {
    index: 0,
    text: "xin chào",
    speaker: "clinician",
    start_ms: 0,
    end_ms: 1000,
    degraded: false,
    ...overrides,
  };
}

const baseFlow: ScribeFlowState = {
  consentCaptured: false,
  consentRequired: true,
  transcribing: false,
  transcriptReady: false,
  usedBatchFallback: false,
  degradedCount: 0,
  generating: false,
  noteReady: false,
  signing: false,
  signed: false,
  exported: false,
  transcriptionError: null,
};

describe("speakerChip (Req 3.2 — bounded diarization labels)", () => {
  it("maps each bounded speaker to its own tone + Vietnamese label", () => {
    expect(speakerChip("clinician").tone).toBe("clinician");
    expect(speakerChip("clinician").label).toBe("Bác sĩ");
    expect(speakerChip("patient").tone).toBe("patient");
    expect(speakerChip("other").tone).toBe("other");
    expect(speakerChip("unknown").tone).toBe("unknown");
  });

  it("is case-insensitive and trims surrounding whitespace", () => {
    expect(speakerChip("  CLINICIAN ").tone).toBe("clinician");
    expect(speakerChip("Patient").tone).toBe("patient");
  });

  it("degrades any out-of-set / nullish value to unknown (never throws)", () => {
    fc.assert(
      fc.property(fc.oneof(fc.string(), fc.constant(null), fc.constant(undefined)), (value) => {
        const chip = speakerChip(value as string | null | undefined);
        const normalized = String(value ?? "").trim().toLowerCase();
        const tone = (BOUNDED_SPEAKERS as readonly string[]).includes(normalized) ? normalized : "unknown";
        expect(chip.tone).toBe(tone);
        // Always one of the four bounded tones.
        expect(BOUNDED_SPEAKERS).toContain(chip.tone);
      })
    );
  });
});

describe("computePipelineStages (process panel derivation)", () => {
  it("always returns the five stages in canonical order with a valid status", () => {
    fc.assert(
      fc.property(
        fc.record({
          consentCaptured: fc.boolean(),
          consentRequired: fc.boolean(),
          transcribing: fc.boolean(),
          transcriptReady: fc.boolean(),
          usedBatchFallback: fc.boolean(),
          degradedCount: fc.nat({ max: 5 }),
          generating: fc.boolean(),
          noteReady: fc.boolean(),
          signing: fc.boolean(),
          signed: fc.boolean(),
          exported: fc.boolean(),
          transcriptionError: fc.option(fc.string(), { nil: null }),
        }),
        (state) => {
          const stages = computePipelineStages(state);
          expect(stages.map((s) => s.id)).toEqual(STAGE_ORDER);
          for (const stage of stages) {
            expect(VALID_STATUSES.has(stage.status)).toBe(true);
          }
        }
      )
    );
  });

  it("gates consent: required + uncaptured ⇒ in_progress; not required ⇒ completed", () => {
    const gated = computePipelineStages({ ...baseFlow, consentRequired: true, consentCaptured: false });
    expect(gated[0].status).toBe("in_progress");

    const skipped = computePipelineStages({ ...baseFlow, consentRequired: false, consentCaptured: false });
    expect(skipped[0].status).toBe("completed");

    const captured = computePipelineStages({ ...baseFlow, consentRequired: true, consentCaptured: true });
    expect(captured[0].status).toBe("completed");
  });

  it("marks a terminal transcription error as failed and surfaces the detail", () => {
    const stages = computePipelineStages({ ...baseFlow, transcriptionError: "asr_unavailable" });
    const transcribe = stages.find((s) => s.id === "transcribe");
    expect(transcribe?.status).toBe("failed");
    expect(transcribe?.detail).toBe("asr_unavailable");
  });

  it("flags the batch fallback path and degraded segments with a warning", () => {
    const fallback = computePipelineStages({
      ...baseFlow,
      transcriptReady: true,
      usedBatchFallback: true,
    });
    const transcribe = fallback.find((s) => s.id === "transcribe");
    expect(transcribe?.detail).toContain("dự phòng");

    const degraded = computePipelineStages({ ...baseFlow, transcriptReady: true, degradedCount: 2 });
    expect(degraded.find((s) => s.id === "transcribe")?.status).toBe("warning");
  });

  it("treats a signed or exported note as a completed sign stage (Req 8)", () => {
    expect(computePipelineStages({ ...baseFlow, signed: true }).find((s) => s.id === "sign")?.status).toBe(
      "completed"
    );
    expect(computePipelineStages({ ...baseFlow, exported: true }).find((s) => s.id === "export")?.status).toBe(
      "completed"
    );
  });
});

describe("templates registry (Req 6 / editor picker)", () => {
  it("exposes the default SOAP template by id", () => {
    expect(DEFAULT_SCRIBE_TEMPLATE_ID).toBe("soap");
    expect(getReviewTemplate("soap")?.label).toBe("SOAP");
    expect(getReviewTemplate("does-not-exist")).toBeNull();
    expect(getReviewTemplate(null)).toBeNull();
  });

  it("every template has a non-empty ordered section list", () => {
    for (const template of SCRIBE_REVIEW_TEMPLATES) {
      expect(template.sections.length).toBeGreaterThan(0);
      for (const section of template.sections) {
        expect(section.key.trim().length).toBeGreaterThan(0);
        expect(section.label.trim().length).toBeGreaterThan(0);
      }
    }
  });
});

describe("orderedNoteSections (Req 8 — editable note)", () => {
  it("follows the template's section order with case-insensitive key fallback", () => {
    const note = {
      SUBJECTIVE: "S text",
      objective: "O text",
      assessment: "A text",
      plan: "P text",
    };
    const sections = orderedNoteSections(note, "soap");
    expect(sections.map((s) => s.key)).toEqual(["subjective", "objective", "assessment", "plan"]);
    expect(sections[0].value).toBe("S text");
    expect(sections[3].value).toBe("P text");
  });

  it("renders empty strings for missing sections (no fabrication)", () => {
    const sections = orderedNoteSections({ subjective: "only S" }, "soap");
    expect(sections.find((s) => s.key === "objective")?.value).toBe("");
  });

  it("surfaces every present key in object order when the template is unknown", () => {
    const sections = orderedNoteSections({ alpha: "1", beta: "2" }, "mystery-template");
    expect(sections.map((s) => s.key)).toEqual(["alpha", "beta"]);
  });

  it("coerces nested/array section values to text", () => {
    const sections = orderedNoteSections({ subjective: ["line a", "line b"] }, "soap");
    expect(sections.find((s) => s.key === "subjective")?.value).toBe("line a\nline b");
  });
});

describe("concatSegmentsText (Req 3.4 — transcript preserved verbatim)", () => {
  it("joins finalized segment text in order, one segment per line", () => {
    const segments = [
      makeSegment({ index: 0, text: "đau bụng" }),
      makeSegment({ index: 1, text: "từ hôm qua", speaker: "patient" }),
    ];
    expect(concatSegmentsText(segments)).toBe("đau bụng\ntừ hôm qua");
  });

  it("preserves the order and content of the segment text regardless of speaker label", () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({ text: fc.string(), speaker: fc.constantFrom(...BOUNDED_SPEAKERS) }), {
          maxLength: 8,
        }),
        (rows) => {
          const segments = rows.map((row, index) => makeSegment({ index, text: row.text, speaker: row.speaker }));
          const expected = rows
            .map((row) => row.text.trim())
            .filter(Boolean)
            .join("\n");
          expect(concatSegmentsText(segments)).toBe(expected);
        }
      )
    );
  });
});

describe("parseContentDispositionFilename (Req 9 — export download)", () => {
  it("parses the basic filename form", () => {
    expect(parseContentDispositionFilename('attachment; filename="clinical-note-7.docx"')).toBe(
      "clinical-note-7.docx"
    );
  });

  it("parses the RFC 5987 extended filename* form (percent-decoded)", () => {
    expect(parseContentDispositionFilename("attachment; filename*=UTF-8''ghi%20ch%C3%BA.docx")).toBe(
      "ghi chú.docx"
    );
  });

  it("returns null when no filename is present", () => {
    expect(parseContentDispositionFilename("attachment")).toBeNull();
    expect(parseContentDispositionFilename(null)).toBeNull();
    expect(parseContentDispositionFilename(undefined)).toBeNull();
  });
});
