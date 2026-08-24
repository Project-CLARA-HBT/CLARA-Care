import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminOverviewPage from "@/app/admin/overview/page";
import * as systemLib from "@/lib/system";
import * as researchLib from "@/lib/research";
import * as auditLib from "@/lib/admin-audit";

vi.mock("@/lib/auth-store", () => ({
  getRole: () => "admin",
}));

describe("AdminOverviewPage", () => {
  beforeEach(() => {
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

  it("renders CommandCenterLayout with admin workspace and AdminOverviewPanel", async () => {
    render(<AdminOverviewPage />);

    const commandCenter = document.querySelector('[data-archetype="command-center"]');
    expect(commandCenter).toBeInTheDocument();
    expect(commandCenter).toHaveAttribute("data-workspace", "admin");

    expect(screen.getByRole("navigation", { name: /Admin command strip/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Tổng quan Điều phối & An toàn Hệ thống")).toBeInTheDocument();
    });

    expect(screen.getByText("4 Phân hệ Trọng yếu (Systems Status Stream)")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Core")).toBeInTheDocument();
    expect(screen.getByText("Answer Flow")).toBeInTheDocument();
    expect(screen.getByText(/Trình Khởi chạy Toàn bộ Công cụ/i)).toBeInTheDocument();
  });
});
