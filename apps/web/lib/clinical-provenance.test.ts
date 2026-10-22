import { describe, expect, it } from "vitest";
import { ClinicalProvenanceHelper, type ClinicalProvenanceRecord } from "./clinical-provenance";

describe("ClinicalProvenanceHelper Acquisition Provenance", () => {
  it("determines clinical authoritativeness based on source type and verification flag", () => {
    const emrRecord: ClinicalProvenanceRecord = {
      factId: "f1",
      sourceType: "EMR_INTEGRATION",
      sourceNameVi: "Bệnh viện Bạch Mai",
      sourceNameEn: "Bach Mai Hospital",
      acquiredAt: new Date().toISOString(),
      contentHash: "hash-123",
      confidenceScore: 0.99,
      isVerified: true,
    };
    expect(ClinicalProvenanceHelper.isClinicallyAuthoritative(emrRecord)).toBe(true);

    const patientRecord: ClinicalProvenanceRecord = {
      factId: "f2",
      sourceType: "PATIENT_PORTAL",
      sourceNameVi: "Bệnh nhân tự nhập",
      sourceNameEn: "Patient Self-Reported",
      acquiredAt: new Date().toISOString(),
      contentHash: "hash-456",
      confidenceScore: 0.7,
      isVerified: false,
    };
    expect(ClinicalProvenanceHelper.isClinicallyAuthoritative(patientRecord)).toBe(false);
  });

  it("returns localized source badges", () => {
    const badgeVi = ClinicalProvenanceHelper.getSourceBadge("DOCUMENT_OCR", false);
    expect(badgeVi.label).toBe("Đơn thuốc quét");

    const badgeEn = ClinicalProvenanceHelper.getSourceBadge("DOCUMENT_OCR", true);
    expect(badgeEn.label).toBe("Prescription Scan");
  });
});
