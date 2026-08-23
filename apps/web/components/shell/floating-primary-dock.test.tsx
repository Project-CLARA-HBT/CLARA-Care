import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FloatingPrimaryDock } from "./floating-primary-dock";
import { ShellModeProvider } from "./shell-mode-provider";

const mocks = vi.hoisted(() => ({
  pathname: "/home",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

describe("FloatingPrimaryDock", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/home";
  });

  it("renders role-adaptive items for consumer/normal role", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="normal" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("navigation", { name: "Thanh điều hướng chính" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Hôm nay" })).toHaveAttribute("href", "/home");
    expect(screen.getByRole("link", { name: "Sức khỏe" })).toHaveAttribute("href", "/health");
    expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/ask");
    expect(screen.getByRole("link", { name: "Chăm sóc" })).toHaveAttribute("href", "/care");
    expect(screen.getByRole("link", { name: "Cá nhân" })).toHaveAttribute("href", "/you");
  });

  it("renders doctor-adaptive items for clinician role", () => {
    mocks.pathname = "/dashboard";
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="doctor" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Scribe" })).toHaveAttribute("href", "/scribe");
    expect(screen.getByRole("link", { name: "Council" })).toHaveAttribute("href", "/council");
    expect(screen.getByRole("link", { name: "Lâm sàng" })).toHaveAttribute("href", "/care");
    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
  });

  it("renders researcher items for researcher role", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="researcher" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("link", { name: "Tra cứu" })).toHaveAttribute("href", "/research");
    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
  });

  it("renders admin items for admin role", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="admin" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("link", { name: "Điều phối" })).toHaveAttribute("href", "/admin");
    expect(screen.getByRole("link", { name: "Giám sát" })).toHaveAttribute("href", "/admin/observability");
  });

  it("morphs into COMPACT state", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="normal" morphState="COMPACT" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("navigation", { name: "Thanh điều hướng thu gọn" })).toBeInTheDocument();
  });

  it("morphs into ORB_ONLY state with expand trigger", () => {
    const handleMorphChange = vi.fn();
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock
          role="normal"
          morphState="ORB_ONLY"
          onMorphStateChange={handleMorphChange}
        />
      </ShellModeProvider>,
    );

    const expandBtn = screen.getByRole("button", { name: "Mở rộng thanh điều hướng" });
    expect(expandBtn).toBeInTheDocument();
    fireEvent.click(expandBtn);
    expect(handleMorphChange).toHaveBeenCalledWith("EXPANDED");
  });

  it("morphs into CONTEXTUAL state when custom entity or actions provided", () => {
    const handleAction = vi.fn();
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock
          role="doctor"
          morphState="CONTEXTUAL"
          customEntity={{
            id: "pt-1",
            type: "patient",
            label: "Bệnh nhân: Tran Thi B",
            badge: "Khẩn cấp",
          }}
          contextualActions={[
            {
              id: "act-1",
              label: "Ký bệnh án",
              onClick: handleAction,
              tone: "brand",
            },
          ]}
        />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("toolbar", { name: "Thanh công cụ ngữ cảnh" })).toBeInTheDocument();
    expect(screen.getByText("Bệnh nhân: Tran Thi B")).toBeInTheDocument();
    expect(screen.getByText("Khẩn cấp")).toBeInTheDocument();

    const signBtn = screen.getByRole("button", { name: "Ký bệnh án" });
    fireEvent.click(signBtn);
    expect(handleAction).toHaveBeenCalledTimes(1);
  });

  it("morphs into HIDDEN_WITH_ESCAPE state with reveal handle", () => {
    const handleMorphChange = vi.fn();
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock
          role="normal"
          morphState="HIDDEN_WITH_ESCAPE"
          onMorphStateChange={handleMorphChange}
        />
      </ShellModeProvider>,
    );

    const revealBtn = screen.getByRole("button", { name: /Mở thanh điều hướng/ });
    expect(revealBtn).toBeInTheDocument();
    fireEvent.click(revealBtn);
    expect(handleMorphChange).toHaveBeenCalledWith("EXPANDED");
  });
});
