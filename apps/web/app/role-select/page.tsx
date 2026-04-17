"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { UserRole, setRole } from "@/lib/auth-store";
import { getRoleHomePath } from "@/lib/navigation.config";

const roles: Array<{ value: UserRole; label: string; description: string }> = [
  {
    value: "normal",
    label: "Người dùng cá nhân",
    description: "Tra cứu thông tin cơ bản và quản lý sức khỏe cá nhân.",
  },
  {
    value: "researcher",
    label: "Nhà nghiên cứu",
    description: "Luồng nghiên cứu chuyên sâu, phản hồi có dẫn chứng.",
  },
  {
    value: "doctor",
    label: "Bác sĩ",
    description: "Luồng lâm sàng chuyên biệt và hội chẩn AI.",
  },
];

export default function RoleSelectionPage() {
  const [selectedRole, setSelectedRole] = useState<UserRole>("normal");
  const router = useRouter();

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setRole(selectedRole);
    router.push(getRoleHomePath(selectedRole));
  };

  return (
    <div className="mx-auto max-w-2xl rounded-2xl border border-slate-300/75 bg-slate-100/88 p-6 shadow-[0_16px_44px_-24px_rgba(15,23,42,0.35)] dark:border-slate-700/70 dark:bg-slate-900/72">
      <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Chọn vai trò người dùng</h1>
      <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
        Vai trò sẽ quyết định menu và workflow của bạn trong hệ thống.
      </p>

      <form className="mt-6 space-y-3" onSubmit={onSubmit}>
        {roles.map((role) => {
          const isActive = selectedRole === role.value;
          return (
            <label
              key={role.value}
              className={[
                "flex cursor-pointer gap-3 rounded-2xl border p-3 transition-colors",
                isActive
                  ? "border-cyan-300/70 bg-cyan-50/75 dark:border-cyan-400/45 dark:bg-cyan-500/14"
                  : "border-slate-300/80 bg-slate-50/75 hover:bg-slate-100/85 dark:border-slate-700/70 dark:bg-slate-800/55 dark:hover:bg-slate-800/75",
              ].join(" ")}
            >
              <input
                type="radio"
                name="role"
                value={role.value}
                checked={isActive}
                onChange={() => setSelectedRole(role.value)}
                className="mt-1 accent-blue-600"
              />
              <div>
                <p className={["font-medium", isActive ? "text-slate-900 dark:text-slate-100" : "text-slate-700 dark:text-slate-300"].join(" ")}>
                  {role.label}
                </p>
                <p className={["text-sm", isActive ? "text-slate-700 dark:text-slate-200" : "text-slate-600 dark:text-slate-400"].join(" ")}>
                  {role.description}
                </p>
              </div>
            </label>
          );
        })}

        <button
          type="submit"
          className="mt-3 rounded-xl bg-blue-600 px-5 py-2.5 font-semibold text-white transition-colors hover:bg-blue-700 dark:bg-cyan-500 dark:text-slate-950 dark:hover:bg-cyan-400"
        >
          Áp dụng vai trò
        </button>
      </form>
    </div>
  );
}

