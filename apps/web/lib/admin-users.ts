import api from "@/lib/http-client";
import type { UserRole } from "@/lib/auth-store";
import type { BadgeTone } from "@/components/ui/badge";
import type { StatusTone } from "@/components/ui/status-chip";

/**
 * User Administration Domain Model & Client (Spec v5 Section 6.61).
 *
 * Provides typed data structures, stats computation, and audited mutations for
 * the User Administration Registry (`/admin/users`, ADMIN_COMMAND / DENSE).
 *
 * Authoritative RBAC is enforced server-side (`require_roles("admin")`), while
 * the client adheres to Zero-PII standards: no passwords, tokens, or raw medical
 * details are exposed or stored.
 */

export type AdminUserStatus = "active" | "locked" | "suspended" | "pending_verification";

export interface UserAuditEntry {
  id: string;
  action: "role_updated" | "account_locked" | "account_unlocked" | "sessions_revoked" | "created" | "mfa_toggled";
  actionLabelVi: string;
  actionLabelEn: string;
  actor: string;
  timestamp: string;
  details?: string;
}

export interface AdminUser {
  id: string;
  email: string;
  fullName: string;
  role: UserRole;
  status: AdminUserStatus;
  activeSessionsCount: number;
  twoFactorEnabled: boolean;
  failedLoginAttempts: number;
  departmentOrOrg?: string;
  phoneMasked?: string;
  lockReason?: string;
  lockedAt?: string;
  lockedBy?: string;
  lastActiveAt: string;
  createdAt: string;
  auditHistory: UserAuditEntry[];
  resourceVersion?: string;
}

export interface UserStats {
  totalUsers: number;
  activeUsers: number;
  lockedUsers: number;
  adminCount: number;
  doctorCount: number;
  researcherCount: number;
  normalCount: number;
  totalActiveSessions: number;
}

export interface RoleMeta {
  role: UserRole;
  labelVi: string;
  labelEn: string;
  badgeTone: BadgeTone;
  icon: string;
  descriptionVi: string;
  descriptionEn: string;
}

export interface StatusMeta {
  status: AdminUserStatus;
  labelVi: string;
  labelEn: string;
  tone: StatusTone;
  descriptionVi: string;
  descriptionEn: string;
}

export const ROLE_METADATA: Record<UserRole, RoleMeta> = {
  admin: {
    role: "admin",
    labelVi: "Quản trị viên (Admin)",
    labelEn: "Administrator",
    badgeTone: "danger",
    icon: "settings",
    descriptionVi: "Toàn quyền quản trị hệ thống, luồng RAG, phân quyền và kiểm soát an toàn.",
    descriptionEn: "Full system administration, RAG pipeline, RBAC, and safety control access.",
  },
  doctor: {
    role: "doctor",
    labelVi: "Bác sĩ lâm sàng (Doctor)",
    labelEn: "Physician / Clinician",
    badgeTone: "warn",
    icon: "clinical-notes",
    descriptionVi: "Truy cập Council chuyên gia, Scribe ghi chú lâm sàng và thẩm định y khoa.",
    descriptionEn: "Access to Council deliberation, Clinical Scribe, and medical peer review.",
  },
  researcher: {
    role: "researcher",
    labelVi: "Nhà nghiên cứu (Researcher)",
    labelEn: "Clinical Researcher",
    badgeTone: "brand",
    icon: "scan",
    descriptionVi: "Truy cập Living Evidence, Source Hub y văn và công cụ phân tích nghiên cứu sâu.",
    descriptionEn: "Access to Living Evidence workspace, Source Hub, and deep literature analytics.",
  },
  normal: {
    role: "normal",
    labelVi: "Người dùng (End User)",
    labelEn: "End User",
    badgeTone: "neutral",
    icon: "user-card",
    descriptionVi: "Sử dụng Ask CLARA, quản lý PHR cá nhân, tủ thuốc và tương tác gia đình.",
    descriptionEn: "Consumer access to Ask CLARA, personal PHR, medication cabinet, and family sharing.",
  },
};

export const STATUS_METADATA: Record<AdminUserStatus, StatusMeta> = {
  active: {
    status: "active",
    labelVi: "Đang hoạt động",
    labelEn: "Active",
    tone: "success",
    descriptionVi: "Tài khoản đang hoạt động bình thường, quyền truy cập đầy đủ.",
    descriptionEn: "Account is active with full authenticated permissions.",
  },
  locked: {
    status: "locked",
    labelVi: "Đã khóa tài khoản",
    labelEn: "Locked",
    tone: "danger",
    descriptionVi: "Tài khoản bị khóa do vi phạm bảo mật hoặc chỉ định quản trị.",
    descriptionEn: "Account is locked due to security anomalies or administrative action.",
  },
  suspended: {
    status: "suspended",
    labelVi: "Tạm đình chỉ",
    labelEn: "Suspended",
    tone: "warning",
    descriptionVi: "Tạm thời vô hiệu hóa quyền đăng nhập để rà soát chứng chỉ hoặc khiếu nại.",
    descriptionEn: "Login temporarily suspended pending credential audit or review.",
  },
  pending_verification: {
    status: "pending_verification",
    labelVi: "Chờ xác minh",
    labelEn: "Pending",
    tone: "info",
    descriptionVi: "Tài khoản mới đăng ký chưa hoàn tất xác thực email hoặc danh tính y tế.",
    descriptionEn: "Newly registered account pending email or medical credential verification.",
  },
};

export function getRoleMeta(role: UserRole): RoleMeta {
  return ROLE_METADATA[role] ?? ROLE_METADATA.normal;
}

export function getStatusMeta(status: AdminUserStatus): StatusMeta {
  return STATUS_METADATA[status] ?? STATUS_METADATA.active;
}

export function mapBackendUserToAdminUser(user: any): AdminUser {
  if (!user) {
    throw new Error("Invalid user payload from server");
  }

  const role = (user.role ?? "normal") as UserRole;
  const status = (user.status ?? "active") as AdminUserStatus;

  return {
    id: String(user.id),
    email: user.email ?? "",
    fullName: user.full_name ?? user.fullName ?? "",
    role,
    status,
    activeSessionsCount: user.active_sessions_count ?? user.activeSessionsCount ?? (status === "active" ? 1 : 0),
    twoFactorEnabled: Boolean(user.two_factor_enabled ?? user.twoFactorEnabled ?? user.is_email_verified),
    failedLoginAttempts: user.failed_login_attempts ?? user.failedLoginAttempts ?? 0,
    departmentOrOrg: user.department_or_org ?? user.departmentOrOrg,
    phoneMasked: user.phone_masked ?? user.phoneMasked,
    lockReason: user.lock_reason ?? user.lockReason,
    lockedAt: user.locked_at ?? user.lockedAt,
    lockedBy: user.locked_by ?? user.lockedBy,
    lastActiveAt: user.last_login_at ?? user.lastActiveAt ?? user.created_at ?? user.createdAt ?? new Date().toISOString(),
    createdAt: user.created_at ?? user.createdAt ?? new Date().toISOString(),
    auditHistory: Array.isArray(user.audit_history ?? user.auditHistory) ? (user.audit_history ?? user.auditHistory) : [],
    resourceVersion: user.resource_version ?? user.resourceVersion,
  };
}

// ---------------------------------------------------------------------------
// Client API Functions (Server Wired & Fail-Closed)
// ---------------------------------------------------------------------------

export interface ListAdminUsersOptions {
  query?: string;
  role?: UserRole | "all";
  status?: AdminUserStatus | "all";
  cursor?: number;
  limit?: number;
}

export async function listAdminUsers(options?: ListAdminUsersOptions): Promise<AdminUser[]> {
  const params: Record<string, string | number> = {};

  if (options?.query && options.query.trim()) {
    params.query = options.query.trim();
  }
  if (options?.role && options.role !== "all") {
    params.role = options.role;
  }
  if (options?.status && options.status !== "all") {
    params.status = options.status;
  }
  if (options?.cursor !== undefined) {
    params.cursor = options.cursor;
  }
  if (options?.limit !== undefined) {
    params.limit = options.limit;
  }

  const res = await api.get<{ items?: any[]; users?: any[]; total?: number } | any[]>("/admin/users", {
    params,
  });

  let rawList: any[] = [];
  if (Array.isArray(res.data)) {
    rawList = res.data;
  } else if (res.data && Array.isArray(res.data.items)) {
    rawList = res.data.items;
  } else if (res.data && Array.isArray(res.data.users)) {
    rawList = res.data.users;
  }

  return rawList.map(mapBackendUserToAdminUser);
}

export async function getAdminUser(userId: string | number): Promise<AdminUser> {
  const res = await api.get<any>(`/admin/users/${encodeURIComponent(String(userId))}`);
  return mapBackendUserToAdminUser(res.data);
}

export async function updateUserRole(
  userId: string | number,
  newRole: UserRole,
  reason?: string,
  actor: string = "Admin Operator",
  expectedResourceVersion?: string,
): Promise<{ success: boolean; user: AdminUser }> {
  const res = await api.patch<any>(`/admin/users/${encodeURIComponent(String(userId))}/role`, {
    role: newRole,
    reason_code: reason || "ADMIN_ROLE_CHANGE",
    expected_resource_version: expectedResourceVersion,
  });

  const rawUser = res.data?.user || res.data;
  const user = mapBackendUserToAdminUser(rawUser);
  return { success: true, user };
}

export async function lockUserAccount(
  userId: string | number,
  reason: string,
  lockedBy: string = "Admin Operator",
  expectedResourceVersion?: string,
): Promise<{ success: boolean; user: AdminUser }> {
  const res = await api.post<any>(`/admin/users/${encodeURIComponent(String(userId))}/lock`, {
    reason,
    expected_resource_version: expectedResourceVersion,
  });

  const rawUser = res.data?.user || res.data;
  const user = mapBackendUserToAdminUser(rawUser);
  return { success: true, user };
}

export async function unlockUserAccount(
  userId: string | number,
  unlockedBy: string = "Admin Operator",
  expectedResourceVersion?: string,
): Promise<{ success: boolean; user: AdminUser }> {
  const res = await api.post<any>(`/admin/users/${encodeURIComponent(String(userId))}/unlock`, {
    reason: "ADMIN_UNLOCK",
    expected_resource_version: expectedResourceVersion,
  });

  const rawUser = res.data?.user || res.data;
  const user = mapBackendUserToAdminUser(rawUser);
  return { success: true, user };
}

export async function revokeUserSessions(
  userId: string | number,
  actor: string = "Admin Operator",
): Promise<{ success: boolean; revokedCount: number; user?: AdminUser }> {
  const res = await api.post<any>(`/admin/users/${encodeURIComponent(String(userId))}/sessions/revoke`);

  const revokedCount =
    res.data?.revoked_sessions_count ?? res.data?.revokedSessionsCount ?? 1;
  const rawUser = res.data?.user;
  return {
    success: true,
    revokedCount,
    user: rawUser ? mapBackendUserToAdminUser(rawUser) : undefined,
  };
}

export function computeUserStats(users: AdminUser[]): UserStats {
  let activeUsers = 0;
  let lockedUsers = 0;
  let adminCount = 0;
  let doctorCount = 0;
  let researcherCount = 0;
  let normalCount = 0;
  let totalActiveSessions = 0;

  for (const user of users) {
    if (user.status === "active") activeUsers++;
    if (user.status === "locked" || user.status === "suspended") lockedUsers++;

    if (user.role === "admin") adminCount++;
    else if (user.role === "doctor") doctorCount++;
    else if (user.role === "researcher") researcherCount++;
    else normalCount++;

    totalActiveSessions += user.activeSessionsCount || 0;
  }

  return {
    totalUsers: users.length,
    activeUsers,
    lockedUsers,
    adminCount,
    doctorCount,
    researcherCount,
    normalCount,
    totalActiveSessions,
  };
}
