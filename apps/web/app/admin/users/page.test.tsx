import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mockListAdminUsers = vi.fn();
const mockUpdateUserRole = vi.fn();
const mockLockUserAccount = vi.fn();
const mockUnlockUserAccount = vi.fn();
const mockRevokeUserSessions = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/admin-users", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-users")>();
  return {
    ...actual,
    listAdminUsers: () => mockListAdminUsers(),
    updateUserRole: (userId: string, newRole: any, reason?: string) =>
      mockUpdateUserRole(userId, newRole, reason),
    lockUserAccount: (userId: string, reason: string) =>
      mockLockUserAccount(userId, reason),
    unlockUserAccount: (userId: string) =>
      mockUnlockUserAccount(userId),
    revokeUserSessions: (userId: string) =>
      mockRevokeUserSessions(userId),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import AdminUsersPage from "@/app/admin/users/page";
import { SEED_ADMIN_USERS } from "@/lib/admin-users";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockListAdminUsers.mockResolvedValue([...SEED_ADMIN_USERS]);
  mockUpdateUserRole.mockImplementation(async (userId, newRole, reason) => {
    const user = SEED_ADMIN_USERS.find((u) => u.id === userId) || SEED_ADMIN_USERS[0];
    return {
      success: true,
      user: {
        ...user,
        role: newRole,
        auditHistory: [
          {
            id: "aud_test_role",
            action: "role_updated",
            actionLabelVi: `Cập nhật vai trò sang ${newRole}`,
            actionLabelEn: `Role updated to ${newRole}`,
            actor: "Admin Tester",
            timestamp: new Date().toISOString(),
            details: reason,
          },
          ...user.auditHistory,
        ],
      },
    };
  });
  mockLockUserAccount.mockImplementation(async (userId, reason) => {
    const user = SEED_ADMIN_USERS.find((u) => u.id === userId) || SEED_ADMIN_USERS[0];
    return {
      success: true,
      user: {
        ...user,
        status: "locked",
        activeSessionsCount: 0,
        lockReason: reason,
        lockedAt: new Date().toISOString(),
        lockedBy: "Admin Tester",
        auditHistory: [
          {
            id: "aud_test_lock",
            action: "account_locked",
            actionLabelVi: "Khóa tài khoản",
            actionLabelEn: "Account locked",
            actor: "Admin Tester",
            timestamp: new Date().toISOString(),
            details: reason,
          },
          ...user.auditHistory,
        ],
      },
    };
  });
  mockUnlockUserAccount.mockImplementation(async (userId) => {
    const user = SEED_ADMIN_USERS.find((u) => u.id === userId) || SEED_ADMIN_USERS[0];
    return {
      success: true,
      user: {
        ...user,
        status: "active",
        lockReason: undefined,
        lockedAt: undefined,
        lockedBy: undefined,
        auditHistory: [
          {
            id: "aud_test_unlock",
            action: "account_unlocked",
            actionLabelVi: "Mở khóa tài khoản",
            actionLabelEn: "Account unlocked",
            actor: "Admin Tester",
            timestamp: new Date().toISOString(),
          },
          ...user.auditHistory,
        ],
      },
    };
  });
  mockRevokeUserSessions.mockImplementation(async (userId) => {
    const user = SEED_ADMIN_USERS.find((u) => u.id === userId) || SEED_ADMIN_USERS[0];
    const count = user.activeSessionsCount;
    return {
      success: true,
      revokedCount: count,
      user: {
        ...user,
        activeSessionsCount: 0,
        auditHistory: [
          {
            id: "aud_test_revoke",
            action: "sessions_revoked",
            actionLabelVi: `Thu hồi ${count} phiên`,
            actionLabelEn: `Revoked ${count} sessions`,
            actor: "Admin Tester",
            timestamp: new Date().toISOString(),
          },
          ...user.auditHistory,
        ],
      },
    };
  });
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AdminUsersPage (Spec v5 Section 6.61: User Administration Registry)", () => {
  describe("1. Shell and RBAC Defense-in-Depth", () => {
    it("renders forbidden notice when user role is not admin", async () => {
      roleState.role = "doctor";
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
      });
      expect(mockListAdminUsers).not.toHaveBeenCalled();
    });

    it("renders forbidden notice when user role is normal", async () => {
      roleState.role = "normal";
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
      });
      expect(mockListAdminUsers).not.toHaveBeenCalled();
    });

    it("renders AdminShell, header, and user table when user role is admin", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(mockListAdminUsers).toHaveBeenCalled();
      });

      expect(
        screen.getByRole("heading", { level: 2, name: /User Administration Registry/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("table", { name: /user administration table/i }),
      ).toBeInTheDocument();
    });
  });

  describe("2. Summary KPIs and Ledger", () => {
    it("renders KPI summary cards with computed counts", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Total Users")).toBeInTheDocument();
      });

      expect(screen.getByText("Active Users")).toBeInTheDocument();
      expect(screen.getByText("Clinicians & Researchers")).toBeInTheDocument();
      expect(screen.getByText("Locked / Flagged")).toBeInTheDocument();
      expect(screen.getByText("Active Sessions")).toBeInTheDocument();
    });
  });

  describe("3. Search and Multi-dimensional Filtering", () => {
    it("filters user table by search query (name / email / ID)", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
      });

      const searchInput = screen.getByRole("searchbox", { name: /search users/i });
      fireEvent.change(searchInput, { target: { value: "Trần Minh Đức" } });

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
        expect(screen.queryByText("TS.BS Lê Thị Thanh Hương")).not.toBeInTheDocument();
        expect(screen.queryByText("Phạm Văn An")).not.toBeInTheDocument();
      });
    });

    it("filters user table by role pill", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
      });

      const doctorPill = screen.getByRole("button", { name: /^Doctor$/i });
      fireEvent.click(doctorPill);

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
        expect(screen.getByText("TS.BS Lê Thị Thanh Hương")).toBeInTheDocument();
        expect(screen.queryByText("ThS. Nguyễn Hoàng Long")).not.toBeInTheDocument();
        expect(screen.queryByText("Phạm Văn An")).not.toBeInTheDocument();
      });
    });

    it("filters user table by status dropdown", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Nguyễn Thị Mai")).toBeInTheDocument();
      });

      const statusSelect = screen.getByRole("combobox", {
        name: /filter by account status/i,
      });
      fireEvent.change(statusSelect, { target: { value: "locked" } });

      await waitFor(() => {
        expect(screen.getByText("Nguyễn Thị Mai")).toBeInTheDocument();
        expect(screen.queryByText("BS.CKII Trần Minh Đức")).not.toBeInTheDocument();
      });
    });
  });

  describe("4. Slide-out Inspector Drawer & User Actions", () => {
    it("opens the slide-out inspector drawer when clicking a user row", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
      });

      const userRow = screen.getByText("BS.CKII Trần Minh Đức").closest("tr");
      expect(userRow).not.toBeNull();
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(screen.getByText("Identity & Organization")).toBeInTheDocument();
        expect(screen.getByText("RBAC Role Assignment")).toBeInTheDocument();
        expect(screen.getByText("Security & Active Sessions")).toBeInTheDocument();
        expect(screen.getByText("Account Lock & Access Control")).toBeInTheDocument();
      });
    });

    it("allows role reassignment from the inspector drawer", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Phạm Văn An")).toBeInTheDocument();
      });

      // Select normal user
      const userRow = screen.getByText("Phạm Văn An").closest("tr");
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(screen.getByText("RBAC Role Assignment")).toBeInTheDocument();
      });

      // Select Researcher role option button in drawer
      const researcherOption = screen.getByTestId("drawer-role-researcher");
      fireEvent.click(researcherOption);

      // Fill reason
      const reasonInput = screen.getByLabelText(/reason for role change/i);
      fireEvent.change(reasonInput, {
        target: { value: "Verified clinical researcher credentials" },
      });

      // Click save role changes button
      const saveBtn = screen.getByRole("button", {
        name: /save role changes/i,
      });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateUserRole).toHaveBeenCalledWith(
          "usr_usr_9012",
          "researcher",
          "Verified clinical researcher credentials",
        );
      });
    });

    it("requires confirmation modal when elevating a user to Admin role", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Phạm Văn An")).toBeInTheDocument();
      });

      const userRow = screen.getByText("Phạm Văn An").closest("tr");
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(screen.getByText("RBAC Role Assignment")).toBeInTheDocument();
      });

      const adminOption = screen.getByTestId("drawer-role-admin");
      fireEvent.click(adminOption);

      const saveBtn = screen.getByRole("button", {
        name: /save role changes/i,
      });
      fireEvent.click(saveBtn);

      // Confirmation modal should open
      await waitFor(() => {
        expect(screen.getByText(/Confirm Admin Privilege Elevation/i)).toBeInTheDocument();
      });

      const confirmBtn = screen.getByRole("button", { name: /confirm admin elevation/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(mockUpdateUserRole).toHaveBeenCalledWith(
          "usr_usr_9012",
          "admin",
          undefined,
        );
      });
    });

    it("locks an active user account with reason and confirmation", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Phạm Văn An")).toBeInTheDocument();
      });

      const userRow = screen.getByText("Phạm Văn An").closest("tr");
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(screen.getByLabelText(/reason for account lock/i)).toBeInTheDocument();
      });

      const lockReasonArea = screen.getByLabelText(/reason for account lock/i);
      fireEvent.change(lockReasonArea, {
        target: { value: "Security compromise investigation" },
      });

      const lockBtn = screen.getByRole("button", {
        name: /lock account & revoke sessions/i,
      });
      fireEvent.click(lockBtn);

      // Confirm modal opens
      await waitFor(() => {
        expect(screen.getByText(/Confirm User Account Lock/i)).toBeInTheDocument();
      });

      const confirmLockBtn = screen.getByRole("button", { name: /confirm account lock/i });
      fireEvent.click(confirmLockBtn);

      await waitFor(() => {
        expect(mockLockUserAccount).toHaveBeenCalledWith(
          "usr_usr_9012",
          "Security compromise investigation",
        );
      });
    });

    it("unlocks a locked user account with confirmation", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("Nguyễn Thị Mai")).toBeInTheDocument();
      });

      const userRow = screen.getByText("Nguyễn Thị Mai").closest("tr");
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(
          screen.getByText(/Account is currently locked \/ suspended/i),
        ).toBeInTheDocument();
      });

      const unlockBtn = screen.getByRole("button", {
        name: /unlock account/i,
      });
      fireEvent.click(unlockBtn);

      // Confirm modal opens
      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /Confirm Account Unlock/i }),
        ).toBeInTheDocument();
      });

      const confirmUnlockBtn = screen.getByRole("button", {
        name: /confirm unlock/i,
      });
      fireEvent.click(confirmUnlockBtn);

      await waitFor(() => {
        expect(mockUnlockUserAccount).toHaveBeenCalledWith("usr_usr_9381");
      });
    });

    it("revokes all active sessions for a user", async () => {
      render(<AdminUsersPage />);

      await waitFor(() => {
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
      });

      const userRow = screen.getByText("BS.CKII Trần Minh Đức").closest("tr");
      fireEvent.click(userRow!);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /revoke all/i })).toBeInTheDocument();
      });

      const revokeBtn = screen.getByRole("button", { name: /revoke all/i });
      fireEvent.click(revokeBtn);

      // Confirmation modal
      await waitFor(() => {
        expect(screen.getByText(/Revoke All Active Sessions/i)).toBeInTheDocument();
      });

      const confirmRevokeBtn = screen.getByRole("button", {
        name: /confirm revoke sessions/i,
      });
      fireEvent.click(confirmRevokeBtn);

      await waitFor(() => {
        expect(mockRevokeUserSessions).toHaveBeenCalledWith("usr_doc_4421");
      });
    });
  });
});
