import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const listConsents = vi.fn();
  const grantConsent = vi.fn();
  const withdrawConsent = vi.fn();
  return {
    listConsents,
    grantConsent,
    withdrawConsent,
  };
});

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/compliance", async () => {
  const actual = await vi.importActual<typeof import("@/lib/compliance")>(
    "@/lib/compliance",
  );
  return {
    ...actual,
    isGranularConsentEnabled: () => true,
    listConsents: mocks.listConsents,
    grantConsent: mocks.grantConsent,
    withdrawConsent: mocks.withdrawConsent,
  };
});

import { saveUILanguage } from "@/lib/ui-language";
import ConsentCenterPage from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED = "true";
  window.localStorage.setItem("clara_ui_language", "vi");
  mocks.listConsents.mockResolvedValue({
    enabled: true,
    policy_version: "2026-04-v1",
    consents: [
      { purpose: "medical_ai_reasoning", granted: true, policy_version: "v2.4", updated_at: "2026-04-01T08:00:00Z" },
      { purpose: "emergency_escalation", granted: true, policy_version: "v2.0", updated_at: "2026-04-01T08:00:00Z" },
      { purpose: "prescription_ocr", granted: true, policy_version: "v1.8", updated_at: "2026-04-02T09:00:00Z" },
      { purpose: "scribe_ambient", granted: false, policy_version: "v1.5", updated_at: "2026-04-03T10:00:00Z" },
      { purpose: "family_sharing", granted: true, policy_version: "v1.2", updated_at: "2026-04-04T11:00:00Z" },
      { purpose: "research_deidentification", granted: false, policy_version: "v2.1", updated_at: "2026-04-05T12:00:00Z" },
    ],
  });
});

afterEach(() => {
  cleanup();
  delete process.env.NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED;
  window.localStorage.clear();
});

describe("ConsentCenterPage — Consent Ledger (Spec v5 Section 6.77)", () => {
  it("renders 1. Header with back link to /you", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("consent-ledger-page")).toBeInTheDocument();
    });

    const backLink = screen.getByTestId("health-page-back-link");
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute("href", "/you");
    expect(
      screen.getByRole("heading", { level: 1, name: /Sổ cái Đồng thuận|Consent Ledger|Trung tâm đồng thuận/i }),
    ).toBeInTheDocument();
  });

  it("renders 2. Editorial overview under Vietnamese Medical Law 2023 & Decree 13/2023/NĐ-CP", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("editorial-overview-section")).toBeInTheDocument();
    });

    const section = screen.getByTestId("editorial-overview-section");
    expect(section).toHaveTextContent(/Luật Khám bệnh 2023/i);
    expect(section).toHaveTextContent(/Nghị định 13\/2023\/NĐ-CP/i);
    expect(section).toHaveTextContent(/Zero-CoT/i);

    expect(screen.getByTestId("pillar-law2023")).toBeInTheDocument();
    expect(screen.getByTestId("pillar-decree13")).toBeInTheDocument();
    expect(screen.getByTestId("pillar-zerocot")).toBeInTheDocument();
  });

  it("renders 3. Ledger of active consent purposes with all 6 purposes", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("consent-ledger-section")).toBeInTheDocument();
    });

    // 1. Medical AI Assistant reasoning
    expect(screen.getByTestId("consent-row-medical_ai_reasoning")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-medical_ai_reasoning")).toHaveTextContent(/Suy luận Trợ lý AI Y tế|Medical AI Assistant reasoning/i);

    // 2. Emergency escalation fast-path
    expect(screen.getByTestId("consent-row-emergency_escalation")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-emergency_escalation")).toHaveTextContent(/Luồng cấp cứu khẩn cấp|Emergency escalation fast-path/i);

    // 3. Prescription OCR scanning
    expect(screen.getByTestId("consent-row-prescription_ocr")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-prescription_ocr")).toHaveTextContent(/Bóc tách đơn thuốc OCR|Prescription OCR scanning/i);

    // 4. Scribe ambient transcription
    expect(screen.getByTestId("consent-row-scribe_ambient")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-scribe_ambient")).toHaveTextContent(/Ghi âm hội thoại Scribe|Scribe ambient transcription/i);

    // 5. Family member sharing
    expect(screen.getByTestId("consent-row-family_sharing")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-family_sharing")).toHaveTextContent(/Chia sẻ thành viên gia đình|Family member sharing/i);

    // 6. Research data de-identification
    expect(screen.getByTestId("consent-row-research_deidentification")).toBeInTheDocument();
    expect(screen.getByTestId("consent-row-research_deidentification")).toHaveTextContent(/Khử định danh dữ liệu nghiên cứu|Research data de-identification/i);
  });

  it("renders version history badges and statutory basis tags", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("version-badge-medical_ai_reasoning")).toHaveTextContent("v2.4");
      expect(screen.getByTestId("version-badge-emergency_escalation")).toHaveTextContent("v2.0");
      expect(screen.getByTestId("version-badge-prescription_ocr")).toHaveTextContent("v1.8");
      expect(screen.getByTestId("version-badge-scribe_ambient")).toHaveTextContent("v1.5");
      expect(screen.getByTestId("version-badge-family_sharing")).toHaveTextContent("v1.2");
      expect(screen.getByTestId("version-badge-research_deidentification")).toHaveTextContent("v2.1");
    });
  });

  it("locks core service purpose and disables toggle", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("consent-row-medical_ai_reasoning")).toBeInTheDocument();
    });

    // Medical AI Assistant reasoning is locked/required
    expect(screen.queryByTestId("toggle-medical_ai_reasoning")).not.toBeInTheDocument();
    expect(screen.getByTestId("status-badge-medical_ai_reasoning")).toHaveTextContent(/Bắt buộc|Required/i);
  });

  it("toggles consent grant and withdraw, appending to Revocation Audit Log", async () => {
    mocks.grantConsent.mockResolvedValue({});
    mocks.withdrawConsent.mockResolvedValue({});

    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-research_deidentification")).toBeInTheDocument();
    });

    const researchToggle = screen.getByTestId("toggle-research_deidentification");
    expect(researchToggle).toHaveAttribute("aria-checked", "false");

    // Grant research consent
    fireEvent.click(researchToggle);

    await waitFor(() => {
      expect(mocks.grantConsent).toHaveBeenCalledWith("research_deidentification", "v2.1");
    });

    // Verify audit log has the new grant entry
    const auditLog = screen.getByTestId("revocation-audit-log");
    expect(auditLog).toHaveTextContent(/Khử định danh dữ liệu nghiên cứu|Research data de-identification/i);
    expect(auditLog).toHaveTextContent(/Đã cấp quyền|Granted/i);

    // Withdraw prescription OCR consent
    const ocrToggle = screen.getByTestId("toggle-prescription_ocr");
    expect(ocrToggle).toHaveAttribute("aria-checked", "true");

    fireEvent.click(ocrToggle);

    await waitFor(() => {
      expect(mocks.withdrawConsent).toHaveBeenCalledWith("prescription_ocr");
    });

    // Verify audit log has revocation entry
    expect(auditLog).toHaveTextContent(/Đã thu hồi|Revoked/i);
  });

  it("renders 4. Revocation and Grant Audit Log section with Zero-PII standard badges", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("revocation-audit-log")).toBeInTheDocument();
    });

    const auditSection = screen.getByTestId("revocation-audit-log");
    expect(auditSection).toHaveTextContent(/Nhật ký Kiểm toán Cấp & Thu hồi|Consent Revocation & Grant Audit Log/i);
    expect(auditSection).toHaveTextContent(/Zero-PII/i);
    expect(screen.getByTestId("audit-log-list")).toBeInTheDocument();
    expect(screen.getAllByTestId("audit-log-item").length).toBeGreaterThan(0);
  });

  it("renders disabled state when granular consent feature flag is not active", async () => {
    mocks.listConsents.mockResolvedValueOnce({
      enabled: false,
      consents: [],
    });

    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("consent-disabled-notice")).toBeInTheDocument();
    });
  });

  it("opens Detail Sheet with statutory citation, data scope, and consequence copy (Spec v5 §6.77 Items 4 & 5)", async () => {
    mocks.grantConsent.mockResolvedValue({});
    mocks.withdrawConsent.mockResolvedValue({});

    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("inspect-button-emergency_escalation")).toBeInTheDocument();
    });

    // Open detail sheet for emergency escalation
    const inspectEmergencyBtn = screen.getByTestId("inspect-button-emergency_escalation");
    fireEvent.click(inspectEmergencyBtn);

    await waitFor(() => {
      expect(screen.getByTestId("purpose-detail-sheet")).toBeInTheDocument();
    });

    const sheet = screen.getByTestId("purpose-detail-sheet");
    expect(sheet).toHaveTextContent(/Luật Khám bệnh 2023 §19/i);
    expect(sheet).toHaveTextContent(/Điều 19 Luật Khám bệnh 2023/i);

    // Consequence analysis
    expect(screen.getByTestId("consequence-granted")).toBeInTheDocument();
    expect(screen.getByTestId("consequence-granted")).toHaveTextContent(/115/);
    expect(screen.getByTestId("consequence-revoked")).toBeInTheDocument();

    // Toggle from sheet
    const sheetActionBtn = screen.getByTestId("sheet-toggle-action");
    expect(sheetActionBtn).toBeInTheDocument();
    expect(sheetActionBtn).toHaveTextContent(/Thu hồi|Withdraw/i);

    fireEvent.click(sheetActionBtn);

    await waitFor(() => {
      expect(mocks.withdrawConsent).toHaveBeenCalledWith("emergency_escalation");
    });

    // Close sheet
    const closeBtn = screen.getByTestId("sheet-close-action");
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByTestId("purpose-detail-sheet")).not.toBeInTheDocument();
    });
  });

  it("displays locked consequence in Detail Sheet for core medical AI reasoning purpose", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("inspect-button-medical_ai_reasoning")).toBeInTheDocument();
    });

    // Open detail sheet for core medical AI reasoning
    fireEvent.click(screen.getByTestId("inspect-button-medical_ai_reasoning"));

    await waitFor(() => {
      expect(screen.getByTestId("purpose-detail-sheet")).toBeInTheDocument();
    });

    const sheet = screen.getByTestId("purpose-detail-sheet");
    expect(sheet).toHaveTextContent(/Điều 15 Luật Khám bệnh/i);
    expect(sheet).toHaveTextContent(/Zero-CoT/i);
    expect(screen.queryByTestId("sheet-toggle-action")).not.toBeInTheDocument();
    expect(sheet).toHaveTextContent(/căn cứ pháp lý cốt lõi|core statutory lawful basis/i);
  });

  it("switches UI language between Vietnamese and English", async () => {
    render(<ConsentCenterPage />);

    await waitFor(() => {
      expect(screen.getByTestId("editorial-overview-section")).toHaveTextContent(/Luật Khám bệnh 2023/i);
    });

    // Switch language to English
    act(() => {
      saveUILanguage("en");
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { level: 1, name: /Consent Ledger|Consent Center/i }),
      ).toBeInTheDocument();
      expect(screen.getByTestId("editorial-overview-section")).toHaveTextContent(/Vietnamese Medical Law 2023/i);
    });
  });
});
