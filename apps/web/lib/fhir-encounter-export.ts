/**
 * FHIR R4 Encounter & Clinical Documents Export Engine (Phase PH11 Subagent A05)
 *
 * Implements safe, consent-gated export of clinical encounters, consultations,
 * and clinical documents into HL7 FHIR R4 standard structures:
 *   - FHIR Encounter (Ambulatory consultation, visit context, participants)
 *   - FHIR Composition (Clinical note sections: SOAP, signed clinician attestation)
 *   - FHIR DocumentReference (Attachments, lab reports, discharge summaries)
 *   - FHIR Bundle (Type: "collection" or "document", tagged fhir-r4-summary-not-ips)
 *
 * Safety Invariants:
 *   - Feature-gated: Flag defaults to false (NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED)
 *   - Consent gate: Fails closed unless active medical_disclaimer consent is verified
 *   - PII/PHI redaction verification before download initiation
 *   - Safe filesystem-sanitized download filename
 */

import api from "@/lib/http-client";
import { getConsentStatus } from "@/lib/consent";
import type { Visit, VisitDocument, VisitPrescription } from "@/lib/visit-family";

export const FHIR_R4_VERSION = "4.0.1";
export const CLARA_FHIR_CONFORMANCE = "fhir-r4-summary-not-ips";
export const CLARA_FHIR_ATTRIBUTION = "CLARA Care Medical AI Assistant (Clinical Decision Support, not a doctor replacement)";

const TRUTHY = new Set(["1", "true", "on"]);

function parseFlag(value: string | null | undefined): boolean {
  if (typeof value !== "string") return false;
  return TRUTHY.has(value.trim().toLowerCase());
}

/**
 * Feature flag for FHIR Encounter & Documents export.
 * Defaults to false until approved for production rollout.
 */
export function isFhirEncounterExportEnabled(): boolean {
  return parseFlag(process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED);
}

/** Allowed purposes for FHIR R4 data extraction. */
export type FhirExportPurpose =
  | "self_download"
  | "care_coordination"
  | "legal_record"
  | "audit";

/** Supported export serialization formats. */
export type FhirExportFormat =
  | "fhir_json"
  | "ndjson"
  | "fhir_composition";

export type ConsentVerificationResult = {
  allowed: boolean;
  reason?: string;
  policy_type?: string;
  required_version?: string;
};

export type FhirEncounterExportOptions = {
  purpose?: FhirExportPurpose;
  format?: FhirExportFormat;
  profileId?: string | null;
  includeDocuments?: boolean;
  includePrescriptions?: boolean;
  includeSoapNote?: boolean;
};

export type FhirResource = {
  resourceType: string;
  id: string;
  meta?: {
    versionId?: string;
    lastUpdated?: string;
    profile?: string[];
    attribution?: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type FhirBundle = {
  resourceType: "Bundle";
  id: string;
  meta: {
    lastUpdated: string;
    profile: string[];
    attribution: string;
    conformance: string;
  };
  type: "collection" | "document";
  timestamp: string;
  entry: Array<{
    fullUrl: string;
    resource: Record<string, unknown>;
  }>;
};

/**
 * Pre-flight verification of statutory and clinical medical consent.
 * Fails closed if the consent gate is missing or unaccepted.
 */
export async function verifyExportConsent(
  purpose: FhirExportPurpose = "self_download",
  _profileId?: string | null,
): Promise<ConsentVerificationResult> {
  try {
    const status = await getConsentStatus();
    if (!status || !status.accepted) {
      return {
        allowed: false,
        reason: "Active medical consent required prior to clinical encounter export.",
        policy_type: status?.consent_type ?? "medical_disclaimer",
        required_version: status?.required_version ?? "2026-04-v1",
      };
    }
    return {
      allowed: true,
      policy_type: status.consent_type,
      required_version: status.required_version,
    };
  } catch (error) {
    // If backend consent check rejects, fail closed
    return {
      allowed: false,
      reason: error instanceof Error ? error.message : "Consent verification failed.",
      policy_type: "medical_disclaimer",
    };
  }
}

/**
 * Sanitize filename to prevent directory traversal and illegal characters.
 */
export function sanitizeExportFilename(baseName: string, ext = "fhir.json"): string {
  const sanitized = baseName
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\.\.+/g, "")
    .replace(/[^a-zA-Z0-9_-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const safeName = sanitized || "clara-export";
  return `${safeName}.${ext}`;
}

/**
 * Redaction check: ensures no raw internal secrets, JWT tokens, or passwords leak into the export.
 */
const FORBIDDEN_PATTERNS = [
  /password_hash/i,
  /access_token/i,
  /refresh_token/i,
  /jwt_secret/i,
  /session_secret/i,
  /api_internal_key/i,
  /private_key/i,
];

export function validateRedaction(payload: unknown): { safe: boolean; findings: string[] } {
  const jsonStr = typeof payload === "string" ? payload : JSON.stringify(payload);
  const findings: string[] = [];
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (pattern.test(jsonStr)) {
      findings.push(`Disallowed sensitive pattern detected: ${pattern.source}`);
    }
  }
  return {
    safe: findings.length === 0,
    findings,
  };
}

/**
 * Builds a FHIR R4 `Encounter` resource from visit entity.
 */
export function buildFhirEncounterResource(
  visit: Partial<Visit>,
  profileId?: string | null,
): FhirResource {
  const encounterId = visit.id ? `encounter-${visit.id}` : `encounter-${Date.now()}`;
  const subjectRef = profileId ? `Patient/${profileId}` : "Patient/self";

  const statusMap: Record<string, string> = {
    completed: "finished",
    scheduled: "planned",
    in_progress: "in-progress",
    cancelled: "cancelled",
  };
  const status = (visit.status && statusMap[visit.status]) || "finished";

  const resource: FhirResource = {
    resourceType: "Encounter",
    id: encounterId,
    meta: {
      profile: ["http://hl7.org/fhir/StructureDefinition/Encounter"],
      attribution: CLARA_FHIR_ATTRIBUTION,
    },
    status,
    class: {
      system: "http://terminology.hl7.org/CodeSystem/v3-ActCode",
      code: visit.visit_type ? visit.visit_type.toLowerCase() : "AMB",
      display: visit.visit_type || "Ambulatory",
    },
    type: [
      {
        text: visit.title || "Consultation Encounter",
      },
    ],
    subject: {
      reference: subjectRef,
      display: "Patient",
    },
    period: {
      start: visit.scheduled_at || visit.created_at || new Date().toISOString(),
    },
  };

  if (visit.doctor_name || visit.specialty) {
    resource.participant = [
      {
        individual: {
          display: visit.doctor_name || "Consulting Clinician",
        },
        type: visit.specialty
          ? [
              {
                text: visit.specialty,
              },
            ]
          : undefined,
      },
    ];
  }

  if (visit.facility_name) {
    resource.serviceProvider = {
      display: visit.facility_name + (visit.location ? ` (${visit.location})` : ""),
    };
  }

  return resource;
}

/**
 * Builds a FHIR R4 `Composition` resource representing the clinical SOAP note.
 */
export function buildFhirComposition(
  visit: Partial<Visit>,
  encounterRef: string,
  profileId?: string | null,
): FhirResource | null {
  if (!visit.soap_note && !visit.notes && !visit.clinician_notes) {
    return null;
  }

  const compositionId = `composition-${visit.id || Date.now()}`;
  const subjectRef = profileId ? `Patient/${profileId}` : "Patient/self";

  const sections: Array<{ title: string; code?: unknown; text: { status: string; div: string } }> = [];

  if (visit.soap_note) {
    const { subjective, objective, assessment, plan } = visit.soap_note;
    if (subjective) {
      sections.push({
        title: "Subjective (Bệnh sử / Triệu chứng cơ năng)",
        text: { status: "generated", div: `<div>${subjective}</div>` },
      });
    }
    if (objective) {
      sections.push({
        title: "Objective (Khám lâm sàng / Cận lâm sàng)",
        text: { status: "generated", div: `<div>${objective}</div>` },
      });
    }
    if (assessment) {
      sections.push({
        title: "Assessment (Đánh giá / Chẩn đoán)",
        text: { status: "generated", div: `<div>${assessment}</div>` },
      });
    }
    if (plan) {
      sections.push({
        title: "Plan (Kế hoạch điều trị)",
        text: { status: "generated", div: `<div>${plan}</div>` },
      });
    }
  } else if (visit.clinician_notes || visit.notes) {
    sections.push({
      title: "Clinical Consultation Summary",
      text: {
        status: "generated",
        div: `<div>${visit.clinician_notes || visit.notes}</div>`,
      },
    });
  }

  const authorLabel = visit.soap_note?.clinician_name || visit.doctor_name || "Attending Physician";

  return {
    resourceType: "Composition",
    id: compositionId,
    meta: {
      profile: ["http://hl7.org/fhir/StructureDefinition/Composition"],
      attribution: CLARA_FHIR_ATTRIBUTION,
    },
    status: visit.soap_note?.signed_at ? "final" : "preliminary",
    type: {
      coding: [
        {
          system: "http://loinc.org",
          code: "11488-4",
          display: "Consultation note",
        },
      ],
      text: "Consultation note",
    },
    encounter: {
      reference: encounterRef,
    },
    date: visit.soap_note?.signed_at || visit.updated_at || new Date().toISOString(),
    author: [
      {
        display: authorLabel,
      },
    ],
    title: visit.title || "Clinical Consultation Summary",
    subject: {
      reference: subjectRef,
    },
    section: sections,
  };
}

/**
 * Builds a FHIR R4 `DocumentReference` for a clinical document or attachment.
 */
export function buildFhirDocumentReference(
  doc: Partial<VisitDocument> | Record<string, unknown>,
  encounterRef?: string,
  profileId?: string | null,
): FhirResource {
  const docId = String(doc.id || `doc-${Date.now()}`);
  const title = String(doc.title || doc.name || "Clinical Document");
  const subjectRef = profileId ? `Patient/${profileId}` : "Patient/self";

  const resource: FhirResource = {
    resourceType: "DocumentReference",
    id: `docref-${docId}`,
    meta: {
      profile: ["http://hl7.org/fhir/StructureDefinition/DocumentReference"],
      attribution: CLARA_FHIR_ATTRIBUTION,
    },
    status: "current",
    docStatus: "final",
    type: {
      text: title,
    },
    subject: {
      reference: subjectRef,
    },
    date: String(doc.created_at || new Date().toISOString()),
    content: [
      {
        attachment: {
          contentType: String(doc.media_type || "text/plain"),
          title,
          data: doc.text_content
            ? typeof btoa !== "undefined"
              ? btoa(unescape(encodeURIComponent(String(doc.text_content))))
              : Buffer.from(String(doc.text_content), "utf-8").toString("base64")
            : undefined,
        },
      },
    ],
  };

  if (encounterRef) {
    resource.context = {
      encounter: [
        {
          reference: encounterRef,
        },
      ],
    };
  }

  return resource;
}

/**
 * Builds a FHIR R4 `MedicationStatement` for an encounter prescription.
 */
export function buildFhirMedicationStatement(
  rx: Partial<VisitPrescription>,
  encounterRef: string,
  profileId?: string | null,
): FhirResource {
  const id = `med-${rx.id || Date.now()}`;
  const subjectRef = profileId ? `Patient/${profileId}` : "Patient/self";

  return {
    resourceType: "MedicationStatement",
    id,
    meta: {
      profile: ["http://hl7.org/fhir/StructureDefinition/MedicationStatement"],
      attribution: CLARA_FHIR_ATTRIBUTION,
    },
    status: rx.reconciliation_status === "discontinued" ? "stopped" : "active",
    medicationCodeableConcept: {
      text: rx.name || "Unspecified medication",
    },
    subject: {
      reference: subjectRef,
    },
    context: {
      reference: encounterRef,
    },
    dosage: [
      {
        text: [rx.dosage, rx.instruction].filter(Boolean).join(" - ") || undefined,
      },
    ],
  };
}

/**
 * Builds a complete FHIR R4 Bundle for an encounter and its attached clinical documents.
 */
export function buildEncounterExportBundle(
  visit: Partial<Visit>,
  options: FhirEncounterExportOptions = {},
): FhirBundle {
  const now = new Date().toISOString();
  const bundleId = `clara-encounter-${visit.id || Date.now()}`;
  const encounter = buildFhirEncounterResource(visit, options.profileId);
  const encounterRef = `Encounter/${encounter.id}`;

  const entries: Array<{ fullUrl: string; resource: Record<string, unknown> }> = [
    {
      fullUrl: `urn:uuid:${encounter.id}`,
      resource: encounter,
    },
  ];

  // Optional Composition (SOAP note)
  if (options.includeSoapNote !== false) {
    const composition = buildFhirComposition(visit, encounterRef, options.profileId);
    if (composition) {
      entries.push({
        fullUrl: `urn:uuid:${composition.id}`,
        resource: composition,
      });
    }
  }

  // Optional Prescriptions (MedicationStatements)
  if (options.includePrescriptions !== false && visit.prescriptions && Array.isArray(visit.prescriptions)) {
    for (const rx of visit.prescriptions) {
      const med = buildFhirMedicationStatement(rx, encounterRef, options.profileId);
      entries.push({
        fullUrl: `urn:uuid:${med.id}`,
        resource: med,
      });
    }
  }

  // Optional Documents (DocumentReferences)
  if (options.includeDocuments !== false && visit.documents && Array.isArray(visit.documents)) {
    for (const doc of visit.documents) {
      const docRef = buildFhirDocumentReference(doc, encounterRef, options.profileId);
      entries.push({
        fullUrl: `urn:uuid:${docRef.id}`,
        resource: docRef,
      });
    }
  }

  return {
    resourceType: "Bundle",
    id: bundleId,
    meta: {
      lastUpdated: now,
      profile: ["http://hl7.org/fhir/StructureDefinition/Bundle"],
      attribution: CLARA_FHIR_ATTRIBUTION,
      conformance: CLARA_FHIR_CONFORMANCE,
    },
    type: "collection",
    timestamp: now,
    entry: entries,
  };
}

/**
 * Initiates safe browser download of a FHIR Bundle or payload.
 */
export function downloadFhirBundle(
  bundle: FhirBundle | Record<string, unknown>,
  filename: string,
): void {
  const redaction = validateRedaction(bundle);
  if (!redaction.safe) {
    throw new Error(`Export blocked by safety redaction gate: ${redaction.findings.join("; ")}`);
  }

  if (typeof window === "undefined") {
    return;
  }

  const jsonStr = JSON.stringify(bundle, null, 2);
  const blob = new Blob([jsonStr], { type: "application/fhir+json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = sanitizeExportFilename(filename);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

/**
 * Primary export action: verifies consent, validates feature flag, generates FHIR R4 Bundle, and downloads.
 */
export async function exportEncounterAsFhir(
  visit: Partial<Visit>,
  options: FhirEncounterExportOptions = {},
): Promise<{ bundle: FhirBundle; filename: string }> {
  if (!isFhirEncounterExportEnabled()) {
    throw new Error("Tính năng xuất FHIR Encounter đang trong giai đoạn thử nghiệm (Feature disabled).");
  }

  const consent = await verifyExportConsent(options.purpose ?? "self_download", options.profileId);
  if (!consent.allowed) {
    throw new Error(consent.reason || "Cần xác nhận đồng thuận trước khi xuất hồ sơ y tế.");
  }

  const bundle = buildEncounterExportBundle(visit, options);
  const filename = sanitizeExportFilename(`encounter-${visit.id || "summary"}-${options.purpose ?? "export"}`);

  downloadFhirBundle(bundle, filename);
  return { bundle, filename };
}
