import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  return {
    apiGet: vi.fn(),
    getOnboarding: vi.fn(),
    getProfileContext: vi.fn(),
    listFamilyNotifications: vi.fn(),
    routerReplace,
    router: { replace: routerReplace },
    pathname: "/chat",
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/sidebar-nav", () => ({
  default: () => (
    <aside aria-label="Shared primary navigation" data-testid="shared-sidebar" />
  ),
}));

vi.mock("@/components/navigation/app-topbar", () => ({
  default: () => <header data-testid="shared-topbar" />,
}));

vi.mock("@/components/navigation/mobile-bottom-nav", () => ({
  default: () => (
    <nav aria-label="Shared mobile navigation" data-testid="mobile-bottom-nav" />
  ),
}));

vi.mock("@/components/compliance/transparency-notice-gate", () => ({
  default: () => null,
}));

vi.mock("@/lib/auth-store", () => ({
  clearTokens: vi.fn(),
  getRole: () => "normal",
  setRole: vi.fn(),
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: mocks.apiGet,
  },
}));

vi.mock("@/lib/logout", () => ({
  beginLogout: vi.fn(),
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: mocks.getOnboarding,
}));

vi.mock("@/lib/profile-context-api", () => ({
  activateOwnedProfile: vi.fn(),
  getProfileContext: mocks.getProfileContext,
}));

vi.mock("@/lib/visit-family", () => ({
  listFamilyNotifications: mocks.listFamilyNotifications,
}));

import AppShell from "@/components/app-shell";

describe("AppShell authenticated Chat navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/chat";
    window.localStorage.clear();
    mocks.apiGet.mockResolvedValue({ data: { role: "normal" } });
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: false });
    mocks.getProfileContext.mockResolvedValue({
      active_profile_id: "",
      reset_required: false,
      profiles: [],
    });
    mocks.listFamilyNotifications.mockResolvedValue([]);
    vi.stubGlobal(
      "matchMedia",
      vi.fn().mockReturnValue({
        matches: false,
        media: "(min-width: 1024px)",
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    );
  });

  it("keeps every shared navigation surface mounted on /chat", async () => {
    render(
      <AppShell>
        <div>Chat content</div>
      </AppShell>,
    );

    expect(screen.getByTestId("shared-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("shared-topbar")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mở điều hướng trên điện thoại" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("mobile-bottom-nav")).toBeInTheDocument();
    expect(screen.getByText("Chat content")).toBeInTheDocument();

    await waitFor(() => {
      expect(mocks.apiGet).toHaveBeenCalledWith("/auth/me", {
        timeout: 15000,
      });
    });
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });

  it("uses bundled SVG controls in the mobile shell when the icon font is unavailable", async () => {
    render(
      <AppShell>
        <div>Chat content</div>
      </AppShell>,
    );

    const trigger = screen.getByRole("button", { name: "Mở điều hướng trên điện thoại" });
    expect(trigger.querySelector('[data-icon="menu"]')).toBeTruthy();
    fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Đóng menu" }).querySelector('[data-icon="close"]')).toBeTruthy();
  });

  it("keeps nested welcome steps inside the focused authenticated utility shell", async () => {
    mocks.pathname = "/welcome/body";
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

    const { container } = render(
      <AppShell>
        <div>Body measurements</div>
      </AppShell>,
    );

    expect(screen.getByText("Body measurements")).toBeInTheDocument();
    expect(screen.queryByTestId("shared-sidebar")).not.toBeInTheDocument();
    expect(container.querySelectorAll("main")).toHaveLength(1);
    await waitFor(() => expect(mocks.getOnboarding).toHaveBeenCalled());
    expect(mocks.routerReplace).not.toHaveBeenCalled();
  });

  it("redirects an unfinished user to the canonical first welcome step", async () => {
    mocks.pathname = "/today";
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: true });

    render(
      <AppShell>
        <div>Today content</div>
      </AppShell>,
    );

    await waitFor(() => {
      expect(mocks.routerReplace).toHaveBeenCalledWith("/welcome/start");
    });
  });
});
