import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "next/server";
import { GET as getEncounterExport } from "./encounter/route";
import { GET as getDocumentsExport } from "./documents/route";
import * as exportLib from "@/lib/fhir-encounter-export";

describe("Next.js API Export Routes", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.restoreAllMocks();
  });

  describe("GET /api/export/encounter", () => {
    it("returns 404 feature_disabled when feature flag is off", async () => {
      delete process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED;

      const req = new NextRequest("http://localhost:3000/api/export/encounter?id=visit-1");
      const res = await getEncounterExport(req);

      expect(res.status).toBe(404);
      const json = await res.json();
      expect(json.code).toBe("feature_disabled");
    });

    it("returns 422 invalid_request when id parameter is missing", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";

      const req = new NextRequest("http://localhost:3000/api/export/encounter");
      const res = await getEncounterExport(req);

      expect(res.status).toBe(422);
      const json = await res.json();
      expect(json.code).toBe("invalid_request");
    });

    it("returns 403 consent_required when medical consent is missing", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
        allowed: false,
        reason: "Consent missing",
        policy_type: "medical_disclaimer",
      });

      const req = new NextRequest("http://localhost:3000/api/export/encounter?id=visit-1");
      const res = await getEncounterExport(req);

      expect(res.status).toBe(403);
      const json = await res.json();
      expect(json.code).toBe("consent_required");
    });

    it("returns 200 with FHIR R4 Bundle when permitted", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
        allowed: true,
        policy_type: "medical_disclaimer",
      });

      const req = new NextRequest("http://localhost:3000/api/export/encounter?id=visit-42&purpose=self_download");
      const res = await getEncounterExport(req);

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("application/fhir+json");
      expect(res.headers.get("content-disposition")).toContain("clara-encounter-visit-42.fhir.json");
      expect(res.headers.get("x-clara-fhir-version")).toBe("4.0.1");
      expect(res.headers.get("x-clara-conformance")).toBe("fhir-r4-summary-not-ips");

      const bundle = await res.json();
      expect(bundle.resourceType).toBe("Bundle");
      expect(bundle.type).toBe("collection");
      expect(bundle.entry.length).toBeGreaterThan(0);
      expect(bundle.entry[0].resource.resourceType).toBe("Encounter");
    });

    it("returns 200 with application/x-ndjson when format=ndjson", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
        allowed: true,
      });

      const req = new NextRequest("http://localhost:3000/api/export/encounter?id=visit-42&format=ndjson");
      const res = await getEncounterExport(req);

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("application/x-ndjson");
      const text = await res.text();
      const lines = text.trim().split("\n");
      expect(lines.length).toBeGreaterThan(0);
      expect(JSON.parse(lines[0]).resourceType).toBe("Encounter");
    });

    it("accepts pre-verified consent header x-clara-consent-verified", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";

      const req = new NextRequest("http://localhost:3000/api/export/encounter?id=visit-42", {
        headers: {
          "x-clara-consent-verified": "true",
        },
      });
      const res = await getEncounterExport(req);

      expect(res.status).toBe(200);
      const bundle = await res.json();
      expect(bundle.resourceType).toBe("Bundle");
    });
  });

  describe("GET /api/export/documents", () => {
    it("returns 404 when feature flag is off", async () => {
      delete process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED;

      const req = new NextRequest("http://localhost:3000/api/export/documents?id=doc-10");
      const res = await getDocumentsExport(req);

      expect(res.status).toBe(404);
      const json = await res.json();
      expect(json.code).toBe("feature_disabled");
    });

    it("returns 422 when id is missing", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";

      const req = new NextRequest("http://localhost:3000/api/export/documents");
      const res = await getDocumentsExport(req);

      expect(res.status).toBe(422);
    });

    it("returns 403 when consent fails", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
        allowed: false,
        reason: "Consent missing",
      });

      const req = new NextRequest("http://localhost:3000/api/export/documents?id=doc-10");
      const res = await getDocumentsExport(req);

      expect(res.status).toBe(403);
    });

    it("returns 200 with DocumentReference Bundle when permitted", async () => {
      process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
      vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
        allowed: true,
      });

      const req = new NextRequest("http://localhost:3000/api/export/documents?id=doc-10&purpose=care_coordination");
      const res = await getDocumentsExport(req);

      expect(res.status).toBe(200);
      expect(res.headers.get("content-type")).toContain("application/fhir+json");
      expect(res.headers.get("content-disposition")).toContain("clara-doc-doc-10.fhir.json");

      const bundle = await res.json();
      expect(bundle.resourceType).toBe("Bundle");
      expect(bundle.entry[0].resource.resourceType).toBe("DocumentReference");
    });
  });
});
