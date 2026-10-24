import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  buildEncounterExportBundle,
  buildFhirComposition,
  buildFhirDocumentReference,
  buildFhirEncounterResource,
  buildFhirMedicationStatement,
  CLARA_FHIR_ATTRIBUTION,
  CLARA_FHIR_CONFORMANCE,
  FHIR_R4_VERSION,
  isFhirEncounterExportEnabled,
  sanitizeExportFilename,
  validateRedaction,
  verifyExportConsent,
  type FhirEncounterExportOptions,
} from "./fhir-encounter-export";
import * as consentModule from "./consent";
import type { Visit, VisitDocument, VisitPrescription } from "./visit-family";

describe("FHIR Encounter & Documents Export Engine", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.restoreAllMocks();
  });

  describe("Feature Flag Guarding", () => {
    it("defaults to false when environment variable is unset", () => {
      delete process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED;
      expect(isFhirEncounterExportEnabled()).toBe(false);
    });

    it("evaluates to false when explicitly set to 'false' or empty string", () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "false";
      expect(isFhirEncounterExportEnabled()).toBe(false);

      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "";
      expect(isFhirEncounterExportEnabled()).toBe(false);
    });

    it("evaluates to true only when set to 'true', '1', or 'on'", () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      expect(isFhirEncounterExportEnabled()).toBe(true);

      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "1";
      expect(isFhirEncounterExportEnabled()).toBe(true);

      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "on";
      expect(isFhirEncounterExportEnabled()).toBe(true);
    });
  });

  describe("verifyExportConsent (Consent Gate Invariant)", () => {
    it("allows export when medical consent is active and accepted", async () => {
      vi.spyOn(consentModule, "getConsentStatus").mockResolvedValue({
        consent_type: "medical_disclaimer",
        required_version: "2026-04-v1",
        accepted: true,
        accepted_version: "2026-04-v1",
        accepted_at: new Date().toISOString(),
      });

      const result = await verifyExportConsent("self_download");
      expect(result.allowed).toBe(true);
      expect(result.policy_type).toBe("medical_disclaimer");
      expect(result.required_version).toBe("2026-04-v1");
    });

    it("denies export when medical consent is missing or not accepted", async () => {
      vi.spyOn(consentModule, "getConsentStatus").mockResolvedValue({
        consent_type: "medical_disclaimer",
        required_version: "2026-04-v1",
        accepted: false,
      });

      const result = await verifyExportConsent("care_coordination");
      expect(result.allowed).toBe(false);
      expect(result.reason).toContain("Active medical consent required");
    });

    it("fails closed (denies) when consent service errors", async () => {
      vi.spyOn(consentModule, "getConsentStatus").mockRejectedValue(new Error("Network timeout"));

      const result = await verifyExportConsent("legal_record");
      expect(result.allowed).toBe(false);
      expect(result.reason).toContain("Network timeout");
    });
  });

  describe("sanitizeExportFilename (Filesystem Security)", () => {
    it("cleans standard filenames with fhir.json extension", () => {
      expect(sanitizeExportFilename("encounter-123")).toBe("encounter-123.fhir.json");
    });

    it("prevents directory traversal attempts", () => {
      const sanitized = sanitizeExportFilename("../../../etc/passwd");
      expect(sanitized).not.toContain("..");
      expect(sanitized).not.toContain("/");
      expect(sanitized).toBe("etc-passwd.fhir.json");
    });

    it("sanitizes spaces, illegal characters, and slashes", () => {
      const sanitized = sanitizeExportFilename("Visit #42 (Dr. Hoang Nguyen)?*<|>");
      expect(sanitized).toMatch(/^[a-zA-Z0-9_-]+\.fhir\.json$/);
      expect(sanitized).toBe("Visit-42-Dr-Hoang-Nguyen.fhir.json");
    });

    it("falls back to default name if string becomes empty", () => {
      expect(sanitizeExportFilename("")).toBe("clara-export.fhir.json");
      expect(sanitizeExportFilename("???///:::")).toBe("clara-export.fhir.json");
    });
  });

  describe("validateRedaction (Safety & Privacy Gate)", () => {
    it("passes safe clinical payloads", () => {
      const safePayload = {
        resourceType: "Encounter",
        id: "encounter-1",
        doctor: "Dr. Nguyen",
        diagnosis: "Essential hypertension",
      };
      const verdict = validateRedaction(safePayload);
      expect(verdict.safe).toBe(true);
      expect(verdict.findings).toHaveLength(0);
    });

    it("rejects payloads containing access tokens or passwords", () => {
      const dirtyPayload = {
        resourceType: "Encounter",
        id: "encounter-1",
        user_credentials: {
          access_token: "secret-token-12345",
          password_hash: "$2b$12$e8f...",
        },
      };
      const verdict = validateRedaction(dirtyPayload);
      expect(verdict.safe).toBe(false);
      expect(verdict.findings.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("FHIR R4 Resource Builders", () => {
    const mockVisit: Partial<Visit> = {
      id: "v-99",
      title: "Tim mach tong quat (Cardiology Follow-up)",
      visit_type: "Specialty",
      scheduled_at: "2026-10-24T08:30:00Z",
      status: "completed",
      doctor_name: "Dr. Le Minh Tri",
      specialty: "Noi tim mach",
      facility_name: "Benh vien Bach Mai",
      location: "Tang 3, Phong 302",
      soap_note: {
        subjective: "Benh nhan tinh tao, khong con dau nguc khi gang suc nhe.",
        objective: "Huyet ap: 125/80 mmHg, nhip tim 72 ck/phut deu.",
        assessment: "Tang huyet ap vo can do 1 - kiem soat on dinh.",
        plan: "Tiep tuc duy tri phac do Amlodipine 5mg. Tai kham sau 3 thang.",
        clinician_name: "BS. Le Minh Tri",
        signed_at: "2026-10-24T09:00:00Z",
      },
    };

    it("builds a conformant FHIR Encounter resource", () => {
      const encounter = buildFhirEncounterResource(mockVisit, "patient-456");

      expect(encounter.resourceType).toBe("Encounter");
      expect(encounter.id).toBe("encounter-v-99");
      expect(encounter.status).toBe("finished");
      expect(encounter.subject).toEqual({ reference: "Patient/patient-456", display: "Patient" });
      expect(encounter.period).toEqual({ start: "2026-10-24T08:30:00Z" });
      expect(encounter.participant).toBeDefined();
      expect((encounter.participant as Array<Record<string, unknown>>)[0].individual).toEqual({
        display: "Dr. Le Minh Tri",
      });
      expect(encounter.serviceProvider).toEqual({ display: "Benh vien Bach Mai (Tang 3, Phong 302)" });
      expect(encounter.meta?.attribution).toBe(CLARA_FHIR_ATTRIBUTION);
    });

    it("builds a FHIR Composition resource from signed SOAP note", () => {
      const comp = buildFhirComposition(mockVisit, "Encounter/encounter-v-99", "patient-456");
      expect(comp).not.toBeNull();
      expect(comp?.resourceType).toBe("Composition");
      expect(comp?.status).toBe("final");
      expect(comp?.encounter).toEqual({ reference: "Encounter/encounter-v-99" });
      expect(comp?.author).toEqual([{ display: "BS. Le Minh Tri" }]);

      const sections = comp?.section as Array<{ title: string; text: { div: string } }>;
      expect(sections).toHaveLength(4);
      expect(sections[0].title).toContain("Subjective");
      expect(sections[0].text.div).toContain("khong con dau nguc");
      expect(sections[3].title).toContain("Plan");
      expect(sections[3].text.div).toContain("Amlodipine 5mg");
    });

    it("builds a FHIR MedicationStatement from prescription item", () => {
      const rx: Partial<VisitPrescription> = {
        id: "rx-101",
        name: "Amlodipine 5mg",
        dosage: "1 vien / ngay",
        instruction: "Uong buoi sang sau an",
        reconciliation_status: "continued",
      };

      const med = buildFhirMedicationStatement(rx, "Encounter/encounter-v-99", "patient-456");
      expect(med.resourceType).toBe("MedicationStatement");
      expect(med.status).toBe("active");
      expect(med.medicationCodeableConcept).toEqual({ text: "Amlodipine 5mg" });
      expect(med.context).toEqual({ reference: "Encounter/encounter-v-99" });
      expect((med.dosage as Array<Record<string, unknown>>)[0].text).toContain("1 vien / ngay");
    });

    it("builds a FHIR DocumentReference from attached visit document", () => {
      const doc: Partial<VisitDocument> = {
        id: "doc-505",
        title: "Dien tam do (ECG)",
        media_type: "text/plain",
        text_content: "Nhip xoang deu, tan so 72 bpm, khong co bien doi ST-T benh ly.",
        created_at: "2026-10-24T08:45:00Z",
      };

      const docRef = buildFhirDocumentReference(doc, "Encounter/encounter-v-99", "patient-456");
      expect(docRef.resourceType).toBe("DocumentReference");
      expect(docRef.status).toBe("current");
      expect(docRef.type).toEqual({ text: "Dien tam do (ECG)" });
      expect(docRef.context).toEqual({ encounter: [{ reference: "Encounter/encounter-v-99" }] });

      const content = docRef.content as Array<{ attachment: { data: string; title: string } }>;
      expect(content[0].attachment.title).toBe("Dien tam do (ECG)");
      expect(content[0].attachment.data).toBeDefined();
    });
  });

  describe("buildEncounterExportBundle (Bundle Assembler)", () => {
    it("assembles full FHIR R4 Bundle with all clinical components", () => {
      const fullVisit: Partial<Visit> = {
        id: "v-777",
        title: "Kham Tong Quat",
        visit_type: "Checkup",
        status: "completed",
        prescriptions: [
          { id: "rx-1", name: "Metformin 500mg", reconciliation_status: "continued" },
        ],
        documents: [
          { id: "doc-1", title: "Ket qua HbA1c", media_type: "text/plain", text_content: "HbA1c: 6.4%" },
        ],
        soap_note: {
          assessment: "Dai thao duong type 2 kiem soat tot",
        },
      };

      const options: FhirEncounterExportOptions = {
        purpose: "care_coordination",
        format: "fhir_json",
        profileId: "pat-123",
      };

      const bundle = buildEncounterExportBundle(fullVisit, options);

      expect(bundle.resourceType).toBe("Bundle");
      expect(bundle.type).toBe("collection");
      expect(bundle.meta.conformance).toBe(CLARA_FHIR_CONFORMANCE);
      expect(bundle.meta.profile).toContain("http://hl7.org/fhir/StructureDefinition/Bundle");

      const resourceTypes = bundle.entry.map((e) => e.resource.resourceType);
      expect(resourceTypes).toContain("Encounter");
      expect(resourceTypes).toContain("Composition");
      expect(resourceTypes).toContain("MedicationStatement");
      expect(resourceTypes).toContain("DocumentReference");
      expect(bundle.entry.length).toBe(4);
    });

    it("respects exclusions when include options are toggled off", () => {
      const fullVisit: Partial<Visit> = {
        id: "v-888",
        prescriptions: [{ id: "rx-1", name: "Thuoc A" }],
        documents: [{ id: "doc-1", title: "Tai lieu B" }],
        soap_note: { assessment: "Ghi chu C" },
      };

      const bundle = buildEncounterExportBundle(fullVisit, {
        includeSoapNote: false,
        includePrescriptions: false,
        includeDocuments: false,
      });

      const resourceTypes = bundle.entry.map((e) => e.resource.resourceType);
      expect(resourceTypes).toEqual(["Encounter"]);
      expect(bundle.entry.length).toBe(1);
    });

    it("guarantees idempotent and reproducible structure across calls", () => {
      const visitData: Partial<Visit> = { id: "idem-1", title: "Lượt khám định kỳ" };
      const bundle1 = buildEncounterExportBundle(visitData);
      const bundle2 = buildEncounterExportBundle(visitData);

      expect(bundle1.entry[0].resource.id).toBe(bundle2.entry[0].resource.id);
      expect(bundle1.entry[0].resource.class).toEqual(bundle2.entry[0].resource.class);
    });
  });
});
