import AdminObservabilityPanel from "@/components/admin/admin-observability-panel";
import AdminShell from "@/components/admin/admin-shell";

export default function AdminObservabilityPage() {
  return (
    <AdminShell
      activeTab="observability"
      title="Admin Control Plane - Observability"
      description="Futuristic command center cho runtime CLARA: telemetry đa lớp, flow integrity, risk matrix và alert triage."
    >
      <AdminObservabilityPanel />
    </AdminShell>
  );
}
