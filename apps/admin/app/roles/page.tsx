"use client";

import React, { useState } from "react";

interface RoleMatrixItem {
  role: string;
  scope: "platform" | "tenant";
  description: string;
  permissions: string[];
}

const INITIAL_ROLES: RoleMatrixItem[] = [
  {
    role: "platform_admin",
    scope: "platform",
    description: "Platform infrastructure and tenant lifecycle governance",
    permissions: ["platform:tenants:create", "platform:tenants:suspend", "platform:flags:manage"],
  },
  {
    role: "tenant_admin",
    scope: "tenant",
    description: "Clinic or hospital workspace and clinician administration",
    permissions: ["tenant:users:invite", "tenant:users:remove", "tenant:workspaces:create"],
  },
  {
    role: "auditor",
    scope: "platform",
    description: "Read-only compliance and security trace auditing",
    permissions: ["platform:audit:read", "tenant:audit:read"],
  },
];

export default function RoleMatrixPage() {
  const [roles] = useState<RoleMatrixItem[]>(INITIAL_ROLES);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">Role & Permission Matrix</h1>
        <p className="mt-1 text-sm text-slate-400">
          Platform-level vs Tenant-scoped RBAC authorization boundaries (Read-Only)
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <table className="w-full text-left text-sm text-slate-200">
          <thead className="border-b border-slate-800 bg-slate-900/50 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-6 py-3">Role</th>
              <th className="px-6 py-3">Scope</th>
              <th className="px-6 py-3">Description</th>
              <th className="px-6 py-3">Permissions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {roles.map((r) => (
              <tr key={r.role}>
                <td className="px-6 py-4 font-mono font-medium text-sky-400">{r.role}</td>
                <td className="px-6 py-4">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-semibold ${
                      r.scope === "platform"
                        ? "bg-purple-950 text-purple-400 border border-purple-800"
                        : "bg-blue-950 text-blue-400 border border-blue-800"
                    }`}
                  >
                    {r.scope}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-300">{r.description}</td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {r.permissions.map((p) => (
                      <span key={p} className="rounded bg-slate-900 px-2 py-0.5 text-xs font-mono text-slate-300">
                        {p}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
