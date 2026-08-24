import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mockGetAdminAuditLog = vi.fn();
const mockExportAuditLogZeroPii = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/admin-audit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-audit")>();
  return {
    ...actual,
    getAdminAuditLog: (limit?: number) => mockGetAdminAuditLog(limit),
    exportAuditLogZeroPii: (records: any[], format?: "json" | "csv") =>
      mockExportAuditLogZeroPii(records, format),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import SecurityAuditLogPage from "@/app/admin/audit/page";
import { SEED_ADMIN_AUDIT_LOGS } from "@/lib/admin-audit";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockGetAdminAuditLog.mockResolvedValue({
    records: [...SEED_ADMIN_AUDIT_LOGS],
  });
  mockExportAuditLogZeroPii.mockImplementation((records, format = "json") => ({
    success: true,
    count: records.length,
    filename: `clara_security_audit_log_zero_pii_test.${format}`,
  }));
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("SecurityAuditLogPage (Spec v5 Section 6.62: Security Audit Log Explorer)", () => {
  describe("1. Shell & Role-Based Access Control (RBAC)", () => {
    it("renders forbidden access notice when user role is not admin", async () => {
      roleState.role = "doctor";
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
      });

      expect(mockGetAdminAuditLog).not.toHaveBeenCalled();
    });

    it("renders AdminShell with ADMIN_COMMAND shell and Security Audit Log Explorer archetype", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(mockGetAdminAuditLog).toHaveBeenCalled();
      });

      const explorerContainer = document.querySelector(
        '[data-layout-archetype="Security Audit Log Explorer"]'
      );
      expect(explorerContainer).toBeInTheDocument();
      expect(explorerContainer).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(explorerContainer).toHaveAttribute("data-density", "dense");

      expect(
        screen.getByRole("heading", { level: 1, name: /Security Audit Log Explorer/i })
      ).toBeInTheDocument();
      expect(screen.getByText("GOV-02")).toBeInTheDocument();
      expect(screen.getByText(/Immutable WAL Active/i)).toBeInTheDocument();
    });
  });

  describe("2. Summary KPI Strip", () => {
    it("renders all 5 KPI summary cards with computed metrics", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText(/Total Audit Events/i)).toBeInTheDocument();
      });

      expect(screen.getByText("Total Audit Events")).toBeInTheDocument();
      expect(screen.getByText("Success Rate")).toBeInTheDocument();
      expect(screen.getByText(/Security & High-Risk/i)).toBeInTheDocument();
      expect(screen.getByText("Unique Actors")).toBeInTheDocument();
      expect(screen.getByText(/PII Redaction & WAL/i)).toBeInTheDocument();
      expect(screen.getByText("100% Zero-PII")).toBeInTheDocument();
    });
  });

  describe("3. Dense Immutable Audit Trail Table", () => {
    it("renders table headers with actor, action, resource, IP hash, and outcome", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByRole("table", { name: /Security audit log table/i })).toBeInTheDocument();
      });

      const table = screen.getByRole("table", { name: /Security audit log table/i });
      expect(within(table).getByText("Timestamp")).toBeInTheDocument();
      expect(within(table).getByText("Actor")).toBeInTheDocument();
      expect(within(table).getAllByText("Action").length).toBeGreaterThan(0);
      expect(within(table).getByText("Resource")).toBeInTheDocument();
      expect(within(table).getByText("IP Hash")).toBeInTheDocument();
      expect(within(table).getByText("Outcome")).toBeInTheDocument();

      const actorCells = within(table).getAllByText("usr_adm_8810");
      expect(actorCells.length).toBeGreaterThan(0);
    });

    it("renders expected audit record rows with Zero-PII IP hash and action verbs", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      expect(screen.getByText("user.lock")).toBeInTheDocument();
      expect(screen.getByText("kb_source.create")).toBeInTheDocument();
      expect(screen.getByText("rag_source.update")).toBeInTheDocument();
      expect(screen.getByText("auth.unauthorized_access")).toBeInTheDocument();
      expect(screen.getByText("sha256:4a8c...1f0d")).toBeInTheDocument();
    });
  });

  describe("4. Multi-dimensional Filters & Search", () => {
    it("filters records by search query (e.g. searching 'key_rotate')", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const searchInput = screen.getByRole("searchbox", { name: /Search audit logs/i });
      fireEvent.change(searchInput, { target: { value: "key_rotate" } });

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        expect(screen.queryByText("user.lock")).not.toBeInTheDocument();
        expect(screen.queryByText("kb_source.create")).not.toBeInTheDocument();
      });
    });

    it("filters records by action category (e.g. 'Security & Alerts')", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const categorySelect = screen.getByRole("combobox", {
        name: /Filter by action category/i,
      });
      fireEvent.change(categorySelect, { target: { value: "security" } });

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        expect(screen.getByText("auth.unauthorized_access")).toBeInTheDocument();
        expect(screen.queryByText("kb_source.create")).not.toBeInTheDocument();
      });
    });

    it("filters records by outcome (e.g. 'Denied')", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("auth.unauthorized_access")).toBeInTheDocument();
      });

      const outcomeSelect = screen.getByRole("combobox", {
        name: /Filter by outcome status/i,
      });
      fireEvent.change(outcomeSelect, { target: { value: "denied" } });

      await waitFor(() => {
        expect(screen.getByText("auth.unauthorized_access")).toBeInTheDocument();
        expect(screen.queryByText("security.key_rotate")).not.toBeInTheDocument();
      });
    });

    it("resets filters when clicking 'Reset filters' button", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const searchInput = screen.getByRole("searchbox", { name: /Search audit logs/i });
      fireEvent.change(searchInput, { target: { value: "nonexistent_action_query" } });

      await waitFor(() => {
        expect(screen.getByText(/No matching audit records found/i)).toBeInTheDocument();
      });

      const resetBtn = screen.getByRole("button", { name: /^Clear filters$/i });
      fireEvent.click(resetBtn);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        expect(screen.getByText("user.lock")).toBeInTheDocument();
      });
    });
  });

  describe("5. Slide-out Event Inspector Drawer", () => {
    it("opens inspector drawer with full Zero-PII details when clicking an audit record", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const inspectBtn = screen.getByRole("button", {
        name: /Inspect audit log #101/i,
      });
      fireEvent.click(inspectBtn);

      await waitFor(() => {
        expect(screen.getByText(/Audit Event #101/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/Event Overview/i)).toBeInTheDocument();
      expect(screen.getByText(/Security & Identity Coordinates/i)).toBeInTheDocument();
      expect(screen.getByText(/Zero-PII Context Payload/i)).toBeInTheDocument();
      expect(screen.getByText(/APPEND_ONLY_WAL_WITNESS/i)).toBeInTheDocument();
      expect(screen.getByText(/key_sec_9931/i)).toBeInTheDocument();
    });

    it("exports single event from within inspector drawer", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const inspectBtn = screen.getByRole("button", {
        name: /Inspect audit log #101/i,
      });
      fireEvent.click(inspectBtn);

      await waitFor(() => {
        expect(screen.getByText(/Audit Event #101/i)).toBeInTheDocument();
      });

      const exportEventBtn = screen.getByRole("button", { name: /Export Event/i });
      fireEvent.click(exportEventBtn);

      expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
        expect.arrayContaining([expect.objectContaining({ id: 101 })]),
        "json"
      );
      expect(screen.getByText(/Exported audit event #101/i)).toBeInTheDocument();
    });
  });

  describe("6. Zero-PII Export Trigger", () => {
    it("opens export modal and executes Zero-PII JSON export", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const exportTriggerBtn = screen.getByRole("button", {
        name: /Zero-PII export trigger/i,
      });
      fireEvent.click(exportTriggerBtn);

      await waitFor(() => {
        expect(screen.getByText(/Zero-PII Audit Log Export/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/Zero-PII Compliance Guarantee:/i)).toBeInTheDocument();

      const downloadBtn = screen.getByRole("button", {
        name: /Download Zero-PII Export/i,
      });
      fireEvent.click(downloadBtn);

      expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
        expect.any(Array),
        "json"
      );

      await waitFor(() => {
        expect(
          screen.getByText(/Successfully exported \d+ Zero-PII audit records/i)
        ).toBeInTheDocument();
      });
    });

    it("supports CSV format selection for Zero-PII export", async () => {
      render(<SecurityAuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
      });

      const exportTriggerBtn = screen.getByRole("button", {
        name: /Zero-PII export trigger/i,
      });
      fireEvent.click(exportTriggerBtn);

      await waitFor(() => {
        expect(screen.getByText(/Zero-PII Audit Log Export/i)).toBeInTheDocument();
      });

      const csvBtn = screen.getByText(/CSV \(Spreadsheet\)/i);
      fireEvent.click(csvBtn);

      const downloadBtn = screen.getByRole("button", {
        name: /Download Zero-PII Export/i,
      });
      fireEvent.click(downloadBtn);

      expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
        expect.any(Array),
        "csv"
      );
    });
  });
});
