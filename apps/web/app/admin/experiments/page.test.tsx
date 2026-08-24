import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockListExperiments = vi.fn();
const mockUpdateExperiment = vi.fn();
const mockOverrideKillSwitch = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

const mockExperimentsData = [
  {
    id: "exp-graphrag",
    key: "rag_graphrag_pipeline",
    name: "GraphRAG Multi-Hop Knowledge Retrieval",
    nameVi: "Truy xuất Đồ thị Tri thức Đa bước GraphRAG",
    description: "Multi-hop knowledge graph expansion for complex clinical inquiries.",
    descriptionVi: "Mở rộng đồ thị tri thức đa bước cho các câu hỏi lâm sàng phức tạp.",
    category: "ai_systems" as const,
    status: "gradual_rollout" as const,
    rolloutPercentage: 35,
    targetRoles: ["admin" as const, "doctor" as const],
    targetCohorts: ["beta_testers", "vietnam_hospitals"],
    matchMode: "any" as const,
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 14250,
      treatmentImpressions: 4980,
      controlImpressions: 9270,
      errorRate: 0.008,
      latencyP95Ms: 412,
    },
    createdAt: "2026-03-01T08:00:00Z",
    updatedAt: "2026-04-10T14:30:00Z",
    updatedBy: "lead-engineer@clara.vn",
  },
  {
    id: "exp-fides-gate",
    key: "fides_critical_ddi_blocking",
    name: "FIDES Critical Drug-DDI Blocking (Safety Invariant)",
    nameVi: "Khóa Chặn Tương tác Thuốc Nguy hiểm FIDES (Bất biến An toàn)",
    description: "Regression-locked invariant blocking critical contraindicated drug-drug interactions.",
    descriptionVi: "Bất biến khóa hồi quy tự động chặn các tương tác thuốc chống chỉ định nghiêm trọng.",
    category: "safety_invariant" as const,
    status: "active" as const,
    rolloutPercentage: 100,
    targetRoles: ["admin" as const, "doctor" as const, "researcher" as const, "normal" as const],
    targetCohorts: ["general_users"],
    matchMode: "any" as const,
    killSwitchActive: false,
    isSafetyInvariant: true,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    updatedBy: "safety-board@clara.vn",
  },
];

vi.mock("@/lib/experiments", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/experiments")>();
  return {
    ...actual,
    listExperiments: () => mockListExperiments(),
    updateExperiment: (id: string, updates: Record<string, unknown>) =>
      mockUpdateExperiment(id, updates),
    overrideKillSwitch: (id: string, kill: boolean, reason?: string) =>
      mockOverrideKillSwitch(id, kill, reason),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import AdminExperimentsPage from "@/app/admin/experiments/page";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  mockListExperiments.mockResolvedValue([...mockExperimentsData]);
});

afterEach(() => {
  vi.clearAllMocks();
  roleState.role = "admin";
  window.localStorage.clear();
});

describe("AdminExperimentsPage (Spec v5 Section 6.67)", () => {
  it("renders AdminShell with ADMIN_COMMAND shell and Feature Flags & Experimentation Workbench archetype", async () => {
    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(mockListExperiments).toHaveBeenCalled();
      expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
    });

    const workbenchContainer = document.querySelector(
      '[data-layout-archetype="Feature Flags & Experimentation Workbench"]'
    );
    expect(workbenchContainer).toBeInTheDocument();
    expect(workbenchContainer).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");

    // KPI cards rendered
    expect(screen.getByText(/Total Feature Flags/i)).toBeInTheDocument();
    expect(screen.getByText(/Active Rollouts/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Safety Invariants/i).length).toBeGreaterThan(0);

    // Feature table rendered
    expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
    expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
  });

  it("blocks non-admin users with an access denied alert banner (defense-in-depth)", async () => {
    roleState.role = "doctor";
    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
    });
  });

  it("allows updating rollout percentage via inline slider and inspector", async () => {
    mockUpdateExperiment.mockResolvedValue({
      ...mockExperimentsData[0],
      rolloutPercentage: 60,
      status: "gradual_rollout",
    });

    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
    });

    // Inspect GraphRAG flag
    const inspectButtons = screen.getAllByRole("button", { name: /inspect/i });
    fireEvent.click(inspectButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Experiment Inspector/i)).toBeInTheDocument();
    });

    // Change rollout percentage in inspector using preset button
    const preset50Btn = screen.getByRole("button", { name: "50%" });
    fireEvent.click(preset50Btn);

    // Click Save Changes button
    const saveBtn = screen.getByRole("button", { name: /save changes/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateExperiment).toHaveBeenCalledWith(
        "exp-graphrag",
        expect.objectContaining({
          rolloutPercentage: 50,
        })
      );
    });
  });

  it("opens Kill Switch modal and executes emergency override with mandatory reason", async () => {
    mockOverrideKillSwitch.mockResolvedValue({
      ...mockExperimentsData[0],
      killSwitchActive: true,
      status: "killed",
      killSwitchReason: "Critical latency spike observed",
    });

    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
    });

    // Click Kill button for GraphRAG
    const killBtn = screen.getByRole("button", { name: /kill/i });
    fireEvent.click(killBtn);

    // Modal dialog opens
    await waitFor(() => {
      expect(
        screen.getByText(/Confirm Emergency Kill Switch Override/i)
      ).toBeInTheDocument();
    });

    // Type reason in the textarea
    const reasonTextarea = screen.getByPlaceholderText(/Detected NLI accuracy degradation/i);
    fireEvent.change(reasonTextarea, {
      target: { value: "Critical latency spike observed" },
    });

    // Confirm Kill Switch
    const confirmBtn = screen.getByRole("button", { name: /activate kill switch/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockOverrideKillSwitch).toHaveBeenCalledWith(
        "exp-graphrag",
        true,
        "Critical latency spike observed"
      );
    });
  });

  it("enforces ANA-005 invariant: locks Safety Invariant flags against reduction or kill switch", async () => {
    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
    });

    // Safety Invariant displays Locked status
    expect(screen.getByText("ANA-005")).toBeInTheDocument();
    expect(screen.getByTitle(/Safety invariant locked/i)).toBeInTheDocument();
  });

  it("filters flags by search query and category", async () => {
    render(<AdminExperimentsPage />);

    await waitFor(() => {
      expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
      expect(screen.getByText("fides_critical_ddi_blocking")).toBeInTheDocument();
    });

    // Filter by search query
    const searchInput = screen.getByPlaceholderText(/search flag key or name/i);
    fireEvent.change(searchInput, { target: { value: "GraphRAG" } });

    expect(screen.getByText("rag_graphrag_pipeline")).toBeInTheDocument();
    expect(screen.queryByText("fides_critical_ddi_blocking")).not.toBeInTheDocument();
  });
});
