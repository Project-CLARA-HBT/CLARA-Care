import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionBoundary, useSession } from "./session-boundary";

const mocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  return {
    apiGet: vi.fn(),
    getOnboarding: vi.fn(),
    clearTokens: vi.fn(),
    beginLogout: vi.fn(),
    routerReplace,
    router: { replace: routerReplace },
    pathname: "/home",
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.pathname,
  useRouter: () => mocks.router,
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: mocks.apiGet,
  },
}));

vi.mock("@/lib/auth-store", () => ({
  clearTokens: mocks.clearTokens,
  getRole: () => "normal",
  setRole: vi.fn(),
}));

vi.mock("@/lib/logout", () => ({
  beginLogout: mocks.beginLogout,
}));

vi.mock("@/lib/phr-onboarding", () => ({
  getPhrOnboarding: mocks.getOnboarding,
}));

function SessionConsumer() {
  const {
    role,
    effectiveRole,
    adminPreviewMode,
    setAdminPreviewMode,
    isRoleHydrated,
    isSessionChecked,
    isLoggingOut,
    handleLogout,
  } = useSession();
  return (
    <div>
      <span data-testid="role">{role}</span>
      <span data-testid="effective-role">{effectiveRole}</span>
      <span data-testid="preview-mode">{adminPreviewMode ?? "none"}</span>
      <span data-testid="hydrated">{String(isRoleHydrated)}</span>
      <span data-testid="checked">{String(isSessionChecked)}</span>
      <span data-testid="logging-out">{String(isLoggingOut)}</span>
      <button onClick={handleLogout}>Log out</button>
      <button onClick={() => setAdminPreviewMode("clinical")}>Preview Clinical</button>
      <button onClick={() => setAdminPreviewMode("research")}>Preview Research</button>
      <button onClick={() => setAdminPreviewMode("personal")}>Preview Personal</button>
      <button onClick={() => setAdminPreviewMode(null)}>Exit Preview</button>
    </div>
  );
}

describe("SessionBoundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.pathname = "/home";
    mocks.apiGet.mockResolvedValue({ data: { role: "normal" } });
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: false });
  });

  it("hydrates session role from /auth/me for protected routes", async () => {
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "doctor" } });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("hydrated")).toHaveTextContent("true");
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });
    expect(screen.getByTestId("role")).toHaveTextContent("doctor");
    expect(mocks.apiGet).toHaveBeenCalledWith("/auth/me", { timeout: 15000 });
  });

  it("clears tokens and redirects to /login on 401 unauthenticated response", async () => {
    mocks.pathname = "/health";
    const axiosError = {
      isAxiosError: true,
      response: { status: 401 },
    };
    mocks.apiGet.mockRejectedValueOnce(axiosError);

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(mocks.clearTokens).toHaveBeenCalled();
      expect(mocks.routerReplace).toHaveBeenCalledWith("/login?next=%2Fhealth");
    });
  });

  it("skips /auth/me request on public routes and hydrates immediately", async () => {
    mocks.pathname = "/login";

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    expect(screen.getByTestId("hydrated")).toHaveTextContent("true");
    expect(screen.getByTestId("checked")).toHaveTextContent("true");
    expect(mocks.apiGet).not.toHaveBeenCalled();
  });

  it("redirects unauthorized role away from protected role routes to role home", async () => {
    mocks.pathname = "/admin/overview";
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "normal" } });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(mocks.routerReplace).toHaveBeenCalledWith("/home");
    });
  });

  it("redirects unfinished user to /welcome/start when needs_onboarding is true", async () => {
    mocks.pathname = "/home";
    mocks.getOnboarding.mockResolvedValueOnce({ needs_onboarding: true });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(mocks.routerReplace).toHaveBeenCalledWith("/welcome/start");
    });
  });

  it("does not block professional role (doctor) even when needs_onboarding is true", async () => {
    mocks.pathname = "/council";
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "doctor" } });
    mocks.getOnboarding.mockResolvedValueOnce({ needs_onboarding: true });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("hydrated")).toHaveTextContent("true");
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });

    // Doctor should NOT be redirected to /welcome/start
    expect(mocks.routerReplace).not.toHaveBeenCalledWith("/welcome/start");
  });

  it("handles logout by setting loggingOut state and calling beginLogout", async () => {
    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(mocks.beginLogout).toHaveBeenCalled();
  });

  it("maps effectiveRole dynamically based on adminPreviewMode for admin role", async () => {
    mocks.pathname = "/admin";
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "admin" } });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });

    // Default admin without preview
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("admin");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("none");

    // Preview Clinical -> effectiveRole: doctor
    fireEvent.click(screen.getByRole("button", { name: "Preview Clinical" }));
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("clinical");

    // Preview Research -> effectiveRole: researcher
    fireEvent.click(screen.getByRole("button", { name: "Preview Research" }));
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("researcher");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("research");

    // Preview Personal -> effectiveRole: normal
    fireEvent.click(screen.getByRole("button", { name: "Preview Personal" }));
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("normal");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("personal");

    // Exit preview -> effectiveRole: admin
    fireEvent.click(screen.getByRole("button", { name: "Exit Preview" }));
    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("admin");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("none");
  });

  it("keeps effectiveRole unchanged for non-admin role even if preview mode is updated", async () => {
    mocks.pathname = "/council";
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "doctor" } });

    render(
      <SessionBoundary>
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });

    expect(screen.getByTestId("role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");

    fireEvent.click(screen.getByRole("button", { name: "Preview Personal" }));
    expect(screen.getByTestId("role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");
  });

  it("ensures route guarding uses authoritative role so admin previewing personal never 403s on admin routes", async () => {
    mocks.pathname = "/admin/overview";
    mocks.apiGet.mockResolvedValueOnce({ data: { role: "admin" } });

    render(
      <SessionBoundary initialPreviewMode="personal">
        <SessionConsumer />
      </SessionBoundary>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("checked")).toHaveTextContent("true");
    });

    expect(screen.getByTestId("role")).toHaveTextContent("admin");
    expect(screen.getByTestId("effective-role")).toHaveTextContent("normal");
    expect(screen.getByTestId("preview-mode")).toHaveTextContent("personal");

    // Admin should NOT be redirected to /home even though effectiveRole is normal
    expect(mocks.routerReplace).not.toHaveBeenCalledWith("/home");
  });
});
