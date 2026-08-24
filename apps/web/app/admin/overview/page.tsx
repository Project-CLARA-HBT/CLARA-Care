"use client";

import AdminOverviewPanel from "@/components/admin/admin-overview-panel";
import AdminCommandStrip from "@/components/admin/admin-command-strip";
import CommandCenterLayout from "@/components/page/command-center-layout";

export default function AdminOverviewPage() {
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
