import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn().mockRejectedValue(new Error("Offline fallback")),
    post: vi.fn().mockRejectedValue(new Error("Offline fallback")),
    patch: vi.fn().mockRejectedValue(new Error("Offline fallback")),
    delete: vi.fn().mockRejectedValue(new Error("Offline fallback")),
  },
}));

import {
  computeUserStats,
  getRoleMeta,
  getStatusMeta,
  listAdminUsers,
  lockUserAccount,
  resetUsersCacheForTesting,
  revokeUserSessions,
  unlockUserAccount,
  updateUserRole,
  SEED_ADMIN_USERS,
} from "./admin-users";

describe("admin-users domain and utility functions", () => {
  beforeEach(() => {
    resetUsersCacheForTesting();
  });

  afterEach(() => {
    resetUsersCacheForTesting();
  });

  describe("computeUserStats", () => {
    it("computes accurate user and session breakdown from seed users", () => {
      const stats = computeUserStats(SEED_ADMIN_USERS);
      expect(stats.totalUsers).toBe(SEED_ADMIN_USERS.length);
      expect(stats.activeUsers).toBeGreaterThan(0);
      expect(stats.adminCount).toBeGreaterThanOrEqual(1);
      expect(stats.doctorCount).toBeGreaterThanOrEqual(1);
      expect(stats.researcherCount).toBeGreaterThanOrEqual(1);
      expect(stats.normalCount).toBeGreaterThanOrEqual(1);
      expect(stats.totalActiveSessions).toBeGreaterThanOrEqual(0);
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
    it("returns all users when no filter is applied", async () => {
      const users = await listAdminUsers();
      expect(users.length).toBe(SEED_ADMIN_USERS.length);
    });

    it("filters users by role", async () => {
      const doctors = await listAdminUsers({ role: "doctor" });
      expect(doctors.length).toBeGreaterThan(0);
      expect(doctors.every((u) => u.role === "doctor")).toBe(true);
    });

    it("filters users by status", async () => {
      const locked = await listAdminUsers({ status: "locked" });
      expect(locked.length).toBeGreaterThan(0);
      expect(locked.every((u) => u.status === "locked")).toBe(true);
    });

    it("filters users by query text matching name or email", async () => {
      const matches = await listAdminUsers({ query: "bachmai" });
      expect(matches.length).toBeGreaterThan(0);
      expect(matches[0].email).toContain("bachmai");
    });
  });

  describe("updateUserRole", () => {
    it("updates role and appends audit event", async () => {
      const user = SEED_ADMIN_USERS.find((u) => u.role === "normal")!;
      const result = await updateUserRole(
        user.id,
        "doctor",
        "Assigned clinical doctor credentials",
        "Chief Admin",
      );

      expect(result.success).toBe(true);
      expect(result.user.role).toBe("doctor");
      expect(result.user.auditHistory[0].action).toBe("role_updated");
      expect(result.user.auditHistory[0].actor).toBe("Chief Admin");
    });

    it("throws error for non-existent user", async () => {
      await expect(
        updateUserRole("usr_non_existent", "admin"),
      ).rejects.toThrow(/not found/i);
    });
  });

  describe("lockUserAccount and unlockUserAccount", () => {
    it("locks user account, records reason, and revokes sessions", async () => {
      const user = SEED_ADMIN_USERS.find((u) => u.status === "active" && u.activeSessionsCount > 0)!;
      const result = await lockUserAccount(
        user.id,
        "Security audit alert",
        "SecOps",
      );

      expect(result.success).toBe(true);
      expect(result.user.status).toBe("locked");
      expect(result.user.activeSessionsCount).toBe(0);
      expect(result.user.lockReason).toBe("Security audit alert");
      expect(result.user.lockedBy).toBe("SecOps");
    });

    it("unlocks locked user account and clears lock fields", async () => {
      const user = SEED_ADMIN_USERS.find((u) => u.status === "locked")!;
      const result = await unlockUserAccount(user.id, "SecOps Lead");

      expect(result.success).toBe(true);
      expect(result.user.status).toBe("active");
      expect(result.user.lockReason).toBeUndefined();
      expect(result.user.lockedAt).toBeUndefined();
      expect(result.user.auditHistory[0].action).toBe("account_unlocked");
    });
  });

  describe("revokeUserSessions", () => {
    it("revokes all active sessions for a user", async () => {
      const user = SEED_ADMIN_USERS.find((u) => u.activeSessionsCount > 0)!;
      const initialCount = user.activeSessionsCount;
      const result = await revokeUserSessions(user.id, "Admin Console");

      expect(result.success).toBe(true);
      expect(result.revokedCount).toBe(initialCount);
      expect(result.user.activeSessionsCount).toBe(0);
      expect(result.user.auditHistory[0].action).toBe("sessions_revoked");
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
