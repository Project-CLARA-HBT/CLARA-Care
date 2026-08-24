import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminOverviewPage from "@/app/admin/overview/page";
import * as systemLib from "@/lib/system";
import * as researchLib from "@/lib/research";
import * as auditLib from "@/lib/admin-audit";

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

describe("AdminOverviewPage", () => {
  beforeEach(() => {
    roleState.role = "admin";
    window.localStorage.setItem("clara_ui_language", "vi");

    vi.spyOn(systemLib, "getApiHealth").mockResolvedValue({
      status: "ok",
      message: "All systems nominal",
    } as any);

    vi.spyOn(systemLib, "getSystemDependencies").mockResolvedValue({
      status: "ok",
      dependencies: {
        ml: { reachable: true, status: "healthy" },
        database: { reachable: true, status: "healthy" },
      },
    } as any);

    vi.spyOn(systemLib, "getControlTowerConfig").mockResolvedValue({
      rag_sources: [
        { id: "src_1", name: "Dược thư QG", priority: 1, weight: 1.0, enabled: true, category: "pharmacopeia" },
      ],
      rag_flow: {
        rule_verification_enabled: true,
        low_context_threshold: 0.2,
      },
    } as any);

    vi.spyOn(researchLib, "listKnowledgeSources").mockResolvedValue([]);
    vi.spyOn(researchLib, "listSourceHubCatalog").mockResolvedValue([]);
    vi.spyOn(auditLib, "getAdminAuditLog").mockResolvedValue({ records: [], total: 0 } as any);
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("renders CommandCenterLayout with admin workspace, AdminCommandStrip, and ordered visual hierarchy", async () => {
    render(<AdminOverviewPage />);

    const commandCenter = document.querySelector('[data-archetype="command-center"]');
    expect(commandCenter).toBeInTheDocument();
    expect(commandCenter).toHaveAttribute("data-workspace", "admin");

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
    });

    // 1. Attention Queue
    expect(screen.getByText("Hàng đợi Cần lưu ý (Attention Queue)")).toBeInTheDocument();

    // 2. System Status Ledger
    expect(screen.getByText("Sổ cái Trạng thái Phân hệ (System Status Ledger)")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Core")).toBeInTheDocument();
    expect(screen.getByText("Answer Flow")).toBeInTheDocument();

    // 3. Recent Operations
    expect(screen.getByText("Hoạt động Vận hành Gần đây (Recent Operations)")).toBeInTheDocument();

    // 4. Audit Digest
    expect(screen.getByText("Tóm lược Kiểm toán & Tuân thủ (Audit Digest)")).toBeInTheDocument();
  });

  it("blocks non-admin users with 403 access denied message", async () => {
    roleState.role = "normal";
    render(<AdminOverviewPage />);

    expect(screen.getByText(/Từ chối quyền truy cập/i)).toBeInTheDocument();
  });
});
