import AdminAnswerFlowPanel from "@/components/admin/admin-answer-flow-panel";
import AdminShell from "@/components/admin/admin-shell";

export default function AdminAnswerFlowPage() {
  return (
    <AdminShell
      activeTab="answer-flow"
      title="Luồng trả lời"
      description="Điều khiển flow flags và low_context_threshold để tinh chỉnh logic trả lời nhiều tầng."
    >
      <AdminAnswerFlowPanel />
    </AdminShell>
  );
}
