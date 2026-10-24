import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { FhirEncounterExportDialog } from "./fhir-encounter-export-dialog";
import * as exportLib from "@/lib/fhir-encounter-export";
import type { Visit } from "@/lib/visit-family";

const mockVisit: Partial<Visit> = {
  id: "visit-123",
  title: "Kham Hau Phau",
  visit_type: "Specialty",
  status: "completed",
  prescriptions: [
    { id: "rx-1", name: "Paracetamol 500mg", reconciliation_status: "continued" },
  ],
  documents: [
    { id: "doc-1", title: "Phieu X-Quang", media_type: "text/plain", text_content: "Binh thuong" },
  ],
};

describe("FhirEncounterExportDialog Component", () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
    vi.restoreAllMocks();
  });

  it("renders when open=true and shows disabled banner when flag is false", async () => {
    delete process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED;
    vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
      allowed: true,
      policy_type: "medical_disclaimer",
    });

    render(
      <FhirEncounterExportDialog
        open={true}
        onClose={vi.fn()}
        visit={mockVisit}
      />,
    );

    expect(screen.getByTestId("fhir-encounter-export-dialog")).toBeDefined();
    expect(screen.getByTestId("fhir-export-disabled-banner")).toBeDefined();
    expect(screen.getByText(/Feature in Preview Mode|giai đoạn thử nghiệm/i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByTestId("fhir-export-consent-indicator")).toBeDefined();
    });

    const downloadBtn = screen.getByTestId("fhir-export-download-btn");
    expect(downloadBtn.hasAttribute("disabled")).toBe(true);
  });

  it("displays consent verified indicator when consent check passes", async () => {
    process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
    vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
      allowed: true,
      policy_type: "medical_disclaimer",
      required_version: "2026-04-v1",
    });

    render(
      <FhirEncounterExportDialog
        open={true}
        onClose={vi.fn()}
        visit={mockVisit}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("fhir-export-consent-indicator")).toBeDefined();
      expect(screen.getByText(/Đồng thuận y tế hợp lệ|Medical consent verified/i)).toBeDefined();
    });

    const downloadBtn = screen.getByTestId("fhir-export-download-btn");
    expect(downloadBtn.hasAttribute("disabled")).toBe(false);
  });

  it("displays error message and disables download when consent is rejected", async () => {
    process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
    vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
      allowed: false,
      reason: "Medical disclaimer consent missing",
      policy_type: "medical_disclaimer",
    });

    render(
      <FhirEncounterExportDialog
        open={true}
        onClose={vi.fn()}
        visit={mockVisit}
      />,
    );

    await waitFor(() => {
      const errorMsg = screen.getByTestId("fhir-export-error-message");
      expect(errorMsg.textContent).toContain("Medical disclaimer consent missing");
    });

    const downloadBtn = screen.getByTestId("fhir-export-download-btn");
    expect(downloadBtn.hasAttribute("disabled")).toBe(true);
  });

  it("updates export purpose and format selectors", async () => {
    process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
    vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
      allowed: true,
      policy_type: "medical_disclaimer",
    });

    render(
      <FhirEncounterExportDialog
        open={true}
        onClose={vi.fn()}
        visit={mockVisit}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("fhir-export-consent-indicator")).toBeDefined();
    });

    const purposeSelect = screen.getByTestId("fhir-export-purpose-select") as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(purposeSelect, { target: { value: "care_coordination" } });
    });
    expect(purposeSelect.value).toBe("care_coordination");

    const formatSelect = screen.getByTestId("fhir-export-format-select") as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(formatSelect, { target: { value: "ndjson" } });
    });
    expect(formatSelect.value).toBe("ndjson");
  });

  it("executes downloadFhirBundle when permitted", async () => {
    process.env.NEXT_PUBLIC_FHIR_ENCOUNTER_EXPORT_ENABLED = "true";
    vi.spyOn(exportLib, "verifyExportConsent").mockResolvedValue({
      allowed: true,
      policy_type: "medical_disclaimer",
    });
    const downloadSpy = vi.spyOn(exportLib, "downloadFhirBundle").mockImplementation(() => {});

    render(
      <FhirEncounterExportDialog
        open={true}
        onClose={vi.fn()}
        visit={mockVisit}
      />,
    );

    await waitFor(() => {
      const downloadBtn = screen.getByTestId("fhir-export-download-btn");
      expect(downloadBtn.hasAttribute("disabled")).toBe(false);
    });

    const downloadBtn = screen.getByTestId("fhir-export-download-btn");
    fireEvent.click(downloadBtn);

    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalled();
      expect(screen.getByTestId("fhir-export-success-message")).toBeDefined();
    });
  });
});
