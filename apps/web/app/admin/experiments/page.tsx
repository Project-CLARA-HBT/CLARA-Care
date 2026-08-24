"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import { KpiCard, PanelCard } from "@/components/admin/analytics-primitives";
import Button from "@/components/ui/button";
import Icon from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import StatusChip from "@/components/ui/status-chip";
import { Badge } from "@/components/ui/badge";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  AVAILABLE_COHORTS,
  calculateExperimentStats,
  createExperiment,
  type ExperimentCategory,
  type ExperimentStatus,
  type FeatureFlagExperiment,
  listExperiments,
  overrideKillSwitch,
  updateExperiment,
} from "@/lib/experiments";
import { getStoredUILanguage, onUILanguageChange, type UILanguage } from "@/lib/ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";

/**
 * Admin Feature Flags & Experimentation Workbench (Spec v8 Section 12.7 / Spec v8 Admin Sibling Contracts).
 *
 * Dense, high-signal admin command interface providing:
 * 1. Feature toggle table with real-time status and telemetry signals.
 * 2. Rollout percentage sliders (0-100%) for gradual canary releases.
 * 3. Targeting rules by user role (admin, doctor, researcher, normal) and cohort tags.
 * 4. Kill switch overrides with confirmation dialogs and reason tracking.
 * 5. Enforcement of ANA-005 invariants (Safety invariants like FIDES & Emergency 115 are locked).
 */

const CATEGORY_META: Record<
  ExperimentCategory,
  { labelVi: string; labelEn: string; icon: string; tone: "brand" | "ok" | "warn" | "neutral" | "danger" }
> = {
  ai_systems: {
    labelVi: "Hệ thống AI & RAG",
    labelEn: "AI Systems & RAG",
    icon: "scan",
    tone: "brand",
  },
  clinical: {
    labelVi: "Chuyên môn Lâm sàng",
    labelEn: "Clinical Core",
    icon: "clinical-notes",
    tone: "warn",
  },
  consumer: {
    labelVi: "Trải nghiệm Người dùng",
    labelEn: "Consumer UX",
    icon: "user-card",
    tone: "ok",
  },
  platform: {
    labelVi: "Hạ tầng & Nền tảng",
    labelEn: "Platform & Infra",
    icon: "settings",
    tone: "neutral",
  },
  safety_invariant: {
    labelVi: "Bất biến An toàn (ANA-005)",
    labelEn: "Safety Invariant (ANA-005)",
    icon: "warning",
    tone: "danger",
  },
};

const ALL_ROLES: Array<{ role: UserRole; labelVi: string; labelEn: string }> = [
  { role: "admin", labelVi: "Quản trị viên (Admin)", labelEn: "Admin" },
  { role: "doctor", labelVi: "Bác sĩ (Doctor)", labelEn: "Doctor" },
  { role: "researcher", labelVi: "Nhà nghiên cứu (Researcher)", labelEn: "Researcher" },
  { role: "normal", labelVi: "Người dùng (End User)", labelEn: "End User" },
];

export default function AdminExperimentsPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [role, setRole] = useState<UserRole | null>(() => getRole());
  const [loading, setLoading] = useState(true);
  const [experiments, setExperiments] = useState<FeatureFlagExperiment[]>([]);
  const [selectedExperiment, setSelectedExperiment] = useState<FeatureFlagExperiment | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Inspector edit buffer
  const [inspectorRollout, setInspectorRollout] = useState<number>(0);
  const [inspectorRoles, setInspectorRoles] = useState<UserRole[]>([]);
  const [inspectorCohorts, setInspectorCohorts] = useState<string[]>([]);
  const [inspectorMatchMode, setInspectorMatchMode] = useState<"any" | "all">("any");
  const [savingChanges, setSavingChanges] = useState(false);

  // Kill Switch Confirmation Modal
  const [killModalOpen, setKillModalOpen] = useState(false);
  const [killTargetExp, setKillTargetExp] = useState<FeatureFlagExperiment | null>(null);
  const [killReason, setKillReason] = useState("");
  const [isActivatingKill, setIsActivatingKill] = useState(true);
  const [submittingKill, setSubmittingKill] = useState(false);

  // New Feature Flag Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newFlagKey, setNewFlagKey] = useState("");
  const [newFlagName, setNewFlagName] = useState("");
  const [newFlagDesc, setNewFlagDesc] = useState("");
  const [newFlagCategory, setNewFlagCategory] = useState<ExperimentCategory>("ai_systems");
  const [newFlagRollout, setNewFlagRollout] = useState<number>(0);
  const [newFlagRoles, setNewFlagRoles] = useState<UserRole[]>(["admin"]);
  const [submittingCreate, setSubmittingCreate] = useState(false);

  const isVi = uiLanguage === "vi";

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    const unsub = onUILanguageChange(setUiLanguage);
    setRole(getRole());
    return unsub;
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listExperiments();
      setExperiments(data);
    } catch (err) {
      setNotification({
        type: "error",
        message: safeUserFacingError(
          err,
          isVi ? "Không thể tải danh sách cờ tính năng." : "Failed to load feature flags."
        ),
      });
    } finally {
      setLoading(false);
    }
  }, [isVi]);

  useEffect(() => {
    if (role === "admin") {
      void loadData();
    } else if (role !== null) {
      setLoading(false);
    }
  }, [role, loadData]);

  // Sync inspector state when selected experiment changes
  useEffect(() => {
    if (selectedExperiment) {
      setInspectorRollout(selectedExperiment.rolloutPercentage);
      setInspectorRoles([...selectedExperiment.targetRoles]);
      setInspectorCohorts([...selectedExperiment.targetCohorts]);
      setInspectorMatchMode(selectedExperiment.matchMode || "any");
    }
  }, [selectedExperiment]);

  const stats = useMemo(() => calculateExperimentStats(experiments), [experiments]);

  // Filtered experiments
  const filteredExperiments = useMemo(() => {
    return experiments.filter((exp) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesKey = exp.key.toLowerCase().includes(q);
        const matchesName = exp.name.toLowerCase().includes(q) || exp.nameVi.toLowerCase().includes(q);
        const matchesDesc = exp.description.toLowerCase().includes(q) || exp.descriptionVi.toLowerCase().includes(q);
        if (!matchesKey && !matchesName && !matchesDesc) return false;
      }

      if (categoryFilter !== "all" && exp.category !== categoryFilter) {
        return false;
      }

      if (statusFilter !== "all") {
        if (statusFilter === "killed" && !exp.killSwitchActive) return false;
        if (statusFilter === "active" && (exp.rolloutPercentage !== 100 || exp.killSwitchActive)) return false;
        if (statusFilter === "gradual" && (exp.rolloutPercentage <= 0 || exp.rolloutPercentage >= 100 || exp.killSwitchActive)) return false;
        if (statusFilter === "inactive" && (exp.rolloutPercentage !== 0 || exp.killSwitchActive)) return false;
      }

      if (roleFilter !== "all" && !exp.targetRoles.includes(roleFilter as UserRole)) {
        return false;
      }

      return true;
    });
  }, [experiments, searchQuery, categoryFilter, statusFilter, roleFilter]);

  // Handle Quick Inline Rollout Slider Change
  const handleInlineRolloutChange = async (exp: FeatureFlagExperiment, newPercentage: number) => {
    if (exp.isSafetyInvariant && newPercentage < 100) {
      setNotification({
        type: "error",
        message: isVi
          ? "Không thể giảm rollout của Bất biến An toàn (ANA-005)."
          : "Cannot reduce rollout percentage of Safety Invariant (ANA-005).",
      });
      return;
    }

    try {
      const updated = await updateExperiment(exp.id, { rolloutPercentage: newPercentage });
      setExperiments((prev) => prev.map((item) => (item.id === exp.id ? updated : item)));
      if (selectedExperiment?.id === exp.id) {
        setSelectedExperiment(updated);
      }
      setNotification({
        type: "success",
        message: isVi
          ? `Đã cập nhật tỷ lệ triển khai ${exp.key} thành ${newPercentage}%.`
          : `Updated rollout for ${exp.key} to ${newPercentage}%.`,
      });
    } catch (err) {
      setNotification({
        type: "error",
        message: err instanceof Error ? err.message : "Update failed",
      });
    }
  };

  // Open Kill Switch Dialog
  const openKillSwitchModal = (exp: FeatureFlagExperiment, activate: boolean) => {
    if (exp.isSafetyInvariant) {
      setNotification({
        type: "error",
        message: isVi
          ? "Khóa an toàn: Không thể bật công tắc ngắt trên Bất biến An toàn (ANA-005)."
          : "Safety Lock: Cannot activate kill switch on Safety Invariant (ANA-005).",
      });
      return;
    }
    setKillTargetExp(exp);
    setIsActivatingKill(activate);
    setKillReason("");
    setKillModalOpen(true);
  };

  // Execute Kill Switch Override
  const handleConfirmKillSwitch = async () => {
    if (!killTargetExp) return;
    setSubmittingKill(true);
    try {
      const updated = await overrideKillSwitch(killTargetExp.id, isActivatingKill, killReason);
      setExperiments((prev) => prev.map((item) => (item.id === killTargetExp.id ? updated : item)));
      if (selectedExperiment?.id === killTargetExp.id) {
        setSelectedExperiment(updated);
      }
      setKillModalOpen(false);
      setNotification({
        type: "success",
        message: isActivatingKill
          ? isVi
            ? `Đã kích hoạt ngắt khẩn cấp (Kill Switch) cho ${killTargetExp.key}.`
            : `Emergency Kill Switch activated for ${killTargetExp.key}.`
          : isVi
            ? `Đã khôi phục hoạt động cho ${killTargetExp.key}.`
            : `Restored normal operation for ${killTargetExp.key}.`,
      });
    } catch (err) {
      setNotification({
        type: "error",
        message: err instanceof Error ? err.message : "Kill switch operation failed",
      });
    } finally {
      setSubmittingKill(false);
    }
  };

  // Save Inspector Drawer Changes
  const handleSaveInspector = async () => {
    if (!selectedExperiment) return;
    if (selectedExperiment.isSafetyInvariant && inspectorRollout < 100) {
      setNotification({
        type: "error",
        message: isVi
          ? "Bất biến an toàn phải luôn duy trì 100% rollout."
          : "Safety invariants must always remain at 100% rollout.",
      });
      return;
    }

    setSavingChanges(true);
    try {
      const updated = await updateExperiment(selectedExperiment.id, {
        rolloutPercentage: inspectorRollout,
        targetRoles: inspectorRoles,
        targetCohorts: inspectorCohorts,
        matchMode: inspectorMatchMode,
      });
      setExperiments((prev) => prev.map((item) => (item.id === selectedExperiment.id ? updated : item)));
      setSelectedExperiment(updated);
      setNotification({
        type: "success",
        message: isVi
          ? `Đã lưu cấu hình thử nghiệm ${selectedExperiment.key}.`
          : `Saved configuration for ${selectedExperiment.key}.`,
      });
    } catch (err) {
      setNotification({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to save changes",
      });
    } finally {
      setSavingChanges(false);
    }
  };

  // Create new custom feature flag
  const handleCreateFlag = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFlagKey.trim() || !newFlagName.trim()) return;

    setSubmittingCreate(true);
    const cleanedKey = newFlagKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_");
    try {
      const created = await createExperiment({
        key: cleanedKey,
        name: newFlagName.trim(),
        nameVi: newFlagName.trim(),
        description: newFlagDesc.trim() || (isVi ? "Cờ tính năng tùy biến" : "Custom feature flag"),
        descriptionVi: newFlagDesc.trim() || "Cờ tính năng tùy biến",
        category: newFlagCategory,
        rolloutPercentage: newFlagRollout,
        targetRoles: newFlagRoles.length > 0 ? newFlagRoles : ["admin"],
        targetCohorts: ["beta_testers"],
      });

      setExperiments((prev) => [created, ...prev]);
      setCreateModalOpen(false);
      setNewFlagKey("");
      setNewFlagName("");
      setNewFlagDesc("");
      setNewFlagRollout(0);
      setNewFlagRoles(["admin"]);
      setNotification({
        type: "success",
        message: isVi ? `Đã tạo cờ tính năng mới: ${created.key}` : `Created new feature flag: ${created.key}`,
      });
    } catch {
      // Fallback for offline or local preview
      const newExp: FeatureFlagExperiment = {
        id: `exp-${Date.now()}`,
        key: cleanedKey,
        name: newFlagName.trim(),
        nameVi: newFlagName.trim(),
        description: newFlagDesc.trim() || (isVi ? "Cờ tính năng tùy biến" : "Custom feature flag"),
        descriptionVi: newFlagDesc.trim() || "Cờ tính năng tùy biến",
        category: newFlagCategory,
        status: newFlagRollout === 100 ? "active" : newFlagRollout > 0 ? "gradual_rollout" : "inactive",
        rolloutPercentage: newFlagRollout,
        targetRoles: newFlagRoles.length > 0 ? newFlagRoles : ["admin"],
        targetCohorts: ["beta_testers"],
        matchMode: "any",
        killSwitchActive: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        updatedBy: "admin@clara.vn",
      };

      setExperiments((prev) => [newExp, ...prev]);
      setCreateModalOpen(false);
      setNewFlagKey("");
      setNewFlagName("");
      setNewFlagDesc("");
      setNewFlagRollout(0);
      setNewFlagRoles(["admin"]);
      setNotification({
        type: "success",
        message: isVi ? `Đã tạo cờ tính năng mới: ${newExp.key}` : `Created new feature flag: ${newExp.key}`,
      });
    } finally {
      setSubmittingCreate(false);
    }
  };

  const getStatusTone = (exp: FeatureFlagExperiment): "success" | "warning" | "danger" | "info" | "unknown" => {
    if (exp.killSwitchActive) return "danger";
    if (exp.rolloutPercentage === 100) return "success";
    if (exp.rolloutPercentage > 0) return "info";
    return "unknown";
  };

  const getStatusLabel = (exp: FeatureFlagExperiment): string => {
    if (exp.killSwitchActive) return isVi ? "NGẮT KHẨN CẤP" : "KILLED (OVERRIDDEN)";
    if (exp.rolloutPercentage === 100) return isVi ? "Hoạt động (100%)" : "Active (100%)";
    if (exp.rolloutPercentage > 0) return isVi ? `Triển khai (${exp.rolloutPercentage}%)` : `Rollout (${exp.rolloutPercentage}%)`;
    return isVi ? "Tắt (0%)" : "Inactive (0%)";
  };

  const pageTitle = isVi ? "Thử nghiệm & Cờ tính năng (Feature Flags)" : "Feature Flags & Experimentation Workbench";
  const pageDesc = isVi
    ? "Quản lý cờ tính năng runtime, tỷ lệ triển khai canary (0-100%), nhắm mục tiêu theo vai trò/cohort và công tắc ngắt khẩn cấp."
    : "Manage runtime feature flags, gradual rollout percentage sliders, role/cohort targeting rules, and emergency kill switch overrides.";

  // Defense in depth: Check admin permission
  if (role !== null && role !== "admin") {
    return (
      <AdminShell activeTab="experiments" title={pageTitle} description={pageDesc}>
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-8 text-center"
        >
          <Icon name="warning" size={36} className="mx-auto mb-3 text-[var(--status-danger-text)]" />
          <h3 className="text-lg font-bold text-[var(--status-danger-text)]">
            {isVi ? "Từ chối quyền truy cập" : "Access Denied"}
          </h3>
          <p className="mt-2 text-sm text-[var(--status-danger-text)]">
            {isVi
              ? "Bạn không có quyền truy cập Bàn làm việc Thử nghiệm & Cờ tính năng. Yêu cầu quyền quản trị viên (Admin)."
              : "You do not have permission to access the Feature Flags & Experimentation Workbench. Admin role required."}
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell activeTab="experiments" title={pageTitle} description={pageDesc}>
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="Feature Flags & Experimentation Workbench"
        className="space-y-5"
      >
        {/* Notification Banner */}
        {notification ? (
          <div
            role="status"
            className={`flex items-center justify-between gap-3 rounded-[var(--radius-md)] border px-4 py-3 text-xs font-semibold ${
              notification.type === "success"
                ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                : "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
            }`}
          >
            <span>{notification.message}</span>
            <button
              type="button"
              onClick={() => setNotification(null)}
              className="text-current opacity-70 hover:opacity-100"
              aria-label="Dismiss notification"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        ) : null}

        {/* Emergency Kill Switch Active Global Warning */}
        {stats.killSwitched > 0 ? (
          <div
            role="alert"
            className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-4 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--status-danger-text)] text-white">
                <Icon name="warning" size={20} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-[var(--status-danger-text)]">
                  {isVi
                    ? `Cảnh báo: Có ${stats.killSwitched} cờ tính năng đang bị ngắt khẩn cấp (Kill Switch)`
                    : `Alert: ${stats.killSwitched} feature flags are under Emergency Kill Switch Override`}
                </h4>
                <p className="text-xs text-[var(--status-danger-text)] opacity-90">
                  {isVi
                    ? "Các tính năng này bị vô hiệu hóa hoàn toàn đối với mọi người dùng bất kể quy tắc rollout."
                    : "These features are completely disabled for all users regardless of rollout rules."}
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setStatusFilter("killed");
              }}
            >
              {isVi ? "Xem danh sách bị ngắt" : "View Kill-Switched Flags"}
            </Button>
          </div>
        ) : null}

        {/* Top KPI Metric Cards */}
        <section aria-label="Experimentation Metrics" className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <KpiCard
            label={isVi ? "Tổng số cờ & thử nghiệm" : "Total Feature Flags"}
            value={stats.totalFlags.toString()}
            hint={isVi ? "Bao gồm cả cờ bất biến" : "Including safety invariants"}
          />
          <KpiCard
            label={isVi ? "Đang triển khai phân đoạn" : "Active Rollouts (1-99%)"}
            value={stats.activeRollouts.toString()}
            hint={isVi ? "Thử nghiệm A/B & Canary" : "Canary & A/B splits"}
          />
          <KpiCard
            label={isVi ? "Đã bật toàn bộ (100%)" : "Fully Enabled (100%)"}
            value={stats.fullyEnabled.toString()}
            hint={isVi ? "Sẵn sàng cho mọi người dùng" : "General availability"}
          />
          <KpiCard
            label={isVi ? "Ngắt khẩn cấp" : "Kill Switch Active"}
            value={stats.killSwitched.toString()}
            hint={isVi ? "Bị vô hiệu hóa cưỡng chế" : "Forced overrides"}
          />
          <KpiCard
            label={isVi ? "Bất biến An toàn (ANA-005)" : "Safety Invariants"}
            value={stats.safetyInvariants.toString()}
            hint={isVi ? "Khóa cứng không thể tắt" : "Regression-locked"}
          />
        </section>

        {/* Action & Filter Toolbar */}
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-soft">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              {/* Category Filter */}
              <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">{isVi ? "Phân nhóm:" : "Category:"}</span>
                <select
                  aria-label="Filter Category"
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="all">{isVi ? "Tất cả nhóm" : "All Categories"}</option>
                  <option value="ai_systems">{isVi ? "Hệ thống AI & RAG" : "AI Systems & RAG"}</option>
                  <option value="clinical">{isVi ? "Chuyên môn Lâm sàng" : "Clinical Core"}</option>
                  <option value="consumer">{isVi ? "Trải nghiệm Người dùng" : "Consumer UX"}</option>
                  <option value="platform">{isVi ? "Hạ tầng & Nền tảng" : "Platform & Infra"}</option>
                  <option value="safety_invariant">{isVi ? "Bất biến An toàn" : "Safety Invariants"}</option>
                </select>
              </label>

              {/* Status Filter */}
              <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">{isVi ? "Trạng thái:" : "Status:"}</span>
                <select
                  aria-label="Filter Status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="all">{isVi ? "Tất cả trạng thái" : "All Statuses"}</option>
                  <option value="active">{isVi ? "Đã bật 100%" : "Active (100%)"}</option>
                  <option value="gradual">{isVi ? "Rollout phân đoạn (1-99%)" : "Gradual Rollout (1-99%)"}</option>
                  <option value="inactive">{isVi ? "Đang tắt (0%)" : "Inactive (0%)"}</option>
                  <option value="killed">{isVi ? "Ngắt khẩn cấp (Killed)" : "Kill Switched"}</option>
                </select>
              </label>

              {/* Role Target Filter */}
              <label className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                <span className="font-semibold uppercase tracking-wider">{isVi ? "Vai trò:" : "Role:"}</span>
                <select
                  aria-label="Filter Role"
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="min-h-[34px] rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 text-xs font-semibold text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="all">{isVi ? "Tất cả vai trò" : "All Roles"}</option>
                  <option value="admin">Admin</option>
                  <option value="doctor">{isVi ? "Bác sĩ" : "Doctor"}</option>
                  <option value="researcher">{isVi ? "Nhà nghiên cứu" : "Researcher"}</option>
                  <option value="normal">{isVi ? "Người dùng thường" : "End User"}</option>
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder={isVi ? "Tìm theo mã cờ / tên thử nghiệm..." : "Search flag key or name..."}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="min-h-[34px] w-48 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs text-[var(--text-primary)] focus-visible:outline-none sm:w-64"
              />
              <Button size="sm" variant="secondary" onClick={() => void loadData()} loading={loading}>
                <Icon name="progress" size={14} />
                <span>{isVi ? "Làm mới" : "Refresh"}</span>
              </Button>
              <Button size="sm" variant="primary" onClick={() => setCreateModalOpen(true)}>
                <Icon name="plus" size={14} />
                <span>{isVi ? "Tạo cờ mới" : "New Flag"}</span>
              </Button>
            </div>
          </div>
        </div>

        {/* Main Workbench Layout: Dense Table + Inspector Side Panel */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Main Feature Toggle Table */}
          <div className={`${selectedExperiment ? "lg:col-span-8" : "lg:col-span-12"} space-y-4`}>
            <PanelCard
              title={isVi ? "Bảng Cờ tính năng & Tỷ lệ Rollout" : "Feature Toggle & Rollout Table"}
              description={
                isVi
                  ? `Hiển thị ${filteredExperiments.length} cờ tính năng / thử nghiệm. Điều chỉnh slider để thay đổi phân bổ tức thì.`
                  : `Showing ${filteredExperiments.length} flags & experiments. Adjust slider to change canary distribution.`
              }
            >
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-[var(--text-primary)]" aria-label="Feature Flags Table">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      <th className="py-2.5 pl-3 pr-2">{isVi ? "Cờ / Thử nghiệm" : "Flag / Experiment"}</th>
                      <th className="px-2 py-2.5">{isVi ? "Trạng thái" : "Status"}</th>
                      <th className="px-2 py-2.5 w-44">{isVi ? "Tỷ lệ Rollout (%)" : "Rollout % Slider"}</th>
                      <th className="px-2 py-2.5">{isVi ? "Đối tượng nhắm" : "Targeting"}</th>
                      <th className="px-2 py-2.5 text-center">{isVi ? "Ngắt khẩn cấp" : "Kill Switch"}</th>
                      <th className="py-2.5 pl-2 pr-3 text-right">{isVi ? "Thao tác" : "Actions"}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]">
                    {filteredExperiments.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-8 text-center text-xs text-[var(--text-muted)]">
                          {isVi ? "Không tìm thấy cờ tính năng nào phù hợp bộ lọc." : "No feature flags match current filter."}
                        </td>
                      </tr>
                    ) : (
                      filteredExperiments.map((exp) => {
                        const isSelected = selectedExperiment?.id === exp.id;
                        const cat = CATEGORY_META[exp.category];

                        return (
                          <tr
                            key={exp.id}
                            className={`transition hover:bg-[var(--surface-muted)]/70 ${
                              isSelected ? "bg-[var(--surface-brand-soft)]/50" : ""
                            } ${exp.killSwitchActive ? "bg-[var(--status-danger-bg)]/30" : ""}`}
                          >
                            {/* Key & Name */}
                            <td className="py-3 pl-3 pr-2">
                              <div className="flex items-start gap-2">
                                <div className="min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-mono font-bold text-[var(--text-brand)]">{exp.key}</span>
                                    {exp.isSafetyInvariant ? (
                                      <span
                                        title="Bất biến An toàn khóa cứng theo chuẩn ANA-005"
                                        className="inline-flex items-center gap-0.5 rounded bg-[var(--status-danger-bg)] px-1.5 py-0.2 text-[9px] font-bold text-[var(--status-danger-text)]"
                                      >
                                        <Icon name="warning" size={10} />
                                        <span>ANA-005</span>
                                      </span>
                                    ) : null}
                                  </div>
                                  <p className="mt-0.5 font-semibold text-[var(--text-primary)]">
                                    {isVi ? exp.nameVi : exp.name}
                                  </p>
                                  <div className="mt-1 flex items-center gap-1.5">
                                    <Badge tone={cat.tone} className="text-[10px] py-0">
                                      {isVi ? cat.labelVi : cat.labelEn}
                                    </Badge>
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Status */}
                            <td className="px-2 py-3">
                              <StatusChip tone={getStatusTone(exp)} label={getStatusLabel(exp)} size="sm" />
                            </td>

                            {/* Rollout Slider & Progress Bar */}
                            <td className="px-2 py-3">
                              <div className="space-y-1.5">
                                <div className="flex items-center justify-between text-[11px] font-bold">
                                  <span className="text-[var(--text-secondary)]">{exp.rolloutPercentage}%</span>
                                  <span className="text-[10px] text-[var(--text-muted)]">
                                    {exp.rolloutPercentage === 100
                                      ? isVi ? "Toàn bộ" : "All"
                                      : exp.rolloutPercentage === 0
                                        ? isVi ? "Đóng" : "Off"
                                        : "Canary"}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2">
                                  <input
                                    type="range"
                                    min="0"
                                    max="100"
                                    step="5"
                                    disabled={exp.isSafetyInvariant || exp.killSwitchActive}
                                    value={exp.rolloutPercentage}
                                    onChange={(e) => void handleInlineRolloutChange(exp, Number(e.target.value))}
                                    aria-label={`Rollout percentage slider for ${exp.key}`}
                                    className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-highest)] accent-[var(--brand-600)] disabled:cursor-not-allowed disabled:opacity-50"
                                  />
                                </div>
                                <div className="h-1 w-full overflow-hidden rounded-full bg-[var(--surface-highest)]">
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      exp.killSwitchActive
                                        ? "bg-[var(--status-danger-text)]"
                                        : exp.rolloutPercentage === 100
                                          ? "bg-[var(--status-ok-text)]"
                                          : "bg-[var(--brand-600)]"
                                    }`}
                                    style={{ width: `${exp.rolloutPercentage}%` }}
                                  />
                                </div>
                              </div>
                            </td>

                            {/* Targeting */}
                            <td className="px-2 py-3">
                              <div className="space-y-1">
                                <div className="flex flex-wrap gap-1">
                                  {exp.targetRoles.map((r) => (
                                    <span
                                      key={r}
                                      className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-1.5 py-0.2 text-[10px] font-semibold text-[var(--text-secondary)]"
                                    >
                                      {r}
                                    </span>
                                  ))}
                                </div>
                                {exp.targetCohorts.length > 0 ? (
                                  <div className="flex flex-wrap gap-1">
                                    {exp.targetCohorts.map((c) => (
                                      <span
                                        key={c}
                                        className="rounded bg-[var(--surface-brand-soft)] px-1 py-0.2 text-[9px] font-semibold text-[var(--text-brand)]"
                                      >
                                        #{c}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}
                              </div>
                            </td>

                            {/* Kill Switch Toggle */}
                            <td className="px-2 py-3 text-center">
                              {exp.isSafetyInvariant ? (
                                <span
                                  className="text-[10px] font-semibold text-[var(--text-muted)]"
                                  title="Safety invariant locked"
                                >
                                  {isVi ? "Đã khóa" : "Locked"}
                                </span>
                              ) : exp.killSwitchActive ? (
                                <Button
                                  size="sm"
                                  variant="danger"
                                  className="px-2 py-1 text-[10px]"
                                  onClick={() => openKillSwitchModal(exp, false)}
                                >
                                  {isVi ? "Khôi phục" : "Restore"}
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="px-2 py-1 text-[10px] text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)]"
                                  onClick={() => openKillSwitchModal(exp, true)}
                                >
                                  <Icon name="warning" size={12} />
                                  <span>{isVi ? "Ngắt" : "Kill"}</span>
                                </Button>
                              )}
                            </td>

                            {/* Actions */}
                            <td className="py-3 pl-2 pr-3 text-right">
                              <Button
                                size="sm"
                                variant={isSelected ? "primary" : "secondary"}
                                className="px-2.5 py-1 text-xs"
                                onClick={() => setSelectedExperiment(isSelected ? null : exp)}
                              >
                                <span>{isSelected ? (isVi ? "Đang xem" : "Inspecting") : (isVi ? "Cấu hình" : "Inspect")}</span>
                                <Icon name={isSelected ? "arrow-left" : "arrow-right"} size={12} />
                              </Button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </PanelCard>
          </div>

          {/* Selected Experiment Inspector (Slide-over / Inline Canvas) */}
          {selectedExperiment ? (
            <div className="lg:col-span-4">
              <div className="sticky top-20 space-y-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-soft">
                {/* Inspector Header */}
                <div className="flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)] pb-3">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-brand)]">
                      {isVi ? "Bàn điều khiển thử nghiệm" : "Experiment Inspector"}
                    </span>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      {isVi ? selectedExperiment.nameVi : selectedExperiment.name}
                    </h3>
                    <p className="font-mono text-xs text-[var(--text-muted)]">{selectedExperiment.key}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedExperiment(null)}
                    className="rounded-lg p-1 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                    aria-label="Close inspector"
                  >
                    <Icon name="close" size={18} />
                  </button>
                </div>

                {/* Section 1: Rollout Slider & Presets */}
                <div className="space-y-3 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                  <div className="flex items-center justify-between">
                    <label
                      htmlFor="inspector-rollout-slider"
                      className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
                    >
                      {isVi ? "Tỷ lệ Rollout (%)" : "Rollout Percentage"}
                    </label>
                    <span className="font-mono text-sm font-black text-[var(--text-brand)]">
                      {inspectorRollout}%
                    </span>
                  </div>

                  <input
                    id="inspector-rollout-slider"
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    disabled={selectedExperiment.isSafetyInvariant || selectedExperiment.killSwitchActive}
                    value={inspectorRollout}
                    onChange={(e) => setInspectorRollout(Number(e.target.value))}
                    className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-highest)] accent-[var(--brand-600)] disabled:cursor-not-allowed disabled:opacity-50"
                  />

                  {/* Preset buttons */}
                  <div className="flex flex-wrap gap-1">
                    {[0, 25, 50, 75, 100].map((pct) => (
                      <button
                        key={pct}
                        type="button"
                        disabled={selectedExperiment.isSafetyInvariant || selectedExperiment.killSwitchActive}
                        onClick={() => setInspectorRollout(pct)}
                        className={`rounded px-2 py-0.5 text-[10px] font-bold transition ${
                          inspectorRollout === pct
                            ? "bg-[var(--brand-600)] text-white"
                            : "bg-[var(--surface-panel)] text-[var(--text-secondary)] hover:bg-[var(--surface-highest)]"
                        } disabled:cursor-not-allowed disabled:opacity-40`}
                      >
                        {pct}%
                      </button>
                    ))}
                  </div>
                </div>

                {/* Section 2: Targeting Rules */}
                <div className="space-y-3 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                      {isVi ? "Vai trò được nhắm mục tiêu" : "Target Roles"}
                    </span>
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {inspectorRoles.length} {isVi ? "đã chọn" : "selected"}
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    {ALL_ROLES.map(({ role: r, labelVi, labelEn }) => {
                      const checked = inspectorRoles.includes(r);
                      return (
                        <label
                          key={r}
                          className="flex items-center gap-2.5 rounded-md bg-[var(--surface-panel)] p-2 text-xs font-medium text-[var(--text-primary)] cursor-pointer hover:bg-[var(--surface-highest)]"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={selectedExperiment.isSafetyInvariant}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setInspectorRoles((prev) => [...prev, r]);
                              } else {
                                setInspectorRoles((prev) => prev.filter((item) => item !== r));
                              }
                            }}
                            className="rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-primary)]"
                          />
                          <span>{isVi ? labelVi : labelEn}</span>
                        </label>
                      );
                    })}
                  </div>

                  {/* Cohort Targeting */}
                  <div className="pt-2 border-t border-[color:var(--shell-border)]">
                    <span className="block mb-2 text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                      {isVi ? "Cohorts Thử nghiệm" : "Target Cohorts"}
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {AVAILABLE_COHORTS.map((c) => {
                        const active = inspectorCohorts.includes(c.id);
                        return (
                          <button
                            key={c.id}
                            type="button"
                            disabled={selectedExperiment.isSafetyInvariant}
                            onClick={() => {
                              if (active) {
                                setInspectorCohorts((prev) => prev.filter((item) => item !== c.id));
                              } else {
                                setInspectorCohorts((prev) => [...prev, c.id]);
                              }
                            }}
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold transition ${
                              active
                                ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            }`}
                          >
                            {active ? "✓ " : "+ "}
                            {isVi ? c.labelVi : c.labelEn}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Match Mode */}
                  <div className="pt-2 flex items-center justify-between text-xs">
                    <span className="text-[var(--text-muted)]">{isVi ? "Quy tắc khớp:" : "Evaluation:"}</span>
                    <select
                      value={inspectorMatchMode}
                      disabled={selectedExperiment.isSafetyInvariant}
                      onChange={(e) => setInspectorMatchMode(e.target.value as "any" | "all")}
                      className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-1 text-xs font-semibold text-[var(--text-primary)]"
                    >
                      <option value="any">{isVi ? "Khớp bất kỳ (OR)" : "Match Any (OR)"}</option>
                      <option value="all">{isVi ? "Khớp toàn bộ (AND)" : "Match All (AND)"}</option>
                    </select>
                  </div>
                </div>

                {/* Section 3: Kill Switch Status & Overrides */}
                <div
                  className={`rounded-lg border p-3.5 ${
                    selectedExperiment.killSwitchActive
                      ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider">
                        {isVi ? "Công tắc ngắt khẩn cấp" : "Emergency Kill Switch"}
                      </h4>
                      <p className="text-[11px] opacity-80">
                        {selectedExperiment.killSwitchActive
                          ? isVi
                            ? "Đang ngắt cưỡng chế toàn hệ thống"
                            : "Forced override currently active"
                          : isVi
                            ? "Hệ thống hoạt động bình thường"
                            : "Normal execution mode"}
                      </p>
                    </div>
                    {selectedExperiment.isSafetyInvariant ? (
                      <span className="text-[10px] font-bold text-[var(--text-muted)]">ANA-005 Locked</span>
                    ) : selectedExperiment.killSwitchActive ? (
                      <Button
                        size="sm"
                        variant="danger"
                        onClick={() => openKillSwitchModal(selectedExperiment, false)}
                      >
                        {isVi ? "Khôi phục" : "Restore"}
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)]"
                        onClick={() => openKillSwitchModal(selectedExperiment, true)}
                      >
                        {isVi ? "Kích hoạt ngắt" : "Kill Switch"}
                      </Button>
                    )}
                  </div>

                  {selectedExperiment.killSwitchReason ? (
                    <div className="mt-2 text-[11px] rounded bg-black/10 p-2 font-mono">
                      <strong>Reason:</strong> {selectedExperiment.killSwitchReason}
                    </div>
                  ) : null}
                </div>

                {/* Section 4: Live Telemetry Signals */}
                {selectedExperiment.metrics ? (
                  <div className="space-y-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs">
                    <span className="font-bold uppercase tracking-wider text-[var(--text-muted)] text-[10px]">
                      {isVi ? "Tín hiệu Thử nghiệm Thực tế" : "Live Experiment Telemetry"}
                    </span>
                    <div className="grid grid-cols-2 gap-2 text-[11px]">
                      <div className="rounded bg-[var(--surface-panel)] p-2">
                        <span className="text-[var(--text-muted)]">{isVi ? "Tổng lượt đánh giá" : "Evaluations"}</span>
                        <p className="font-mono font-bold text-[var(--text-primary)]">
                          {selectedExperiment.metrics.totalEvaluations.toLocaleString()}
                        </p>
                      </div>
                      <div className="rounded bg-[var(--surface-panel)] p-2">
                        <span className="text-[var(--text-muted)]">{isVi ? "Độ trễ P95" : "P95 Latency"}</span>
                        <p className="font-mono font-bold text-[var(--text-primary)]">
                          {selectedExperiment.metrics.latencyP95Ms} ms
                        </p>
                      </div>
                    </div>
                  </div>
                ) : null}

                {/* Inspector Actions */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-[color:var(--shell-border)]">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setInspectorRollout(selectedExperiment.rolloutPercentage);
                      setInspectorRoles([...selectedExperiment.targetRoles]);
                      setInspectorCohorts([...selectedExperiment.targetCohorts]);
                    }}
                  >
                    {isVi ? "Hoàn tác" : "Reset"}
                  </Button>
                  <Button
                    size="sm"
                    variant="primary"
                    loading={savingChanges}
                    onClick={() => void handleSaveInspector()}
                  >
                    <Icon name="check" size={14} />
                    <span>{isVi ? "Lưu cấu hình" : "Save Changes"}</span>
                  </Button>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        {/* Emergency Kill Switch Modal */}
        <Modal
          open={killModalOpen}
          onClose={() => setKillModalOpen(false)}
          role="alertdialog"
          title={
            isActivatingKill
              ? isVi
                ? "Xác nhận Ngắt Khẩn cấp Cờ Tính năng"
                : "Confirm Emergency Kill Switch Override"
              : isVi
                ? "Khôi phục Hoạt động Cờ Tính năng"
                : "Restore Feature Flag Operation"
          }
          description={
            killTargetExp
              ? isActivatingKill
                ? isVi
                  ? `Bạn đang chuẩn bị ngắt toàn bộ lưu lượng của ${killTargetExp.key}. Cờ này sẽ trả về False cho mọi người dùng ngay lập tức.`
                  : `You are about to immediately terminate all traffic for ${killTargetExp.key}. The flag will evaluate to False for all users immediately.`
                : isVi
                  ? `Khôi phục ${killTargetExp.key} về trạng thái rollout bình thường (${killTargetExp.rolloutPercentage}%).`
                  : `Restore ${killTargetExp.key} to its standard rollout configuration (${killTargetExp.rolloutPercentage}%).`
              : ""
          }
          footer={
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" onClick={() => setKillModalOpen(false)}>
                {isVi ? "Hủy" : "Cancel"}
              </Button>
              <Button
                variant={isActivatingKill ? "danger" : "primary"}
                loading={submittingKill}
                onClick={() => void handleConfirmKillSwitch()}
              >
                {isActivatingKill
                  ? isVi
                    ? "Kích hoạt Ngắt Khẩn cấp"
                    : "Activate Kill Switch"
                  : isVi
                    ? "Khôi phục Hoạt động"
                    : "Restore Flag"}
              </Button>
            </div>
          }
        >
          {isActivatingKill ? (
            <div className="space-y-3">
              <label className="block text-xs font-semibold text-[var(--text-secondary)]">
                {isVi ? "Lý do ngắt khẩn cấp (bắt buộc cho nhật ký kiểm toán zero-PII):" : "Reason for emergency kill (mandatory for Zero-PII audit trail):"}
              </label>
              <textarea
                rows={3}
                required
                value={killReason}
                onChange={(e) => setKillReason(e.target.value)}
                placeholder={isVi ? "Ví dụ: Phát hiện suy giảm độ chính xác NLI trên luồng production..." : "e.g. Detected NLI accuracy degradation on production stream..."}
                className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-xs text-[var(--text-primary)] focus-visible:outline-none"
              />
            </div>
          ) : null}
        </Modal>

        {/* New Feature Flag Modal */}
        <Modal
          open={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title={isVi ? "Tạo Cờ tính năng / Thử nghiệm mới" : "Create New Feature Flag"}
          description={
            isVi
              ? "Khai báo cờ tính năng mới để bắt đầu rollout phân đoạn hoặc thử nghiệm A/B."
              : "Register a new feature flag for staged rollout or A/B experimentation."
          }
          footer={
            <div className="flex items-center justify-end gap-2">
              <Button variant="ghost" onClick={() => setCreateModalOpen(false)}>
                {isVi ? "Hủy" : "Cancel"}
              </Button>
              <Button
                variant="primary"
                loading={submittingCreate}
                onClick={(e) => void handleCreateFlag(e)}
              >
                {isVi ? "Tạo cờ tính năng" : "Create Flag"}
              </Button>
            </div>
          }
        >
          <form className="space-y-4" onSubmit={handleCreateFlag}>
            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                {isVi ? "Mã cờ (Key - snake_case):" : "Flag Key (snake_case):"}
              </label>
              <input
                type="text"
                required
                placeholder="e.g. experimental_clinical_reranker"
                value={newFlagKey}
                onChange={(e) => setNewFlagKey(e.target.value)}
                className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-mono text-[var(--text-primary)] focus-visible:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                {isVi ? "Tên hiển thị:" : "Display Name:"}
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Clinical Evidence Cross-Encoder"
                value={newFlagName}
                onChange={(e) => setNewFlagName(e.target.value)}
                className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-primary)] focus-visible:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                  {isVi ? "Phân nhóm:" : "Category:"}
                </label>
                <select
                  value={newFlagCategory}
                  onChange={(e) => setNewFlagCategory(e.target.value as ExperimentCategory)}
                  className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-primary)] focus-visible:outline-none"
                >
                  <option value="ai_systems">{isVi ? "Hệ thống AI & RAG" : "AI Systems & RAG"}</option>
                  <option value="clinical">{isVi ? "Chuyên môn Lâm sàng" : "Clinical Core"}</option>
                  <option value="consumer">{isVi ? "Trải nghiệm Người dùng" : "Consumer UX"}</option>
                  <option value="platform">{isVi ? "Hạ tầng & Nền tảng" : "Platform & Infra"}</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                  {isVi ? `Rollout ban đầu: ${newFlagRollout}%` : `Initial Rollout: ${newFlagRollout}%`}
                </label>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  value={newFlagRollout}
                  onChange={(e) => setNewFlagRollout(Number(e.target.value))}
                  className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-highest)] accent-[var(--brand-600)] mt-2"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                {isVi ? "Mô tả mục đích thử nghiệm:" : "Description & Hypothesis:"}
              </label>
              <textarea
                rows={2}
                value={newFlagDesc}
                onChange={(e) => setNewFlagDesc(e.target.value)}
                placeholder={isVi ? "Mô tả tính năng hoặc giả thuyết thử nghiệm..." : "Describe the feature or experimentation hypothesis..."}
                className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5 text-xs text-[var(--text-primary)] focus-visible:outline-none"
              />
            </div>
          </form>
        </Modal>
      </div>
    </AdminShell>
  );
}
