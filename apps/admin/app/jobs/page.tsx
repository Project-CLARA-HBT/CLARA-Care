"use client";

import React, { useState } from "react";

interface JobItem {
  jobId: string;
  queueName: string;
  jobType: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "DEAD_LETTER";
  attemptCount: number;
  maxAttempts: number;
  lastErrorCode: string;
  createdAt: string;
}

interface ConnectorStatus {
  provider: string;
  transport: "device" | "cloud";
  status: "connected" | "paused" | "disconnected";
  lastSyncAt: string;
}

const INITIAL_JOBS: JobItem[] = [
  {
    jobId: "job-ocr-5101",
    queueName: "ocr_processing",
    jobType: "OCR_DOCUMENT_SCAN",
    status: "COMPLETED",
    attemptCount: 1,
    maxAttempts: 8,
    lastErrorCode: "",
    createdAt: "2026-10-22T19:30:00Z",
  },
  {
    jobId: "job-dlq-5102",
    queueName: "webhooks_egress",
    jobType: "EXTERNAL_EMR_SYNC",
    status: "DEAD_LETTER",
    attemptCount: 8,
    maxAttempts: 8,
    lastErrorCode: "WEBHOOK_TIMEOUT_EXCEEDED",
    createdAt: "2026-10-22T18:15:00Z",
  },
  {
    jobId: "job-conn-5103",
    queueName: "wearable_sync",
    jobType: "HEALTH_CONNECT_BATCH",
    status: "PENDING",
    attemptCount: 0,
    maxAttempts: 5,
    lastErrorCode: "",
    createdAt: "2026-10-22T19:42:00Z",
  },
];

const INITIAL_CONNECTORS: ConnectorStatus[] = [
  {
    provider: "HEALTH_CONNECT",
    transport: "device",
    status: "connected",
    lastSyncAt: "2026-10-22T19:35:00Z",
  },
  {
    provider: "HUAWEI_HEALTH",
    transport: "device",
    status: "paused",
    lastSyncAt: "2026-10-22T14:10:00Z",
  },
  {
    provider: "FITBIT",
    transport: "cloud",
    status: "connected",
    lastSyncAt: "2026-10-22T19:40:00Z",
  },
];

export default function AdminJobsDashboardPage() {
  const [jobs, setJobs] = useState<JobItem[]>(INITIAL_JOBS);
  const [connectors] = useState<ConnectorStatus[]>(INITIAL_CONNECTORS);
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);

  const handleReplay = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.jobId === jobId ? { ...j, status: "PENDING", attemptCount: 0, lastErrorCode: "" } : j
      )
    );
  };

  const handleCancel = (jobId: string) => {
    setJobs((prev) =>
      prev.map((j) =>
        j.jobId === jobId ? { ...j, status: "FAILED", lastErrorCode: "USER_CANCELLED" } : j
      )
    );
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">
          Job Queues, Outbox & Connector Console
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Supervise durable transactional outbox relay, dead-letter queue recovery, and connector sync status.
        </p>
      </div>

      {/* Metrics Overview */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
          <div className="text-xs uppercase text-slate-400">Active Queues</div>
          <div className="mt-1 text-2xl font-bold text-sky-400">3</div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
          <div className="text-xs uppercase text-slate-400">Pending Jobs</div>
          <div className="mt-1 text-2xl font-bold text-amber-400">
            {jobs.filter((j) => j.status === "PENDING").length}
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
          <div className="text-xs uppercase text-slate-400">Dead Letters (DLQ)</div>
          <div className="mt-1 text-2xl font-bold text-rose-500">
            {jobs.filter((j) => j.status === "DEAD_LETTER").length}
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
          <div className="text-xs uppercase text-slate-400">Connected Adapters</div>
          <div className="mt-1 text-2xl font-bold text-emerald-400">
            {connectors.filter((c) => c.status === "connected").length} / {connectors.length}
          </div>
        </div>
      </div>

      {/* Jobs Table */}
      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <div className="border-b border-slate-800 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-200">Execution Ledger & Requeue Gate</h2>
        </div>
        <table className="w-full text-left text-sm text-slate-200">
          <thead className="border-b border-slate-800 bg-slate-900/50 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-6 py-3">Job ID</th>
              <th className="px-6 py-3">Queue</th>
              <th className="px-6 py-3">Job Type</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Attempts</th>
              <th className="px-6 py-3">Last Error</th>
              <th className="px-6 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
            {jobs.map((job) => (
              <tr key={job.jobId} className="hover:bg-slate-900/40">
                <td className="px-6 py-4 font-semibold text-sky-300">{job.jobId}</td>
                <td className="px-6 py-4 text-slate-400">{job.queueName}</td>
                <td className="px-6 py-4 text-slate-300">{job.jobType}</td>
                <td className="px-6 py-4">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      job.status === "COMPLETED"
                        ? "bg-emerald-950/80 text-emerald-400"
                        : job.status === "DEAD_LETTER"
                        ? "bg-rose-950/80 text-rose-400"
                        : "bg-amber-950/80 text-amber-300"
                    }`}
                  >
                    {job.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-300">
                  {job.attemptCount} / {job.maxAttempts}
                </td>
                <td className="px-6 py-4 text-rose-400">
                  {job.lastErrorCode || "—"}
                </td>
                <td className="px-6 py-4">
                  <div className="flex gap-2">
                    <button
                      onClick={() => setSelectedJob(job)}
                      className="rounded bg-slate-800 px-2 py-1 text-slate-200 hover:bg-slate-700"
                    >
                      Inspect
                    </button>
                    {job.status === "DEAD_LETTER" && (
                      <button
                        onClick={() => handleReplay(job.jobId)}
                        className="rounded bg-amber-900/80 px-2 py-1 text-amber-200 hover:bg-amber-800"
                      >
                        Replay
                      </button>
                    )}
                    {job.status === "PENDING" && (
                      <button
                        onClick={() => handleCancel(job.jobId)}
                        className="rounded bg-rose-900/80 px-2 py-1 text-rose-200 hover:bg-rose-800"
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Connectors Table */}
      <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
        <div className="border-b border-slate-800 px-6 py-4">
          <h2 className="text-base font-semibold text-slate-200">Connected Health Adapters</h2>
        </div>
        <table className="w-full text-left text-sm text-slate-200">
          <thead className="border-b border-slate-800 bg-slate-900/50 text-xs uppercase text-slate-400">
            <tr>
              <th className="px-6 py-3">Provider</th>
              <th className="px-6 py-3">Transport</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Last Sync</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
            {connectors.map((c) => (
              <tr key={c.provider} className="hover:bg-slate-900/40">
                <td className="px-6 py-4 font-semibold text-slate-200">{c.provider}</td>
                <td className="px-6 py-4 text-slate-400">{c.transport}</td>
                <td className="px-6 py-4">
                  <span
                    className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                      c.status === "connected"
                        ? "bg-emerald-950/80 text-emerald-400"
                        : "bg-amber-950/80 text-amber-300"
                    }`}
                  >
                    {c.status}
                  </span>
                </td>
                <td className="px-6 py-4 text-slate-400">{c.lastSyncAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Inspection Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-950 p-6">
            <h3 className="text-lg font-bold text-slate-100">Job Metadata Inspection</h3>
            <p className="mt-1 text-xs text-slate-400">
              Payload PHI is permanently redacted from administrative inspect views.
            </p>
            <div className="mt-4 space-y-2 font-mono text-xs text-slate-300">
              <div>Job ID: {selectedJob.jobId}</div>
              <div>Queue: {selectedJob.queueName}</div>
              <div>Type: {selectedJob.jobType}</div>
              <div>Status: {selectedJob.status}</div>
              <div>Attempts: {selectedJob.attemptCount} / {selectedJob.maxAttempts}</div>
              <div>Error: {selectedJob.lastErrorCode || "None"}</div>
              <div>Enqueued: {selectedJob.createdAt}</div>
            </div>
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedJob(null)}
                className="rounded bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
