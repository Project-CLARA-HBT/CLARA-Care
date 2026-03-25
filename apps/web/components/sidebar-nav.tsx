"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { getRole } from "@/lib/auth-store";
import type { UserRole } from "@/lib/auth/roles";

type NavItem = {
  href: string;
  label: string;
  desc: string;
};

const NAV_BY_ROLE: Record<"normal" | "researcher" | "doctor", NavItem[]> = {
  normal: [
    { href: "/dashboard", label: "Tổng quan", desc: "Bức tranh nhanh hôm nay" },
    { href: "/research", label: "Hỏi đáp y tế", desc: "Hỏi nhanh hoặc chuyên sâu" },
    { href: "/selfmed", label: "Tủ thuốc", desc: "Quản lý thuốc cá nhân" },
    { href: "/careguard", label: "Kiểm tra tương tác", desc: "DDI và cảnh báo an toàn" },
    { href: "/huong-dan", label: "Hướng dẫn", desc: "Bắt đầu trong 5 phút" }
  ],
  researcher: [
    { href: "/dashboard", label: "Tổng quan", desc: "Theo dõi hệ thống và truy vấn" },
    { href: "/research", label: "Hỏi đáp nghiên cứu", desc: "Tra cứu có nguồn tham chiếu" },
    { href: "/selfmed", label: "Tủ thuốc", desc: "Flow người dùng thực tế" },
    { href: "/admin/overview", label: "Admin Control Tower", desc: "Nguồn RAG và answer flow" },
    { href: "/huong-dan", label: "Hướng dẫn", desc: "Tài liệu sử dụng nhanh" }
  ],
  doctor: [
    { href: "/dashboard", label: "Tổng quan", desc: "Trạng thái ca và hệ thống" },
    { href: "/research", label: "Hỏi đáp nghiên cứu", desc: "Hỗ trợ guideline và evidence" },
    { href: "/council", label: "Hội chẩn AI", desc: "Nhiều góc nhìn chuyên khoa" },
    { href: "/scribe", label: "Medical Scribe", desc: "Ghi chép khám bệnh" },
    { href: "/selfmed", label: "Tủ thuốc", desc: "Theo dõi sử dụng thuốc tại nhà" },
    { href: "/careguard", label: "Kiểm tra tương tác", desc: "Đánh giá rủi ro DDI" },
    { href: "/admin/overview", label: "Admin Control Tower", desc: "Điều phối RAG và quan sát" }
  ]
};

function itemIsActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function SidebarNav() {
  const pathname = usePathname();
  const [role, setRole] = useState<UserRole>("normal");

  useEffect(() => {
    setRole(getRole());
  }, []);

  const navItems = useMemo(() => NAV_BY_ROLE[role] ?? NAV_BY_ROLE.normal, [role]);
  const roleLabel = role === "doctor" ? "Bác sĩ" : role === "researcher" ? "Nhà nghiên cứu" : "Người dùng";

  return (
    <aside className="sticky top-0 hidden h-screen w-80 shrink-0 border-r border-slate-200/80 bg-white/90 px-4 py-5 backdrop-blur lg:block">
      <div className="glass-card rounded-2xl px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700">CLARA Care</p>
        <div className="mt-2 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-900">Không gian làm việc</p>
            <p className="text-xs text-slate-500">Trải nghiệm đơn giản, rõ hành động</p>
          </div>
          <span className="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700">
            {roleLabel}
          </span>
        </div>
      </div>

      <p className="mb-2 mt-5 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Điều hướng chính</p>
      <nav className="space-y-2">
        {navItems.map((item) => {
          const active = itemIsActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group block rounded-xl border px-3 py-2.5 transition ${
                active
                  ? "border-sky-200 bg-sky-50 shadow-sm"
                  : "border-transparent bg-white hover:border-slate-200 hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`text-sm font-semibold ${active ? "text-sky-700" : "text-slate-800"}`}>{item.label}</span>
                <span className={`h-2 w-2 rounded-full ${active ? "bg-sky-600" : "bg-slate-300 group-hover:bg-slate-400"}`} />
              </div>
              <p className="mt-1 text-xs text-slate-500">{item.desc}</p>
            </Link>
          );
        })}
      </nav>

      <div className="mt-5 border-t border-slate-200 pt-4">
        <Link href="/role-select" className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100">
          Đổi vai trò
        </Link>
        <Link href="/huong-dan" className="mt-1 block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100">
          Trung tâm hướng dẫn
        </Link>
      </div>
    </aside>
  );
}
