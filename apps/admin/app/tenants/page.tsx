import React from "react";

export default function AdminTenantsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Tenant Governance Directory</h1>
      <p className="text-sm text-slate-400">
        Enterprise clinic and hospital tenancy configurations.
      </p>
      <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
        <p className="text-sm text-slate-300">HBT Central Hospital (Tier: Hospital, Active: True)</p>
      </div>
    </div>
  );
}
