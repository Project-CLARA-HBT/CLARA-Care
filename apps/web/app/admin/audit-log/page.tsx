import AdminAuditPanel from "@/components/admin/admin-audit-panel";
import AdminShell from "@/components/admin/admin-shell";

export default function AdminAuditLogPage() {
  return (
    <AdminShell
      activeTab="observability"
      title="Nhật ký kiểm toán quản trị"
      description="Lịch sử hành động quản trị (append-only), mới nhất trước. Không chứa thông tin định danh."
    >
      <AdminAuditPanel />
    </AdminShell>
  );
}
