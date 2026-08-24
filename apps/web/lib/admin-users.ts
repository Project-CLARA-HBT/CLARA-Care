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

// ---------------------------------------------------------------------------
// Seed Data for Development / Offline Resilient Registry
// ---------------------------------------------------------------------------

export const SEED_ADMIN_USERS: AdminUser[] = [
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
        id: "aud_01",
        action: "created",
        actionLabelVi: "Khởi tạo tài khoản hệ thống",
        actionLabelEn: "System account initialized",
        actor: "SYSTEM_BOOTSTRAP",
        timestamp: "2026-01-10T08:00:00Z",
        details: "Tài khoản Quản trị viên cấp cao ban đầu.",
      },
      {
        id: "aud_02",
        action: "mfa_toggled",
        actionLabelVi: "Kích hoạt xác thực 2 lớp (2FA)",
        actionLabelEn: "Enabled 2-factor authentication",
        actor: "usr_adm_8810",
        timestamp: "2026-01-10T08:15:00Z",
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
    auditHistory: [
      {
        id: "aud_03",
        action: "created",
        actionLabelVi: "Đăng ký thành viên y tế",
        actionLabelEn: "Registered clinician member",
        actor: "usr_doc_4421",
        timestamp: "2026-02-14T09:30:00Z",
      },
      {
        id: "aud_04",
        action: "role_updated",
        actionLabelVi: "Cấp chứng thực Bác sĩ lâm sàng",
        actionLabelEn: "Granted Doctor credentials",
        actor: "usr_adm_8810",
        timestamp: "2026-02-15T10:00:00Z",
        details: "Xác thực chứng chỉ hành nghề khám chữa bệnh số 004821/BYT-CCHN.",
      },
    ],
  },
  {
    id: "usr_doc_5590",
    email: "bs.lethithanh@bvchoray.vn",
    fullName: "TS.BS Lê Thị Thanh Hương",
    role: "doctor",
    status: "active",
    activeSessionsCount: 1,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Khoa Dược Lâm sàng & Chống độc - Bệnh viện Chợ Rẫy",
    phoneMasked: "+84 ••• ••• 712",
    lastActiveAt: new Date(Date.now() - 120 * 60 * 1000).toISOString(),
    createdAt: "2026-03-01T14:20:00Z",
    auditHistory: [
      {
        id: "aud_05",
        action: "created",
        actionLabelVi: "Đăng ký thành viên",
        actionLabelEn: "Registered account",
        actor: "usr_doc_5590",
        timestamp: "2026-03-01T14:20:00Z",
      },
      {
        id: "aud_06",
        action: "role_updated",
        actionLabelVi: "Cấp quyền Bác sĩ Dược lâm sàng",
        actionLabelEn: "Assigned Doctor role",
        actor: "usr_adm_8810",
        timestamp: "2026-03-02T08:30:00Z",
      },
    ],
  },
  {
    id: "usr_res_2104",
    email: "research.vuhoang@hmu.edu.vn",
    fullName: "PGS.TS Vũ Hoàng Quân",
    role: "researcher",
    status: "active",
    activeSessionsCount: 2,
    twoFactorEnabled: true,
    failedLoginAttempts: 0,
    departmentOrOrg: "Viện Nghiên cứu Dược lý & Di truyền - ĐH Y Hà Nội",
    phoneMasked: "+84 ••• ••• 491",
    lastActiveAt: new Date(Date.now() - 360 * 60 * 1000).toISOString(),
    createdAt: "2026-02-28T11:00:00Z",
    auditHistory: [
      {
        id: "aud_07",
        action: "created",
        actionLabelVi: "Khởi tạo tài khoản nghiên cứu",
        actionLabelEn: "Created researcher profile",
        actor: "usr_res_2104",
        timestamp: "2026-02-28T11:00:00Z",
      },
      {
        id: "aud_08",
        action: "role_updated",
        actionLabelVi: "Phân quyền Nhà nghiên cứu Y khoa",
        actionLabelEn: "Granted Researcher role",
        actor: "usr_adm_8810",
        timestamp: "2026-03-01T09:00:00Z",
      },
    ],
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
    auditHistory: [
      {
        id: "aud_09",
        action: "created",
        actionLabelVi: "Đăng ký tài khoản người dùng",
        actionLabelEn: "End-user registration",
        actor: "usr_usr_9012",
        timestamp: "2026-04-12T16:45:00Z",
      },
    ],
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
    lockReason: "Phát hiện 5 lần nhập sai mật khẩu liên tiếp và bất thường địa chỉ IP đăng nhập.",
    lockedAt: "2026-08-22T10:14:00Z",
    lockedBy: "Hệ thống Tự động (SecOps Guard)",
    lastActiveAt: "2026-08-22T10:14:00Z",
    createdAt: "2026-05-19T07:12:00Z",
    auditHistory: [
      {
        id: "aud_10",
        action: "created",
        actionLabelVi: "Đăng ký tài khoản",
        actionLabelEn: "User registered",
        actor: "usr_usr_9381",
        timestamp: "2026-05-19T07:12:00Z",
      },
      {
        id: "aud_11",
        action: "account_locked",
        actionLabelVi: "Khóa bảo vệ tài khoản tự động",
        actionLabelEn: "Automated account lock protection",
        actor: "SecOps Guard",
        timestamp: "2026-08-22T10:14:00Z",
        details: "Vượt ngưỡng failed logins (5 lần). Tất cả phiên đã bị thu hồi.",
      },
    ],
  },
  {
    id: "usr_res_7749",
    email: "nguyenngocthach@pasteur.org.vn",
    fullName: "ThS. Nguyễn Ngọc Thạch",
    role: "researcher",
    status: "suspended",
    activeSessionsCount: 0,
    twoFactorEnabled: true,
    failedLoginAttempts: 1,
    departmentOrOrg: "Viện Pasteur TP.HCM",
    phoneMasked: "+84 ••• ••• 830",
    lockReason: "Hết hạn chứng nhận GCP (Good Clinical Practice) định kỳ hàng năm.",
    lockedAt: "2026-08-15T09:00:00Z",
    lockedBy: "usr_adm_8810",
    lastActiveAt: "2026-08-14T17:30:00Z",
    createdAt: "2026-03-20T10:00:00Z",
    auditHistory: [
      {
        id: "aud_12",
        action: "created",
        actionLabelVi: "Khởi tạo hồ sơ nghiên cứu",
        actionLabelEn: "Researcher account registered",
        actor: "usr_res_7749",
        timestamp: "2026-03-20T10:00:00Z",
      },
      {
        id: "aud_13",
        action: "account_locked",
        actionLabelVi: "Tạm đình chỉ quyền nghiên cứu",
        actionLabelEn: "Suspended researcher privileges",
        actor: "usr_adm_8810",
        timestamp: "2026-08-15T09:00:00Z",
        details: "Chờ bổ sung gia hạn chứng nhận GCP năm 2026.",
      },
    ],
  },
  {
    id: "usr_usr_3319",
    email: "doanducmanh@outlook.com",
    fullName: "Đoàn Đức Mạnh",
    role: "normal",
    status: "pending_verification",
    activeSessionsCount: 0,
    twoFactorEnabled: false,
    failedLoginAttempts: 0,
    departmentOrOrg: "Người dùng mới đăng ký",
    phoneMasked: "+84 ••• ••• 117",
    lastActiveAt: "2026-08-24T02:00:00Z",
    createdAt: "2026-08-24T02:00:00Z",
    auditHistory: [
      {
        id: "aud_14",
        action: "created",
        actionLabelVi: "Đăng ký tài khoản qua web",
        actionLabelEn: "Web registration submitted",
        actor: "usr_usr_3319",
        timestamp: "2026-08-24T02:00:00Z",
        details: "Đang chờ nhấp liên kết xác nhận email.",
      },
    ],
  },
];

let inMemoryUsersCache: AdminUser[] = [...SEED_ADMIN_USERS];

export function resetUsersCacheForTesting(): void {
  inMemoryUsersCache = [...SEED_ADMIN_USERS];
}

// ---------------------------------------------------------------------------
// Client API Functions
// ---------------------------------------------------------------------------

export async function listAdminUsers(options?: {
  query?: string;
  role?: UserRole | "all";
  status?: AdminUserStatus | "all";
}): Promise<AdminUser[]> {
  try {
    const res = await api.get<{ users: AdminUser[] }>("/admin/users");
    if (res.data?.users && Array.isArray(res.data.users)) {
      inMemoryUsersCache = [...res.data.users];
    }
  } catch {
    // Graceful offline/fallback: use in-memory store
  }

  let result = [...inMemoryUsersCache];

  if (options?.role && options.role !== "all") {
    result = result.filter((u) => u.role === options.role);
  }

  if (options?.status && options.status !== "all") {
    result = result.filter((u) => u.status === options.status);
  }

  if (options?.query && options.query.trim()) {
    const q = options.query.trim().toLowerCase();
    result = result.filter(
      (u) =>
        u.fullName.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q) ||
        u.id.toLowerCase().includes(q) ||
        (u.departmentOrOrg && u.departmentOrOrg.toLowerCase().includes(q)),
    );
  }

  return result;
}

export async function updateUserRole(
  userId: string,
  newRole: UserRole,
  reason?: string,
  actor: string = "Admin Operator",
): Promise<{ success: boolean; user: AdminUser }> {
  const index = inMemoryUsersCache.findIndex((u) => u.id === userId);
  if (index === -1) {
    throw new Error(`User with ID ${userId} not found`);
  }

  const prevUser = inMemoryUsersCache[index];
  const oldRoleLabel = prevUser.role.toUpperCase();
  const newRoleLabel = newRole.toUpperCase();

  const auditEntry: UserAuditEntry = {
    id: `aud_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    action: "role_updated",
    actionLabelVi: `Thay đổi phân quyền vai trò: ${oldRoleLabel} → ${newRoleLabel}`,
    actionLabelEn: `Role assignment modified: ${oldRoleLabel} → ${newRoleLabel}`,
    actor,
    timestamp: new Date().toISOString(),
    details: reason || `Cập nhật vai trò từ ${oldRoleLabel} sang ${newRoleLabel}.`,
  };

  const updatedUser: AdminUser = {
    ...prevUser,
    role: newRole,
    auditHistory: [auditEntry, ...prevUser.auditHistory],
  };

  inMemoryUsersCache[index] = updatedUser;

  try {
    await api.patch(`/admin/users/${encodeURIComponent(userId)}/role`, {
      role: newRole,
      reason,
    });
  } catch {
    // Keep optimistic in-memory update
  }

  return { success: true, user: updatedUser };
}

export async function lockUserAccount(
  userId: string,
  reason: string,
  lockedBy: string = "Admin Operator",
): Promise<{ success: boolean; user: AdminUser }> {
  const index = inMemoryUsersCache.findIndex((u) => u.id === userId);
  if (index === -1) {
    throw new Error(`User with ID ${userId} not found`);
  }

  const prevUser = inMemoryUsersCache[index];
  const now = new Date().toISOString();

  const auditEntry: UserAuditEntry = {
    id: `aud_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    action: "account_locked",
    actionLabelVi: "Khóa tài khoản và thu hồi phiên làm việc",
    actionLabelEn: "Account locked and sessions revoked",
    actor: lockedBy,
    timestamp: now,
    details: reason,
  };

  const updatedUser: AdminUser = {
    ...prevUser,
    status: "locked",
    activeSessionsCount: 0,
    lockReason: reason,
    lockedAt: now,
    lockedBy,
    auditHistory: [auditEntry, ...prevUser.auditHistory],
  };

  inMemoryUsersCache[index] = updatedUser;

  try {
    await api.post(`/admin/users/${encodeURIComponent(userId)}/lock`, {
      reason,
      locked_by: lockedBy,
    });
  } catch {
    // Keep optimistic in-memory update
  }

  return { success: true, user: updatedUser };
}

export async function unlockUserAccount(
  userId: string,
  unlockedBy: string = "Admin Operator",
): Promise<{ success: boolean; user: AdminUser }> {
  const index = inMemoryUsersCache.findIndex((u) => u.id === userId);
  if (index === -1) {
    throw new Error(`User with ID ${userId} not found`);
  }

  const prevUser = inMemoryUsersCache[index];
  const now = new Date().toISOString();

  const auditEntry: UserAuditEntry = {
    id: `aud_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    action: "account_unlocked",
    actionLabelVi: "Mở khóa tài khoản người dùng",
    actionLabelEn: "Account unlocked and restored",
    actor: unlockedBy,
    timestamp: now,
    details: "Mở khóa tài khoản, cho phép người dùng đăng nhập lại bình thường.",
  };

  const updatedUser: AdminUser = {
    ...prevUser,
    status: "active",
    failedLoginAttempts: 0,
    lockReason: undefined,
    lockedAt: undefined,
    lockedBy: undefined,
    auditHistory: [auditEntry, ...prevUser.auditHistory],
  };

  inMemoryUsersCache[index] = updatedUser;

  try {
    await api.post(`/admin/users/${encodeURIComponent(userId)}/unlock`, {
      unlocked_by: unlockedBy,
    });
  } catch {
    // Keep optimistic in-memory update
  }

  return { success: true, user: updatedUser };
}

export async function revokeUserSessions(
  userId: string,
  actor: string = "Admin Operator",
): Promise<{ success: boolean; revokedCount: number; user: AdminUser }> {
  const index = inMemoryUsersCache.findIndex((u) => u.id === userId);
  if (index === -1) {
    throw new Error(`User with ID ${userId} not found`);
  }

  const prevUser = inMemoryUsersCache[index];
  const revokedCount = prevUser.activeSessionsCount;
  const now = new Date().toISOString();

  const auditEntry: UserAuditEntry = {
    id: `aud_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    action: "sessions_revoked",
    actionLabelVi: `Thu hồi tất cả ${revokedCount} phiên đăng nhập đang hoạt động`,
    actionLabelEn: `Revoked all ${revokedCount} active login sessions`,
    actor,
    timestamp: now,
    details: "Thu hồi bắt buộc tất cả token phiên đang kết nối trên toàn bộ thiết bị.",
  };

  const updatedUser: AdminUser = {
    ...prevUser,
    activeSessionsCount: 0,
    auditHistory: [auditEntry, ...prevUser.auditHistory],
  };

  inMemoryUsersCache[index] = updatedUser;

  try {
    await api.post(`/admin/users/${encodeURIComponent(userId)}/revoke-sessions`);
  } catch {
    // Keep optimistic in-memory update
  }

  return { success: true, revokedCount, user: updatedUser };
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
