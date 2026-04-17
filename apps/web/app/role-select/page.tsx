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
    <div className="mx-auto max-w-2xl rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-[0_16px_44px_-24px_rgba(15,23,42,0.35)]">
      <h1 className="text-2xl font-bold text-[var(--text-primary)]">Chọn vai trò người dùng</h1>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">
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
                  ? "border-[color:var(--shell-border-strong)] bg-[var(--surface-brand-soft)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] hover:bg-[var(--surface-panel)]",
              ].join(" ")}
            >
              <input
                type="radio"
                name="role"
                value={role.value}
                checked={isActive}
                onChange={() => setSelectedRole(role.value)}
                className="mt-1 accent-cyan-500"
              />
              <div>
                <p className="font-medium text-[var(--text-primary)]">{role.label}</p>
                <p className={[
                  "text-sm",
                  isActive ? "text-[var(--text-secondary)]" : "text-[var(--text-muted)]",
                ].join(" ")}
                >
                  {role.description}
                </p>
              </div>
            </label>
          );
        })}

        <button
          type="submit"
          className="mt-3 rounded-xl bg-[color:var(--brand-500)] px-5 py-2.5 font-semibold text-slate-950 transition-colors hover:bg-[color:var(--brand-400)]"
        >
          Áp dụng vai trò
        </button>
      </form>
    </div>
  );
}