import React from "react";

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Platform Operational Governance</h1>
      <p className="text-slate-400">
        Control plane dashboard strictly segregated from consumer clinical records.
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-sm font-medium text-slate-400">Tenants Governed</h2>
          <p className="mt-2 text-3xl font-bold text-slate-100">12</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-sm font-medium text-slate-400">Control Health</h2>
          <p className="mt-2 text-3xl font-bold text-emerald-400">Healthy</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-5">
          <h2 className="text-sm font-medium text-slate-400">Dark Safety Flags</h2>
          <p className="mt-2 text-3xl font-bold text-amber-400">3 Active</p>
        </div>
      </div>
    </div>
  );
}
