"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type CouncilWorkspaceLink = {
  href: string;
  label: string;
  hint: string;
};

export const COUNCIL_WORKSPACE_LINKS: CouncilWorkspaceLink[] = [
  { href: "/council", label: "Tổng quan hội chẩn", hint: "Bức tranh ca hiện tại" },
  { href: "/council/new", label: "Nhập ca bệnh", hint: "Tạo ca hội chẩn mới" },
  { href: "/council/result", label: "Kết luận", hint: "Kết quả hội chẩn" },
];

function isActiveLink(pathname: string, href: string): boolean {
  if (href === "/council") {
    return pathname === "/council";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function CouncilWorkspaceNav({ className = "" }: { className?: string }) {
  const pathname = usePathname();

  return (
    <nav className={`rounded-[1.3rem] border border-[#B6D4FE] bg-white p-2.5 shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90 ${className}`.trim()}>
      <p className="px-1 text-[11px] font-bold uppercase tracking-[0.15em] text-[#4B5563] dark:text-slate-200">Không gian hội chẩn</p>
      <div className="mt-2 grid gap-1.5 sm:grid-cols-3">
        {COUNCIL_WORKSPACE_LINKS.map((item) => {
          const active = isActiveLink(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-xl border px-3 py-2.5 transition ${
                active
                  ? "border-[#2563EB] bg-[#DBEAFE] text-[#1E3A8A] shadow-sm dark:border-sky-400 dark:bg-sky-500/20 dark:text-sky-100"
                  : "border-[#B6D4FE] bg-white text-[#1F2937] hover:border-[#2563EB] hover:bg-[#F8FBFF] dark:border-sky-800 dark:bg-slate-900/90 dark:text-slate-100 dark:hover:border-sky-500"
              }`}
            >
              <p className="text-sm font-bold">{item.label}</p>
              <p className="mt-0.5 text-xs font-medium text-[#4B5563] dark:text-slate-300">{item.hint}</p>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
