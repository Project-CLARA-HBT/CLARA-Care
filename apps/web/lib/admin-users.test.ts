import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/http-client";
import {
  computeUserStats,
  getAdminUser,
  getRoleMeta,
  getStatusMeta,
  listAdminUsers,
  lockUserAccount,
  revokeUserSessions,
  unlockUserAccount,
  updateUserRole,
  type AdminUser,
} from "./admin-users";

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

const sampleUsers: AdminUser[] = [
  {
    id: "1",
    email: "admin@clara-care.vn",
    fullName: "ThS. Nguyen Long",
    role: "admin",
    status: "active",
    activeSessionsCount: 2,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Security Ops",
    phoneMasked: "+84 ••• 019",
    lastActiveAt: "2026-08-24T00:00:00Z",
    createdAt: "2026-01-10T08:00:00Z",
    auditHistory: [],
  },
  {
    id: "2",
    email: "bs.duc@bvbachmai.vn",
    fullName: "BS.CKII Tran Duc",
    role: "doctor",
    status: "active",
    activeSessionsCount: 1,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "ICU Bach Mai",
    phoneMasked: "+84 ••• 358",
    lastActiveAt: "2026-08-24T00:00:00Z",
    createdAt: "2026-02-14T09:30:00Z",
    auditHistory: [],
  },
  {
    id: "3",
    email: "mai.nguyen@gmail.com",
    fullName: "Nguyen Thi Mai",
    role: "normal",
    status: "locked",
    activeSessionsCount: 0,
    twoFactorEnabled: false,
    failedLoginAttempts: 5,
    lockReason: "Excessive failed logins",
    lastActiveAt: "2026-08-22T10:14:00Z",
    createdAt: "2026-05-19T07:12:00Z",
    auditHistory: [],
  },
  {
    id: "4",
    email: "research.quan@hmu.edu.vn",
    fullName: "PGS.TS Vu Quan",
    role: "researcher",
    status: "suspended",
    activeSessionsCount: 0,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    lastActiveAt: "2026-08-20T00:00:00Z",
    createdAt: "2026-02-28T11:00:00Z",
    auditHistory: [],
  },
];

describe("admin-users domain and client (Spec v5 Section 6.61)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("computeUserStats", () => {
    it("computes accurate user and session breakdown from sample users", () => {
      const stats = computeUserStats(sampleUsers);
      expect(stats.totalUsers).toBe(4);
      expect(stats.activeUsers).toBe(2);
      expect(stats.lockedUsers).toBe(2); // 1 locked + 1 suspended
      expect(stats.adminCount).toBe(1);
      expect(stats.doctorCount).toBe(1);
      expect(stats.researcherCount).toBe(1);
      expect(stats.normalCount).toBe(1);
      expect(stats.totalActiveSessions).toBe(3);
    });

    it("handles empty user array safely", () => {
      const stats = computeUserStats([]);
      expect(stats).toEqual({
        totalUsers: 0,
        activeUsers: 0,
        lockedUsers: 0,
        adminCount: 0,
        doctorCount: 0,
        researcherCount: 0,
        normalCount: 0,
        totalActiveSessions: 0,
      });
    });
  });

  describe("listAdminUsers", () => {
    it("fetches and maps users from /admin/users endpoint", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 101,
              email: "bs.duc@bvbachmai.vn",
              role: "doctor",
              full_name: "BS. Tran Duc",
              status: "active",
              is_email_verified: true,
              resource_version: "2",
              created_at: "2026-02-14T09:30:00Z",
            },
          ],
          total: 1,
          next_cursor: null,
        },
      });

      const users = await listAdminUsers({ role: "doctor", query: "duc" });
      expect(mockApi.get).toHaveBeenCalledWith("/admin/users", {
        params: { role: "doctor", query: "duc" },
      });
      expect(users.length).toBe(1);
      expect(users[0].id).toBe("101");
      expect(users[0].role).toBe("doctor");
      expect(users[0].fullName).toBe("BS. Tran Duc");
      expect(users[0].twoFactorEnabled).toBe(true);
    });

    it("fails closed on 403 Forbidden", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("403 Forbidden: Insufficient permissions"));

      await expect(listAdminUsers()).rejects.toThrow(/403 Forbidden/i);
    });

    it("fails closed on 500 Internal Server Error", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(listAdminUsers()).rejects.toThrow(/500/);
    });
  });

  describe("getAdminUser", () => {
    it("fetches single user details from server", async () => {
      mockApi.get.mockResolvedValueOnce({
        data: {
          id: 42,
          email: "user@test.vn",
          role: "normal",
          full_name: "Test User",
          status: "active",
          resource_version: "1",
        },
      });

      const user = await getAdminUser(42);
      expect(mockApi.get).toHaveBeenCalledWith("/admin/users/42");
      expect(user.id).toBe("42");
      expect(user.fullName).toBe("Test User");
    });

    it("fails closed when user is not found (404)", async () => {
      mockApi.get.mockRejectedValueOnce(new Error("USER_NOT_FOUND"));

      await expect(getAdminUser(999)).rejects.toThrow(/USER_NOT_FOUND/);
    });
  });

  describe("updateUserRole", () => {
    it("updates role and returns receipt user on HTTP 200", async () => {
      mockApi.patch.mockResolvedValueOnce({
        data: {
          success: true,
          resource_version: "2",
          user: {
            id: 1,
            email: "user@clara.vn",
            role: "doctor",
            full_name: "BS. Test",
            status: "active",
            resource_version: "2",
          },
        },
      });

      const res = await updateUserRole("1", "doctor", "Granted Doctor License", "Admin Leader", "1");
      expect(mockApi.patch).toHaveBeenCalledWith("/admin/users/1/role", {
        role: "doctor",
        reason_code: "Granted Doctor License",
        expected_resource_version: "1",
      });
      expect(res.success).toBe(true);
      expect(res.user.role).toBe("doctor");
    });

    it("fails closed on 409 Conflict (LAST_ACTIVE_ADMIN_INVARIANT)", async () => {
      mockApi.patch.mockRejectedValueOnce(
        new Error("LAST_ACTIVE_ADMIN_INVARIANT: Cannot demote or lock the last active administrator."),
      );

      await expect(
        updateUserRole("1", "normal", "Demoting admin"),
      ).rejects.toThrow(/LAST_ACTIVE_ADMIN_INVARIANT/);
    });

    it("fails closed on 409 Conflict (RESOURCE_VERSION_CONFLICT)", async () => {
      mockApi.patch.mockRejectedValueOnce(
        new Error("RESOURCE_VERSION_CONFLICT: Expected 1, found 2"),
      );

      await expect(
        updateUserRole("1", "doctor", "Update role", "Admin", "1"),
      ).rejects.toThrow(/RESOURCE_VERSION_CONFLICT/);
    });

    it("fails closed on 403 Forbidden", async () => {
      mockApi.patch.mockRejectedValueOnce(new Error("403 Forbidden"));

      await expect(
        updateUserRole("1", "doctor"),
      ).rejects.toThrow(/403 Forbidden/);
    });
  });

  describe("lockUserAccount and unlockUserAccount", () => {
    it("locks user account via POST /admin/users/:id/lock", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          success: true,
          resource_version: "3",
          user: {
            id: 2,
            email: "user@test.vn",
            role: "normal",
            full_name: "Test User",
            status: "locked",
            resource_version: "3",
          },
        },
      });

      const res = await lockUserAccount("2", "Security Compromise Investigation", "SecOps");
      expect(mockApi.post).toHaveBeenCalledWith("/admin/users/2/lock", {
        reason: "Security Compromise Investigation",
        expected_resource_version: undefined,
      });
      expect(res.success).toBe(true);
      expect(res.user.status).toBe("locked");
    });

    it("fails closed when trying to lock last active admin (409 Conflict)", async () => {
      mockApi.post.mockRejectedValueOnce(
        new Error("LAST_ACTIVE_ADMIN_INVARIANT: Cannot demote or lock the last active administrator."),
      );

      await expect(
        lockUserAccount("1", "Emergency lockdown"),
      ).rejects.toThrow(/LAST_ACTIVE_ADMIN_INVARIANT/);
    });

    it("unlocks user account via POST /admin/users/:id/unlock", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          success: true,
          resource_version: "4",
          user: {
            id: 3,
            email: "mai.nguyen@gmail.com",
            role: "normal",
            full_name: "Nguyen Thi Mai",
            status: "active",
            resource_version: "4",
          },
        },
      });

      const res = await unlockUserAccount("3", "SecOps Lead");
      expect(mockApi.post).toHaveBeenCalledWith("/admin/users/3/unlock", {
        reason: "ADMIN_UNLOCK",
        expected_resource_version: undefined,
      });
      expect(res.success).toBe(true);
      expect(res.user.status).toBe("active");
    });

    it("fails closed on 500 error during unlock", async () => {
      mockApi.post.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(unlockUserAccount("3")).rejects.toThrow(/500/);
    });
  });

  describe("revokeUserSessions", () => {
    it("revokes all active sessions via POST /admin/users/:id/sessions/revoke", async () => {
      mockApi.post.mockResolvedValueOnce({
        data: {
          success: true,
          revoked_sessions_count: 3,
          user_id: 2,
          revoked_at: "2026-08-24T10:00:00Z",
        },
      });

      const res = await revokeUserSessions("2", "Admin Operator");
      expect(mockApi.post).toHaveBeenCalledWith("/admin/users/2/sessions/revoke");
      expect(res.success).toBe(true);
      expect(res.revokedCount).toBe(3);
    });

    it("fails closed on 500 Server Error during session revocation", async () => {
      mockApi.post.mockRejectedValueOnce(new Error("Failed to revoke Redis session tokens"));

      await expect(revokeUserSessions("2")).rejects.toThrow(/Redis session tokens/);
    });
  });

  describe("metadata helpers", () => {
    it("provides metadata for all roles", () => {
      for (const role of ["admin", "doctor", "researcher", "normal"] as const) {
        const meta = getRoleMeta(role);
        expect(meta.role).toBe(role);
        expect(meta.labelVi).toBeDefined();
        expect(meta.labelEn).toBeDefined();
        expect(meta.badgeTone).toBeDefined();
      }
    });

    it("provides metadata for all statuses", () => {
      for (const status of ["active", "locked", "suspended", "pending_verification"] as const) {
        const meta = getStatusMeta(status);
        expect(meta.status).toBe(status);
        expect(meta.labelVi).toBeDefined();
        expect(meta.labelEn).toBeDefined();
        expect(meta.tone).toBeDefined();
      }
    });
  });
});
