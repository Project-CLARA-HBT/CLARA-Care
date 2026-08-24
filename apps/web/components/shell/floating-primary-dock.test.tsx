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
    expect(screen.getByRole("link", { name: "Hôm nay" })).toHaveAttribute("href", "/today");
    expect(screen.getByRole("link", { name: "Hành trình" })).toHaveAttribute("href", "/lifemap");
    expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Thuốc men" })).toHaveAttribute("href", "/medicines");
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
    expect(screen.getByRole("link", { name: "Hội chẩn" })).toHaveAttribute("href", "/council");
    expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Scribe" })).toHaveAttribute("href", "/scribe");
    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
  });

  it("renders researcher items for researcher role", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="researcher" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("link", { name: "Bằng chứng" })).toHaveAttribute("href", "/evidence");
    expect(screen.getByRole("link", { name: "Nguồn Y văn" })).toHaveAttribute("href", "/research/source-hub");
    expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "Cá nhân" })).toHaveAttribute("href", "/you");
  });

  it("renders admin items for admin role", () => {
    render(
      <ShellModeProvider>
        <FloatingPrimaryDock role="admin" morphState="EXPANDED" />
      </ShellModeProvider>,
    );

    expect(screen.getByRole("link", { name: "Tổng quan" })).toHaveAttribute("href", "/admin/overview");
    expect(screen.getByRole("link", { name: "Người dùng" })).toHaveAttribute("href", "/admin/users");
    expect(screen.getByRole("link", { name: "Hỏi CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Hệ thống" })).toHaveAttribute("href", "/admin/system");
    expect(screen.getByRole("link", { name: "Nhật ký" })).toHaveAttribute("href", "/admin/audit");
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
