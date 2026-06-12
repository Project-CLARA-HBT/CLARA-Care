import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  DEFAULT_SCRIBE_TEMPLATE_ID,
  SCRIBE_REVIEW_TEMPLATES,
  codingHasData,
  computePipelineStages,
  concatSegmentsText,
  confirmedEmCptSuggestions,
  countConfirmedEmCpt,
  emCptCodeKey,
  formatGroundedClaimRate,
  getReviewTemplate,
  groundingChip,
  groundingHasData,
  initialEmCptSelections,
  isEmCptSelected,
  normalizeEmCptSuggestion,
  normalizeEmCptSuggestions,
  normalizeGroundingReport,
  orderedNoteSections,
  parseContentDispositionFilename,
  parseSpanId,
  partitionEmCpt,
  partitionGroundingStatements,
  resolveTranscriptSpan,
  speakerChip,
  toggleEmCptSelection,
  type ScribeFlowState,
  type ScribeStageId,
} from "@/lib/scribe-review";
import type {
  ScribeCodingReport,
  ScribeEmCptSuggestion,
  ScribeGroundedStatement,
  ScribeStreamSegment,
} from "@/lib/scribe";

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

// ---------------------------------------------------------------------------
// Transcript grounding / claim traceability (Requirement 12.7).
// ---------------------------------------------------------------------------

function makeStatement(overrides: Partial<ScribeGroundedStatement> = {}): ScribeGroundedStatement {
  return {
    statement: "Bệnh nhân đau bụng",
    section: "subjective",
    significant: true,
    critical_safety: false,
    grounded: true,
    supporting_span_ids: ["seg-0001"],
    method: "nli",
    status: "grounded",
    asserted: true,
    fact_check: "supported",
    ...overrides,
  };
}

describe("parseSpanId (Req 12.7 — span drill-down)", () => {
  it("parses a whole-segment span id", () => {
    expect(parseSpanId("seg-0003")).toEqual({ raw: "seg-0003", segmentIndex: 3, start: null, end: null });
  });

  it("parses a sub-range span id with character offsets", () => {
    expect(parseSpanId("seg-0003:6-16")).toEqual({ raw: "seg-0003:6-16", segmentIndex: 3, start: 6, end: 16 });
  });

  it("returns null fields for an unrecognized or empty id (never throws)", () => {
    expect(parseSpanId("garbage").segmentIndex).toBeNull();
    expect(parseSpanId("").segmentIndex).toBeNull();
    expect(parseSpanId(null).segmentIndex).toBeNull();
    expect(parseSpanId(undefined).segmentIndex).toBeNull();
  });
});

describe("resolveTranscriptSpan (Req 12.7 — span drill-down)", () => {
  const segments = [
    makeSegment({ index: 0, text: "xin chào bác sĩ", speaker: "patient" }),
    makeSegment({ index: 3, text: "huyết áp 120/80 mmHg", speaker: "clinician" }),
  ];

  it("resolves a whole-segment span to the full segment text + speaker tone", () => {
    const span = resolveTranscriptSpan("seg-0003", segments);
    expect(span.resolved).toBe(true);
    expect(span.text).toBe("huyết áp 120/80 mmHg");
    expect(span.full).toBe("huyết áp 120/80 mmHg");
    expect(span.speaker).toBe("clinician");
  });

  it("slices the supporting sub-range when offsets are present", () => {
    const span = resolveTranscriptSpan("seg-0003:9-15", segments);
    expect(span.text).toBe("120/80");
    expect(span.full).toBe("huyết áp 120/80 mmHg");
  });

  it("degrades to an unresolved span (empty text, unknown speaker) for an unknown segment", () => {
    const span = resolveTranscriptSpan("seg-0099", segments);
    expect(span.resolved).toBe(false);
    expect(span.text).toBe("");
    expect(span.speaker).toBe("unknown");
  });

  it("never resolves an unparseable id", () => {
    expect(resolveTranscriptSpan("nope", segments).resolved).toBe(false);
  });
});

describe("groundingChip (Req 12.3 / 12.4 — grounded vs unverified)", () => {
  it("maps a grounded statement to the grounded tone", () => {
    const chip = groundingChip(makeStatement({ grounded: true }));
    expect(chip.status).toBe("grounded");
    expect(chip.tone).toBe("grounded");
    expect(chip.label).toBe("Có dẫn chứng");
  });

  it("maps an ungrounded statement to the unverified tone", () => {
    const chip = groundingChip(makeStatement({ grounded: false }));
    expect(chip.status).toBe("unverified");
    expect(chip.label).toBe("Chưa xác minh");
  });

  it("carries the critical-safety flag through", () => {
    expect(groundingChip(makeStatement({ critical_safety: true })).critical).toBe(true);
  });

  it("only ever yields grounded or unverified for any statement", () => {
    fc.assert(
      fc.property(fc.boolean(), fc.boolean(), (grounded, critical) => {
        const chip = groundingChip(makeStatement({ grounded, critical_safety: critical }));
        expect(["grounded", "unverified"]).toContain(chip.status);
        expect(chip.status).toBe(grounded ? "grounded" : "unverified");
      })
    );
  });
});

describe("partitionGroundingStatements (Req 12.7 — grounded/unverified split)", () => {
  it("buckets only clinically significant statements and drops boilerplate", () => {
    const report = normalizeGroundingReport({
      enabled: true,
      statements: [
        makeStatement({ statement: "A grounded", grounded: true, significant: true }),
        makeStatement({ statement: "B unverified", grounded: false, significant: true }),
        makeStatement({ statement: "C heading", grounded: false, significant: false }),
      ],
    });
    const { grounded, unverified } = partitionGroundingStatements(report);
    expect(grounded.map((s) => s.statement)).toEqual(["A grounded"]);
    expect(unverified.map((s) => s.statement)).toEqual(["B unverified"]);
  });

  it("every significant statement lands in exactly one bucket", () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({ grounded: fc.boolean(), significant: fc.boolean() }), { maxLength: 12 }),
        (rows) => {
          const report = normalizeGroundingReport({
            enabled: true,
            statements: rows.map((row, index) =>
              makeStatement({ statement: `s${index}`, grounded: row.grounded, significant: row.significant })
            ),
          });
          const { grounded, unverified } = partitionGroundingStatements(report);
          const significantCount = rows.filter((row) => row.significant).length;
          expect(grounded.length + unverified.length).toBe(significantCount);
          // Buckets are disjoint by construction.
          for (const s of grounded) expect(s.grounded).toBe(true);
          for (const s of unverified) expect(s.grounded).toBe(false);
        }
      )
    );
  });
});

describe("normalizeGroundingReport (Req 12.7 — defensive coercion)", () => {
  it("fills safe defaults for a malformed/partial payload (never throws)", () => {
    const report = normalizeGroundingReport({ enabled: true, statements: "nope" });
    expect(report.statements).toEqual([]);
    expect(report.unverified_candidates).toEqual([]);
    expect(report.grounded_claim_rate).toBe(0);
  });

  it("derives significant counts when the server omits them", () => {
    const report = normalizeGroundingReport({
      enabled: true,
      statements: [
        makeStatement({ significant: true, grounded: true }),
        makeStatement({ significant: true, grounded: false }),
        makeStatement({ significant: false, grounded: false }),
      ],
    });
    expect(report.total_significant).toBe(2);
    expect(report.grounded_significant).toBe(1);
  });

  it("coerces a non-object payload to a disabled empty report", () => {
    expect(normalizeGroundingReport(null).enabled).toBe(false);
    expect(normalizeGroundingReport(undefined).statements).toEqual([]);
  });
});

describe("groundingHasData (Req 12.1 — flag off ⇒ render unchanged)", () => {
  it("is false for an absent, disabled, or empty report", () => {
    expect(groundingHasData(null)).toBe(false);
    expect(groundingHasData(normalizeGroundingReport({ enabled: false, statements: [makeStatement()] }))).toBe(
      false
    );
    expect(groundingHasData(normalizeGroundingReport({ enabled: true }))).toBe(false);
  });

  it("is true when enabled with at least one statement or unverified candidate", () => {
    expect(groundingHasData(normalizeGroundingReport({ enabled: true, statements: [makeStatement()] }))).toBe(
      true
    );
    expect(
      groundingHasData(normalizeGroundingReport({ enabled: true, unverified_candidates: ["penicillin 500mg"] }))
    ).toBe(true);
  });
});

describe("formatGroundedClaimRate (Req 12.8 — summary badge)", () => {
  it("renders a whole-percent string and clamps to 0–100", () => {
    expect(formatGroundedClaimRate(1)).toBe("100%");
    expect(formatGroundedClaimRate(0.5)).toBe("50%");
    expect(formatGroundedClaimRate(0)).toBe("0%");
    expect(formatGroundedClaimRate(2)).toBe("100%");
    expect(formatGroundedClaimRate(-1)).toBe("0%");
    expect(formatGroundedClaimRate(NaN)).toBe("0%");
  });
});

// ---------------------------------------------------------------------------
// E/M + CPT coding suggestions (Requirement 14.3 / 14.5). Pure helpers backing
// the advisory suggestion list + explicit per-code clinician confirmation. The
// key invariants: nothing is auto-selected, selection is local + explicit, and
// a malformed/absent payload degrades to an empty (no-op) suggestion set.
// ---------------------------------------------------------------------------

function makeEmCpt(overrides: Partial<ScribeEmCptSuggestion> = {}): ScribeEmCptSuggestion {
  return {
    code: "99214",
    kind: "E/M",
    system: "E/M",
    display: "Office visit, level 4",
    display_vi: "Khám phòng khám, mức 4",
    level: 4,
    spans: ["seg-0001"],
    rationale: "moderate MDM",
    selected: false,
    status: "advisory",
    ...overrides,
  };
}

function codingReport(em_cpt: Array<Partial<ScribeEmCptSuggestion>>): ScribeCodingReport {
  return { icd: [], medications: [], interactions: [], advisory: true, em_cpt: em_cpt.map(makeEmCpt) };
}

describe("normalizeEmCptSuggestion (Req 14.3/14.5 — never trust server selection)", () => {
  it("forces selected=false even when the payload claims selected=true", () => {
    const s = normalizeEmCptSuggestion({ code: "99213", kind: "E/M", selected: true, level: 3 });
    expect(s.selected).toBe(false);
    expect(s.status).toBe("advisory");
  });

  it("fills safe defaults for a malformed/partial payload (never throws)", () => {
    const s = normalizeEmCptSuggestion({ code: "93000" });
    expect(s.kind).toBe("CPT"); // unknown kind degrades to CPT
    expect(s.spans).toEqual([]);
    expect(s.level).toBeNull();
  });

  it("keeps a numeric E/M level and a valid kind", () => {
    const s = normalizeEmCptSuggestion({ code: "99215", kind: "E/M", level: 5 });
    expect(s.kind).toBe("E/M");
    expect(s.level).toBe(5);
  });
});

describe("normalizeEmCptSuggestions (Req 14.1 — absent ⇒ empty)", () => {
  it("returns an empty list for an absent / malformed coding report", () => {
    expect(normalizeEmCptSuggestions(null)).toEqual([]);
    expect(normalizeEmCptSuggestions(undefined)).toEqual([]);
    expect(normalizeEmCptSuggestions({ em_cpt: "nope" } as unknown as ScribeCodingReport)).toEqual([]);
  });

  it("drops suggestions with no code and normalizes the rest", () => {
    const list = normalizeEmCptSuggestions(codingReport([{ code: "" }, { code: "99214" }]));
    expect(list).toHaveLength(1);
    expect(list[0].code).toBe("99214");
    expect(list[0].selected).toBe(false);
  });
});

describe("partitionEmCpt (Req 14.2 — E/M vs CPT split)", () => {
  it("buckets E/M and CPT suggestions, preserving order", () => {
    const list = [
      makeEmCpt({ code: "99214", kind: "E/M" }),
      makeEmCpt({ code: "93000", kind: "CPT", level: null }),
      makeEmCpt({ code: "94640", kind: "CPT", level: null }),
    ];
    const { em, cpt } = partitionEmCpt(list);
    expect(em.map((s) => s.code)).toEqual(["99214"]);
    expect(cpt.map((s) => s.code)).toEqual(["93000", "94640"]);
  });

  it("every suggestion lands in exactly one bucket (non-E/M ⇒ CPT)", () => {
    fc.assert(
      fc.property(
        fc.array(fc.record({ kind: fc.constantFrom("E/M", "CPT", "weird") }), { maxLength: 10 }),
        (rows) => {
          const list = rows.map((row, index) => makeEmCpt({ code: `c${index}`, kind: row.kind }));
          const { em, cpt } = partitionEmCpt(list);
          expect(em.length + cpt.length).toBe(list.length);
          for (const s of em) expect(s.kind).toBe("E/M");
          for (const s of cpt) expect(s.kind).not.toBe("E/M");
        }
      )
    );
  });
});

describe("codingHasData (Req 14.1 — flag off ⇒ render unchanged)", () => {
  it("is false for an absent or empty coding report", () => {
    expect(codingHasData(null)).toBe(false);
    expect(codingHasData(codingReport([]))).toBe(false);
    expect(codingHasData(codingReport([{ code: "" }]))).toBe(false);
  });

  it("is true when at least one valid suggestion is present", () => {
    expect(codingHasData(codingReport([{ code: "99214" }]))).toBe(true);
  });
});

describe("E/M+CPT selection state (Req 14.3/14.5 — nothing auto-selected)", () => {
  it("starts with an empty selection map (nothing pre-selected)", () => {
    const selections = initialEmCptSelections();
    expect(selections).toEqual({});
    expect(countConfirmedEmCpt(selections)).toBe(0);
    const suggestions = normalizeEmCptSuggestions(codingReport([{ code: "99214" }, { code: "93000", kind: "CPT" }]));
    for (const s of suggestions) expect(isEmCptSelected(selections, s)).toBe(false);
    // No code is "confirmed" without an explicit toggle.
    expect(confirmedEmCptSuggestions(suggestions, selections)).toEqual([]);
  });

  it("emCptCodeKey is stable + distinguishes kind/code/level", () => {
    expect(emCptCodeKey(makeEmCpt({ code: "99214", kind: "E/M", level: 4 }))).toBe("E/M:99214:4");
    expect(emCptCodeKey(makeEmCpt({ code: "93000", kind: "CPT", level: null }))).toBe("CPT:93000:");
    // Same code, different kind ⇒ different key (no collision).
    expect(emCptCodeKey(makeEmCpt({ code: "x", kind: "E/M", level: 2 }))).not.toBe(
      emCptCodeKey(makeEmCpt({ code: "x", kind: "CPT", level: null }))
    );
  });

  it("toggling a code is pure and confirms exactly that code", () => {
    const s = makeEmCpt({ code: "99214" });
    const before = initialEmCptSelections();
    const after = toggleEmCptSelection(before, s);
    // Input map is never mutated (pure).
    expect(before).toEqual({});
    expect(isEmCptSelected(after, s)).toBe(true);
    expect(countConfirmedEmCpt(after)).toBe(1);
    // Toggling again clears it.
    const cleared = toggleEmCptSelection(after, s);
    expect(isEmCptSelected(cleared, s)).toBe(false);
    expect(countConfirmedEmCpt(cleared)).toBe(0);
  });

  it("confirmedEmCptSuggestions returns only toggled codes with selected=true", () => {
    const suggestions = normalizeEmCptSuggestions(
      codingReport([{ code: "99214", kind: "E/M" }, { code: "93000", kind: "CPT", level: null }])
    );
    const selections = toggleEmCptSelection(initialEmCptSelections(), suggestions[1]);
    const confirmed = confirmedEmCptSuggestions(suggestions, selections);
    expect(confirmed.map((s) => s.code)).toEqual(["93000"]);
    expect(confirmed[0].selected).toBe(true);
  });

  it("a code is selected iff it was explicitly toggled an odd number of times", () => {
    fc.assert(
      fc.property(fc.nat({ max: 6 }), (toggles) => {
        const s = makeEmCpt({ code: "99214" });
        let selections = initialEmCptSelections();
        for (let i = 0; i < toggles; i += 1) selections = toggleEmCptSelection(selections, s);
        expect(isEmCptSelected(selections, s)).toBe(toggles % 2 === 1);
      })
    );
  });
});
