import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks for /admin/users and /admin/audit
// ---------------------------------------------------------------------------

const mockListAdminUsers = vi.fn();
const mockUpdateUserRole = vi.fn();
const mockLockUserAccount = vi.fn();
const mockUnlockUserAccount = vi.fn();
const mockRevokeUserSessions = vi.fn();

const mockGetAdminAuditLog = vi.fn();
const mockExportAuditLogZeroPii = vi.fn();

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

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

vi.mock("@/lib/admin-audit", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-audit")>();
  return {
    ...actual,
    getAdminAuditLog: (limit?: number) => mockGetAdminAuditLog(limit),
    exportAuditLogZeroPii: (records: any[], format?: "json" | "csv") =>
      mockExportAuditLogZeroPii(records, format),
  };
});

import AdminUsersPage from "@/app/admin/users/page";
import SecurityAuditLogPage from "@/app/admin/audit/page";
import type { AdminUser } from "@/lib/admin-users";
import { SEED_ADMIN_AUDIT_LOGS } from "@/lib/admin-audit";

// ---------------------------------------------------------------------------
// Test Fixtures
// ---------------------------------------------------------------------------

const TEST_ADMIN_USERS: AdminUser[] = [
  {
    id: "usr_adm_8810",
    email: "admin.system@clara-care.vn",
    fullName: "ThS. Nguyễn Hoàng Long",
    role: "admin",
    status: "active",
    activeSessionsCount: 2,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Trung tâm Điều hành Hệ thống & Bảo mật CLARA",
    phoneMasked: "+84 ••• ••• 019",
    lastActiveAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    createdAt: "2026-01-10T08:00:00Z",
    auditHistory: [
      {
        id: "aud_hist_01",
        action: "created",
        actionLabelVi: "Khởi tạo tài khoản",
        actionLabelEn: "Account created",
        actor: "System Bootstrap",
        timestamp: "2026-01-10T08:00:00Z",
      },
    ],
  },
  {
    id: "usr_doc_4421",
    email: "bs.tranminhduc@bvbachmai.vn",
    fullName: "BS.CKII Trần Minh Đức",
    role: "doctor",
    status: "active",
    activeSessionsCount: 3,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Khoa Hồi sức Tích cực (ICU) - Bệnh viện Bạch Mai",
    phoneMasked: "+84 ••• ••• 358",
    lastActiveAt: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    createdAt: "2026-02-14T09:30:00Z",
    auditHistory: [],
  },
  {
    id: "usr_res_2104",
    email: "research.vuhoang@hmu.edu.vn",
    fullName: "PGS.TS Vũ Hoàng Quân",
    role: "researcher",
    status: "active",
    activeSessionsCount: 1,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Viện Nghiên cứu Dược lý - ĐH Y Hà Nội",
    phoneMasked: "+84 ••• ••• 491",
    lastActiveAt: new Date(Date.now() - 360 * 60 * 1000).toISOString(),
    createdAt: "2026-02-28T11:00:00Z",
    auditHistory: [],
  },
  {
    id: "usr_usr_9012",
    email: "phamvanan.hanoi@gmail.com",
    fullName: "Phạm Văn An",
    role: "normal",
    status: "active",
    activeSessionsCount: 1,
    twoFactorEnabled: false,
    failedLoginAttempts: 0,
    departmentOrOrg: "Người dùng cá nhân (PHR)",
    phoneMasked: "+84 ••• ••• 925",
    lastActiveAt: new Date(Date.now() - 1800 * 60 * 1000).toISOString(),
    createdAt: "2026-04-12T16:45:00Z",
    auditHistory: [],
  },
  {
    id: "usr_usr_9381",
    email: "nguyenthimai.danang@gmail.com",
    fullName: "Nguyễn Thị Mai",
    role: "normal",
    status: "locked",
    activeSessionsCount: 0,
    twoFactorEnabled: false,
    failedLoginAttempts: 5,
    departmentOrOrg: "Người dùng cá nhân",
    phoneMasked: "+84 ••• ••• 634",
    lockReason: "Phát hiện 5 lần nhập sai mật khẩu liên tiếp.",
    lockedAt: "2026-08-22T10:14:00Z",
    lockedBy: "Hệ thống Tự động (SecOps Guard)",
    lastActiveAt: "2026-08-22T10:14:00Z",
    createdAt: "2026-05-19T07:12:00Z",
    auditHistory: [
      {
        id: "aud_hist_lock_01",
        action: "account_locked",
        actionLabelVi: "Khóa tài khoản",
        actionLabelEn: "Account locked",
        actor: "SecOps Guard",
        timestamp: "2026-08-22T10:14:00Z",
        details: "5 failed logins detected",
      },
    ],
  },
];

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";

  mockListAdminUsers.mockResolvedValue([...TEST_ADMIN_USERS]);

  mockUpdateUserRole.mockImplementation(async (userId, newRole, reason) => {
    const user = TEST_ADMIN_USERS.find((u) => u.id === userId) || TEST_ADMIN_USERS[0];
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
    const user = TEST_ADMIN_USERS.find((u) => u.id === userId) || TEST_ADMIN_USERS[0];
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
    const user = TEST_ADMIN_USERS.find((u) => u.id === userId) || TEST_ADMIN_USERS[0];
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
    const user = TEST_ADMIN_USERS.find((u) => u.id === userId) || TEST_ADMIN_USERS[0];
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

  mockGetAdminAuditLog.mockResolvedValue({
    records: [...SEED_ADMIN_AUDIT_LOGS],
  });

  mockExportAuditLogZeroPii.mockImplementation((records, format = "json") => ({
    success: true,
    count: records.length,
    filename: `clara_security_audit_log_zero_pii_test.${format}`,
  }));
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe("Spec v8 Section 12.5 & 12.6: Admin Users & Security Audit Workbenches", () => {
  describe("Section 12.5 — /admin/users User Administration Registry", () => {
    describe("1. Shell Architecture & RBAC Invariant", () => {
      it("blocks non-admin roles (doctor, researcher, normal) with 403 Forbidden notice", async () => {
        roleState.role = "doctor";
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
        });
        expect(mockListAdminUsers).not.toHaveBeenCalled();
      });

      it("renders ADMIN_COMMAND shell mode with User Directory Ledger archetype for admin", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(mockListAdminUsers).toHaveBeenCalled();
        });

        const registryContainer = document.querySelector(
          '[data-layout-archetype="User Directory Ledger"]'
        );
        expect(registryContainer).toBeInTheDocument();
        expect(registryContainer).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
        expect(registryContainer).toHaveAttribute("data-density", "dense");

        expect(
          screen.getByRole("heading", { level: 1, name: /User Administration Registry/i })
        ).toBeInTheDocument();
        expect(screen.getByText("USER-ADM")).toBeInTheDocument();
      });
    });

    describe("2. Summary KPIs & Registry Metrics", () => {
      it("renders all 5 KPI cards with aggregated counts", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText("Total Users")).toBeInTheDocument();
        });

        expect(screen.getByText("Total Users")).toBeInTheDocument();
        expect(screen.getByText("Active Users")).toBeInTheDocument();
        expect(screen.getByText("Clinicians & Researchers")).toBeInTheDocument();
        expect(screen.getByText("Locked / Flagged")).toBeInTheDocument();
        expect(screen.getByText("Active Sessions")).toBeInTheDocument();
      });
    });

    describe("3. Dense Table & Multi-dimensional Filtering", () => {
      it("renders dense user table with security and session indicators", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByRole("table", { name: /user administration table/i })).toBeInTheDocument();
        });

        const table = screen.getByRole("table", { name: /user administration table/i });
        expect(within(table).getByText("User & Org")).toBeInTheDocument();
        expect(within(table).getByText("Role")).toBeInTheDocument();
        expect(within(table).getByText("Status")).toBeInTheDocument();
        expect(within(table).getByText("Security")).toBeInTheDocument();
        expect(within(table).getByText("Sessions")).toBeInTheDocument();
        expect(within(table).getByText("Last Active")).toBeInTheDocument();

        expect(screen.getByText("ThS. Nguyễn Hoàng Long")).toBeInTheDocument();
        expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
      });

      it("filters users dynamically by text search query", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
        });

        const searchInput = screen.getByRole("searchbox", { name: /search users/i });
        fireEvent.change(searchInput, { target: { value: "Trần Minh Đức" } });

        await waitFor(() => {
          expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
          expect(screen.queryByText("ThS. Nguyễn Hoàng Long")).not.toBeInTheDocument();
          expect(screen.queryByText("Phạm Văn An")).not.toBeInTheDocument();
        });
      });

      it("filters users by role pill selector", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
        });

        const doctorPill = screen.getByRole("button", { name: /^Doctor$/i });
        fireEvent.click(doctorPill);

        await waitFor(() => {
          expect(screen.getByText("BS.CKII Trần Minh Đức")).toBeInTheDocument();
          expect(screen.queryByText("ThS. Nguyễn Hoàng Long")).not.toBeInTheDocument();
          expect(screen.queryByText("Phạm Văn An")).not.toBeInTheDocument();
        });
      });

      it("filters users by status dropdown selector", async () => {
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

    describe("4. Slide-out Inspector Drawer & Critical Administrative Actions", () => {
      it("opens inspector drawer upon selecting a user row", async () => {
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
          expect(screen.getByText("Account Audit Trail (Zero-PII)")).toBeInTheDocument();
        });
      });

      it("handles standard role change with audit justification", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText("Phạm Văn An")).toBeInTheDocument();
        });

        const userRow = screen.getByText("Phạm Văn An").closest("tr");
        fireEvent.click(userRow!);

        await waitFor(() => {
          expect(screen.getByText("RBAC Role Assignment")).toBeInTheDocument();
        });

        const researcherBtn = screen.getByTestId("drawer-role-researcher");
        fireEvent.click(researcherBtn);

        const reasonInput = screen.getByLabelText(/reason for role change/i);
        fireEvent.change(reasonInput, {
          target: { value: "Verified clinical trials researcher license #8821" },
        });

        const saveRoleBtn = screen.getByRole("button", { name: /save role changes/i });
        fireEvent.click(saveRoleBtn);

        await waitFor(() => {
          expect(mockUpdateUserRole).toHaveBeenCalledWith(
            "usr_usr_9012",
            "researcher",
            "Verified clinical trials researcher license #8821"
          );
        });
      });

      it("enforces confirmation modal for Admin privilege elevation", async () => {
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

        const saveBtn = screen.getByRole("button", { name: /save role changes/i });
        fireEvent.click(saveBtn);

        // Danger Confirmation Modal should open
        await waitFor(() => {
          expect(screen.getByText(/Confirm Admin Privilege Elevation/i)).toBeInTheDocument();
        });

        const confirmBtn = screen.getByRole("button", { name: /confirm admin elevation/i });
        fireEvent.click(confirmBtn);

        await waitFor(() => {
          expect(mockUpdateUserRole).toHaveBeenCalledWith(
            "usr_usr_9012",
            "admin",
            undefined
          );
        });
      });

      it("locks active user account with justification and confirmation modal", async () => {
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
          target: { value: "Suspected account takeover anomaly" },
        });

        const lockBtn = screen.getByRole("button", {
          name: /lock account & revoke sessions/i,
        });
        fireEvent.click(lockBtn);

        await waitFor(() => {
          expect(screen.getByText(/Confirm User Account Lock/i)).toBeInTheDocument();
        });

        const confirmLockBtn = screen.getByRole("button", { name: /confirm account lock/i });
        fireEvent.click(confirmLockBtn);

        await waitFor(() => {
          expect(mockLockUserAccount).toHaveBeenCalledWith(
            "usr_usr_9012",
            "Suspected account takeover anomaly"
          );
        });
      });

      it("unlocks a locked user account with confirmation modal", async () => {
        render(<AdminUsersPage />);

        await waitFor(() => {
          expect(screen.getByText("Nguyễn Thị Mai")).toBeInTheDocument();
        });

        const userRow = screen.getByText("Nguyễn Thị Mai").closest("tr");
        fireEvent.click(userRow!);

        await waitFor(() => {
          expect(screen.getByText(/Account is currently locked \/ suspended/i)).toBeInTheDocument();
        });

        const unlockBtn = screen.getByRole("button", { name: /unlock account/i });
        fireEvent.click(unlockBtn);

        await waitFor(() => {
          expect(screen.getByRole("heading", { name: /Confirm Account Unlock/i })).toBeInTheDocument();
        });

        const confirmUnlockBtn = screen.getByRole("button", { name: /confirm unlock/i });
        fireEvent.click(confirmUnlockBtn);

        await waitFor(() => {
          expect(mockUnlockUserAccount).toHaveBeenCalledWith("usr_usr_9381");
        });
      });

      it("revokes all active sessions for a selected user with confirmation modal", async () => {
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

        await waitFor(() => {
          expect(screen.getByText(/Revoke All Active Sessions/i)).toBeInTheDocument();
        });

        const confirmRevokeBtn = screen.getByRole("button", { name: /confirm revoke sessions/i });
        fireEvent.click(confirmRevokeBtn);

        await waitFor(() => {
          expect(mockRevokeUserSessions).toHaveBeenCalledWith("usr_doc_4421");
        });
      });
    });
  });

  describe("Section 12.6 — /admin/audit Security Audit Log Explorer", () => {
    describe("1. Shell Architecture & RBAC Invariant", () => {
      it("blocks non-admin access with 403 Forbidden message", async () => {
        roleState.role = "doctor";
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
        });
        expect(mockGetAdminAuditLog).not.toHaveBeenCalled();
      });

      it("renders ADMIN_COMMAND shell mode with Security Audit Log Explorer archetype for admin", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(mockGetAdminAuditLog).toHaveBeenCalled();
        });

        const auditContainer = document.querySelector(
          '[data-layout-archetype="Security Audit Log Explorer"]'
        );
        expect(auditContainer).toBeInTheDocument();
        expect(auditContainer).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
        expect(auditContainer).toHaveAttribute("data-density", "dense");

        expect(
          screen.getByRole("heading", { level: 1, name: /Security Audit Log Explorer/i })
        ).toBeInTheDocument();
        expect(screen.getByText("GOV-02")).toBeInTheDocument();
        expect(screen.getByText(/Immutable WAL Active/i)).toBeInTheDocument();
      });
    });

    describe("2. Summary KPI Strip", () => {
      it("renders all 5 KPI cards with Zero-PII guarantees", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("Total Audit Events")).toBeInTheDocument();
        });

        expect(screen.getByText("Total Audit Events")).toBeInTheDocument();
        expect(screen.getByText("Success Rate")).toBeInTheDocument();
        expect(screen.getByText(/Security & High-Risk/i)).toBeInTheDocument();
        expect(screen.getByText("Unique Actors")).toBeInTheDocument();
        expect(screen.getByText(/PII Redaction & WAL/i)).toBeInTheDocument();
        expect(screen.getByText("100% Zero-PII")).toBeInTheDocument();
      });
    });

    describe("3. Dense Immutable Audit Trail Table", () => {
      it("renders table headers and immutable audit records with SHA-256 IP masks", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByRole("table", { name: /Security audit log table/i })).toBeInTheDocument();
        });

        const table = screen.getByRole("table", { name: /Security audit log table/i });
        expect(within(table).getByText("Timestamp")).toBeInTheDocument();
        expect(within(table).getByText("Actor")).toBeInTheDocument();
        expect(within(table).getAllByText("Action").length).toBeGreaterThan(0);
        expect(within(table).getByText("Resource")).toBeInTheDocument();
        expect(within(table).getByText("IP Hash")).toBeInTheDocument();
        expect(within(table).getByText("Outcome")).toBeInTheDocument();

        expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        expect(screen.getByText("user.lock")).toBeInTheDocument();
      });
    });

    describe("4. Multi-dimensional Filters", () => {
      it("filters audit records by search query", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const searchInput = screen.getByRole("searchbox", { name: /Search audit logs/i });
        fireEvent.change(searchInput, { target: { value: "key_rotate" } });

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
          expect(screen.queryByText("user.lock")).not.toBeInTheDocument();
        });
      });

      it("filters audit records by category dropdown", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const categorySelect = screen.getByRole("combobox", {
          name: /Filter by action category/i,
        });
        fireEvent.change(categorySelect, { target: { value: "security" } });

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
          expect(screen.queryByText("kb_source.create")).not.toBeInTheDocument();
        });
      });

      it("filters audit records by outcome dropdown and clears filter", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const outcomeSelect = screen.getByRole("combobox", {
          name: /Filter by outcome status/i,
        });
        fireEvent.change(outcomeSelect, { target: { value: "denied" } });

        await waitFor(() => {
          expect(screen.getByText("auth.unauthorized_access")).toBeInTheDocument();
          expect(screen.queryByText("security.key_rotate")).not.toBeInTheDocument();
        });

        const clearBtn = screen.getByRole("button", { name: /Reset filters/i });
        fireEvent.click(clearBtn);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });
      });
    });

    describe("5. Slide-out Event Inspector Drawer & Single Event Export", () => {
      it("opens inspector drawer with cryptographic witness coordinates and JSON payload", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const inspectBtn = screen.getByRole("button", {
          name: /Inspect audit log #101/i,
        });
        fireEvent.click(inspectBtn);

        await waitFor(() => {
          expect(screen.getByText(/Audit Event #101/i)).toBeInTheDocument();
        });

        expect(screen.getByText("Event Overview")).toBeInTheDocument();
        expect(screen.getByText("Security & Identity Coordinates")).toBeInTheDocument();
        expect(screen.getByText("Zero-PII Context Payload")).toBeInTheDocument();
        expect(screen.getByText(/APPEND_ONLY_WAL_WITNESS/i)).toBeInTheDocument();
      });

      it("exports single event from drawer", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const inspectBtn = screen.getByRole("button", {
          name: /Inspect audit log #101/i,
        });
        fireEvent.click(inspectBtn);

        await waitFor(() => {
          expect(screen.getByText(/Audit Event #101/i)).toBeInTheDocument();
        });

        const exportEventBtn = screen.getByRole("button", { name: /Export Event/i });
        fireEvent.click(exportEventBtn);

        expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
          expect.arrayContaining([expect.objectContaining({ id: 101 })]),
          "json"
        );
      });
    });

    describe("6. Zero-PII Export Modal (JSON / CSV)", () => {
      it("opens export modal and executes JSON export with Zero-PII guarantee", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const exportTriggerBtn = screen.getByRole("button", {
          name: /Zero-PII export trigger/i,
        });
        fireEvent.click(exportTriggerBtn);

        await waitFor(() => {
          expect(screen.getByText(/Zero-PII Audit Log Export/i)).toBeInTheDocument();
        });

        expect(screen.getByText(/Zero-PII Compliance Guarantee:/i)).toBeInTheDocument();

        const downloadBtn = screen.getByRole("button", {
          name: /Download Zero-PII Export/i,
        });
        fireEvent.click(downloadBtn);

        expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
          expect.any(Array),
          "json"
        );
      });

      it("supports CSV format selection for spreadsheet export", async () => {
        render(<SecurityAuditLogPage />);

        await waitFor(() => {
          expect(screen.getByText("security.key_rotate")).toBeInTheDocument();
        });

        const exportTriggerBtn = screen.getByRole("button", {
          name: /Zero-PII export trigger/i,
        });
        fireEvent.click(exportTriggerBtn);

        await waitFor(() => {
          expect(screen.getByText(/Zero-PII Audit Log Export/i)).toBeInTheDocument();
        });

        const csvBtn = screen.getByText(/CSV \(Spreadsheet\)/i);
        fireEvent.click(csvBtn);

        const downloadBtn = screen.getByRole("button", {
          name: /Download Zero-PII Export/i,
        });
        fireEvent.click(downloadBtn);

        expect(mockExportAuditLogZeroPii).toHaveBeenCalledWith(
          expect.any(Array),
          "csv"
        );
      });
    });
  });
});
