import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import RoleSelectPage from "./page";
import { SessionContext, type SessionContextValue } from "@/components/shell/session-boundary";
import * as authStore from "@/lib/auth-store";

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    pathname: "/role-select",
  }),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

describe("RoleSelectPage — Role & Workspace Selection Canvas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    vi.spyOn(authStore, "getRole").mockReturnValue("admin");
    vi.spyOn(authStore, "setAuthoritativeServerRole").mockImplementation((role) => {
      window.localStorage.setItem("clara_role", role || "");
    });
  });

  const createMockSession = (overrides?: Partial<SessionContextValue>): SessionContextValue => ({
    role: "admin",
    effectiveRole: "admin",
    adminPreviewMode: null,
    setAdminPreviewMode: vi.fn(),
    setRole: vi.fn(),
    isRoleHydrated: true,
    isSessionChecked: true,
    isLoggingOut: false,
    handleLogout: vi.fn(),
    ...overrides,
  });

  it("renders the canvas header, title, and live status bar", () => {
    render(<RoleSelectPage />);

    expect(
      screen.getByText("Trung tâm Điều phối Không gian & Vai trò"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Chọn Không gian Làm việc & Vai trò" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/CLARA cung cấp 4 bàn làm việc chuyên biệt/i)).toBeInTheDocument();
    expect(screen.getByText("Trạng thái hiện tại:")).toBeInTheDocument();
    expect(screen.getByText("admin")).toBeInTheDocument();
  });

  it("renders all 4 prominent workspace cards with rich descriptions and target personas", () => {
    render(<RoleSelectPage />);

    // 1. Admin Command
    expect(
      screen.getByRole("heading", { level: 2, name: /Quản trị Toàn diện \(Admin Command\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Bàn điều khiển trung tâm tối cao để quản trị hạ tầng AI, phân quyền người dùng, giám sát luồng quyết định y tế và tuân thủ an toàn FIDES.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Quản trị viên hệ thống, Trưởng khoa Y tế, Cán bộ tuân thủ & An ninh/i),
    ).toBeInTheDocument();

    // 2. Clinical Instrument
    expect(
      screen.getByRole("heading", { level: 2, name: /Bác sĩ Lâm sàng \(Clinical Instrument\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Không gian công cụ lâm sàng chuyên sâu hỗ trợ hội chẩn đa tác tử, ghi chép bối cảnh khám tự động và phân tầng nguy cơ bệnh nhân.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Bác sĩ lâm sàng, Chuyên gia nội\/ngoại khoa, Bác sĩ hội chẩn/i),
    ).toBeInTheDocument();

    // 3. Living Evidence
    expect(
      screen.getByRole("heading", { level: 2, name: /Nhà nghiên cứu Y sinh \(Living Evidence\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Không gian tổng hợp bằng chứng y văn sống, đối chiếu thử nghiệm lâm sàng, quản lý nguồn dữ liệu uy tín và AI nghiên cứu chuyên sâu.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Nhà nghiên cứu y sinh, Dược sĩ lâm sàng, Học giả y khoa/i),
    ).toBeInTheDocument();

    // 4. Personal Companion
    expect(
      screen.getByRole("heading", { level: 2, name: /Người dùng Cá nhân \(Personal Companion\)/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Trợ lý đồng hành sức khỏe cá nhân và gia đình, hướng dẫn các hành động hôm nay, theo dõi hành trình bệnh và quản lý tủ thuốc an toàn.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Người bệnh, Người chăm sóc gia đình, Cá nhân theo dõi sức khỏe/i),
    ).toBeInTheDocument();
  });

  it("renders all 6 key capabilities on the Admin Command card", () => {
    render(<RoleSelectPage />);

    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("System health")).toBeInTheDocument();
    expect(screen.getByText("User admin")).toBeInTheDocument();
    expect(screen.getByText("Security audit")).toBeInTheDocument();
    expect(screen.getByText("Flow debugger")).toBeInTheDocument();
    expect(screen.getByText("Ingestion monitor")).toBeInTheDocument();
  });

  it("renders all 4 key capabilities on the Clinical Instrument card", () => {
    render(<RoleSelectPage />);

    expect(screen.getByText("Clinical Overview launchpad")).toBeInTheDocument();
    expect(screen.getByText("Council multi-agent deliberation")).toBeInTheDocument();
    expect(screen.getByText("Scribe ambient transcription")).toBeInTheDocument();
    expect(screen.getByText("Patient queue")).toBeInTheDocument();
  });

  it("renders all 4 key capabilities on the Living Evidence card", () => {
    render(<RoleSelectPage />);

    expect(screen.getByText("Evidence synthesis")).toBeInTheDocument();
    expect(screen.getByText("Literature search")).toBeInTheDocument();
    expect(screen.getByText("Source hub catalog")).toBeInTheDocument();
    expect(screen.getByText("AI research chat")).toBeInTheDocument();
  });

  it("renders all 4 key capabilities on the Personal Companion card", () => {
    render(<RoleSelectPage />);

    expect(screen.getByText("Next-action Today canvas")).toBeInTheDocument();
    expect(screen.getByText("LifeMap care journeys")).toBeInTheDocument();
    expect(screen.getByText("Medicines safety cabinet")).toBeInTheDocument();
    expect(screen.getByText("Family sharing")).toBeInTheDocument();
  });

  it("allows 1-click active role switching and persists preference", () => {
    const mockSession = createMockSession();
    render(
      <SessionContext.Provider value={mockSession}>
        <RoleSelectPage />
      </SessionContext.Provider>,
    );

    // Click "Chọn vai trò này" on Clinical card
    const selectButton = screen.getByTestId("select-role-clinical");
    fireEvent.click(selectButton);

    expect(authStore.setAuthoritativeServerRole).toHaveBeenCalledWith("doctor");
    expect(window.localStorage.getItem("clara_role")).toBe("doctor");
    expect(window.localStorage.getItem("clara_active_workspace:doctor")).toBe("clinical");
    expect(window.localStorage.getItem("clara_active_workspace")).toBe("clinical");
    expect(mockSession.setRole).toHaveBeenCalledWith("doctor");
    expect(mockSession.setAdminPreviewMode).toHaveBeenCalledWith("clinical");

    expect(screen.getByText(/Đã kích hoạt chế độ xem: Bác sĩ Lâm sàng/i)).toBeInTheDocument();
  });

  it("launches instant workspace on clicking primary launch button", () => {
    const mockSession = createMockSession();
    render(
      <SessionContext.Provider value={mockSession}>
        <RoleSelectPage />
      </SessionContext.Provider>,
    );

    // Launch Admin
    const launchAdminBtn = screen.getByTestId("launch-workspace-admin");
    fireEvent.click(launchAdminBtn);
    expect(mockPush).toHaveBeenCalledWith("/admin/overview");

    // Launch Clinical
    const launchClinicalBtn = screen.getByTestId("launch-workspace-clinical");
    fireEvent.click(launchClinicalBtn);
    expect(mockPush).toHaveBeenCalledWith("/clinical/overview");

    // Launch Research
    const launchResearchBtn = screen.getByTestId("launch-workspace-research");
    fireEvent.click(launchResearchBtn);
    expect(mockPush).toHaveBeenCalledWith("/evidence");

    // Launch Personal
    const launchPersonalBtn = screen.getByTestId("launch-workspace-personal");
    fireEvent.click(launchPersonalBtn);
    expect(mockPush).toHaveBeenCalledWith("/today");
  });

  it("navigates directly when clicking a capability item", () => {
    const mockSession = createMockSession();
    render(
      <SessionContext.Provider value={mockSession}>
        <RoleSelectPage />
      </SessionContext.Provider>,
    );

    // Click "Council multi-agent deliberation"
    const councilBtn = screen.getByTestId("capability-btn-council");
    fireEvent.click(councilBtn);

    expect(authStore.setAuthoritativeServerRole).toHaveBeenCalledWith("doctor");
    expect(mockPush).toHaveBeenCalledWith("/council");
  });

  it("filters capabilities and cards via search input", () => {
    render(<RoleSelectPage />);

    const searchInput = screen.getByPlaceholderText(/Tìm tính năng, vai trò/i);
    fireEvent.change(searchInput, { target: { value: "Scribe" } });

    expect(screen.getByTestId("workspace-card-clinical")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-card-personal")).not.toBeInTheDocument();
  });

  it("filters cards via category tabs", () => {
    render(<RoleSelectPage />);

    // Click "Cá nhân & Gia đình" category tab
    const personalTab = screen.getByTestId("filter-tab-personal");
    fireEvent.click(personalTab);

    expect(screen.getByTestId("workspace-card-personal")).toBeInTheDocument();
    expect(screen.queryByTestId("workspace-card-admin")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workspace-card-clinical")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workspace-card-research")).not.toBeInTheDocument();
  });

  it("renders empty state when search matches nothing and allows resetting", () => {
    render(<RoleSelectPage />);

    const searchInput = screen.getByPlaceholderText(/Tìm tính năng, vai trò/i);
    fireEvent.change(searchInput, { target: { value: "non_existent_capability_xyz" } });

    expect(
      screen.getByText("Không tìm thấy tính năng hoặc vai trò phù hợp"),
    ).toBeInTheDocument();

    const resetBtn = screen.getByRole("button", { name: /Đặt lại bộ lọc/i });
    fireEvent.click(resetBtn);

    expect(screen.getByTestId("workspace-card-admin")).toBeInTheDocument();
    expect(screen.getByTestId("workspace-card-clinical")).toBeInTheDocument();
  });

  it("navigates directly when clicking Admin, Research, and Personal capability items", () => {
    const mockSession = createMockSession();
    render(
      <SessionContext.Provider value={mockSession}>
        <RoleSelectPage />
      </SessionContext.Provider>,
    );

    // Click "System health" on Admin card
    const systemHealthBtn = screen.getByTestId("capability-btn-system-health");
    fireEvent.click(systemHealthBtn);
    expect(authStore.setAuthoritativeServerRole).toHaveBeenCalledWith("admin");
    expect(mockPush).toHaveBeenCalledWith("/admin/system");

    // Click "Evidence synthesis" on Research card
    const evidenceBtn = screen.getByTestId("capability-btn-evidence-synthesis");
    fireEvent.click(evidenceBtn);
    expect(authStore.setAuthoritativeServerRole).toHaveBeenCalledWith("researcher");
    expect(mockPush).toHaveBeenCalledWith("/evidence");

    // Click "Next-action Today canvas" on Personal card
    const todayBtn = screen.getByTestId("capability-btn-today-canvas");
    fireEvent.click(todayBtn);
    expect(authStore.setAuthoritativeServerRole).toHaveBeenCalledWith("normal");
    expect(mockPush).toHaveBeenCalledWith("/today");
  });

  it("renders the Safety & RBAC clarification banner", () => {
    render(<RoleSelectPage />);

    expect(
      screen.getByRole("heading", { level: 2, name: /Nguyên tắc An toàn & Phân quyền RBAC của CLARA/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Việc chuyển đổi không gian làm việc hoặc chế độ xem trước trên giao diện chỉ điều chỉnh góc nhìn và bố cục tác vụ./i,
      ),
    ).toBeInTheDocument();
  });
});
