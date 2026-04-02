import AdminObservabilityPanel from "@/components/admin/admin-observability-panel";
import AdminShell from "@/components/admin/admin-shell";

export default function AdminObservabilityPage() {
  return (
    <AdminShell
      activeTab="observability"
      title="Observability"
      description="Theo dõi health, dependency, latency từ control tower runtime và giám sát tập trung bằng Grafana."
    >
      <AdminObservabilityPanel />
    </AdminShell>
  );
}
