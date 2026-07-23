import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  routerReplace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/chat",
  useRouter: () => ({ replace: mocks.routerReplace }),
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

import AppShell from "@/components/app-shell";

describe("AppShell authenticated Chat navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    mocks.apiGet.mockResolvedValue({ data: { role: "normal" } });
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
      screen.getByRole("button", { name: "Open navigation menu" }),
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
});
