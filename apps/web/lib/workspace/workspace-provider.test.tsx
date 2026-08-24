import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  derivePermittedWorkspaces,
  getCanonicalWorkspaceForPath,
  getDefaultWorkspace,
  getPermittedWorkspaces,
  getStoredWorkspace,
  isNeutralRoute,
  isValidAdminPreviewPersona,
  isValidWorkspace,
  reconcileWorkspaceWithRoute,
  saveStoredWorkspace,
} from "./workspace.config";
import {
  WORKSPACE_COOKIE_NAME,
  WORKSPACE_STORAGE_KEY,
  type AdminPreviewPersona,
  type UserRole,
  type WorkspaceId,
} from "./workspace.contract";
import { WorkspaceProvider, useWorkspace } from "./workspace-provider";
import * as authStore from "@/lib/auth-store";

function WorkspaceConsumer() {
  const {
    activeWorkspace,
    permittedWorkspaces,
    setActiveWorkspace,
    adminPreviewPersona,
    setAdminPreviewPersona,
  } = useWorkspace();

  return (
    <div>
      <span data-testid="active-workspace">{activeWorkspace}</span>
      <span data-testid="permitted-workspaces">
        {permittedWorkspaces.join(",")}
      </span>
      <span data-testid="admin-preview-persona">
        {adminPreviewPersona ?? "null"}
      </span>

      <button onClick={() => setActiveWorkspace("personal")}>
        Set Personal
      </button>
      <button onClick={() => setActiveWorkspace("clinical")}>
        Set Clinical
      </button>
      <button onClick={() => setActiveWorkspace("research")}>
        Set Research
      </button>
      <button onClick={() => setActiveWorkspace("admin")}>Set Admin</button>

      <button onClick={() => setAdminPreviewPersona("clinical")}>
        Set Preview Clinical
      </button>
      <button onClick={() => setAdminPreviewPersona("research")}>
        Set Preview Research
      </button>
      <button onClick={() => setAdminPreviewPersona("personal")}>
        Set Preview Personal
      </button>
      <button onClick={() => setAdminPreviewPersona(null)}>
        Clear Preview
      </button>
    </div>
  );
}

describe("Workspace Contract & Config", () => {
  describe("Pure role -> permitted workspaces derivation", () => {
    it("derives permitted workspaces for normal role -> ['personal']", () => {
      expect(getPermittedWorkspaces("normal")).toEqual(["personal"]);
      expect(derivePermittedWorkspaces("normal")).toEqual(["personal"]);
    });

    it("derives permitted workspaces for doctor role -> ['clinical', 'personal']", () => {
      expect(getPermittedWorkspaces("doctor")).toEqual(["clinical", "personal"]);
      expect(derivePermittedWorkspaces("doctor")).toEqual(["clinical", "personal"]);
    });

    it("derives permitted workspaces for researcher role -> ['research', 'personal']", () => {
      expect(getPermittedWorkspaces("researcher")).toEqual(["research", "personal"]);
      expect(derivePermittedWorkspaces("researcher")).toEqual(["research", "personal"]);
    });

    it("derives permitted workspaces for admin role -> ['admin', 'clinical', 'research', 'personal']", () => {
      expect(getPermittedWorkspaces("admin")).toEqual([
        "admin",
        "clinical",
        "research",
        "personal",
      ]);
      expect(derivePermittedWorkspaces("admin")).toEqual([
        "admin",
        "clinical",
        "research",
        "personal",
      ]);
    });

    it("falls back to ['personal'] for undefined or invalid roles", () => {
      expect(getPermittedWorkspaces(undefined)).toEqual(["personal"]);
      expect(getPermittedWorkspaces(null)).toEqual(["personal"]);
      expect(getPermittedWorkspaces("unknown" as unknown as UserRole)).toEqual(["personal"]);
    });
  });

  describe("Role default workspace derivation", () => {
    it("maps roles to their respective default workspaces", () => {
      expect(getDefaultWorkspace("normal")).toBe("personal");
      expect(getDefaultWorkspace("doctor")).toBe("clinical");
      expect(getDefaultWorkspace("researcher")).toBe("research");
      expect(getDefaultWorkspace("admin")).toBe("admin");
      expect(getDefaultWorkspace(undefined)).toBe("personal");
    });
  });

  describe("Type guards", () => {
    it("validates WorkspaceId correctly", () => {
      expect(isValidWorkspace("personal")).toBe(true);
      expect(isValidWorkspace("clinical")).toBe(true);
      expect(isValidWorkspace("research")).toBe(true);
      expect(isValidWorkspace("admin")).toBe(true);
      expect(isValidWorkspace("other")).toBe(false);
      expect(isValidWorkspace(null)).toBe(false);
    });

    it("validates AdminPreviewPersona correctly", () => {
      expect(isValidAdminPreviewPersona("clinical")).toBe(true);
      expect(isValidAdminPreviewPersona("research")).toBe(true);
      expect(isValidAdminPreviewPersona("personal")).toBe(true);
      expect(isValidAdminPreviewPersona("admin")).toBe(false);
      expect(isValidAdminPreviewPersona(null)).toBe(false);
    });
  });

  describe("Route canonical workspace mapping", () => {
    it("maps admin routes to 'admin'", () => {
      expect(getCanonicalWorkspaceForPath("/admin")).toBe("admin");
      expect(getCanonicalWorkspaceForPath("/admin/overview")).toBe("admin");
      expect(getCanonicalWorkspaceForPath("/admin/observability")).toBe("admin");
      expect(getCanonicalWorkspaceForPath("/dashboard/control-tower")).toBe("admin");
      expect(getCanonicalWorkspaceForPath("/dashboard/ecosystem")).toBe("admin");
    });

    it("maps clinical routes to 'clinical'", () => {
      expect(getCanonicalWorkspaceForPath("/clinical")).toBe("clinical");
      expect(getCanonicalWorkspaceForPath("/council")).toBe("clinical");
      expect(getCanonicalWorkspaceForPath("/council/new/intake")).toBe("clinical");
      expect(getCanonicalWorkspaceForPath("/scribe")).toBe("clinical");
    });

    it("maps research routes to 'research'", () => {
      expect(getCanonicalWorkspaceForPath("/evidence")).toBe("research");
      expect(getCanonicalWorkspaceForPath("/research/source-hub")).toBe("research");
    });

    it("maps personal routes to 'personal'", () => {
      expect(getCanonicalWorkspaceForPath("/today")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/lifemap")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/visits")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/family")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/medicines")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/phr")).toBe("personal");
      expect(getCanonicalWorkspaceForPath("/chat/shares")).toBe("personal");
    });

    it("identifies neutral routes", () => {
      expect(isNeutralRoute("/chat")).toBe(true);
      expect(isNeutralRoute("/chat/c-123")).toBe(true);
      expect(isNeutralRoute("/dashboard")).toBe(true);
      expect(isNeutralRoute("/huong-dan")).toBe(true);
      expect(isNeutralRoute("/welcome")).toBe(true);
      expect(isNeutralRoute("/council")).toBe(false);
      expect(isNeutralRoute("/admin/overview")).toBe(false);
    });
  });

  describe("reconcileWorkspaceWithRoute", () => {
    it("reconciles to route canonical workspace when permitted", () => {
      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/council",
          serverRole: "doctor",
          currentWorkspace: "personal",
        }),
      ).toBe("clinical");

      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/evidence",
          serverRole: "researcher",
          currentWorkspace: "personal",
        }),
      ).toBe("research");

      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/admin/overview",
          serverRole: "admin",
          currentWorkspace: "clinical",
        }),
      ).toBe("admin");
    });

    it("maintains current workspace on neutral routes when permitted", () => {
      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/chat",
          serverRole: "doctor",
          currentWorkspace: "clinical",
        }),
      ).toBe("clinical");

      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/dashboard",
          serverRole: "admin",
          currentWorkspace: "research",
        }),
      ).toBe("research");
    });

    it("does not allow unpermitted workspace on forbidden route", () => {
      // Normal user visits /admin/overview -> remains 'personal'
      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/admin/overview",
          serverRole: "normal",
          currentWorkspace: "personal",
        }),
      ).toBe("personal");

      // Researcher visits /council -> remains permitted (default or current)
      expect(
        reconcileWorkspaceWithRoute({
          pathname: "/council",
          serverRole: "researcher",
          currentWorkspace: "research",
        }),
      ).toBe("research");
    });
  });
});

describe("WorkspaceProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.cookie = `${WORKSPACE_COOKIE_NAME}=; Path=/; Max-Age=0`;
    document.cookie = `${authStore.ADMIN_PREVIEW_COOKIE_NAME}=; Path=/; Max-Age=0`;
    vi.clearAllMocks();
  });

  it("provides initial state for normal role", () => {
    render(
      <WorkspaceProvider serverRole="normal" pathname="/home">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("personal");
    expect(screen.getByTestId("permitted-workspaces")).toHaveTextContent("personal");
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");
  });

  it("provides initial state for doctor role", () => {
    render(
      <WorkspaceProvider serverRole="doctor" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");
    expect(screen.getByTestId("permitted-workspaces")).toHaveTextContent(
      "clinical,personal",
    );
  });

  it("provides initial state for researcher role", () => {
    render(
      <WorkspaceProvider serverRole="researcher" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("research");
    expect(screen.getByTestId("permitted-workspaces")).toHaveTextContent(
      "research,personal",
    );
  });

  it("provides initial state for admin role", () => {
    render(
      <WorkspaceProvider serverRole="admin" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("admin");
    expect(screen.getByTestId("permitted-workspaces")).toHaveTextContent(
      "admin,clinical,research,personal",
    );
  });

  it("allows switching active workspace among permitted workspaces and persists to localStorage and cookie", () => {
    render(
      <WorkspaceProvider serverRole="doctor" pathname="/chat">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");

    // Switch to personal
    fireEvent.click(screen.getByRole("button", { name: "Set Personal" }));
    expect(screen.getByTestId("active-workspace")).toHaveTextContent("personal");
    expect(window.localStorage.getItem(WORKSPACE_STORAGE_KEY)).toBe("personal");
    expect(document.cookie).toContain(`${WORKSPACE_COOKIE_NAME}=personal`);

    // Switch back to clinical
    fireEvent.click(screen.getByRole("button", { name: "Set Clinical" }));
    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");
    expect(window.localStorage.getItem(WORKSPACE_STORAGE_KEY)).toBe("clinical");
    expect(document.cookie).toContain(`${WORKSPACE_COOKIE_NAME}=clinical`);
  });

  it("blocks switching to unpermitted workspace", () => {
    render(
      <WorkspaceProvider serverRole="doctor" pathname="/chat">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    // Doctor has no access to admin workspace
    fireEvent.click(screen.getByRole("button", { name: "Set Admin" }));
    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");

    // Doctor has no access to research workspace in this contract
    fireEvent.click(screen.getByRole("button", { name: "Set Research" }));
    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");
  });

  it("manages adminPreviewPersona when serverRole is admin", () => {
    render(
      <WorkspaceProvider serverRole="admin" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");

    // Set clinical preview persona
    fireEvent.click(screen.getByRole("button", { name: "Set Preview Clinical" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("clinical");
    expect(window.localStorage.getItem(authStore.ADMIN_PREVIEW_STORAGE_KEY)).toBe("clinical");
    expect(document.cookie).toContain(`${authStore.ADMIN_PREVIEW_COOKIE_NAME}=clinical`);

    // Set research preview persona
    fireEvent.click(screen.getByRole("button", { name: "Set Preview Research" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("research");

    // Set personal preview persona
    fireEvent.click(screen.getByRole("button", { name: "Set Preview Personal" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("personal");

    // Clear preview persona
    fireEvent.click(screen.getByRole("button", { name: "Clear Preview" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");
  });

  it("disallows adminPreviewPersona for non-admin roles", () => {
    render(
      <WorkspaceProvider serverRole="doctor" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");

    fireEvent.click(screen.getByRole("button", { name: "Set Preview Clinical" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");
  });

  it("hydrates stored workspace from localStorage on load if permitted", () => {
    saveStoredWorkspace("personal");

    render(
      <WorkspaceProvider serverRole="doctor" pathname="/chat">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("personal");
  });

  it("reconciles active workspace when pathname changes to a canonical destination", () => {
    const { rerender } = render(
      <WorkspaceProvider serverRole="doctor" pathname="/today">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("personal");

    // Navigate to council
    rerender(
      <WorkspaceProvider serverRole="doctor" pathname="/council">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");
  });

  it("synchronizes active workspace across storage events", () => {
    render(
      <WorkspaceProvider serverRole="doctor" pathname="/chat">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");

    act(() => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: WORKSPACE_STORAGE_KEY,
          newValue: "personal",
        }),
      );
    });

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("personal");
  });

  it("resets adminPreviewPersona when serverRole changes from admin to another role", () => {
    const { rerender } = render(
      <WorkspaceProvider serverRole="admin" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Set Preview Clinical" }));
    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("clinical");

    // Change serverRole to doctor
    rerender(
      <WorkspaceProvider serverRole="doctor" pathname="/dashboard">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("admin-preview-persona")).toHaveTextContent("null");
  });

  it("handles pathname when pathname prop is not provided", () => {
    render(
      <WorkspaceProvider serverRole="doctor">
        <WorkspaceConsumer />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("active-workspace")).toHaveTextContent("clinical");
  });

  it("throws an error when useWorkspace is used outside WorkspaceProvider", () => {
    // Suppress console.error in test output for expected error boundary test
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<WorkspaceConsumer />)).toThrow(
      "useWorkspace must be used within a WorkspaceProvider",
    );

    consoleSpy.mockRestore();
  });
});
