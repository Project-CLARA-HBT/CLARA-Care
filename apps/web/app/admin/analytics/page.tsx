import AdminShell from "@/components/admin/admin-shell";
import ProductAnalyticsPanel from "@/components/admin/product-analytics-panel";

export default function AdminProductAnalyticsPage() {
  return (
    <AdminShell
      activeTab="product-analytics"
      title="Phân tích sản phẩm"
      description="Xu hướng người dùng hoạt động, mức độ sử dụng theo Surface, phễu chuyển đổi và giữ chân theo khoảng ngày."
    >
      <ProductAnalyticsPanel />
    </AdminShell>
  );
}
