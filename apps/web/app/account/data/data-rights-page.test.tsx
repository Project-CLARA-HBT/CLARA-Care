import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const listDsarRequests = vi.fn();
  const requestDsarExport = vi.fn();
  const submitDsarRequest = vi.fn();
  const triggerBlobDownload = vi.fn();
  return {
    listDsarRequests,
    requestDsarExport,
    submitDsarRequest,
    triggerBlobDownload,
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
    isDsarEnabled: () => true,
    listDsarRequests: mocks.listDsarRequests,
    requestDsarExport: mocks.requestDsarExport,
    submitDsarRequest: mocks.submitDsarRequest,
  };
});

vi.mock("@/app/chat/_v2/lib/chat-format", () => ({
  triggerBlobDownload: mocks.triggerBlobDownload,
}));

import DataRightsPage from "./page";

beforeEach(() => {
  vi.clearAllMocks();
  process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED = "true";
  window.localStorage.setItem("clara_ui_language", "vi");
  mocks.listDsarRequests.mockResolvedValue({
    enabled: true,
    requests: [
      {
        id: 101,
        kind: "export",
        status: "fulfilled",
        created_at: "2026-04-01T08:00:00Z",
        due_at: "2026-04-15T08:00:00Z",
      },
      {
        id: 102,
        kind: "correct",
        status: "in_progress",
        created_at: "2026-04-02T09:00:00Z",
        due_at: "2026-04-16T09:00:00Z",
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  delete process.env.NEXT_PUBLIC_COMPLIANCE_DSAR_ENABLED;
  window.localStorage.clear();
});

describe("DataRightsPage — Data Rights Center (Spec v5 §6.78)", () => {
  it("renders 1. Header with back link to /you", async () => {
    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("data-rights-center")).toBeInTheDocument();
    });

    const backLink = screen.getByTestId("health-page-back-link");
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute("href", "/you");
    expect(screen.getByRole("heading", { level: 1, name: /Trung tâm Quyền Dữ liệu|Data Rights Center/i })).toBeInTheDocument();
  });

  it("renders 2. Editorial overview of data rights under Decree 13 & GDPR", async () => {
    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("editorial-overview-section")).toBeInTheDocument();
    });

    const section = screen.getByTestId("editorial-overview-section");
    expect(section).toHaveTextContent(/Nghị định 13\/2023\/NĐ-CP/i);
    expect(section).toHaveTextContent(/GDPR/i);
    expect(section).toHaveTextContent(/Bảo vệ Dữ liệu Y tế Nhạy cảm|Sensitive Health/i);
  });

  it("renders 3. Primary action rows (Export, Rectify, Audit Log) without 2-column card grid", async () => {
    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("primary-actions-section")).toBeInTheDocument();
    });

    // Verify each action row exists
    expect(screen.getByTestId("action-row-export")).toBeInTheDocument();
    expect(screen.getByTestId("action-row-correct")).toBeInTheDocument();
    expect(screen.getByTestId("action-row-audit")).toBeInTheDocument();
    expect(screen.getByTestId("action-row-consent")).toBeInTheDocument();

    // Verify machine-readable JSON badge & download button
    expect(screen.getByTestId("action-row-export")).toHaveTextContent(/JSON/i);
    expect(screen.getByTestId("export-json-button")).toBeInTheDocument();
    expect(screen.getByTestId("rectify-record-button")).toBeInTheDocument();
    expect(screen.getByTestId("request-audit-log-button")).toBeInTheDocument();
  });

  it("triggers machine-readable JSON export download upon clicking export action", async () => {
    mocks.requestDsarExport.mockResolvedValue({
      schema: "clara.dsar.export.v1",
      user_id: "user-123",
      phr_records: [{ condition: "Hypertension" }],
    });

    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("export-json-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("export-json-button"));

    await waitFor(() => {
      expect(mocks.requestDsarExport).toHaveBeenCalledTimes(1);
      expect(mocks.triggerBlobDownload).toHaveBeenCalledTimes(1);
    });
  });

  it("submits rectification and audit log requests through DSAR pipeline", async () => {
    mocks.submitDsarRequest.mockResolvedValue({
      id: 103,
      kind: "correct",
      status: "received",
    });

    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rectify-record-button")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("rectify-record-button"));

    await waitFor(() => {
      expect(mocks.submitDsarRequest).toHaveBeenCalledWith("correct");
      expect(screen.getByTestId("dsar-notice-banner")).toBeInTheDocument();
    });
  });

  it("renders 4. Dedicated destructive section linking to /account/data/delete/warning", async () => {
    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("destructive-delete-section")).toBeInTheDocument();
    });

    const destructiveSection = screen.getByTestId("destructive-delete-section");
    expect(destructiveSection).toHaveTextContent(/Xóa tài khoản|Delete Account/i);
    expect(destructiveSection).toHaveTextContent(/Nghị định 13|Decree 13/i);

    const deleteButton = screen.getByTestId("delete-account-button");
    expect(deleteButton).toBeInTheDocument();
    expect(deleteButton).toHaveAttribute("href", "/account/data/delete/warning");
  });

  it("renders 5. Request timeline & status history with status badges", async () => {
    render(<DataRightsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("requests-timeline-list")).toBeInTheDocument();
    });

    expect(screen.getByText(/#101/)).toBeInTheDocument();
    expect(screen.getByText(/#102/)).toBeInTheDocument();
  });
});
