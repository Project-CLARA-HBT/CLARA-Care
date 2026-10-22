/**
 * Clinical Source & Data Acquisition Provenance Model.
 *
 * Spec: PH10 / A05 (Web UX).
 * Enforces:
 * 1. Tracking acquisition origin for every displayed medical observation (EHR, OCR, Patient, Device).
 * 2. Visual confidence indicators and provenance badges in clinical dossier.
 * 3. Non-repudiation link to raw artifact hashes.
 */

export type AcquisitionSourceType =
  | "EMR_INTEGRATION"
  | "DOCUMENT_OCR"
  | "SCRIBE_CONSULTATION"
  | "PATIENT_PORTAL"
  | "WEARABLE_DEVICE";

export interface ClinicalProvenanceRecord {
  factId: string;
  sourceType: AcquisitionSourceType;
  sourceNameVi: string;
  sourceNameEn: string;
  acquiredAt: string;
  contentHash: string;
  confidenceScore: number;
  practitionerName?: string;
  isVerified: boolean;
}

export class ClinicalProvenanceHelper {
  static getSourceBadge(sourceType: AcquisitionSourceType, isEnglish: boolean = false): {
    label: string;
    tone: "info" | "success" | "warn" | "neutral";
  } {
    switch (sourceType) {
      case "EMR_INTEGRATION":
        return { label: isEnglish ? "Hospital EMR" : "Bệnh viện liên thông", tone: "success" };
      case "DOCUMENT_OCR":
        return { label: isEnglish ? "Prescription Scan" : "Đơn thuốc quét", tone: "info" };
      case "SCRIBE_CONSULTATION":
        return { label: isEnglish ? "Doctor Consultation" : "Khám bệnh trực tiếp", tone: "success" };
      case "PATIENT_PORTAL":
        return { label: isEnglish ? "Self-Reported" : "Tự khai báo", tone: "warn" };
      case "WEARABLE_DEVICE":
        return { label: isEnglish ? "Wearable Sensor" : "Thiết bị đeo", tone: "info" };
    }
  }

  static isClinicallyAuthoritative(record: ClinicalProvenanceRecord): boolean {
    return (
      (record.sourceType === "EMR_INTEGRATION" || record.sourceType === "SCRIBE_CONSULTATION") &&
      record.isVerified
    );
  }
}
