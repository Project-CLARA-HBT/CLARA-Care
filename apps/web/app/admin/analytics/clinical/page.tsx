import AdminShell from "@/components/admin/admin-shell";
import ClinicalAnalyticsPanel from "@/components/admin/clinical-analytics-panel";

export default function AdminClinicalAnalyticsPage() {
  return (
    <AdminShell
      activeTab="clinical-analytics"
      title="Phân tích lâm sàng"
      description="Phân bố phán quyết FIDES, mức độ tương tác thuốc (DDI) và độ trễ theo tier cho khoảng ngày đã chọn. Tách biệt với bảng tổng hợp scribe."
    >
      <ClinicalAnalyticsPanel />
    </AdminShell>
  );
}
