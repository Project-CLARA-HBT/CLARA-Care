"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import { Badge } from "@/components/ui/badge";
import { StatusChip } from "@/components/ui/status-chip";
import {
  Inspector,
  InspectorField,
  InspectorSection,
} from "@/components/ui/inspector";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  computeUserStats,
  getRoleMeta,
  getStatusMeta,
  listAdminUsers,
  lockUserAccount,
  revokeUserSessions,
  unlockUserAccount,
  updateUserRole,
  type AdminUser,
  type AdminUserStatus,
} from "@/lib/admin-users";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * User Administration Registry (Spec v8 Section 12.5 / Spec v5 Section 6.61).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: User Administration Registry / User Directory Ledger
 *
 * Dense, high-signal administrative workbench providing:
 * 1. KPI summary cards (Total Users, Active, Doctors & Researchers, Locked Accounts, Active Sessions).
 * 2. High-density user registry table with real-time multi-dimensional filtering
 *    (search by name/email/org/ID, role filter `admin`/`doctor`/`researcher`/`normal`, status filter).
 * 3. Status badges and security indicators (2FA status, session count, failed logins).
 * 4. Slide-out inspector drawer for:
 *    - Role elevation / reassignment with justification tracking.
 *    - Account lock & unlock management with audit trail.
 *    - Session revocation (instant invalidation across all devices).
 *    - Zero-PII account audit history.
 * 5. Authoritative defense-in-depth access gating for Admin role.
 */

const ROLE_OPTIONS: Array<{ role: UserRole; labelVi: string; labelEn: string }> = [
  { role: "admin", labelVi: "Quản trị viên (Admin)", labelEn: "Admin" },
  { role: "doctor", labelVi: "Bác sĩ lâm sàng (Doctor)", labelEn: "Doctor" },
  { role: "researcher", labelVi: "Nhà nghiên cứu (Researcher)", labelEn: "Researcher" },
  { role: "normal", labelVi: "Người dùng cá nhân (End User)", labelEn: "End User" },
];

const STATUS_FILTER_OPTIONS: Array<{
  value: AdminUserStatus | "all";
  labelVi: string;
  labelEn: string;
}> = [
  { value: "all", labelVi: "Tất cả trạng thái", labelEn: "All Statuses" },
  { value: "active", labelVi: "Đang hoạt động", labelEn: "Active" },
  { value: "locked", labelVi: "Đã khóa", labelEn: "Locked" },
  { value: "suspended", labelVi: "Tạm đình chỉ", labelEn: "Suspended" },
  { value: "pending_verification", labelVi: "Chờ xác minh", labelEn: "Pending" },
];

function formatDateSafe(
  locale: UILanguage,
  value: string | number | Date | null | undefined,
): string {
  if (!value) return "--";
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return formatLocaleDate(locale, d);
  } catch {
    return String(value);
  }
}

export default function AdminUsersPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // User Registry Data
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);

  // Filters State
  const [searchQuery, setSearchQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "all">("all");
  const [statusFilter, setStatusFilter] = useState<AdminUserStatus | "all">("all");

  // Drawer Form State
  const [editRole, setEditRole] = useState<UserRole>("normal");
  const [roleReason, setRoleReason] = useState("");
  const [lockReasonInput, setLockReasonInput] = useState("");
  const [isSubmittingRole, setIsSubmittingRole] = useState(false);
  const [isSubmittingLock, setIsSubmittingLock] = useState(false);
  const [isSubmittingRevoke, setIsSubmittingRevoke] = useState(false);

  // Confirmation Modals
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    variant: "danger" | "primary";
    action: () => Promise<void>;
  }>({
    open: false,
    title: "",
    description: "",
    confirmLabel: "",
    variant: "primary",
    action: async () => {},
  });

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAdminUsers();
      setUsers(data);
    } catch (err) {
      setError(
        safeUserFacingError(
          err,
          uiLanguage === "vi"
            ? "Không thể tải danh sách người dùng hệ thống."
            : "Failed to load user administration registry.",
        ),
      );
    } finally {
      setLoading(false);
    }
  }, [uiLanguage]);

  useEffect(() => {
    if (role === "admin") {
      loadData();
    }
  }, [role, loadData]);

  // Sync drawer state when selectedUser changes
  useEffect(() => {
    if (selectedUser) {
      setEditRole(selectedUser.role);
      setRoleReason("");
      setLockReasonInput("");
    }
  }, [selectedUser]);

  // Auto-dismiss toast after 4s
  useEffect(() => {
    if (toastMessage) {
      const timer = setTimeout(() => setToastMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toastMessage]);

  // Filtered Users
  const filteredUsers = useMemo(() => {
    return users.filter((user) => {
      if (roleFilter !== "all" && user.role !== roleFilter) return false;
      if (statusFilter !== "all" && user.status !== statusFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const matchName = user.fullName.toLowerCase().includes(q);
        const matchEmail = user.email.toLowerCase().includes(q);
        const matchId = user.id.toLowerCase().includes(q);
        const matchOrg = user.departmentOrOrg?.toLowerCase().includes(q) ?? false;
        if (!matchName && !matchEmail && !matchId && !matchOrg) return false;
      }
      return true;
    });
  }, [users, roleFilter, statusFilter, searchQuery]);

  // Summary Metrics
  const stats = useMemo(() => computeUserStats(users), [users]);

  // Actions
  const handleRoleChangeSubmit = async () => {
    if (!selectedUser) return;
    if (editRole === selectedUser.role) {
      setToastMessage({
        type: "error",
        text:
          uiLanguage === "vi"
            ? "Vai trò mới trùng khớp với vai trò hiện tại."
            : "New role matches the current role.",
      });
      return;
    }

    const executeUpdate = async () => {
      setIsSubmittingRole(true);
      try {
        const res = await updateUserRole(
          selectedUser.id,
          editRole,
          roleReason.trim() || undefined,
        );
        if (res.success) {
          setUsers((prev) =>
            prev.map((u) => (u.id === selectedUser.id ? res.user : u)),
          );
          setSelectedUser(res.user);
          setRoleReason("");
          setToastMessage({
            type: "success",
            text:
              uiLanguage === "vi"
                ? `Đã cập nhật vai trò người dùng thành ${getRoleMeta(editRole).labelVi}.`
                : `Successfully updated user role to ${getRoleMeta(editRole).labelEn}.`,
          });
        }
      } catch (err) {
        setToastMessage({
          type: "error",
          text: safeUserFacingError(
            err,
            uiLanguage === "vi"
              ? "Không thể cập nhật phân quyền người dùng."
              : "Failed to update user role.",
          ),
        });
      } finally {
        setIsSubmittingRole(false);
        setConfirmModal((prev) => ({ ...prev, open: false }));
      }
    };

    // If granting Admin privilege, require confirmation modal
    if (editRole === "admin") {
      setConfirmModal({
        open: true,
        title:
          uiLanguage === "vi"
            ? "Xác nhận cấp toàn quyền Quản trị viên (Admin)"
            : "Confirm Admin Privilege Elevation",
        description:
          uiLanguage === "vi"
            ? `Bạn đang cấp toàn quyền Quản trị viên cho tài khoản ${selectedUser.email}. Tài khoản này sẽ có quyền truy cập toàn bộ hệ thống, cấu hình RAG và kiểm soát người dùng.`
            : `You are elevating ${selectedUser.email} to full Administrator. This account will gain full access to system configuration, RAG controls, and user administration.`,
        confirmLabel:
          uiLanguage === "vi" ? "Xác nhận cấp quyền Admin" : "Confirm Admin Elevation",
        variant: "danger",
        action: executeUpdate,
      });
      return;
    }

    await executeUpdate();
  };

  const handleLockAccount = () => {
    if (!selectedUser) return;
    const reason = lockReasonInput.trim();
    if (!reason) {
      setToastMessage({
        type: "error",
        text:
          uiLanguage === "vi"
            ? "Vui lòng nhập lý do khóa tài khoản."
            : "Please provide a reason for locking the account.",
      });
      return;
    }

    setConfirmModal({
      open: true,
      title:
        uiLanguage === "vi"
          ? "Xác nhận khóa tài khoản người dùng"
          : "Confirm User Account Lock",
      description:
        uiLanguage === "vi"
          ? `Tài khoản ${selectedUser.email} (${selectedUser.fullName}) sẽ bị khóa ngay lập tức và toàn bộ phiên làm việc sẽ bị thu hồi.`
          : `Account ${selectedUser.email} (${selectedUser.fullName}) will be locked immediately and all active sessions will be revoked.`,
      confirmLabel:
        uiLanguage === "vi" ? "Xác nhận khóa tài khoản" : "Confirm Account Lock",
      variant: "danger",
      action: async () => {
        setIsSubmittingLock(true);
        try {
          const res = await lockUserAccount(selectedUser.id, reason);
          if (res.success) {
            setUsers((prev) =>
              prev.map((u) => (u.id === selectedUser.id ? res.user : u)),
            );
            setSelectedUser(res.user);
            setLockReasonInput("");
            setToastMessage({
              type: "success",
              text:
                uiLanguage === "vi"
                  ? `Đã khóa tài khoản ${selectedUser.email} và thu hồi các phiên đăng nhập.`
                  : `Successfully locked account ${selectedUser.email} and revoked active sessions.`,
            });
          }
        } catch (err) {
          setToastMessage({
            type: "error",
            text: safeUserFacingError(
              err,
              uiLanguage === "vi"
                ? "Không thể khóa tài khoản người dùng."
                : "Failed to lock account.",
            ),
          });
        } finally {
          setIsSubmittingLock(false);
          setConfirmModal((prev) => ({ ...prev, open: false }));
        }
      },
    });
  };

  const handleUnlockAccount = () => {
    if (!selectedUser) return;

    setConfirmModal({
      open: true,
      title:
        uiLanguage === "vi"
          ? "Xác nhận mở khóa tài khoản"
          : "Confirm Account Unlock",
      description:
        uiLanguage === "vi"
          ? `Mở khóa tài khoản cho ${selectedUser.email}. Người dùng sẽ có thể đăng nhập lại bình thường.`
          : `Unlock account for ${selectedUser.email}. The user will be able to log in normally.`,
      confirmLabel:
        uiLanguage === "vi" ? "Xác nhận mở khóa" : "Confirm Unlock",
      variant: "primary",
      action: async () => {
        setIsSubmittingLock(true);
        try {
          const res = await unlockUserAccount(selectedUser.id);
          if (res.success) {
            setUsers((prev) =>
              prev.map((u) => (u.id === selectedUser.id ? res.user : u)),
            );
            setSelectedUser(res.user);
            setToastMessage({
              type: "success",
              text:
                uiLanguage === "vi"
                  ? `Đã mở khóa tài khoản ${selectedUser.email}.`
                  : `Successfully unlocked account ${selectedUser.email}.`,
            });
          }
        } catch (err) {
          setToastMessage({
            type: "error",
            text: safeUserFacingError(
              err,
              uiLanguage === "vi"
                ? "Không thể mở khóa tài khoản."
                : "Failed to unlock account.",
            ),
          });
        } finally {
          setIsSubmittingLock(false);
          setConfirmModal((prev) => ({ ...prev, open: false }));
        }
      },
    });
  };

  const handleRevokeSessions = () => {
    if (!selectedUser) return;
    if (selectedUser.activeSessionsCount <= 0) {
      setToastMessage({
        type: "error",
        text:
          uiLanguage === "vi"
            ? "Tài khoản hiện không có phiên hoạt động nào."
            : "No active sessions found for this user.",
      });
      return;
    }

    setConfirmModal({
      open: true,
      title:
        uiLanguage === "vi"
          ? "Thu hồi toàn bộ phiên đăng nhập"
          : "Revoke All Active Sessions",
      description:
        uiLanguage === "vi"
          ? `Toàn bộ ${selectedUser.activeSessionsCount} phiên làm việc đang kết nối của ${selectedUser.email} sẽ bị thu hồi bắt buộc trên tất cả thiết bị.`
          : `All ${selectedUser.activeSessionsCount} active sessions for ${selectedUser.email} will be immediately terminated on all devices.`,
      confirmLabel:
        uiLanguage === "vi" ? "Xác nhận thu hồi phiên" : "Confirm Revoke Sessions",
      variant: "danger",
      action: async () => {
        setIsSubmittingRevoke(true);
        try {
          const res = await revokeUserSessions(selectedUser.id);
          if (res.success) {
            if (res.user) {
              const updatedUser = res.user;
              setUsers((prev) =>
                prev.map((u) => (u.id === selectedUser.id ? updatedUser : u)),
              );
              setSelectedUser(updatedUser);
            }
            setToastMessage({
              type: "success",
              text:
                uiLanguage === "vi"
                  ? `Đã thu hồi ${res.revokedCount} phiên đăng nhập của ${selectedUser.email}.`
                  : `Successfully revoked ${res.revokedCount} active sessions for ${selectedUser.email}.`,
            });
          }
        } catch (err) {
          setToastMessage({
            type: "error",
            text: safeUserFacingError(
              err,
              uiLanguage === "vi"
                ? "Không thể thu hồi phiên đăng nhập."
                : "Failed to revoke sessions.",
            ),
          });
        } finally {
          setIsSubmittingRevoke(false);
          setConfirmModal((prev) => ({ ...prev, open: false }));
        }
      },
    });
  };

  // Defense-in-depth RBAC View
  if (role !== "admin") {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center p-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]">
          <Icon name="warning" size="1.5rem" />
        </div>
        <h1 className="mt-4 text-lg font-semibold text-[var(--text-primary)]">
          {uiLanguage === "vi"
            ? "Từ chối truy cập (403 Forbidden)"
            : "Access Forbidden (403 Forbidden)"}
        </h1>
        <p className="mt-1 max-w-md text-sm text-[var(--text-muted)]">
          {uiLanguage === "vi"
            ? "Bạn không có quyền truy cập trang quản trị này. Chỉ quản trị viên hệ thống (Admin) mới có thể xem và quản lý danh sách người dùng."
            : "You do not have permission to access this administration registry. Only system administrators can view and manage users."}
        </p>
      </div>
    );
  }

  const pageTitle =
    uiLanguage === "vi"
      ? "Quản trị người dùng & Phân quyền"
      : "User Administration Registry";
  const pageDescription =
    uiLanguage === "vi"
      ? "Quản lý tài khoản người dùng, phân bổ vai trò RBAC, kiểm soát khóa truy cập và thu hồi phiên làm việc."
      : "Manage user accounts, assign RBAC roles, control account locks, and revoke active sessions.";

  return (
    <AdminShell
      activeTab="users"
      title={pageTitle}
      description={pageDescription}
    >
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="User Directory Ledger"
        data-density="dense"
        className="space-y-6"
      >
        {/* Page Title & Context Header */}
        <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-[var(--text-primary)]">
                {pageTitle}
              </h1>
              <span className="rounded bg-[var(--surface-brand-soft)] px-2 py-0.5 text-[10px] font-mono font-bold text-[var(--brand-600)]">
                USER-ADM
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {pageDescription}
            </p>
          </div>
        </header>

        {/* Toast Banner */}
        {toastMessage && (
          <div
            role="status"
            className={`flex items-center justify-between gap-3 rounded-[var(--radius-md)] border px-4 py-3 text-xs font-medium transition-all ${
              toastMessage.type === "success"
                ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                : "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
            }`}
          >
            <div className="flex items-center gap-2">
              <Icon
                name={toastMessage.type === "success" ? "check" : "warning"}
                size="1rem"
              />
              <span>{toastMessage.text}</span>
            </div>
            <button
              onClick={() => setToastMessage(null)}
              className="text-current opacity-70 hover:opacity-100"
              aria-label={uiLanguage === "vi" ? "Đóng thông báo" : "Dismiss notification"}
            >
              <Icon name="close" size="0.9rem" />
            </button>
          </div>
        )}

        {/* Global Error Banner */}
        {error && (
          <div
            role="alert"
            className="flex items-center justify-between rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 text-sm text-[var(--status-danger-text)]"
          >
            <div className="flex items-center gap-2">
              <Icon name="warning" size="1.2rem" />
              <span>{error}</span>
            </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={loadData}
                className="border-[color:var(--status-danger-border)] bg-transparent text-current hover:bg-[var(--status-danger-bg)]"
              >
              {uiLanguage === "vi" ? "Thử lại" : "Retry"}
            </Button>
          </div>
        )}

        {/* Summary KPI Ledger */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <KpiCard
            label={uiLanguage === "vi" ? "Tổng người dùng" : "Total Users"}
            value={stats.totalUsers.toString()}
            hint={
              uiLanguage === "vi"
                ? `${stats.adminCount} Quản trị viên`
                : `${stats.adminCount} Admins`
            }
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Đang hoạt động" : "Active Users"}
            value={stats.activeUsers.toString()}
            hint={
              uiLanguage === "vi"
                ? `${Math.round((stats.activeUsers / (stats.totalUsers || 1)) * 100)}% toàn bộ tài khoản`
                : `${Math.round((stats.activeUsers / (stats.totalUsers || 1)) * 100)}% of all users`
            }
          />
          <KpiCard
            label={
              uiLanguage === "vi"
                ? "Bác sĩ & Nghiên cứu"
                : "Clinicians & Researchers"
            }
            value={(stats.doctorCount + stats.researcherCount).toString()}
            hint={
              uiLanguage === "vi"
                ? `${stats.doctorCount} Bác sĩ · ${stats.researcherCount} Nghiên cứu`
                : `${stats.doctorCount} Doctors · ${stats.researcherCount} Researchers`
            }
          />
          <KpiCard
            label={
              uiLanguage === "vi" ? "Tài khoản bị khóa" : "Locked / Flagged"
            }
            value={stats.lockedUsers.toString()}
            hint={
              uiLanguage === "vi"
                ? stats.lockedUsers > 0
                  ? "Cần kiểm tra an toàn"
                  : "Không có cảnh báo"
                : stats.lockedUsers > 0
                  ? "Security review needed"
                  : "All clear"
            }
          />
          <KpiCard
            label={uiLanguage === "vi" ? "Phiên đang kết nối" : "Active Sessions"}
            value={stats.totalActiveSessions.toString()}
            hint={
              uiLanguage === "vi"
                ? "Tổng phiên đa thiết bị"
                : "Across all devices"
            }
          />
        </div>

        {/* User Administration Registry Panel */}
        <PanelCard
          title={
            uiLanguage === "vi"
              ? "Danh sách Người dùng Hệ thống"
              : "User Administration Registry"
          }
          description={
            uiLanguage === "vi"
              ? "Bảng quản trị tài khoản mật độ cao. Nhấp vào dòng để mở thanh kiểm tra chi tiết, phân quyền vai trò, khóa tài khoản hoặc thu hồi phiên."
              : "High-density account management table. Click a row to open the inspector drawer for role assignment, account locking, or session revocation."
          }
        >
          <div className="space-y-4">
            {/* Filter & Search Toolbar */}
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              {/* Search Bar */}
              <div className="relative flex-1 max-w-md">
                <Icon
                  name="search"
                  size="1rem"
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <input
                  type="search"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={
                    uiLanguage === "vi"
                      ? "Tìm theo tên, email, User ID, bệnh viện/tổ chức..."
                      : "Search by name, email, User ID, hospital/org..."
                  }
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] py-2 pl-9 pr-8 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[var(--brand-500)]"
                  aria-label={
                    uiLanguage === "vi"
                      ? "Tìm kiếm người dùng"
                      : "Search users"
                  }
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    aria-label="Xóa tìm kiếm"
                  >
                    <Icon name="close" size="0.85rem" />
                  </button>
                )}
              </div>

              {/* Filters & Actions */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Role Filter Pills */}
                <div className="flex items-center rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-0.5">
                  <button
                    type="button"
                    onClick={() => setRoleFilter("all")}
                    className={`rounded-[var(--radius-sm)] px-2.5 py-1 text-xs font-medium transition-colors ${
                      roleFilter === "all"
                        ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                        : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    {uiLanguage === "vi" ? "Tất cả vai trò" : "All Roles"}
                  </button>
                  {ROLE_OPTIONS.map((opt) => (
                    <button
                      key={opt.role}
                      type="button"
                      onClick={() => setRoleFilter(opt.role)}
                      className={`rounded-[var(--radius-sm)] px-2.5 py-1 text-xs font-medium transition-colors ${
                        roleFilter === opt.role
                          ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm font-semibold"
                          : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                      }`}
                    >
                      {uiLanguage === "vi" ? opt.labelVi.split(" ")[0] : opt.labelEn}
                    </button>
                  ))}
                </div>

                {/* Status Dropdown Filter */}
                <select
                  value={statusFilter}
                  onChange={(e) =>
                    setStatusFilter(e.target.value as AdminUserStatus | "all")
                  }
                  className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-500)] focus:outline-none"
                  aria-label={
                    uiLanguage === "vi"
                      ? "Lọc theo trạng thái tài khoản"
                      : "Filter by account status"
                  }
                >
                  {STATUS_FILTER_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {uiLanguage === "vi" ? opt.labelVi : opt.labelEn}
                    </option>
                  ))}
                </select>

                {/* Refresh Button */}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={loadData}
                  disabled={loading}
                  className="h-8 gap-1.5 text-xs"
                >
                  <Icon
                    name="refresh"
                    size="0.85rem"
                    className={loading ? "animate-spin" : ""}
                  />
                  <span>{uiLanguage === "vi" ? "Làm mới" : "Refresh"}</span>
                </Button>
              </div>
            </div>

            {/* Results Count Counter */}
            <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
              <span>
                {uiLanguage === "vi"
                  ? `Hiển thị ${filteredUsers.length} / ${users.length} tài khoản người dùng`
                  : `Showing ${filteredUsers.length} of ${users.length} user accounts`}
              </span>
              {selectedUser && (
                <span className="font-medium text-[var(--brand-600)]">
                  {uiLanguage === "vi"
                    ? `Đang chọn: ${selectedUser.fullName} (${selectedUser.id})`
                    : `Selected: ${selectedUser.fullName} (${selectedUser.id})`}
                </span>
              )}
            </div>

            {/* Dense User Table */}
            <div className="overflow-x-auto rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)]">
              <table
                className="w-full text-left text-xs border-collapse"
                aria-label={
                  uiLanguage === "vi"
                    ? "Bảng danh sách quản trị người dùng"
                    : "User administration table"
                }
              >
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Người dùng & Tổ chức" : "User & Org"}
                    </th>
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Vai trò (RBAC)" : "Role"}
                    </th>
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Trạng thái" : "Status"}
                    </th>
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Bảo mật / 2FA" : "Security"}
                    </th>
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Phiên" : "Sessions"}
                    </th>
                    <th className="py-2.5 px-3">
                      {uiLanguage === "vi" ? "Hoạt động gần nhất" : "Last Active"}
                    </th>
                    <th className="py-2.5 px-3 text-right">
                      {uiLanguage === "vi" ? "Thao tác" : "Action"}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color:var(--shell-border)]">
                  {loading && users.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-10 text-center text-[var(--text-muted)]">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <Icon name="refresh" size="1.25rem" className="animate-spin text-[var(--brand-600)]" />
                          <span>{uiLanguage === "vi" ? "Đang tải dữ liệu người dùng..." : "Loading user records..."}</span>
                        </div>
                      </td>
                    </tr>
                  ) : filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-[var(--text-muted)]">
                        <div className="flex flex-col items-center justify-center gap-2">
                          <Icon name="search" size="1.5rem" className="text-[var(--text-muted)]" />
                          <p className="font-medium text-[var(--text-primary)]">
                            {uiLanguage === "vi" ? "Không tìm thấy người dùng nào" : "No users match your criteria"}
                          </p>
                          <p className="text-xs">
                            {uiLanguage === "vi"
                              ? "Hãy thử thay đổi từ khóa tìm kiếm hoặc điều chỉnh bộ lọc vai trò/trạng thái."
                              : "Try adjusting your search query or relaxing role/status filters."}
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map((user) => {
                      const roleMeta = getRoleMeta(user.role);
                      const statusMeta = getStatusMeta(user.status);
                      const isSelected = selectedUser?.id === user.id;

                      return (
                        <tr
                          key={user.id}
                          onClick={() => setSelectedUser(user)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              setSelectedUser(user);
                            }
                          }}
                          tabIndex={0}
                          role="button"
                          aria-pressed={isSelected}
                          className={`group cursor-pointer transition-colors focus:outline-none focus:bg-[var(--surface-brand-soft)]/50 ${
                            isSelected
                              ? "bg-[var(--surface-brand-soft)]/60 font-medium"
                              : "hover:bg-[var(--surface-muted)]/70"
                          }`}
                        >
                          {/* User Name, Email, Org */}
                          <td className="py-2.5 px-3">
                            <div className="flex items-center gap-2.5">
                              <div
                                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                                  user.role === "admin"
                                    ? "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                                    : user.role === "doctor"
                                      ? "bg-[var(--status-warning-bg)] text-[var(--status-warning-text)]"
                                      : user.role === "researcher"
                                        ? "bg-[var(--status-info-bg)] text-[var(--status-info-text)]"
                                        : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                                }`}
                              >
                                {user.fullName
                                  .split(" ")
                                  .filter(Boolean)
                                  .slice(-1)[0]?.[0] || "U"}
                              </div>
                              <div className="min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-semibold text-[var(--text-primary)] truncate">
                                    {user.fullName}
                                  </span>
                                  <span className="font-mono text-[10px] text-[var(--text-muted)]">
                                    #{user.id}
                                  </span>
                                </div>
                                <div className="text-[11px] text-[var(--text-muted)] truncate">
                                  {user.email}
                                </div>
                                {user.departmentOrOrg && (
                                  <div className="text-[10px] text-[var(--text-secondary)] truncate">
                                    {user.departmentOrOrg}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Role Badge */}
                          <td className="py-2.5 px-3">
                            <Badge
                              tone={roleMeta.badgeTone}
                              icon={roleMeta.icon}
                              className="text-[11px] font-medium"
                            >
                              {uiLanguage === "vi"
                                ? roleMeta.labelVi.split(" (")[0]
                                : roleMeta.labelEn}
                            </Badge>
                          </td>

                          {/* Status Badge */}
                          <td className="py-2.5 px-3">
                            <StatusChip
                              tone={statusMeta.tone}
                              label={
                                uiLanguage === "vi"
                                  ? statusMeta.labelVi
                                  : statusMeta.labelEn
                              }
                              size="sm"
                            />
                          </td>

                          {/* Security & 2FA */}
                          <td className="py-2.5 px-3">
                            <div className="flex flex-col gap-0.5">
                              {user.twoFactorEnabled ? (
                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[var(--status-ok-text)]">
                                  <Icon name="check" size="0.75rem" />
                                  2FA On
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] text-[var(--text-muted)]">
                                  2FA Off
                                </span>
                              )}
                              {user.failedLoginAttempts > 0 && (
                                <span className="text-[10px] font-semibold text-[var(--status-danger-text)]">
                                  {user.failedLoginAttempts} {uiLanguage === "vi" ? "lần sai pass" : "failed logins"}
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Active Sessions Count */}
                          <td className="py-2.5 px-3">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ${
                                user.activeSessionsCount > 0
                                  ? "bg-[var(--surface-brand-soft)] text-[var(--brand-600)]"
                                  : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                              }`}
                            >
                              {user.activeSessionsCount}{" "}
                              {uiLanguage === "vi" ? "phiên" : "active"}
                            </span>
                          </td>

                          {/* Last Active Timestamp */}
                          <td className="py-2.5 px-3 text-[11px] text-[var(--text-muted)]">
                            {formatDateSafe(uiLanguage, user.lastActiveAt)}
                          </td>

                          {/* Inspect Button */}
                          <td className="py-2.5 px-3 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedUser(user);
                              }}
                              className="h-7 px-2.5 text-xs text-[var(--brand-600)] hover:bg-[var(--surface-brand-soft)]"
                              aria-label={
                                uiLanguage === "vi"
                                  ? `Kiểm tra tài khoản ${user.fullName}`
                                  : `Inspect user ${user.fullName}`
                              }
                            >
                              <Icon name="eye" size="0.85rem" className="mr-1" />
                              {uiLanguage === "vi" ? "Kiểm tra" : "Inspect"}
                            </Button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </PanelCard>

        {/* Slide-out Inspector Drawer */}
        <Inspector
          open={Boolean(selectedUser)}
          onClose={() => setSelectedUser(null)}
          size="lg"
          title={selectedUser?.fullName || (uiLanguage === "vi" ? "Chi tiết tài khoản" : "User Details")}
          subtitle={selectedUser?.email}
          badge={
            selectedUser ? (
              <StatusChip
                tone={getStatusMeta(selectedUser.status).tone}
                label={
                  uiLanguage === "vi"
                    ? getStatusMeta(selectedUser.status).labelVi
                    : getStatusMeta(selectedUser.status).labelEn
                }
                size="sm"
              />
            ) : undefined
          }
          actions={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelectedUser(null)}
              aria-label={uiLanguage === "vi" ? "Đóng bảng kiểm tra" : "Close inspector"}
            >
              <Icon name="close" size="1rem" />
            </Button>
          }
        >
          {selectedUser && (
            <div className="space-y-4">
              {/* Section 1: User Identity & Demographics */}
              <InspectorSection
                title={
                  uiLanguage === "vi"
                    ? "Thông tin định danh & Tổ chức"
                    : "Identity & Organization"
                }
                description={
                  uiLanguage === "vi"
                    ? "Dữ liệu định danh tài khoản và tổ chức công tác được chứng thực."
                    : "Verified user credentials and affiliated organization."
                }
              >
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <InspectorField
                    label={uiLanguage === "vi" ? "Mã người dùng (User ID)" : "User ID"}
                    value={selectedUser.id}
                    copyable
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Email đăng nhập" : "Email Address"}
                    value={selectedUser.email}
                    copyable
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Đơn vị / Bệnh viện" : "Affiliated Unit"}
                    value={
                      selectedUser.departmentOrOrg ||
                      (uiLanguage === "vi" ? "Người dùng cá nhân" : "Independent User")
                    }
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Số điện thoại bảo mật" : "Phone (Masked)"}
                    value={selectedUser.phoneMasked || "--"}
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Ngày tạo tài khoản" : "Account Created"}
                    value={formatDateSafe(uiLanguage, selectedUser.createdAt)}
                  />
                  <InspectorField
                    label={uiLanguage === "vi" ? "Hoạt động gần nhất" : "Last Active"}
                    value={formatDateSafe(uiLanguage, selectedUser.lastActiveAt)}
                  />
                </div>
              </InspectorSection>

              {/* Section 2: Role Assignment (RBAC) */}
              <InspectorSection
                title={
                  uiLanguage === "vi"
                    ? "Phân quyền vai trò (Role Assignment)"
                    : "RBAC Role Assignment"
                }
                description={
                  uiLanguage === "vi"
                    ? "Chỉ định cấp bậc quyền hạn trong hệ thống CLARA. Quyền Quản trị viên yêu cầu xác thực bảo mật."
                    : "Assign privilege level across the platform. Admin promotion requires confirmation."
                }
              >
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {uiLanguage === "vi" ? "Vai trò hiện tại:" : "Current Role:"}
                    </span>
                    <Badge
                      tone={getRoleMeta(selectedUser.role).badgeTone}
                      icon={getRoleMeta(selectedUser.role).icon}
                    >
                      {uiLanguage === "vi"
                        ? getRoleMeta(selectedUser.role).labelVi
                        : getRoleMeta(selectedUser.role).labelEn}
                    </Badge>
                  </div>

                  {/* Role Selector Grid */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-[var(--text-primary)]">
                      {uiLanguage === "vi"
                        ? "Chọn vai trò mới:"
                        : "Select New Role:"}
                    </label>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {ROLE_OPTIONS.map((opt) => {
                        const isCurrent = editRole === opt.role;
                        const meta = getRoleMeta(opt.role);

                        return (
                          <button
                            key={opt.role}
                            type="button"
                            data-testid={`drawer-role-${opt.role}`}
                            aria-label={`Select role ${opt.labelEn}`}
                            onClick={() => setEditRole(opt.role)}
                            className={`flex flex-col text-left rounded-[var(--radius-md)] border p-2.5 transition-all ${
                              isCurrent
                                ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] ring-1 ring-[var(--brand-500)]"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-base)] hover:bg-[var(--surface-muted)]"
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-[var(--text-primary)]">
                                {uiLanguage === "vi" ? opt.labelVi : opt.labelEn}
                              </span>
                              {isCurrent && (
                                <Icon
                                  name="check"
                                  size="0.9rem"
                                  className="text-[var(--brand-600)]"
                                />
                              )}
                            </div>
                            <p className="mt-1 text-[11px] text-[var(--text-muted)] line-clamp-2">
                              {uiLanguage === "vi"
                                ? meta.descriptionVi
                                : meta.descriptionEn}
                            </p>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Reason Textfield */}
                  <div className="space-y-1">
                    <label
                      htmlFor="role-reason"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      {uiLanguage === "vi"
                        ? "Lý do thay đổi phân quyền (Ghi vào nhật ký kiểm toán):"
                        : "Reason for role change (Logged into audit trail):"}
                    </label>
                    <input
                      id="role-reason"
                      type="text"
                      value={roleReason}
                      onChange={(e) => setRoleReason(e.target.value)}
                      placeholder={
                        uiLanguage === "vi"
                          ? "Ví dụ: Cấp chứng thực bác sĩ theo quyết định số..."
                          : "E.g., Verified clinician license #..."
                      }
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] px-3 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-[color:var(--brand-500)] focus:outline-none"
                    />
                  </div>

                  {/* Submit Role Button */}
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleRoleChangeSubmit}
                    disabled={
                      isSubmittingRole || editRole === selectedUser.role
                    }
                    className="w-full justify-center gap-1.5 text-xs font-semibold"
                  >
                    <Icon
                      name="check"
                      size="0.85rem"
                      className={isSubmittingRole ? "animate-spin" : ""}
                    />
                    <span>
                      {uiLanguage === "vi"
                        ? "Lưu thay đổi vai trò"
                        : "Save Role Changes"}
                    </span>
                  </Button>
                </div>
              </InspectorSection>

              {/* Section 3: Security & Session Revocation */}
              <InspectorSection
                title={
                  uiLanguage === "vi"
                    ? "Bảo mật & Phiên làm việc"
                    : "Security & Active Sessions"
                }
                description={
                  uiLanguage === "vi"
                    ? "Kiểm soát xác thực 2 bước, theo dõi đăng nhập sai và thu hồi phiên truy cập từ xa."
                    : "Manage 2FA status, track failed logins, and revoke active device sessions."
                }
              >
                <div className="space-y-3">
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <InspectorField
                      label={
                        uiLanguage === "vi"
                          ? "Xác thực 2 yếu tố (2FA)"
                          : "Two-Factor Auth"
                      }
                      value={
                        selectedUser.twoFactorEnabled ? (
                          <span className="font-semibold text-[var(--status-ok-text)]">
                            {uiLanguage === "vi"
                              ? "Đã kích hoạt"
                              : "Enabled"}
                          </span>
                        ) : (
                          <span className="text-[var(--text-muted)]">
                            {uiLanguage === "vi"
                              ? "Chưa kích hoạt"
                              : "Disabled"}
                          </span>
                        )
                      }
                    />
                    <InspectorField
                      label={
                        uiLanguage === "vi"
                          ? "Lần đăng nhập sai"
                          : "Failed Login Attempts"
                      }
                      value={`${selectedUser.failedLoginAttempts} ${
                        uiLanguage === "vi" ? "lần" : "attempts"
                      }`}
                    />
                    <InspectorField
                      label={
                        uiLanguage === "vi"
                          ? "Số phiên đang hoạt động"
                          : "Active Sessions"
                      }
                      value={`${selectedUser.activeSessionsCount} ${
                        uiLanguage === "vi" ? "thiết bị đang kết nối" : "active devices"
                      }`}
                    />
                  </div>

                  {/* Revoke Sessions Action */}
                  <div className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h4 className="text-xs font-semibold text-[var(--text-primary)]">
                          {uiLanguage === "vi"
                            ? "Thu hồi phiên đăng nhập từ xa"
                            : "Revoke Active Sessions"}
                        </h4>
                        <p className="text-[11px] text-[var(--text-muted)]">
                          {uiLanguage === "vi"
                            ? "Đăng xuất tài khoản này khỏi tất cả trình duyệt và ứng dụng di động ngay lập tức."
                            : "Force logout from all browser and mobile app sessions immediately."}
                        </p>
                      </div>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleRevokeSessions}
                        disabled={
                          isSubmittingRevoke ||
                          selectedUser.activeSessionsCount <= 0
                        }
                        className="shrink-0 border-[color:var(--status-danger-border)] text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)] text-xs"
                      >
                        <Icon name="trash" size="0.85rem" className="mr-1" />
                        {uiLanguage === "vi"
                          ? "Thu hồi phiên"
                          : "Revoke All"}
                      </Button>
                    </div>
                  </div>
                </div>
              </InspectorSection>

              {/* Section 4: Account Lock & Access Control */}
              <InspectorSection
                title={
                  uiLanguage === "vi"
                    ? "Kiểm soát khóa tài khoản"
                    : "Account Lock & Access Control"
                }
                description={
                  uiLanguage === "vi"
                    ? "Khóa tài khoản khi phát hiện dấu hiệu vi phạm bảo mật hoặc mở khóa khi đã xử lý xong."
                    : "Lock account upon security anomaly or restore access after resolution."
                }
              >
                {selectedUser.status === "locked" ||
                selectedUser.status === "suspended" ? (
                  <div className="space-y-3 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]/30 p-3.5">
                    <div className="flex items-center gap-2 text-[var(--status-danger-text)] font-semibold text-xs">
                      <Icon name="warning" size="1rem" />
                      <span>
                        {uiLanguage === "vi"
                          ? "Tài khoản hiện đang bị khóa truy cập"
                          : "Account is currently locked / suspended"}
                      </span>
                    </div>

                    {selectedUser.lockReason && (
                      <p className="text-xs text-[var(--text-primary)]">
                        <strong>
                          {uiLanguage === "vi" ? "Lý do khóa: " : "Reason: "}
                        </strong>
                        {selectedUser.lockReason}
                      </p>
                    )}

                    <div className="flex flex-wrap gap-3 text-[11px] text-[var(--text-muted)]">
                      {selectedUser.lockedAt && (
                        <span>
                          {uiLanguage === "vi" ? "Thời gian: " : "At: "}
                          {formatDateSafe(uiLanguage, selectedUser.lockedAt)}
                        </span>
                      )}
                      {selectedUser.lockedBy && (
                        <span>
                          {uiLanguage === "vi" ? "Người thực hiện: " : "By: "}
                          {selectedUser.lockedBy}
                        </span>
                      )}
                    </div>

                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleUnlockAccount}
                      disabled={isSubmittingLock}
                      className="w-full justify-center text-xs bg-[var(--status-ok-text)] text-white hover:opacity-90"
                    >
                      <Icon name="check" size="0.85rem" className="mr-1" />
                      {uiLanguage === "vi"
                        ? "Mở khóa tài khoản ngay"
                        : "Unlock Account"}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    <label
                      htmlFor="lock-reason"
                      className="text-xs font-medium text-[var(--text-secondary)]"
                    >
                      {uiLanguage === "vi"
                        ? "Nhập lý do khóa tài khoản:"
                        : "Reason for account lock:"}
                    </label>
                    <textarea
                      id="lock-reason"
                      rows={2}
                      value={lockReasonInput}
                      onChange={(e) => setLockReasonInput(e.target.value)}
                      placeholder={
                        uiLanguage === "vi"
                          ? "Ghi rõ lý do khóa tài khoản (bắt buộc)..."
                          : "State clear justification for account lock..."
                      }
                      className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] p-2.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-[color:var(--status-danger-border)] focus:outline-none"
                    />

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleLockAccount}
                      disabled={
                        isSubmittingLock || !lockReasonInput.trim()
                      }
                      className="w-full justify-center border-[color:var(--status-danger-border)] text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)] text-xs font-semibold"
                    >
                      <Icon name="warning" size="0.85rem" className="mr-1" />
                      {uiLanguage === "vi"
                        ? "Khóa tài khoản & Thu hồi phiên"
                        : "Lock Account & Revoke Sessions"}
                    </Button>
                  </div>
                )}
              </InspectorSection>

              {/* Section 5: Governance Audit Trail */}
              <InspectorSection
                title={
                  uiLanguage === "vi"
                    ? "Nhật ký kiểm toán tài khoản (Zero-PII)"
                    : "Account Audit Trail (Zero-PII)"
                }
                description={
                  uiLanguage === "vi"
                    ? "Lịch sử các thao tác quản trị, phân quyền và khóa bảo mật trên tài khoản."
                    : "Immutable history of role changes, lock events, and security revocations."
                }
                collapsible
                defaultExpanded={true}
              >
                {selectedUser.auditHistory &&
                selectedUser.auditHistory.length > 0 ? (
                  <div className="space-y-2">
                    {selectedUser.auditHistory.map((item) => (
                      <div
                        key={item.id}
                        className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-base)] p-2 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[var(--text-primary)]">
                            {uiLanguage === "vi"
                              ? item.actionLabelVi
                              : item.actionLabelEn}
                          </span>
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {formatDateSafe(uiLanguage, item.timestamp)}
                          </span>
                        </div>
                        <div className="mt-1 flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
                          <span>
                            {uiLanguage === "vi" ? "Tác nhân: " : "Actor: "}
                            <span className="font-mono text-[10px] text-[var(--text-muted)]">
                              {item.actor}
                            </span>
                          </span>
                        </div>
                        {item.details && (
                          <p className="mt-1 text-[11px] text-[var(--text-muted)] italic">
                            {item.details}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="py-2 text-xs text-[var(--text-muted)] text-center">
                    {uiLanguage === "vi"
                      ? "Chưa có sự kiện kiểm toán nào được ghi nhận."
                      : "No audit events recorded for this user."}
                  </p>
                )}
              </InspectorSection>
            </div>
          )}
        </Inspector>

        {/* Confirmation Action Modal */}
        <Modal
          open={confirmModal.open}
          onClose={() => setConfirmModal((prev) => ({ ...prev, open: false }))}
          title={confirmModal.title}
          size="sm"
        >
          <div className="space-y-4">
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {confirmModal.description}
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setConfirmModal((prev) => ({ ...prev, open: false }))
                }
              >
                {uiLanguage === "vi" ? "Hủy bỏ" : "Cancel"}
              </Button>
              <Button
                variant={
                  confirmModal.variant === "danger" ? "danger" : "primary"
                }
                size="sm"
                onClick={confirmModal.action}
              >
                {confirmModal.confirmLabel}
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AdminShell>
  );
}
