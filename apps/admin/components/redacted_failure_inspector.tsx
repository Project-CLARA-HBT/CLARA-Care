"use client";

import React from "react";

export interface RedactedFailureInspectorProps {
  jobId: string;
  errorTraceId: string;
  errorCode: string;
  timestamp: string;
  sanitizedStackTrace: string;
  isOpen: boolean;
  onClose: () => void;
}

export function RedactedFailureInspector({
  jobId,
  errorTraceId,
  errorCode,
  timestamp,
  sanitizedStackTrace,
  isOpen,
  onClose,
}: RedactedFailureInspectorProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-xl rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-base font-semibold text-slate-100">
            Redacted Failure Inspector
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 space-y-3 font-mono text-xs">
          <div className="grid grid-cols-2 gap-2 rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-slate-300">
            <div><span className="text-slate-500">Job:</span> {jobId}</div>
            <div><span className="text-slate-500">Trace:</span> {errorTraceId}</div>
            <div><span className="text-slate-500">Code:</span> <span className="text-rose-400">{errorCode}</span></div>
            <div><span className="text-slate-500">Time:</span> {timestamp}</div>
          </div>

          <div>
            <div className="flex items-center justify-between py-1">
              <span className="text-xs font-semibold text-slate-400">Sanitized Stack Diagnostics</span>
              <span className="rounded bg-sky-950 px-2 py-0.5 text-[10px] text-sky-400">PHI Redacted</span>
            </div>
            <pre className="max-h-56 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-[11px] text-slate-300">
              {sanitizedStackTrace || "No diagnostics stack trace recorded."}
            </pre>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="rounded bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
