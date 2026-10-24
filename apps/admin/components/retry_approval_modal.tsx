"use client";

import React, { useState } from "react";

export interface RetryApprovalModalProps {
  jobId: string;
  queueName: string;
  jobType: string;
  lastErrorCode: string;
  attemptCount: number;
  isOpen: boolean;
  onConfirmRetry: (jobId: string, rationale: string) => Promise<void> | void;
  onClose: () => void;
}

export function RetryApprovalModal({
  jobId,
  queueName,
  jobType,
  lastErrorCode,
  attemptCount,
  isOpen,
  onConfirmRetry,
  onClose,
}: RetryApprovalModalProps) {
  const [rationale, setRationale] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmedStatutoryCheck, setConfirmedStatutoryCheck] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!confirmedStatutoryCheck || rationale.trim().length < 5) return;
    setIsSubmitting(true);
    try {
      await onConfirmRetry(jobId, rationale.trim());
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-950 p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h2 className="text-base font-semibold text-slate-100">
            Manual Requeue & Retry Approval
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
            disabled={isSubmitting}
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 font-mono text-xs text-slate-300 space-y-1">
            <div><span className="text-slate-500">Job ID:</span> {jobId}</div>
            <div><span className="text-slate-500">Queue:</span> {queueName}</div>
            <div><span className="text-slate-500">Job Type:</span> {jobType}</div>
            <div><span className="text-slate-500">Prior Attempts:</span> {attemptCount}</div>
            <div><span className="text-slate-500">Failure Code:</span> <span className="text-rose-400">{lastErrorCode}</span></div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300">
              Administrative Rationale (Minimum 5 characters)
            </label>
            <textarea
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Explain the root cause remediation before manual requeue..."
              rows={3}
              required
              className="mt-1 w-full rounded border border-slate-700 bg-slate-900 p-2 text-xs text-slate-200 placeholder-slate-500 focus:border-sky-500 focus:outline-none"
            />
          </div>

          <div className="flex items-start gap-2">
            <input
              type="checkbox"
              id="statutoryCheck"
              checked={confirmedStatutoryCheck}
              onChange={(e) => setConfirmedStatutoryCheck(e.target.checked)}
              className="mt-0.5 rounded border-slate-700 bg-slate-900 text-sky-600 focus:ring-sky-500"
            />
            <label htmlFor="statutoryCheck" className="text-xs text-slate-400">
              I certify that patient consent purpose has been re-verified and downstream partner network is operational.
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="rounded bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!confirmedStatutoryCheck || rationale.trim().length < 5 || isSubmitting}
              className="rounded bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-500 disabled:opacity-50"
            >
              {isSubmitting ? "Requeuing..." : "Approve Requeue"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
