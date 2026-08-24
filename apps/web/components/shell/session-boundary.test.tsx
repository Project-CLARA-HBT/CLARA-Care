import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ADMIN_PREVIEW_CHANGE_EVENT,
  ADMIN_PREVIEW_STORAGE_KEY,
  ROLE_CHANGE_EVENT,
  ROLE_KEY,
  SESSION_CHANGE_EVENT,
  SessionBoundary,
  useSession,
} from "./session-boundary";
import { isRouteAllowedForRole } from "@/lib/navigation.access";

const mocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  let storedRole = "normal";
  let storedAdminPreviewMode: string | null = null;
  return {
    apiGet: vi.fn(),
    getOnboarding: vi.fn(),
    clearTokens: vi.fn(),
    beginLogout: vi.fn(),
    routerReplace,
    router: { replace: routerReplace },
    pathname: "/home",
    getStoredRole: () => storedRole,
    setStoredRole: vi.fn((role: string) => {
      storedRole = role;
    }),
    getStoredAdminPreviewMode: vi.fn(() => storedAdminPreviewMode),
    setStoredAdminPreviewMode: vi.fn((mode: string | null) => {
      storedAdminPreviewMode = mode;
    }),
    resetStorage: () => {
      storedRole = "normal";
      storedAdminPreviewMode = null;
    },
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
  getRole: () => mocks.getStoredRole(),
  setAuthoritativeServerRole: mocks.setStoredRole,
  getStoredAdminPreviewMode: mocks.getStoredAdminPreviewMode,
  setStoredAdminPreviewMode: mocks.setStoredAdminPreviewMode,
  ADMIN_PREVIEW_STORAGE_KEY: "clara_admin_preview_mode",
  ADMIN_PREVIEW_COOKIE_NAME: "clara_admin_preview_mode",
  ADMIN_PREVIEW_CHANGE_EVENT: "clara:admin-preview-change",
  ROLE_CHANGE_EVENT: "clara:role-change",
  ROLE_KEY: "clara_role",
  SESSION_CHANGE_EVENT: "clara:session-change",
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
    setRole,
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
      <button onClick={() => setRole("doctor")}>Set Doctor Role</button>
      <button onClick={() => setRole("researcher")}>Set Researcher Role</button>
      <button onClick={() => setRole("admin")}>Set Admin Role</button>
      <button onClick={() => setRole("normal")}>Set Normal Role</button>
    </div>
  );
}

describe("SessionBoundary & Navigation Access Policy", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.resetStorage();
    mocks.pathname = "/home";
    mocks.apiGet.mockResolvedValue({ data: { role: "normal" } });
    mocks.getOnboarding.mockResolvedValue({ needs_onboarding: false });
  });

  describe("Session Hydration & Auth", () => {
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
      expect(mocks.setStoredRole).toHaveBeenCalledWith("doctor");
    });

    it("clears tokens, resets preview mode, and redirects to /login on 401 unauthenticated response", async () => {
      mocks.pathname = "/health";
      const axiosError = {
        isAxiosError: true,
        response: { status: 401 },
      };
      mocks.apiGet.mockRejectedValueOnce(axiosError);

      render(
        <SessionBoundary initialPreviewMode="clinical">
          <SessionConsumer />
        </SessionBoundary>,
      );

      await waitFor(() => {
        expect(mocks.clearTokens).toHaveBeenCalled();
        expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBeNull();
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

      expect(mocks.routerReplace).not.toHaveBeenCalledWith("/welcome/start");
    });

    it("handles logout by setting loggingOut state, clearing preview mode, and calling beginLogout", async () => {
      render(
        <SessionBoundary initialPreviewMode="clinical">
          <SessionConsumer />
        </SessionBoundary>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checked")).toHaveTextContent("true");
      });

      fireEvent.click(screen.getByRole("button", { name: "Log out" }));
      expect(screen.getByTestId("logging-out")).toHaveTextContent("true");
      expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBeNull();
      expect(mocks.beginLogout).toHaveBeenCalled();
    });
  });

  describe("setAdminPreviewMode & effectiveRole", () => {
    it("maps effectiveRole dynamically based on adminPreviewMode for admin role, updates storage, and dispatches events", async () => {
      mocks.pathname = "/admin";
      mocks.apiGet.mockResolvedValueOnce({ data: { role: "admin" } });

      const previewListener = vi.fn();
      const sessionListener = vi.fn();
      window.addEventListener(ADMIN_PREVIEW_CHANGE_EVENT, previewListener);
      window.addEventListener(SESSION_CHANGE_EVENT, sessionListener);

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
      expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBe("clinical");
      expect(document.cookie).toContain("clara_admin_preview_mode=clinical");
      expect(previewListener).toHaveBeenCalledWith(
        expect.objectContaining({ detail: "clinical" }),
      );
      expect(sessionListener).toHaveBeenCalledWith(
        expect.objectContaining({ detail: { adminPreviewMode: "clinical" } }),
      );

      // Preview Research -> effectiveRole: researcher
      fireEvent.click(screen.getByRole("button", { name: "Preview Research" }));
      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("researcher");
      expect(screen.getByTestId("preview-mode")).toHaveTextContent("research");
      expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBe("research");

      // Preview Personal -> effectiveRole: normal
      fireEvent.click(screen.getByRole("button", { name: "Preview Personal" }));
      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("normal");
      expect(screen.getByTestId("preview-mode")).toHaveTextContent("personal");
      expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBe("personal");

      // Exit preview -> effectiveRole: admin
      fireEvent.click(screen.getByRole("button", { name: "Exit Preview" }));
      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("admin");
      expect(screen.getByTestId("preview-mode")).toHaveTextContent("none");
      expect(localStorage.getItem(ADMIN_PREVIEW_STORAGE_KEY)).toBeNull();

      window.removeEventListener(ADMIN_PREVIEW_CHANGE_EVENT, previewListener);
      window.removeEventListener(SESSION_CHANGE_EVENT, sessionListener);
    });

    it("keeps effectiveRole unchanged for non-admin role even if preview mode is set", async () => {
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

    it("re-renders and synchronizes immediately when an external ADMIN_PREVIEW_CHANGE_EVENT is dispatched", async () => {
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

      act(() => {
        window.dispatchEvent(
          new CustomEvent(ADMIN_PREVIEW_CHANGE_EVENT, { detail: "research" }),
        );
      });

      expect(screen.getByTestId("preview-mode")).toHaveTextContent("research");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("researcher");
    });

    it("re-renders and synchronizes immediately when storage event fires for ADMIN_PREVIEW_STORAGE_KEY", async () => {
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

      act(() => {
        const storageEvent = new StorageEvent("storage", {
          key: ADMIN_PREVIEW_STORAGE_KEY,
          newValue: "clinical",
        });
        window.dispatchEvent(storageEvent);
      });

      expect(screen.getByTestId("preview-mode")).toHaveTextContent("clinical");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");
    });
  });

  describe("setRole in Development / Preview", () => {
    it("allows switching roles via setRole, updating state and storage without session dropout", async () => {
      mocks.pathname = "/chat";
      mocks.apiGet.mockResolvedValueOnce({ data: { role: "normal" } });

      const roleListener = vi.fn();
      window.addEventListener(ROLE_CHANGE_EVENT, roleListener);

      render(
        <SessionBoundary>
          <SessionConsumer />
        </SessionBoundary>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checked")).toHaveTextContent("true");
      });

      expect(screen.getByTestId("role")).toHaveTextContent("normal");

      // Switch to Doctor
      fireEvent.click(screen.getByRole("button", { name: "Set Doctor Role" }));
      expect(screen.getByTestId("role")).toHaveTextContent("doctor");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");
      expect(mocks.setStoredRole).toHaveBeenCalledWith("doctor");
      expect(roleListener).toHaveBeenCalledWith(
        expect.objectContaining({ detail: "doctor" }),
      );

      // On /chat, doctor is authorized, so no redirect should occur
      expect(mocks.routerReplace).not.toHaveBeenCalled();

      // Switch to Researcher
      fireEvent.click(screen.getByRole("button", { name: "Set Researcher Role" }));
      expect(screen.getByTestId("role")).toHaveTextContent("researcher");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("researcher");
      expect(mocks.setStoredRole).toHaveBeenCalledWith("researcher");

      // Switch to Admin
      fireEvent.click(screen.getByRole("button", { name: "Set Admin Role" }));
      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("admin");
      expect(mocks.setStoredRole).toHaveBeenCalledWith("admin");

      window.removeEventListener(ROLE_CHANGE_EVENT, roleListener);
    });

    it("redirects cleanly to role home path when role switches to an unauthorized role without infinite loops", async () => {
      mocks.pathname = "/admin/overview";
      mocks.apiGet.mockResolvedValueOnce({ data: { role: "admin" } });

      render(
        <SessionBoundary>
          <SessionConsumer />
        </SessionBoundary>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checked")).toHaveTextContent("true");
      });

      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(mocks.routerReplace).not.toHaveBeenCalled();

      // Switch to normal role on /admin/overview (unauthorized for normal)
      fireEvent.click(screen.getByRole("button", { name: "Set Normal Role" }));
      expect(screen.getByTestId("role")).toHaveTextContent("normal");

      // Should redirect to /home exactly once
      await waitFor(() => {
        expect(mocks.routerReplace).toHaveBeenCalledWith("/home");
      });
      expect(mocks.routerReplace).toHaveBeenCalledTimes(1);
    });

    it("synchronizes role state when external ROLE_CHANGE_EVENT or storage event occurs", async () => {
      mocks.pathname = "/chat";
      mocks.apiGet.mockResolvedValueOnce({ data: { role: "normal" } });

      render(
        <SessionBoundary>
          <SessionConsumer />
        </SessionBoundary>,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checked")).toHaveTextContent("true");
      });

      act(() => {
        window.dispatchEvent(new CustomEvent(ROLE_CHANGE_EVENT, { detail: "doctor" }));
      });

      expect(screen.getByTestId("role")).toHaveTextContent("doctor");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("doctor");

      act(() => {
        const storageEvent = new StorageEvent("storage", {
          key: ROLE_KEY,
          newValue: "admin",
        });
        window.dispatchEvent(storageEvent);
      });

      expect(screen.getByTestId("role")).toHaveTextContent("admin");
      expect(screen.getByTestId("effective-role")).toHaveTextContent("admin");
    });
  });

  describe("isRouteAllowedForRole Comprehensive Safety", () => {
    const ALL_WORKSPACE_PATHS = [
      // Personal Workspace
      "/home",
      "/today",
      "/chat",
      "/lifemap",
      "/medicines",
      "/phr",
      "/visits",
      "/family",
      "/huong-dan",
      "/ask",
      "/health",
      "/care",
      "/you",
      "/selfmed",
      "/careguard",
      // Clinical Workspace
      "/dashboard",
      "/clinical",
      "/council",
      "/scribe",
      // Research Workspace
      "/research",
      "/evidence",
      "/research/source-hub",
      // Admin Workspace
      "/admin",
      "/admin/overview",
      "/admin/knowledge-sources",
      "/admin/answer-flow",
      "/admin/observability",
      "/admin/community-moderation",
      "/admin/analytics",
      "/admin/analytics/clinical",
      "/admin/audit-log",
      "/admin/rag-eval",
      "/admin/rag-ingestion",
      "/dashboard/control-tower",
      "/dashboard/ecosystem",
      // Deeply nested and parametrized paths
      "/admin/custom-feature?view=grid&sort=asc#top",
      "/council/case-123?mode=full",
      "/chat/thread-abc",
      "/unknown/deep/path/for/admin",
    ];

    it("never throws and always permits Admin on every workspace view and route", () => {
      for (const path of ALL_WORKSPACE_PATHS) {
        expect(isRouteAllowedForRole(path, "admin")).toBe(true);
      }
      // Malformed, empty, and nullish edge cases
      expect(isRouteAllowedForRole(undefined, "admin")).toBe(true);
      expect(isRouteAllowedForRole(null, "admin")).toBe(true);
      expect(isRouteAllowedForRole("", "admin")).toBe(true);
      expect(isRouteAllowedForRole("   ", "admin")).toBe(true);
    });

    it("safely validates non-admin roles without throwing on malformed or query-string inputs", () => {
      // Safe handling of null/undefined
      expect(isRouteAllowedForRole(undefined, "normal")).toBe(false);
      expect(isRouteAllowedForRole(null, "normal")).toBe(false);
      expect(isRouteAllowedForRole("", "normal")).toBe(false);

      // Normal role allowed on personal care paths with query strings
      expect(isRouteAllowedForRole("/home?tab=1", "normal")).toBe(true);
      expect(isRouteAllowedForRole("/today?date=2026-08-24", "normal")).toBe(true);
      expect(isRouteAllowedForRole("/chat#message-5", "normal")).toBe(true);
      expect(isRouteAllowedForRole("/medicines?search=aspirin", "normal")).toBe(true);

      // Normal role blocked on admin and clinical routes
      expect(isRouteAllowedForRole("/admin/overview", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/council", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/scribe", "normal")).toBe(false);
      expect(isRouteAllowedForRole("/dashboard", "normal")).toBe(false);

      // Doctor role allowed on clinical and dashboard
      expect(isRouteAllowedForRole("/dashboard", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/council", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/scribe", "doctor")).toBe(true);
      expect(isRouteAllowedForRole("/admin/overview", "doctor")).toBe(false);

      // Researcher role allowed on research and dashboard
      expect(isRouteAllowedForRole("/dashboard", "researcher")).toBe(true);
      expect(isRouteAllowedForRole("/research", "researcher")).toBe(true);
      expect(isRouteAllowedForRole("/research/source-hub", "researcher")).toBe(true);
      expect(isRouteAllowedForRole("/council", "researcher")).toBe(false);
    });

    it("ensures Admin in preview mode (e.g. personal) retains authoritative Admin route access", async () => {
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

      // Admin should NEVER be redirected away from /admin/overview even in preview mode
      expect(mocks.routerReplace).not.toHaveBeenCalled();
    });
  });
});
