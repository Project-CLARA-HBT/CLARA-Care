import { render, renderHook, screen, waitFor, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import React from "react";
import {
  SessionProvider,
  useSession,
  useServerSession,
} from "./session-provider";
import { normalizeServerRole, type ServerSessionState } from "./session.contract";
import { TestSessionInjector } from "./test-session-injector";
import * as authStore from "@/lib/auth-store";
import api from "@/lib/http-client";

// Mock api client
vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

function ConsumerComponent() {
  const session = useSession();
  return (
    <div>
      <div data-testid="is-hydrating">{String(session.isHydrating)}</div>
      <div data-testid="is-authenticated">{String(session.isAuthenticated)}</div>
      <div data-testid="server-role">{session.serverRole ?? "null"}</div>
      <div data-testid="user-id">{session.user?.id ?? "none"}</div>
      <div data-testid="user-email">{session.user?.email ?? "none"}</div>
      <div data-testid="user-name">{session.user?.full_name ?? "none"}</div>
      <div data-testid="error-message">{session.error?.message ?? "none"}</div>
      <button onClick={() => session.refreshSession()} data-testid="refresh-btn">
        Refresh
      </button>
      <button onClick={() => session.logout()} data-testid="logout-btn">
        Logout
      </button>
    </div>
  );
}

describe("Session Contract & Normalization", () => {
  it("normalizes valid roles correctly", () => {
    expect(normalizeServerRole("normal")).toBe("normal");
    expect(normalizeServerRole("researcher")).toBe("researcher");
    expect(normalizeServerRole("doctor")).toBe("doctor");
    expect(normalizeServerRole("admin")).toBe("admin");
  });

  it("returns null for invalid roles or malicious inputs", () => {
    expect(normalizeServerRole("superuser")).toBeNull();
    expect(normalizeServerRole("root")).toBeNull();
    expect(normalizeServerRole("")).toBeNull();
    expect(normalizeServerRole(null)).toBeNull();
    expect(normalizeServerRole(undefined)).toBeNull();
    expect(normalizeServerRole(123)).toBeNull();
    expect(normalizeServerRole({})).toBeNull();
  });
});

describe("SessionProvider — Server-Authoritative State & Hydration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authStore.clearTokens();
  });

  it("hydrates authenticated user and serverRole from /auth/me", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        id: "user-123",
        role: "doctor",
        email: "doctor@clara.vn",
        full_name: "Dr. Clara Care",
      },
    });

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    // Initial state is hydrating
    expect(screen.getByTestId("is-hydrating")).toHaveTextContent("true");
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");

    await waitFor(() => {
      expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("server-role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("user-id")).toHaveTextContent("user-123");
    expect(screen.getByTestId("user-email")).toHaveTextContent("doctor@clara.vn");
    expect(screen.getByTestId("user-name")).toHaveTextContent("Dr. Clara Care");
    expect(screen.getByTestId("error-message")).toHaveTextContent("none");

    // auth-store getRole() reflects authoritative server role
    expect(authStore.getRole()).toBe("doctor");
    expect(api.get).toHaveBeenCalledWith("/auth/me", { timeout: 15000 });
  });

  it("handles subject fallback when email/id are in subject field", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: {
        subject: "patient@example.com",
        role: "normal",
        full_name: "Nguyen Van A",
      },
    });

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("server-role")).toHaveTextContent("normal");
    expect(screen.getByTestId("user-id")).toHaveTextContent("patient@example.com");
    expect(screen.getByTestId("user-email")).toHaveTextContent("patient@example.com");
    expect(screen.getByTestId("user-name")).toHaveTextContent("Nguyen Van A");
  });

  it("handles 401 unauthenticated response gracefully", async () => {
    const error401 = {
      isAxiosError: true,
      response: { status: 401, data: { detail: "Unauthorized" } },
    };
    vi.mocked(api.get).mockRejectedValueOnce(error401);

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("server-role")).toHaveTextContent("null");
    expect(screen.getByTestId("user-id")).toHaveTextContent("none");
    expect(screen.getByTestId("error-message")).toHaveTextContent("none");
    expect(authStore.getRole()).toBe("normal");
  });

  it("handles network / 500 error response and sets error state", async () => {
    const error500 = new Error("Network Error");
    vi.mocked(api.get).mockRejectedValueOnce(error500);

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("server-role")).toHaveTextContent("null");
    expect(screen.getByTestId("error-message")).toHaveTextContent("Network Error");
  });

  it("deduplicates parallel hydration requests", async () => {
    vi.mocked(api.get).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                data: {
                  id: "1",
                  email: "test@example.com",
                  role: "admin",
                },
              }),
            50,
          ),
        ),
    );

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    // Click refresh while initial hydration is still inflight
    const refreshBtn = screen.getByTestId("refresh-btn");
    fireEventClick(refreshBtn);

    await waitFor(() => {
      expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    });

    // Should only call /auth/me once during initial load deduplication
    expect(api.get).toHaveBeenCalledTimes(1);
  });
});

describe("SessionProvider — Read-Only Role & Immutability Invariant", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authStore.clearTokens();
  });

  it("strictly exposes no setRole method on ServerSessionState", async () => {
    let capturedSession: ServerSessionState | null = null;
    function Inspector() {
      capturedSession = useSession();
      return <div>hydrating: {String(capturedSession.isHydrating)}</div>;
    }

    vi.mocked(api.get).mockResolvedValueOnce({
      data: { id: "1", email: "user@clara.vn", role: "normal" },
    });

    render(
      <SessionProvider>
        <Inspector />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(capturedSession?.isHydrating).toBe(false);
    });

    expect(capturedSession).toBeDefined();
    // Verify no setRole property exists on production session state
    expect((capturedSession as unknown as { setRole?: unknown }).setRole).toBeUndefined();
  });

  it("reads role strictly from session state, ignoring forged localStorage values", () => {
    // Attempt local storage poisoning
    window.localStorage.setItem("clara_role", "admin");

    // auth-store getRole() ignores unhydrated localStorage tampering
    expect(authStore.getRole()).toBe("normal");
  });
});

describe("SessionProvider — Refresh & Logout", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authStore.clearTokens();
  });

  it("refreshes session when refreshSession is called", async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({
        data: { id: "u-1", email: "first@clara.vn", role: "normal" },
      })
      .mockResolvedValueOnce({
        data: { id: "u-1", email: "first@clara.vn", role: "researcher" },
      });

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("server-role")).toHaveTextContent("normal");
    });

    // Trigger refresh
    await act(async () => {
      screen.getByTestId("refresh-btn").click();
    });

    await waitFor(() => {
      expect(screen.getByTestId("server-role")).toHaveTextContent("researcher");
    });

    expect(api.get).toHaveBeenCalledTimes(2);
    expect(authStore.getRole()).toBe("researcher");
  });

  it("executes logout, clearing tokens, resetting state and navigating to /logout", async () => {
    vi.mocked(api.get).mockResolvedValueOnce({
      data: { id: "u-1", email: "user@clara.vn", role: "admin" },
    });
    vi.mocked(api.post).mockResolvedValueOnce({ data: { logged_out: true } });

    // Mock window.location.replace
    const replaceMock = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...originalLocation, replace: replaceMock },
    });

    render(
      <SessionProvider>
        <ConsumerComponent />
      </SessionProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("server-role")).toHaveTextContent("admin");
    });

    await act(async () => {
      screen.getByTestId("logout-btn").click();
    });

    expect(api.post).toHaveBeenCalledWith("/auth/logout", {}, { timeout: 5000 });
    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("false");
    expect(screen.getByTestId("server-role")).toHaveTextContent("null");
    expect(replaceMock).toHaveBeenCalledWith("/logout");

    // Restore original window.location
    Object.defineProperty(window, "location", {
      configurable: true,
      value: originalLocation,
    });
  });
});

describe("useSession Hook Constraints", () => {
  it("throws an error when used outside of SessionProvider", () => {
    // Suppress console.error for expected thrown boundary error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useSession())).toThrow(
      "useSession must be used within a SessionProvider",
    );

    expect(() => renderHook(() => useServerSession())).toThrow(
      "useSession must be used within a SessionProvider",
    );

    spy.mockRestore();
  });
});

describe("TestSessionInjector — Unit Test Mock Utility", () => {
  beforeEach(() => {
    authStore.clearTokens();
  });

  it("injects custom mock session values into child components", () => {
    render(
      <TestSessionInjector
        role="doctor"
        user={{ id: "doc-99", email: "doc99@hospital.vn", full_name: "Dr. Strange" }}
        isAuthenticated={true}
        isHydrating={false}
      >
        <ConsumerComponent />
      </TestSessionInjector>,
    );

    expect(screen.getByTestId("is-authenticated")).toHaveTextContent("true");
    expect(screen.getByTestId("is-hydrating")).toHaveTextContent("false");
    expect(screen.getByTestId("server-role")).toHaveTextContent("doctor");
    expect(screen.getByTestId("user-id")).toHaveTextContent("doc-99");
    expect(screen.getByTestId("user-email")).toHaveTextContent("doc99@hospital.vn");
    expect(screen.getByTestId("user-name")).toHaveTextContent("Dr. Strange");
    expect(authStore.getRole()).toBe("doctor");
  });

  it("accepts sessionState overrides object", () => {
    render(
      <TestSessionInjector
        sessionState={{
          serverRole: "researcher",
          isAuthenticated: true,
          isHydrating: false,
          user: { id: "res-1", email: "researcher@clara.vn" },
        }}
      >
        <ConsumerComponent />
      </TestSessionInjector>,
    );

    expect(screen.getByTestId("server-role")).toHaveTextContent("researcher");
    expect(screen.getByTestId("user-id")).toHaveTextContent("res-1");
  });

  it("supports mock logout and refreshSession triggers", async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined);
    const mockRefresh = vi.fn().mockResolvedValue(undefined);

    render(
      <TestSessionInjector logout={mockLogout} refreshSession={mockRefresh}>
        <ConsumerComponent />
      </TestSessionInjector>,
    );

    await act(async () => {
      screen.getByTestId("refresh-btn").click();
    });
    expect(mockRefresh).toHaveBeenCalledTimes(1);

    await act(async () => {
      screen.getByTestId("logout-btn").click();
    });
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });
});

function fireEventClick(element: HTMLElement) {
  element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}
