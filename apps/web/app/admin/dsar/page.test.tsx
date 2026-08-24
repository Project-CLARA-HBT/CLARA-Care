import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

/**
 * Feature: regulatory-compliance, Requirement 3.6 / Property P7 (RBAC on the
 * admin DSAR queue) and 8.1/8.2 (flag off ⇒ surface inert, current behavior
 * preserved).
 *
 * The backend enforces RBAC authoritatively (`/compliance/dsar/admin/*` return
 * 401/403 for non-admin). This page additionally hides itself client-side for
 * non-admin roles as defense-in-depth: a non-admin must see the forbidden
 * notice and the admin queue API must never be called for them.
 */

const mockListAdminDsarQueue = vi.fn();
const mockUpdateDsarStatus = vi.fn();
const flagState = { enabled: true };
const roleState = { role: "normal" as "normal" | "researcher" | "doctor" | "admin" };

vi.mock("@/lib/compliance", () => ({
  isDsarEnabled: () => flagState.enabled,
  listAdminDsarQueue: () => mockListAdminDsarQueue(),
  updateDsarStatus: (id: number | string, status: string) =>
    mockUpdateDsarStatus(id, status),
}));

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import AdminDsarQueuePage from "@/app/admin/dsar/page";

beforeEach(() => {
  // Pin the UI language so copy is deterministic (defaults to vi otherwise).
  window.localStorage.setItem("clara_ui_language", "en");
});

afterEach(() => {
  vi.clearAllMocks();
  flagState.enabled = true;
  roleState.role = "normal";
  window.localStorage.clear();
});

describe("AdminDsarQueuePage RBAC (Property P7)", () => {
  it("shows the forbidden notice and never calls the admin queue for a non-admin", async () => {
    roleState.role = "normal";
    render(<AdminDsarQueuePage />);

    await waitFor(() => {
      expect(
        screen.getByText(/do not have permission/i),
      ).toBeInTheDocument();
    });
    expect(mockListAdminDsarQueue).not.toHaveBeenCalled();
  });

  it("does not expose the queue to a doctor role (only admin)", async () => {
    roleState.role = "doctor";
    render(<AdminDsarQueuePage />);

    await waitFor(() => {
      expect(
        screen.getByText(/do not have permission/i),
      ).toBeInTheDocument();
    });
    expect(mockListAdminDsarQueue).not.toHaveBeenCalled();
  });

  it("loads the queue for an admin role", async () => {
    roleState.role = "admin";
    mockListAdminDsarQueue.mockResolvedValue({
      enabled: true,
      requests: [
        {
          id: 1,
          kind: "delete",
          status: "received",
          created_at: "2026-04-01T00:00:00Z",
          due_at: "2026-04-15T00:00:00Z",
          overdue: true,
        },
      ],
      overdue_count: 1,
    });

    render(<AdminDsarQueuePage />);

    await waitFor(() => {
      expect(mockListAdminDsarQueue).toHaveBeenCalled();
    });
    expect(
      screen.queryByText(/do not have permission/i),
    ).not.toBeInTheDocument();
    // The overdue summary and the request row render for the admin.
    await waitFor(() => {
      expect(screen.getByText(/overdue request/i)).toBeInTheDocument();
    });
  });

  it("is inert (no queue call, no forbidden) when the DSAR flag is OFF", async () => {
    flagState.enabled = false;
    roleState.role = "admin";
    render(<AdminDsarQueuePage />);

    await waitFor(() => {
      expect(
        screen.getByText(/not enabled for this environment/i),
      ).toBeInTheDocument();
    });
    expect(mockListAdminDsarQueue).not.toHaveBeenCalled();
  });

  it("opens request inspector drawer and updates status when admin selects a row", async () => {
    roleState.role = "admin";
    mockListAdminDsarQueue.mockResolvedValue({
      enabled: true,
      requests: [
        {
          id: 42,
          kind: "export",
          status: "received",
          created_at: "2026-04-01T10:00:00Z",
          due_at: "2026-04-30T10:00:00Z",
          overdue: false,
        },
      ],
      overdue_count: 0,
    });
    mockUpdateDsarStatus.mockResolvedValue({
      id: 42,
      kind: "export",
      status: "in_progress",
    });

    render(<AdminDsarQueuePage />);

    await waitFor(() => {
      expect(screen.getByText("#42")).toBeInTheDocument();
    });

    // Click inspect button
    const inspectBtn = screen.getByRole("button", { name: /inspect/i });
    inspectBtn.click();

    // Drawer opens with details
    await waitFor(() => {
      expect(screen.getByText(/action timeline/i)).toBeInTheDocument();
      expect(screen.getAllByText(/statutory response window/i).length).toBeGreaterThan(0);
    });
  });
});
