import React from "react";

export default function AdminFeatureFlagsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Operational & Dark Safety Flags</h1>
      <p className="text-sm text-slate-400">
        Centrally governed feature toggles for safety gating.
      </p>
      <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
        <p className="text-sm text-slate-300">RAG_SCRIBE_STREAMING_ENABLED: Inactive (Dark)</p>
      </div>
    </div>
  );
}
