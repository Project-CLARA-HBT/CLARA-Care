"use client";

import { useEffect, useState } from "react";
import AdminAnswerFlowPanel from "@/components/admin/admin-answer-flow-panel";
import AdminCommandStrip from "@/components/admin/admin-command-strip";
import CommandCenterLayout from "@/components/page/command-center-layout";
import { getRole, type UserRole } from "@/lib/auth-store";
import { useUILanguage } from "@/lib/use-ui-language";
import Icon from "@/components/ui/icon";

/**
 * Answer Flow Explorer & Pipeline Administration (Spec v8 Section 12.2 / 12.3).
 *
 * Shell: ADMIN_COMMAND / DENSE
 * Archetype: Answer Flow Explorer
 *
 * Core capabilities:
 * 1. AdminCommandStrip integration with compact top-local navigation.
 * 2. Multi-tier flow flag controls and low context threshold tuning.
 * 3. Flow topology visualization with interactive node inspector.
 * 4. Runtime inference debugger & simulation scenarios.
 * 5. Live flow telemetry event stream & multi-agent council canvas.
 */
export default function AdminAnswerFlowPage() {
  const [role, setRoleState] = useState<UserRole | null>(() => getRole());
  const language = useUILanguage();
  const isVi = language !== "en";

  useEffect(() => {
    setRoleState(getRole());
  }, []);

  if (role !== null && role !== "admin") {
    return (
      <CommandCenterLayout
        workspace="admin"
        commandStrip={<AdminCommandStrip activeTab="answer-flow" />}
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
              ? "Bạn không có quyền truy cập vào Trung tâm Chỉ huy Quản trị. Yêu cầu quyền quản trị viên (Admin)."
              : "You do not have permission to access the Admin Command Workbench. Admin role required."}
          </p>
        </div>
      </CommandCenterLayout>
    );
  }

  return (
    <CommandCenterLayout
      workspace="admin"
      commandStrip={<AdminCommandStrip activeTab="answer-flow" />}
      maxWidth="dense"
      density="dense"
    >
      <AdminAnswerFlowPanel />
    </CommandCenterLayout>
  );
}
