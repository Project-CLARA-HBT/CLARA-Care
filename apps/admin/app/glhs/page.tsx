"use client";

import React, { useState } from "react";

interface GlhsTraceItem {
  id: string;
  domain: string;
  proposedAction: string;
  model: string;
  attestationLevel: string;
  status: "PENDING" | "ADMITTED" | "REJECTED";
  d1Digest: string;
  d2Digest: string;
  d3Digest: string;
}

const SAMPLE_PROPOSALS: GlhsTraceItem[] = [
  {
    id: "prop-001",
    domain: "medications",
    proposedAction: "Điều chỉnh liều Metformin 850mg sang 500mg (suy giảm eGFR)",
    model: "deepseek-reasoner:v2.5",
    attestationLevel: "PROVIDER_RECEIPT_VERIFIED (L2)",
    status: "PENDING",
    d1Digest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    d2Digest: "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
    d3Digest: "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
  },
  {
    id: "prop-002",
    domain: "clinical_notes",
    proposedAction: "Ký nháy bệnh án SOAP khám định kỳ tim mạch",
    model: "faster-whisper:large-v3",
    attestationLevel: "SERVER_PRE_DISPATCH (L0)",
    status: "ADMITTED",
    d1Digest: "d41d8cd98f00b204e9800998ecf8427e",
    d2Digest: "7d793037a0760186574b0282f2f435e7",
    d3Digest: "1bc29b36f623ba82aaf6724fd3b16718",
  },
];

export default function GlhsTraceExplorerPage() {
  const [proposals, setProposals] = useState<GlhsTraceItem[]>(SAMPLE_PROPOSALS);

  const handleDecision = (id: string, decision: "ADMITTED" | "REJECTED") => {
    setProposals((prev) =>
      prev.map((p) => (p.id === id ? { ...p, status: decision } : p))
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">
          GLHS Trace Explorer & Human Review Queue
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Forensic verification of AI proposal attestation, 3-digest continuity (D1/D2/D3), and clinical admission decisions
        </p>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <table className="w-full text-left text-sm text-slate-200">
          <thead className="border-b border-slate-800 bg-slate-900/50 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-6 py-3">Proposal ID</th>
              <th className="px-6 py-3">Domain</th>
              <th className="px-6 py-3">Proposed Clinical Action</th>
              <th className="px-6 py-3">Attestation Level</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3 text-right">Human Review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {proposals.map((p) => (
              <tr key={p.id}>
                <td className="px-6 py-4 font-mono text-xs text-sky-400">{p.id}</td>
                <td className="px-6 py-4 capitalize text-slate-300">{p.domain}</td>
                <td className="px-6 py-4 max-w-md">
                  <div className="font-medium text-slate-100">{p.proposedAction}</div>
                  <div className="mt-1 font-mono text-[10px] text-slate-500 truncate">
                    D1: {p.d1Digest.slice(0, 16)}... • D3: {p.d3Digest.slice(0, 16)}...
                  </div>
                </td>
                <td className="px-6 py-4 font-mono text-xs text-emerald-400">
                  {p.attestationLevel}
                </td>
                <td className="px-6 py-4">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-semibold ${
                      p.status === "ADMITTED"
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                        : p.status === "PENDING"
                        ? "bg-amber-950 text-amber-400 border border-amber-800"
                        : "bg-red-950 text-red-400 border border-red-800"
                    }`}
                  >
                    {p.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  {p.status === "PENDING" ? (
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleDecision(p.id, "REJECTED")}
                        className="rounded px-2 py-1 text-xs font-medium text-red-400 hover:bg-red-950/40"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => handleDecision(p.id, "ADMITTED")}
                        className="rounded bg-sky-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-sky-500"
                      >
                        Admit
                      </button>
                    </div>
                  ) : (
                    <span className="text-xs text-slate-500 font-mono">Reviewed</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
