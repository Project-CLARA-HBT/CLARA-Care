"use client";

import React, { useState } from "react";

interface TenantItem {
  id: string;
  slug: string;
  name: string;
  tier: "hospital" | "clinic" | "enterprise";
  status: "ACTIVE" | "SUSPENDED" | "ONBOARDING";
  maxWorkspaces: number;
  maxUsers: number;
}

const INITIAL_TENANTS: TenantItem[] = [
  {
    id: "tenant-hbt-central",
    slug: "hbt-central",
    name: "Bệnh viện Bạch Mai - Central Unit",
    tier: "hospital",
    status: "ACTIVE",
    maxWorkspaces: 20,
    maxUsers: 200,
  },
  {
    id: "tenant-danang-clinic",
    slug: "danang-clinic",
    name: "Phòng khám Đa khoa Đà Nẵng",
    tier: "clinic",
    status: "ACTIVE",
    maxWorkspaces: 5,
    maxUsers: 50,
  },
  {
    id: "tenant-hue-pilot",
    slug: "hue-pilot",
    name: "Cơ sở Y tế Thừa Thiên Huế",
    tier: "clinic",
    status: "SUSPENDED",
    maxWorkspaces: 3,
    maxUsers: 20,
  },
];

export default function AdminTenantsPage() {
  const [tenants, setTenants] = useState<TenantItem[]>(INITIAL_TENANTS);

  const toggleStatus = (tenantId: string) => {
    setTenants((prev) =>
      prev.map((t) => {
        if (t.id === tenantId) {
          const nextStatus = t.status === "ACTIVE" ? "SUSPENDED" : "ACTIVE";
          return { ...t, status: nextStatus };
        }
        return t;
      })
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100">B2B Tenant Organizations</h1>
          <p className="mt-1 text-sm text-slate-400">
            Lifecycle governance, workspace quotas, and operational status management
          </p>
        </div>
        <button className="rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500">
          + Onboard Organization
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <table className="w-full text-left text-sm text-slate-200">
          <thead className="border-b border-slate-800 bg-slate-900/50 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-6 py-3">Organization</th>
              <th className="px-6 py-3">Slug</th>
              <th className="px-6 py-3">Tier</th>
              <th className="px-6 py-3">Workspaces</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {tenants.map((t) => (
              <tr key={t.id}>
                <td className="px-6 py-4 font-semibold text-slate-100">{t.name}</td>
                <td className="px-6 py-4 font-mono text-xs text-sky-400">{t.slug}</td>
                <td className="px-6 py-4 capitalize text-slate-300">{t.tier}</td>
                <td className="px-6 py-4 text-slate-300">
                  {t.maxWorkspaces} / {t.maxUsers} seats
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-semibold ${
                      t.status === "ACTIVE"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : "bg-red-950 text-red-400 border border-red-800"
                    }`}
                  >
                    {t.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <button
                    onClick={() => toggleStatus(t.id)}
                    className={`rounded px-2.5 py-1 text-xs font-medium ${
                      t.status === "ACTIVE"
                        ? "text-red-400 hover:bg-red-950/40"
                        : "text-emerald-400 hover:bg-emerald-950/40"
                    }`}
                  >
                    {t.status === "ACTIVE" ? "Suspend" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
