import AdminObservabilityPanel from "@/components/admin/admin-observability-panel";
import AdminShell from "@/components/admin/admin-shell";

export default function AdminObservabilityPage() {
  return (
    <AdminShell
      activeTab="observability"
      title="Observability"
      description="Runtime metrics, health và signal board."
    >
      <AdminObservabilityPanel />
    </AdminShell>
  );
}
