"use client";

import { useEffect, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import ClinicalAnalyticsPanel from "@/components/admin/clinical-analytics-panel";
import { getStoredUILanguage, onUILanguageChange, type UILanguage } from "@/lib/ui-language";
import { getRole, type UserRole } from "@/lib/auth-store";
import Icon from "@/components/ui/icon";

/**
 * Clinical Analytics Drill-down Page (Spec v8 Section 12.4, Spec v5 Section 6.64).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Clinical Analytics Drill-down
 *
 * Command surface delivering:
 * 1. FIDES verdict breakdown (including blocked CRITICAL claims)
 * 2. DDI severity distribution (low, medium, high, critical)
 * 3. Top blocked hazardous drug interaction pairs with clinical mechanisms & evidence anchors
 * 4. Processing tier latency percentiles (p50 / p90 / p99) & router confidence buckets
 * 5. Interactive slide-over inspector for technical safety auditing
 *
 * Adopts AdminCommandStrip with activeTab="clinical-analytics".
 * Enforces server-side RBAC defense-in-depth and Zero-PII invariants.
 */

export default function AdminClinicalAnalyticsPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>(() => getStoredUILanguage());
  const [role, setRole] = useState<UserRole | null>(() => getRole());

  const isVi = uiLanguage === "vi";

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    const unsub = onUILanguageChange(setUiLanguage);
    setRole(getRole());
    return unsub;
  }, []);

  const pageTitle = isVi
    ? "Phân tích lâm sàng"
    : "Clinical Analytics Drill-down";
  const pageDescription = isVi
    ? "Phân bố phán quyết FIDES, mức độ tương tác thuốc (DDI), các cặp thuốc nguy hiểm hàng đầu và độ trễ theo tier cho khoảng ngày đã chọn. Tách biệt với bảng tổng hợp scribe."
    : "FIDES verdict distribution, DDI severity breakdown, top hazardous drug pairs, and per-tier latency percentiles.";

  // Defense-in-depth: Non-admin role gating
  if (role !== null && role !== "admin") {
    return (
      <AdminShell activeTab="clinical-analytics" title={pageTitle} description={pageDescription}>
        <div
          role="alert"
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-8 text-center text-[var(--status-danger-text)] shadow-soft"
        >
          <Icon name="warning" size={36} className="mx-auto mb-3 text-[var(--status-danger-text)]" />
          <h2 className="text-lg font-bold">
            {isVi ? "Từ chối quyền truy cập (403)" : "Access Denied (403)"}
          </h2>
          <p className="mt-2 text-sm opacity-90 max-w-md mx-auto">
            {isVi
              ? "Bạn không có quyền truy cập Bảng Phân tích Lâm sàng. Chỉ tài khoản Quản trị viên (Admin) mới được phép xem."
              : "You do not have permission to view the Clinical Analytics Dashboard. Administrator role required."}
          </p>
        </div>
      </AdminShell>
    );
  }

  return (
    <AdminShell
      activeTab="clinical-analytics"
      title={pageTitle}
      description={pageDescription}
    >
      <div
        data-shell-mode="ADMIN_COMMAND"
        data-layout-archetype="Clinical Analytics Drill-down"
        data-density="DENSE"
        className="space-y-6"
      >
        <ClinicalAnalyticsPanel />
      </div>
    </AdminShell>
  );
}
