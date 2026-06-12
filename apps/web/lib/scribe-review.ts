/**
 * Pure helpers for the Clara Scribe enterprise review/sign/export flow
 * (spec `clara-scribe-enterprise`, task 2.7 — Requirements 1, 8, 9).
 *
 * Everything here is framework-free and deterministic so it can be unit /
 * property tested in isolation (no React, no network). The React surface lives
 * in `components/scribe/enterprise-review.tsx` and consumes these helpers.
 */

import type { ScribeStreamSegment } from "@/lib/scribe";

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
