"use client";

import { useEffect, useState } from "react";
import AdminOverviewPanel from "@/components/admin/admin-overview-panel";
import AdminCommandStrip from "@/components/admin/admin-command-strip";
import CommandCenterLayout from "@/components/page/command-center-layout";
import { getRole, type UserRole } from "@/lib/auth-store";
import { useUILanguage } from "@/lib/use-ui-language";
import Icon from "@/components/ui/icon";

export default function AdminOverviewPage() {
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
        commandStrip={<AdminCommandStrip activeTab="overview" />}
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
      commandStrip={<AdminCommandStrip activeTab="overview" />}
      maxWidth="dense"
      density="dense"
    >
      <AdminOverviewPanel />
    </CommandCenterLayout>
  );
}
