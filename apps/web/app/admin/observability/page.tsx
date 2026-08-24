"use client";

import { useEffect, useState } from "react";
import AdminObservabilityPanel from "@/components/admin/admin-observability-panel";
import AdminCommandStrip from "@/components/admin/admin-command-strip";
import CommandCenterLayout from "@/components/page/command-center-layout";
import { getRole, type UserRole } from "@/lib/auth-store";
import { useUILanguage } from "@/lib/use-ui-language";
import Icon from "@/components/ui/icon";

/**
 * Admin System Observability Page (Spec v8 Section 12.3 & 12.4).
 *
 * Adopts AdminCommandStrip with activeTab="observability".
 * Surfaces real-time service health cards (API, ML, DB, Redis, OCR, ASR),
 * latency percentiles matrix (p50/p90/p99), signal matrix, and service
 * diagnostic inspector drawer.
 *
 * Enforces Zero-PII invariants and RBAC defense-in-depth.
 */
export default function AdminObservabilityPage() {
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const language = useUILanguage();
  const isVi = language !== "en";

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  const isAuthorized = role === "admin" || role === "doctor";

  if (role !== null && !isAuthorized) {
    return (
      <CommandCenterLayout
        workspace="admin"
        commandStrip={<AdminCommandStrip activeTab="observability" />}
        maxWidth="dense"
        density="dense"
      >
        <div
          role="alert"
          className="rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-8 text-center text-[var(--status-danger-text)] shadow-sm"
        >
          <Icon name="warning" size={40} className="mx-auto mb-3 text-[var(--status-danger-text)]" />
          <h2 className="text-lg font-bold">
            {isVi ? "Từ chối quyền truy cập (403)" : "Access Denied (403)"}
          </h2>
          <p className="mt-2 text-sm opacity-90 max-w-md mx-auto">
            {isVi
              ? "Bạn không có quyền truy cập vào Giám sát Hệ thống. Yêu cầu quyền quản trị viên (Admin) hoặc Bác sĩ (Doctor)."
              : "You do not have permission to access System Observability. Admin or Doctor role required."}
          </p>
        </div>
      </CommandCenterLayout>
    );
  }

  return (
    <CommandCenterLayout
      workspace="admin"
      commandStrip={<AdminCommandStrip activeTab="observability" />}
      maxWidth="dense"
      density="dense"
    >
      <AdminObservabilityPanel />
    </CommandCenterLayout>
  );
}
