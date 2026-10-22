import React from "react";

export interface GlhsEvidenceStatusProps {
  attestationLevel: "L0" | "L1" | "L2" | "L3" | string;
  isConsentActive: boolean;
  dependencyVectorVerified: boolean;
  sourceType: string;
}

export function GlhsEvidenceBadge({
  attestationLevel,
  isConsentActive,
  dependencyVectorVerified,
  sourceType,
}: GlhsEvidenceStatusProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Attestation Level Chip */}
      <span className="rounded bg-sky-950 px-2 py-0.5 text-xs font-mono font-bold text-sky-400 border border-sky-800">
        {attestationLevel.includes("L") ? attestationLevel : `Attestation: ${attestationLevel}`}
      </span>

      {/* Dependency Status Chip */}
      <span
        className={`rounded px-2 py-0.5 text-xs font-semibold ${
          dependencyVectorVerified
            ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
            : "bg-red-950 text-red-400 border border-red-800"
        }`}
      >
        {dependencyVectorVerified ? "OCC Deps Fresh" : "Stale Dependency"}
      </span>

      {/* Consent Gate Chip */}
      <span
        className={`rounded px-2 py-0.5 text-xs font-semibold ${
          isConsentActive
            ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
            : "bg-red-950 text-red-400 border border-red-800"
        }`}
      >
        {isConsentActive ? "Consent Active" : "Consent Revoked"}
      </span>

      {/* Source Category */}
      <span className="rounded bg-slate-800 px-2 py-0.5 text-xs font-medium text-slate-300">
        {sourceType}
      </span>
    </div>
  );
}
