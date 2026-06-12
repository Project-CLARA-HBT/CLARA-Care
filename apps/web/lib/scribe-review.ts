/**
 * Pure helpers for the Clara Scribe enterprise review/sign/export flow
 * (spec `clara-scribe-enterprise`, task 2.7 — Requirements 1, 8, 9).
 *
 * Everything here is framework-free and deterministic so it can be unit /
 * property tested in isolation (no React, no network). The React surface lives
 * in `components/scribe/enterprise-review.tsx` and consumes these helpers.
 */

import type { ScribeGroundedStatement, ScribeGroundingReport, ScribeStreamSegment } from "@/lib/scribe";

// ---------------------------------------------------------------------------
// Templates (mirrors the ML pure-data registry in
// services/ml/.../scribe/templates.py — Requirement 6). The web only needs the
// id + display label + ordered section (key, label) pairs so the picker can
// request a template and the editor can render its sections in order.
// ---------------------------------------------------------------------------

export type ScribeTemplateSection = {
  /** The key the generated note stores this section under. */
  key: string;
  /** Human label rendered in the editor. */
  label: string;
};

export type ScribeReviewTemplate = {
  id: string;
  label: string;
  language: "vi" | "en";
  sections: ScribeTemplateSection[];
};

/**
 * The SOAP template's sections are persisted by the API under normalized
 * lowercase keys (`subjective`/`objective`/`assessment`/`plan`); every other
 * template stores its sections under the registry's exact section-key strings.
 */
export const SCRIBE_REVIEW_TEMPLATES: ScribeReviewTemplate[] = [
  {
    id: "soap",
    label: "SOAP",
    language: "en",
    sections: [
      { key: "subjective", label: "Chủ quan (S)" },
      { key: "objective", label: "Khách quan (O)" },
      { key: "assessment", label: "Đánh giá (A)" },
      { key: "plan", label: "Kế hoạch (P)" },
    ],
  },
  {
    id: "h_and_p",
    label: "History & Physical (H&P)",
    language: "en",
    sections: [
      { key: "Chief Complaint", label: "Chief Complaint" },
      { key: "History of Present Illness", label: "History of Present Illness" },
      { key: "Past Medical History", label: "Past Medical History" },
      { key: "Medications", label: "Medications" },
      { key: "Allergies", label: "Allergies" },
      { key: "Physical Examination", label: "Physical Examination" },
      { key: "Assessment", label: "Assessment" },
      { key: "Plan", label: "Plan" },
    ],
  },
  {
    id: "progress_note",
    label: "Progress note",
    language: "en",
    sections: [
      { key: "Interval History", label: "Interval History" },
      { key: "Examination", label: "Examination" },
      { key: "Assessment", label: "Assessment" },
      { key: "Plan", label: "Plan" },
    ],
  },
  {
    id: "referral_letter",
    label: "Referral letter",
    language: "en",
    sections: [
      { key: "Reason for Referral", label: "Reason for Referral" },
      { key: "Clinical Summary", label: "Clinical Summary" },
      { key: "Current Medications", label: "Current Medications" },
      { key: "Request", label: "Request" },
    ],
  },
  {
    id: "vn_benh_an",
    label: "Bệnh án",
    language: "vi",
    sections: [
      { key: "Lý do khám", label: "Lý do khám" },
      { key: "Bệnh sử", label: "Bệnh sử" },
      { key: "Tiền sử", label: "Tiền sử" },
      { key: "Khám lâm sàng", label: "Khám lâm sàng" },
      { key: "Chẩn đoán", label: "Chẩn đoán" },
      { key: "Hướng xử trí", label: "Hướng xử trí" },
    ],
  },
];

export const DEFAULT_SCRIBE_TEMPLATE_ID = "soap";

export function getReviewTemplate(templateId: string | null | undefined): ScribeReviewTemplate | null {
  if (!templateId) return null;
  const id = String(templateId).trim();
  return SCRIBE_REVIEW_TEMPLATES.find((tpl) => tpl.id === id) ?? null;
}

// ---------------------------------------------------------------------------
// Speaker chips (Requirement 3 / 1). Diarization labels are a bounded set:
// clinician | patient | other | unknown. The chip maps each to a Vietnamese
// label + a stable tone token the component turns into Tailwind classes.
// ---------------------------------------------------------------------------

export type SpeakerTone = "clinician" | "patient" | "other" | "unknown";

export type SpeakerChip = {
  /** Canonical bounded speaker key. */
  speaker: SpeakerTone;
  /** Vietnamese display label. */
  label: string;
  /** Stable tone token (component maps to colors). */
  tone: SpeakerTone;
};

const SPEAKER_CHIPS: Record<SpeakerTone, SpeakerChip> = {
  clinician: { speaker: "clinician", label: "Bác sĩ", tone: "clinician" },
  patient: { speaker: "patient", label: "Người bệnh", tone: "patient" },
  other: { speaker: "other", label: "Khác", tone: "other" },
  unknown: { speaker: "unknown", label: "Chưa rõ", tone: "unknown" },
};

/**
 * Map a raw `segment.speaker` value to a bounded {@link SpeakerChip}. Any value
 * outside the bounded set degrades to `unknown` (Requirement 3.2 — diarization
 * unavailable ⇒ `unknown`, never an error).
 */
export function speakerChip(speaker: string | null | undefined): SpeakerChip {
  const key = String(speaker ?? "").trim().toLowerCase();
  if (key === "clinician" || key === "patient" || key === "other" || key === "unknown") {
    return SPEAKER_CHIPS[key];
  }
  return SPEAKER_CHIPS.unknown;
}

// ---------------------------------------------------------------------------
// Pipeline / process panel stages (Requirement 10.3 — observable pipeline,
// reusing the chat LogicFlow status vocabulary). Pure derivation of per-stage
// status from the current flow state, so the panel mirrors live progress.
// ---------------------------------------------------------------------------

export type ScribeStageStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "warning";

export type ScribeStageId = "consent" | "transcribe" | "generate" | "sign" | "export";

export type ScribeStage = {
  id: ScribeStageId;
  label: string;
  status: ScribeStageStatus;
  detail?: string;
};

const STAGE_LABELS: Record<ScribeStageId, string> = {
  consent: "Đồng thuận",
  transcribe: "Phiên âm",
  generate: "Soạn ghi chú",
  sign: "Ký số",
  export: "Xuất bản",
};

/** Snapshot of the enterprise flow used to derive the process-panel stages. */
export type ScribeFlowState = {
  consentCaptured: boolean;
  /** Consent not required by the server (flag off / capture skipped). */
  consentRequired: boolean;
  transcribing: boolean;
  transcriptReady: boolean;
  /** True when streaming fell back to the batch transcribe path. */
  usedBatchFallback: boolean;
  degradedCount: number;
  generating: boolean;
  noteReady: boolean;
  signing: boolean;
  signed: boolean;
  exported: boolean;
  /** Failure class for a terminal transcription error (no raw internals). */
  transcriptionError?: string | null;
};

/**
 * Derive the ordered process-panel stages from the current flow state. Pure +
 * total: any state yields exactly the 5 stages, each with a single status.
 */
export function computePipelineStages(state: ScribeFlowState): ScribeStage[] {
  const consentStatus: ScribeStageStatus = state.consentCaptured
    ? "completed"
    : state.consentRequired
      ? "in_progress"
      : "completed";

  let transcribeStatus: ScribeStageStatus;
  let transcribeDetail: string | undefined;
  if (state.transcriptionError) {
    transcribeStatus = "failed";
    transcribeDetail = state.transcriptionError;
  } else if (state.transcribing) {
    transcribeStatus = "in_progress";
  } else if (state.transcriptReady) {
    transcribeStatus = state.degradedCount > 0 ? "warning" : "completed";
    if (state.usedBatchFallback) {
      transcribeDetail = "Đã dùng phiên âm theo lô (dự phòng).";
    } else if (state.degradedCount > 0) {
      transcribeDetail = `${state.degradedCount} đoạn tín hiệu yếu.`;
    }
  } else {
    transcribeStatus = "pending";
  }

  let generateStatus: ScribeStageStatus;
  if (state.generating) generateStatus = "in_progress";
  else if (state.noteReady) generateStatus = "completed";
  else if (state.transcriptReady) generateStatus = "pending";
  else generateStatus = "pending";

  let signStatus: ScribeStageStatus;
  if (state.signed || state.exported) signStatus = "completed";
  else if (state.signing) signStatus = "in_progress";
  else signStatus = "pending";

  const exportStatus: ScribeStageStatus = state.exported ? "completed" : "pending";

  return [
    { id: "consent", label: STAGE_LABELS.consent, status: consentStatus },
    { id: "transcribe", label: STAGE_LABELS.transcribe, status: transcribeStatus, detail: transcribeDetail },
    { id: "generate", label: STAGE_LABELS.generate, status: generateStatus },
    { id: "sign", label: STAGE_LABELS.sign, status: signStatus },
    { id: "export", label: STAGE_LABELS.export, status: exportStatus },
  ];
}

// ---------------------------------------------------------------------------
// Note sections (Requirement 8 — review/edit). Coerce a persisted note object
// into ordered editable (key, label, value) entries for the selected template.
// ---------------------------------------------------------------------------

export type NoteSectionEntry = {
  key: string;
  label: string;
  value: string;
};

function coerceSectionText(value: unknown): string {
  if (typeof value === "string") return value;
  if (value == null) return "";
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) {
    return value.map((item) => coerceSectionText(item)).filter(Boolean).join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => {
        const text = coerceSectionText(v);
        return text ? `${k}: ${text}` : "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

/**
 * Produce ordered, editable note sections for `templateId`. When the template
 * is known the section order follows the registry; section text is read from
 * the persisted note object by key (case-insensitive fallback). When the
 * template is unknown every present key is surfaced in object order.
 */
export function orderedNoteSections(
  note: Record<string, unknown> | null | undefined,
  templateId: string | null | undefined
): NoteSectionEntry[] {
  const source = note && typeof note === "object" ? (note as Record<string, unknown>) : {};
  const template = getReviewTemplate(templateId);

  if (template) {
    const lowerIndex = new Map<string, unknown>();
    for (const [k, v] of Object.entries(source)) lowerIndex.set(k.toLowerCase(), v);
    return template.sections.map((section) => {
      const direct = source[section.key];
      const value = direct !== undefined ? direct : lowerIndex.get(section.key.toLowerCase());
      return { key: section.key, label: section.label, value: coerceSectionText(value) };
    });
  }

  return Object.entries(source).map(([key, value]) => ({
    key,
    label: key,
    value: coerceSectionText(value),
  }));
}

// ---------------------------------------------------------------------------
// Transcript helpers
// ---------------------------------------------------------------------------

/**
 * Concatenate finalized segments into a transcript string. Diarization is
 * additive metadata only: the order and text are preserved verbatim
 * (Requirement 3.4), one segment per line.
 */
export function concatSegmentsText(segments: ScribeStreamSegment[]): string {
  return segments
    .map((segment) => (typeof segment.text === "string" ? segment.text.trim() : ""))
    .filter(Boolean)
    .join("\n");
}

// ---------------------------------------------------------------------------
// Export helpers (Requirement 9 — md / docx / fhir).
// ---------------------------------------------------------------------------

/**
 * Parse the filename out of a `Content-Disposition` header, supporting both the
 * `filename="..."` and RFC 5987 `filename*=UTF-8''...` forms. Returns `null`
 * when no filename can be extracted.
 */
export function parseContentDispositionFilename(header: string | null | undefined): string | null {
  if (!header) return null;
  const extended = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header);
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim().replace(/^"|"$/g, ""));
    } catch {
      return extended[1].trim().replace(/^"|"$/g, "");
    }
  }
  const basic = /filename="?([^";]+)"?/i.exec(header);
  if (basic?.[1]) return basic[1].trim();
  return null;
}

// ---------------------------------------------------------------------------
// Transcript grounding / claim traceability (Requirement 12.7). Pure helpers
// backing the per-statement grounded/unverified chips, the transcript-span
// drill-down, and the unverified-candidate review panel. The grounding report
// is additive metadata: nothing here mutates the note text or transcript.
// ---------------------------------------------------------------------------

/**
 * A parsed transcript span identifier. The server emits span ids as either a
 * whole-segment reference (`seg-0003`) or a sub-range with character offsets
 * (`seg-0003:6-16`). `segmentIndex` is the numeric segment ordinal; `start`/
 * `end` are the optional half-open character offsets within that segment.
 */
export type ParsedSpanId = {
  raw: string;
  segmentIndex: number | null;
  start: number | null;
  end: number | null;
};

const SPAN_ID_RE = /^seg-(\d+)(?::(\d+)-(\d+))?$/i;

/**
 * Parse a transcript span id (`seg-0003` or `seg-0003:6-16`) into its segment
 * ordinal + optional character offsets. Returns null fields for any value that
 * is not a recognized span id (never throws).
 */
export function parseSpanId(spanId: string | null | undefined): ParsedSpanId {
  const raw = String(spanId ?? "").trim();
  const empty: ParsedSpanId = { raw, segmentIndex: null, start: null, end: null };
  if (!raw) return empty;
  const match = SPAN_ID_RE.exec(raw);
  if (!match) return empty;
  const segmentIndex = Number.parseInt(match[1], 10);
  const start = match[2] !== undefined ? Number.parseInt(match[2], 10) : null;
  const end = match[3] !== undefined ? Number.parseInt(match[3], 10) : null;
  return {
    raw,
    segmentIndex: Number.isNaN(segmentIndex) ? null : segmentIndex,
    start: start !== null && Number.isNaN(start) ? null : start,
    end: end !== null && Number.isNaN(end) ? null : end,
  };
}

/** A transcript span id resolved against the session's finalized segments. */
export type ResolvedTranscriptSpan = {
  /** The original span id. */
  spanId: string;
  /** The backing segment ordinal (null when the id was unparseable). */
  segmentIndex: number | null;
  /** Bounded speaker tone of the backing segment (`unknown` when unresolved). */
  speaker: SpeakerTone;
  /** The supporting text — the sub-range slice when offsets are present. */
  text: string;
  /** The full backing segment text. */
  full: string;
  start: number | null;
  end: number | null;
  /** True when a backing segment was found for the span id. */
  resolved: boolean;
};

/**
 * Resolve a transcript span id to its supporting transcript text + speaker for
 * the drill-down. The segment is matched by its `index` (falling back to array
 * position); when the id carries character offsets the slice is returned as the
 * span text. An unresolved id degrades gracefully (empty text, `unknown`
 * speaker, `resolved: false`) so the UI can still show the raw id.
 */
export function resolveTranscriptSpan(
  spanId: string | null | undefined,
  segments: ScribeStreamSegment[]
): ResolvedTranscriptSpan {
  const parsed = parseSpanId(spanId);
  const base: ResolvedTranscriptSpan = {
    spanId: parsed.raw,
    segmentIndex: parsed.segmentIndex,
    speaker: "unknown",
    text: "",
    full: "",
    start: parsed.start,
    end: parsed.end,
    resolved: false,
  };
  if (parsed.segmentIndex === null || !Array.isArray(segments)) return base;
  const segment =
    segments.find((item) => item?.index === parsed.segmentIndex) ?? segments[parsed.segmentIndex];
  if (!segment) return base;
  const full = typeof segment.text === "string" ? segment.text : "";
  let text = full;
  if (parsed.start !== null && parsed.end !== null && parsed.end > parsed.start) {
    text = full.slice(parsed.start, parsed.end);
  }
  return {
    spanId: parsed.raw,
    segmentIndex: parsed.segmentIndex,
    speaker: speakerChip(segment.speaker).tone,
    text: text || full,
    full,
    start: parsed.start,
    end: parsed.end,
    resolved: true,
  };
}

/** Bounded grounding status for a statement chip. */
export type GroundingStatus = "grounded" | "unverified";

export type GroundingChip = {
  status: GroundingStatus;
  /** Stable tone token the component maps to colors. */
  tone: GroundingStatus;
  /** Vietnamese display label. */
  label: string;
  /** True for a critical-safety statement (medication/dose/allergy/vital/diagnosis). */
  critical: boolean;
};

/**
 * Derive the grounded/unverified chip for a statement. The `grounded` boolean
 * is the source of truth (Req 12.3: grounded iff a span entails it); anything
 * not grounded is surfaced as `unverified` (Req 12.4).
 */
export function groundingChip(
  statement: Pick<ScribeGroundedStatement, "grounded" | "critical_safety">
): GroundingChip {
  const grounded = Boolean(statement?.grounded);
  const status: GroundingStatus = grounded ? "grounded" : "unverified";
  return {
    status,
    tone: status,
    label: grounded ? "Có dẫn chứng" : "Chưa xác minh",
    critical: Boolean(statement?.critical_safety),
  };
}

function normalizeStatement(raw: unknown): ScribeGroundedStatement {
  const obj = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const spanIds = Array.isArray(obj.supporting_span_ids)
    ? obj.supporting_span_ids.filter((id): id is string => typeof id === "string")
    : [];
  const grounded = Boolean(obj.grounded);
  return {
    statement: typeof obj.statement === "string" ? obj.statement : "",
    section: typeof obj.section === "string" ? obj.section : "",
    significant: Boolean(obj.significant),
    critical_safety: Boolean(obj.critical_safety),
    grounded,
    supporting_span_ids: spanIds,
    method: typeof obj.method === "string" ? obj.method : "",
    status: typeof obj.status === "string" ? obj.status : grounded ? "grounded" : "unverified",
    asserted: Boolean(obj.asserted),
    fact_check: typeof obj.fact_check === "string" ? obj.fact_check : "n/a",
  };
}

/**
 * Coerce an arbitrary grounding payload (e.g. the server `grounding` object)
 * into a well-formed {@link ScribeGroundingReport}, defending against missing
 * or malformed fields so the UI never throws on partial data.
 */
export function normalizeGroundingReport(raw: unknown): ScribeGroundingReport {
  const obj = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const statements = Array.isArray(obj.statements) ? obj.statements.map(normalizeStatement) : [];
  const candidates = Array.isArray(obj.unverified_candidates)
    ? obj.unverified_candidates.filter((c): c is string => typeof c === "string")
    : [];
  const rate = typeof obj.grounded_claim_rate === "number" && Number.isFinite(obj.grounded_claim_rate)
    ? obj.grounded_claim_rate
    : 0;
  return {
    version: typeof obj.version === "string" ? obj.version : undefined,
    enabled: Boolean(obj.enabled),
    statements,
    grounded_claim_rate: rate,
    unverified_candidates: candidates,
    total_significant:
      typeof obj.total_significant === "number" ? obj.total_significant : statements.filter((s) => s.significant).length,
    grounded_significant:
      typeof obj.grounded_significant === "number"
        ? obj.grounded_significant
        : statements.filter((s) => s.significant && s.grounded).length,
  };
}

/**
 * Whether a grounding report carries anything worth surfacing. False when the
 * report is absent, disabled, or empty so the editor renders exactly as before
 * (Req 12.1 — grounding off ⇒ no chips/panel).
 */
export function groundingHasData(report: ScribeGroundingReport | null | undefined): boolean {
  if (!report || !report.enabled) return false;
  const hasStatements = Array.isArray(report.statements) && report.statements.length > 0;
  const hasCandidates =
    Array.isArray(report.unverified_candidates) && report.unverified_candidates.length > 0;
  return hasStatements || hasCandidates;
}

export type GroundingPartition = {
  /** Clinically significant grounded statements. */
  grounded: ScribeGroundedStatement[];
  /** Clinically significant ungrounded (unverified) statements. */
  unverified: ScribeGroundedStatement[];
};

/**
 * Split a report's clinically significant statements into grounded vs
 * unverified buckets (boilerplate/insignificant statements are dropped). The
 * relative order of statements is preserved within each bucket.
 */
export function partitionGroundingStatements(
  report: ScribeGroundingReport | null | undefined
): GroundingPartition {
  const statements = report && Array.isArray(report.statements) ? report.statements : [];
  const significant = statements.filter((statement) => statement?.significant);
  return {
    grounded: significant.filter((statement) => Boolean(statement.grounded)),
    unverified: significant.filter((statement) => !statement.grounded),
  };
}

/**
 * Format the grounded-claim rate as a whole-percent string for the summary
 * badge. Clamps to 0–100 and rounds to the nearest percent.
 */
export function formatGroundedClaimRate(rate: number | null | undefined): string {
  const value = typeof rate === "number" && Number.isFinite(rate) ? rate : 0;
  const clamped = Math.min(1, Math.max(0, value));
  return `${Math.round(clamped * 100)}%`;
}
