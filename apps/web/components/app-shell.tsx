"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import SidebarNav from "@/components/sidebar-nav";
import { getRole } from "@/lib/auth-store";
import type { UserRole } from "@/lib/auth/roles";

type Props = {
  children: ReactNode;
};

const HIDE_SIDEBAR_ROUTES = new Set([
  "/",
  "/huong-dan",
  "/login",
  "/register",
  "/role-select",
  "/forgot-password",
  "/reset-password",
  "/verify-email"
]);

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ"
};

const PAGE_META: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Tổng quan công việc",
    subtitle: "Theo dõi nhanh các tác vụ chăm sóc và vận hành trong ngày."
  },
  "/careguard": {
    title: "Kiểm tra tương tác thuốc",
    subtitle: "Đối chiếu thuốc, dị ứng và triệu chứng để phát hiện rủi ro sớm."
  },
  "/selfmed": {
    title: "Tủ thuốc của tôi",
    subtitle: "Quản lý thuốc đang dùng và quét toa thuốc từ ảnh."
  },
  "/research": {
    title: "Hỏi đáp chuyên môn",
    subtitle: "Tra cứu câu trả lời có dẫn nguồn để hỗ trợ quyết định lâm sàng."
  },
  "/council": {
    title: "Hội chẩn ca bệnh",
    subtitle: "Tập hợp ý kiến đa chuyên khoa để xử lý ca khó."
  },
  "/scribe": {
    title: "Ghi chép khám bệnh",
    subtitle: "Soạn ghi chú khám nhanh theo định dạng rõ ràng, nhất quán."
  },
  "/dashboard/control-tower": {
    title: "Điều phối tri thức",
    subtitle: "Thiết lập nguồn dữ liệu và luồng phản hồi cho hệ thống hỏi đáp."
  },
  "/dashboard/ecosystem": {
    title: "Hệ sinh thái đối tác",
    subtitle: "Theo dõi trạng thái kết nối và độ tin cậy dữ liệu liên thông."
  },
  "/admin/overview": {
    title: "Quản trị hệ thống",
    subtitle: "Bảng điều phối trung tâm cho cấu hình, chất lượng phản hồi và vận hành."
  },
  "/admin/rag-sources": {
    title: "Nguồn tri thức",
    subtitle: "Quản lý nguồn dữ liệu và mức ưu tiên truy xuất."
  },
  "/admin/answer-flow": {
    title: "Luồng trả lời",
    subtitle: "Điều phối các bước phân tích, xác minh và phản hồi cuối."
  },
  "/admin/observability": {
    title: "Giám sát vận hành",
    subtitle: "Theo dõi tình trạng hệ thống, cảnh báo và tín hiệu runtime."
  }
};

export default function AppShell({ children }: Props) {
  const pathname = usePathname();
  const [role, setRole] = useState<UserRole>("normal");

  const hideSidebar = HIDE_SIDEBAR_ROUTES.has(pathname);

  useEffect(() => {
    setRole(getRole());
  }, [pathname]);

  const currentPage = useMemo(() => {
    const exact = PAGE_META[pathname];
    if (exact) return exact;

    const prefixMatch = Object.entries(PAGE_META).find(([key]) => pathname.startsWith(`${key}/`));
    if (prefixMatch) return prefixMatch[1];

    return {
      title: "Không gian làm việc",
      subtitle: "Nền tảng trợ lý y tế giúp bạn xử lý công việc nhanh và rõ ràng hơn."
    };
  }, [pathname]);

  if (hideSidebar) {
    return <main className="min-h-screen bg-[var(--color-bg)]">{children}</main>;
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-slate-900">
      <div className="mx-auto flex min-h-screen w-full max-w-[1560px]">
        <SidebarNav />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/85 px-5 py-3 backdrop-blur sm:px-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Workspace</p>
                <h1 className="mt-1 text-lg font-semibold text-slate-900 sm:text-xl">{currentPage.title}</h1>
                <p className="mt-0.5 text-sm text-slate-600">{currentPage.subtitle}</p>
              </div>
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-700">
                {ROLE_LABELS[role]}
              </span>
            </div>
          </header>

          <main className="flex-1 p-4 sm:p-5 lg:p-6">
            <div className="mx-auto w-full max-w-[1180px]">{children}</div>
          </main>
        </div>
      </div>
    </div>
  );
}
