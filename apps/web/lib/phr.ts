import api from "@/lib/http-client";

/**
 * Where an entry came from (personal-health-record Requirement 6.1–6.4). Manual
 * edits are `self-declared`; OCR import is `ocr`; structured import is
 * `imported`. Optional so the legacy response shape (no provenance) is preserved
 * when the PHR feature flag is off (Requirement 18.1).
 */
export type PhrInformationSource = "self-declared" | "ocr" | "imported";

/**
 * Coded clinical-data verification status (personal-health-record Requirement
 * 6.5). Mirrors FHIR-style verification states; optional for back-compatibility.
 */
export type PhrVerificationStatus =
  | "unconfirmed"
  | "confirmed"
  | "provisional"
  | "refuted"
  | "entered-in-error";

/** Provenance/verification fields shared by every coded PHR entry. */
export type PhrEntryProvenance = {
  information_source?: PhrInformationSource | null;
  verification_status?: PhrVerificationStatus | null;
};

export type PhrAllergyItem = PhrEntryProvenance & {
  id: string;
  name: string;
  reaction: string;
  severity: "mild" | "moderate" | "severe" | "unknown";
  note: string;
  // --- new coded fields (personal-health-record Requirement 4). Optional and
  //     defaulted so the legacy free-text allergy shape still validates when the
  //     PHR feature flag is off (Requirement 18.1). ---
  substance?: string;
  coded_substance_id?: string;
  is_coded?: boolean;
};

export type PhrConditionItem = PhrEntryProvenance & {
  id: string;
  name: string;
  status: "active" | "resolved" | "monitoring" | "unknown";
  diagnosed_on?: string | null;
  note: string;
  // --- new coded fields (personal-health-record Requirement 5). Optional and
  //     defaulted for back-compatibility (Requirement 18.1). ---
  icd10_code?: string;
  snomed_code?: string;
  is_coded?: boolean;
};

export type PhrMedicationItem = PhrEntryProvenance & {
  id: string;
  name: string;
  dose: string;
  frequency: string;
  started_on?: string | null;
  is_current: boolean;
  note: string;
  // --- new structured fields (personal-health-record Requirement 3). Optional
  //     and defaulted so legacy free-text medications still validate when the
  //     PHR feature flag is off (Requirement 18.1). ---
  dose_amount?: number | null;
  dose_unit?: string;
  route?: string;
  // --- new coded fields (personal-health-record Requirement 3.2/3.3/3.4). ---
  normalized_name?: string;
  rx_cui?: string;
  normalization_source?: string;
  is_normalized?: boolean;
  duplicate_of?: string | null;
  ocr_confidence?: number | null;
};

export type PhrRecord = {
  full_name: string;
  date_of_birth?: string | null;
  gender: string;
  blood_type: string;
  height_cm?: number | null;
  weight_kg?: number | null;
  phone: string;
  contact_email: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  emergency_contact_relationship: string;
  emergency_contact_note: string;
  insurance_provider: string;
  insurance_id: string;
  insurance_expiry?: string | null;
  allergy_status: "unknown" | "none_known" | "recorded";
  notes: string;
  allergies: PhrAllergyItem[];
  conditions: PhrConditionItem[];
  medications: PhrMedicationItem[];
  created_at?: string | null;
  updated_at?: string | null;
};

export async function getPhrRecord(): Promise<PhrRecord> {
  const { data } = await api.get<PhrRecord>("/api/v1/phr/record");
  return data;
}

export async function updatePhrRecord(payload: PhrRecord): Promise<PhrRecord> {
  const { data } = await api.put<PhrRecord>("/api/v1/phr/record", payload);
  return data;
}

// ---------------------------------------------------------------------------
// Body measurements
// ---------------------------------------------------------------------------

/** A height/weight pair recorded at the same time; BMI is server-derived. */
export type PhrBodyMeasurement = {
  observed_on: string;
  height_cm: number;
  weight_kg: number;
  bmi: number;
  information_source: PhrInformationSource;
};

export type PhrBodyMeasurementInput = Pick<
  PhrBodyMeasurement,
  "height_cm" | "weight_kg"
> & {
  observed_on?: string;
};

export async function getPhrBodyMeasurements(): Promise<PhrBodyMeasurement[]> {
  const { data } = await api.get<{ measurements?: PhrBodyMeasurement[] }>(
    "/api/v1/phr/body-measurements",
  );
  return Array.isArray(data.measurements) ? data.measurements : [];
}

export async function createPhrBodyMeasurement(
  payload: PhrBodyMeasurementInput,
): Promise<PhrBodyMeasurement> {
  const { data } = await api.post<PhrBodyMeasurement>(
    "/api/v1/phr/body-measurements",
    payload,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Completeness meter (personal-health-record Requirement 16)
// ---------------------------------------------------------------------------

/**
 * USCDI-aligned data classes scored by the completeness meter
 * (personal-health-record Requirement 16.1). Mirrors the server-side
 * `COMPLETENESS_CLASSES` ordering so the web client can render stable,
 * localized labels for the present/missing class names without ever handling
 * PHR values (Requirement 16.4 — the payload carries only class names + score).
 */
export type PhrCompletenessClass =
  | "patient_demographics"
  | "allergies"
  | "medications"
  | "problems"
  | "immunizations"
  | "procedures"
  | "labs";

/**
 * Result of `GET /api/v1/phr/completeness`: a deterministic score in `[0, 1]`
 * plus the present/missing USCDI class names (Requirement 16.1, 16.2). The
 * `telemetry` projection is PII-free (counts + class names only, Requirement
 * 16.4) and is not required for display.
 */
export type PhrCompleteness = {
  score: number;
  present: PhrCompletenessClass[];
  missing: PhrCompletenessClass[];
};

/** The known USCDI class names, in display order. */
export const PHR_COMPLETENESS_CLASSES: readonly PhrCompletenessClass[] = [
  "patient_demographics",
  "allergies",
  "medications",
  "problems",
  "immunizations",
  "procedures",
  "labs",
] as const;

const PHR_COMPLETENESS_CLASS_SET = new Set<string>(PHR_COMPLETENESS_CLASSES);

function coerceClassList(value: unknown): PhrCompletenessClass[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (entry): entry is PhrCompletenessClass =>
      typeof entry === "string" && PHR_COMPLETENESS_CLASS_SET.has(entry),
  );
}

/**
 * Normalize a raw `/phr/completeness` payload into a defensive
 * {@link PhrCompleteness}. Pure: the score is clamped to `[0, 1]`, and only
 * recognized USCDI class names are retained, so a malformed payload can never
 * crash the meter.
 */
export function parsePhrCompleteness(raw: unknown): PhrCompleteness {
  const root =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const rawScore = typeof root.score === "number" ? root.score : 0;
  const score = Number.isFinite(rawScore)
    ? Math.min(1, Math.max(0, rawScore))
    : 0;
  return {
    score,
    present: coerceClassList(root.present),
    missing: coerceClassList(root.missing),
  };
}

/**
 * Fetch the USCDI completeness score for the owner's PHR. Only call this when
 * the `completeness_meter` capability is effective; the endpoint returns 404
 * when the flag is off (Requirement 18.1).
 */
export async function getPhrCompleteness(): Promise<PhrCompleteness> {
  const { data } = await api.get<unknown>("/api/v1/phr/completeness");
  return parsePhrCompleteness(data);
}

// ---------------------------------------------------------------------------
// Capability gating (personal-health-record Requirement 18.1)
// ---------------------------------------------------------------------------

/**
 * Effective PHR capability flags as projected by `GET /api/v1/phr/capabilities`.
 * The backend resolves every sub-capability as `master AND sub`, so when the
 * master `enhanced` flag is off every other flag is `false` and the web client
 * hides all enhanced surfaces, preserving the legacy PHR view (Requirement 18.1).
 *
 * The web client treats these as the single source of truth for which enhanced
 * surfaces (badges, completeness meter, OCR import, export, sharing, reminders)
 * are shown.
 */
export type PhrCapabilityFlags = {
  enhanced: boolean;
  consent_enforcement: boolean;
  reconciliation: boolean;
  allergy_aware_ddi: boolean;
  ocr_import: boolean;
  observations: boolean;
  export: boolean;
  sharing: boolean;
  reminders: boolean;
  completeness_meter: boolean;
};

/** The flag keys, in capability order. */
const PHR_CAPABILITY_KEYS: readonly (keyof PhrCapabilityFlags)[] = [
  "enhanced",
  "consent_enforcement",
  "reconciliation",
  "allergy_aware_ddi",
  "ocr_import",
  "observations",
  "export",
  "sharing",
  "reminders",
  "completeness_meter",
] as const;

/**
 * The safe default: every capability off. This is the legacy behavior and is
 * also the fallback used whenever the capabilities response is missing,
 * malformed, or the request fails — fail closed so a transient error never
 * exposes a flagged-off surface (Requirement 18.1).
 */
export const DEFAULT_PHR_CAPABILITIES: PhrCapabilityFlags = {
  enhanced: false,
  consent_enforcement: false,
  reconciliation: false,
  allergy_aware_ddi: false,
  ocr_import: false,
  observations: false,
  export: false,
  sharing: false,
  reminders: false,
  completeness_meter: false,
};

/**
 * Normalize a raw `/phr/capabilities` payload into a fully-defaulted flag set.
 *
 * Pure and defensive: any missing or non-boolean flag defaults to `false`, and
 * a sub-capability is forced off whenever `enhanced` is off, mirroring the
 * server's `master AND sub` resolution so the client never shows an enhanced
 * surface the backend would reject (Requirement 18.1).
 */
export function parsePhrCapabilities(raw: unknown): PhrCapabilityFlags {
  const root =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  // The endpoint wraps flags under `{ "flags": {...} }`; tolerate a bare object too.
  const flagsSource =
    root.flags && typeof root.flags === "object"
      ? (root.flags as Record<string, unknown>)
      : root;

  const enhanced = flagsSource.enhanced === true;
  const result: PhrCapabilityFlags = { ...DEFAULT_PHR_CAPABILITIES };
  for (const key of PHR_CAPABILITY_KEYS) {
    if (key === "enhanced") {
      result.enhanced = enhanced;
      continue;
    }
    // `master AND sub`: a sub-flag is only effective when `enhanced` is on.
    result[key] = enhanced && flagsSource[key] === true;
  }
  return result;
}

/**
 * Fetch the effective PHR capability flags. On any error the call resolves to
 * {@link DEFAULT_PHR_CAPABILITIES} (all off) so the UI fails closed to the
 * legacy view rather than surfacing flagged-off enhanced surfaces.
 */
export async function getPhrCapabilities(): Promise<PhrCapabilityFlags> {
  try {
    const { data } = await api.get<unknown>("/api/v1/phr/capabilities");
    return parsePhrCapabilities(data);
  } catch {
    return { ...DEFAULT_PHR_CAPABILITIES };
  }
}

// ---------------------------------------------------------------------------
// OCR import: candidate → confirm (personal-health-record Requirement 9)
// ---------------------------------------------------------------------------

/**
 * A single OCR-extracted candidate medication awaiting human confirmation
 * (Requirement 9.1–9.3). Every row is proposal-only. The server binds the
 * complete scan set to an owner-bound review token and accepts only rows the
 * person explicitly confirms; `requires_manual_confirm` is presentation
 * metadata, never a client-side bypass switch.
 */
export type PhrOcrCandidate = {
  candidate_id: string;
  name: string;
  dose: string;
  frequency: string;
  ocr_confidence?: number | null;
  requires_manual_confirm: boolean;
  confirmed: boolean;
  /** Read-only corrected-text offsets for a reviewed OCR proposal. */
  source_coordinates?: PhrOcrSourceCoordinate[];
};

export type PhrOcrSourceCoordinate = {
  coordinate_system: "corrected_text_codepoint_offset";
  start: number;
  end: number;
};

/** Response of `POST /phr/import/ocr/scan`: nothing is committed (Req 9.1). */
export type PhrOcrScanResult = {
  committed: boolean;
  candidates: PhrOcrCandidate[];
  reviewToken: string;
  processingDisclosure: {
    providerCategory:
      | "configured_ocr_service"
      | "google_cloud_vision"
      | "local_tesseract";
    humanConfirmationRequired: boolean;
  } | null;
};

function coerceOcrSourceCoordinate(
  raw: unknown,
): PhrOcrSourceCoordinate | null {
  const value =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const start = value.start;
  const end = value.end;
  if (
    value.coordinate_system !== "corrected_text_codepoint_offset" ||
    typeof start !== "number" ||
    typeof end !== "number" ||
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    end < start
  ) {
    return null;
  }
  return {
    coordinate_system: "corrected_text_codepoint_offset",
    start,
    end,
  };
}

function coerceOcrCandidate(raw: unknown): PhrOcrCandidate {
  const root =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const confidence =
    typeof root.ocr_confidence === "number" &&
    Number.isFinite(root.ocr_confidence)
      ? Math.min(1, Math.max(0, root.ocr_confidence))
      : null;
  const sourceCoordinates = Array.isArray(root.source_coordinates)
    ? root.source_coordinates
        .map(coerceOcrSourceCoordinate)
        .filter(
          (coordinate): coordinate is PhrOcrSourceCoordinate =>
            coordinate !== null,
        )
        .slice(0, 24)
    : [];
  return {
    candidate_id:
      typeof root.candidate_id === "string" ? root.candidate_id : "",
    name: typeof root.name === "string" ? root.name : "",
    dose: typeof root.dose === "string" ? root.dose : "",
    frequency: typeof root.frequency === "string" ? root.frequency : "",
    ocr_confidence: confidence,
    requires_manual_confirm: root.requires_manual_confirm === true,
    confirmed: root.confirmed === true,
    source_coordinates: sourceCoordinates,
  };
}

/**
 * Upload a document for OCR extraction. Returns candidate medications only —
 * the backend commits nothing here (Requirement 9.1, Correctness Property 14).
 */
export async function scanPhrOcr(file: File): Promise<PhrOcrScanResult> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post<unknown>("/api/v1/phr/import/ocr/scan", form);
  const root =
    data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  const candidates = Array.isArray(root.candidates)
    ? root.candidates.map(coerceOcrCandidate)
    : [];
  const reviewToken =
    typeof root.review_token === "string" ? root.review_token : "";
  if (!reviewToken || candidates.some((candidate) => !candidate.candidate_id)) {
    throw new Error("OCR review session is unavailable");
  }
  const disclosure =
    root.processing_disclosure && typeof root.processing_disclosure === "object"
      ? (root.processing_disclosure as Record<string, unknown>)
      : null;
  const providerCategory = disclosure?.provider_category;
  return {
    committed: root.committed === true,
    candidates,
    reviewToken,
    processingDisclosure:
      providerCategory === "configured_ocr_service" ||
      providerCategory === "google_cloud_vision" ||
      providerCategory === "local_tesseract"
        ? {
            providerCategory,
            humanConfirmationRequired:
              disclosure?.human_confirmation_required === true,
          }
        : null,
  };
}

/**
 * Commit the user-reviewed candidate list as `ocr`-sourced medications
 * (Requirement 9.2, 9.4). `reviewCandidateIds` retains the full signed scan
 * set, including discarded rows, while `medications` contains only the
 * explicitly accepted rows. This prevents a client from injecting a new OCR
 * candidate after review without turning discards into stored data.
 */
export async function confirmPhrOcr(
  medications: PhrOcrCandidate[],
  reviewToken: string,
  reviewCandidateIds: string[],
): Promise<PhrRecord> {
  const { data } = await api.post<PhrRecord>("/api/v1/phr/import/ocr/confirm", {
    medications,
    review_token: reviewToken,
    review_candidate_ids: reviewCandidateIds,
  });
  return data;
}

// ---------------------------------------------------------------------------
// FHIR export download (personal-health-record Requirement 11)
// ---------------------------------------------------------------------------

/** Selectable FHIR export scopes (Requirement 11.4). */
export type PhrExportResource =
  | "all"
  | "patient"
  | "allergy"
  | "condition"
  | "medication"
  | "observation";

export const PHR_EXPORT_RESOURCES: readonly PhrExportResource[] = [
  "all",
  "patient",
  "allergy",
  "condition",
  "medication",
  "observation",
] as const;

/**
 * Download the owner's PHR as a FHIR R4 bundle (`application/fhir+json`) for the
 * requested resource scope (Requirement 11.1–11.4). Triggers a browser download
 * and resolves once the download has been initiated.
 */
export async function exportPhr(
  resource: PhrExportResource = "all",
): Promise<void> {
  const { data } = await api.get<Blob>("/api/v1/phr/export", {
    params: { resource },
    responseType: "blob",
  });
  if (typeof window === "undefined") return;
  const blob =
    data instanceof Blob
      ? data
      : new Blob([JSON.stringify(data)], { type: "application/fhir+json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `phr-export-${resource}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Read-only sharing (personal-health-record Requirement 12)
// ---------------------------------------------------------------------------

/** Scope of a read-only share link (Requirement 12.1). */
export type PhrShareScope = "full" | "emergency_card";

/** A created share link as returned by `POST /phr/share`. */
export type PhrShare = {
  share_id: number;
  share_token: string;
  scope: PhrShareScope;
  expires_at?: string | null;
};

/**
 * Create a read-only share link (Requirement 12.1, 12.3). Rejected (428) when
 * sharing consent is absent and consent enforcement is on; the caller surfaces
 * the server message.
 */
export async function createPhrShare(
  scope: PhrShareScope = "full",
  expiresInDays?: number | null,
): Promise<PhrShare> {
  const payload: { scope: PhrShareScope; expires_in_days?: number } = {
    scope,
  };
  if (expiresInDays != null) payload.expires_in_days = expiresInDays;
  const { data } = await api.post<PhrShare>("/api/v1/phr/share", payload);
  return data;
}

/** Revoke a previously created share link (Requirement 12.3). */
export async function revokePhrShare(shareId: number): Promise<void> {
  await api.delete(`/api/v1/phr/share/${shareId}`);
}

/**
 * Reads a public, read-only PHR share by opaque capability token.
 *
 * This endpoint intentionally needs no authenticated session. Callers must
 * never log, persist, or render the token; the public viewer applies a strict
 * field whitelist before displaying the untyped server envelope.
 */
export async function getPublicPhrShare(token: string): Promise<unknown> {
  const { data } = await api.get<unknown>(
    `/api/v1/phr/shared/${encodeURIComponent(token)}`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Emergency card (personal-health-record Requirement 13)
// ---------------------------------------------------------------------------

/** Owner-selectable emergency-card field-inclusion keys (Requirement 13.3). */
export type PhrEmergencyCardField =
  | "allergies"
  | "current_medications"
  | "conditions"
  | "blood_type"
  | "emergency_contact";

export const PHR_EMERGENCY_CARD_FIELDS: readonly PhrEmergencyCardField[] = [
  "allergies",
  "current_medications",
  "conditions",
  "blood_type",
  "emergency_contact",
] as const;

/** Projected emergency card returned by `GET /phr/emergency-card`. */
export type PhrEmergencyCard = {
  disclaimer?: { vi?: string; en?: string };
  allergies?: { name: string; severity: string; reaction: string }[];
  current_medications?: { name: string; dose: string }[];
  conditions?: { name: string; status: string }[];
  blood_type?: string;
  emergency_contact?: { name: string; phone: string };
  hedge?: { vi?: string; en?: string } | string;
};

/**
 * Fetch the owner's emergency-card projection (Requirement 13.1–13.5). Only call
 * when the `enhanced` capability is effective; the endpoint returns 404 when the
 * master flag is off (Requirement 18.1).
 */
export async function getPhrEmergencyCard(): Promise<PhrEmergencyCard> {
  const { data } = await api.get<PhrEmergencyCard>(
    "/api/v1/phr/emergency-card",
  );
  return data && typeof data === "object" ? data : {};
}

// ---------------------------------------------------------------------------
// Reminders / refill / caregiver nudge (personal-health-record Requirement 14)
// ---------------------------------------------------------------------------

/** A configured medication reminder as returned by `GET /phr/reminders`. */
export type PhrReminder = {
  id: number;
  medication_entry_id: string;
  schedule?: Record<string, unknown> | null;
  remaining_supply?: number | null;
  refill_threshold?: number | null;
  caregiver_nudge_enabled?: boolean;
  medication_due?: boolean;
  refill_due?: boolean;
};

/** Payload for `POST /phr/reminders` (Requirement 14.1–14.5). */
export type PhrReminderCreate = {
  medication_entry_id: string;
  schedule?: Record<string, unknown>;
  remaining_supply?: number | null;
  refill_threshold?: number | null;
  caregiver_nudge_enabled?: boolean;
};

/** List the owner's configured reminders with firing decisions (Req 14). */
export async function listPhrReminders(): Promise<PhrReminder[]> {
  const { data } = await api.get<unknown>("/api/v1/phr/reminders");
  const root =
    data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  return Array.isArray(root.reminders) ? (root.reminders as PhrReminder[]) : [];
}

/**
 * Configure a reminder for a current medication with a defined frequency
 * (Requirement 14.1). The server rejects (422) non-current meds or meds without
 * a frequency; the caller surfaces the message.
 */
export async function createPhrReminder(
  payload: PhrReminderCreate,
): Promise<PhrReminder> {
  const { data } = await api.post<PhrReminder>("/api/v1/phr/reminders", {
    medication_entry_id: payload.medication_entry_id,
    schedule: payload.schedule ?? {},
    remaining_supply: payload.remaining_supply ?? null,
    refill_threshold: payload.refill_threshold ?? null,
    caregiver_nudge_enabled: payload.caregiver_nudge_enabled ?? false,
  });
  return data;
}
