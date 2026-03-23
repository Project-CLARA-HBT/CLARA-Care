"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import {
  getApiHealth,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics
} from "@/lib/system";

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Normal",
  researcher: "Researcher",
  doctor: "Doctor"
};

const MODULE_LINKS = [
  { href: "/careguard", label: "CareGuard", description: "Triaging nhanh theo triệu chứng, thuốc, dị ứng." },
  { href: "/scribe", label: "Medical Scribe", description: "Tạo SOAP note từ transcript buổi khám." },
  { href: "/research", label: "Research Workspace", description: "Tier1/Tier2 nghiên cứu có citations và steps." },
  { href: "/council", label: "AI Council", description: "Điểm truy cập workflow hội chẩn." },
  {
    href: "/dashboard/ecosystem",
    label: "Ecosystem Center",
    description: "Theo dõi partner health, trust score và federation alerts (doctor-only API)."
  }
];

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatLatencyMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value)} ms`;
}

function getErrorText(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  return fallback;
}

export default function DashboardPage() {
  const [role, setRole] = useState<UserRole>("normal");

  const [healthStatus, setHealthStatus] = useState("unknown");
  const [healthMessage, setHealthMessage] = useState("Chưa có dữ liệu health.");
  const [healthError, setHealthError] = useState("");

  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [errorCount, setErrorCount] = useState<number | null>(null);
  const [avgLatencyMs, setAvgLatencyMs] = useState<number | null>(null);
  const [metricsError, setMetricsError] = useState("");

  const [mlStatus, setMlStatus] = useState("unknown");
  const [mlReachable, setMlReachable] = useState<boolean | null>(null);
  const [dependenciesError, setDependenciesError] = useState("");

  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? "Normal", [role]);

  const onRefreshSystem = useCallback(async () => {
    setIsRefreshing(true);
    setHealthError("");
    setMetricsError("");
    setDependenciesError("");

    try {
      const [healthResult, metricsResult, dependenciesResult] = await Promise.allSettled([
        getApiHealth(),
        getSystemMetrics(),
        getSystemDependencies()
      ]);

      if (healthResult.status === "fulfilled") {
        const health = normalizeApiHealth(healthResult.value);
        setHealthStatus(health.status);
        setHealthMessage(health.message);
      } else {
        setHealthError(getErrorText(healthResult.reason, "Không thể lấy API health status."));
      }

      if (metricsResult.status === "fulfilled") {
        const metrics = normalizeSystemMetrics(metricsResult.value);
        setRequestCount(metrics.requestCount);
        setErrorCount(metrics.errorCount);
        setAvgLatencyMs(metrics.avgLatencyMs);
      } else {
        setMetricsError(getErrorText(metricsResult.reason, "Không thể lấy API metrics."));
      }

      if (dependenciesResult.status === "fulfilled") {
        const dependencies = normalizeSystemDependencies(dependenciesResult.value);
        setMlStatus(dependencies.mlStatus);
        setMlReachable(dependencies.mlReachable);
      } else {
        setDependenciesError(getErrorText(dependenciesResult.reason, "Không thể lấy dependency status."));
      }

      setCheckedAt(new Date().toLocaleString("vi-VN"));
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    void onRefreshSystem();
  }, [onRefreshSystem]);

  const mlStatusLabel =
    mlReachable === true ? "Reachable" : mlReachable === false ? "Unreachable" : mlStatus || "Unknown";

  const mlStatusColor =
    mlReachable === true
      ? "text-emerald-700"
      : mlReachable === false
        ? "text-red-700"
        : "text-slate-700";

  return (
    <PageShell title="Dashboard">
      <div className="grid gap-4 md:grid-cols-2">
        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Auth Role</p>
          <p className="text-xl font-semibold text-slate-900">{roleLabel}</p>
          <p className="text-sm text-slate-600">Role hiện tại quyết định menu và khả năng truy cập module.</p>
          <Link href="/role-select" className="inline-block text-sm font-medium text-blue-600 hover:underline">
            Đổi vai trò
          </Link>
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">System Monitor</p>
          <p className="text-sm text-slate-600">Theo dõi nhanh trạng thái API, metrics và dependency ML.</p>
          {checkedAt ? <p className="text-xs text-slate-500">Last update: {checkedAt}</p> : null}
          <button
            type="button"
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
            onClick={onRefreshSystem}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Đang làm mới..." : "Refresh"}
          </button>
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">API Health Status</p>
          <p className="text-lg font-semibold text-slate-900">{healthStatus}</p>
          <p className="text-sm text-slate-600">{healthMessage}</p>
          {healthError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{healthError}</p>
          ) : null}
        </section>

        <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">API Metrics Summary</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Request Count</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatCount(requestCount)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Error Count</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatCount(errorCount)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Avg Latency</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatLatencyMs(avgLatencyMs)}</p>
            </div>
          </div>
          {metricsError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{metricsError}</p>
          ) : null}
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Dependency Status</p>
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">ML Service</p>
            <p className={`mt-1 text-lg font-semibold ${mlStatusColor}`}>{mlStatusLabel}</p>
          </div>
          {dependenciesError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {dependenciesError}
            </p>
          ) : null}
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Modules</p>
          <div className="grid gap-2 md:grid-cols-2">
            {MODULE_LINKS.map((module) => (
              <Link
                key={module.href}
                href={module.href}
                className="rounded-md border border-slate-200 bg-white p-3 transition hover:border-blue-300 hover:bg-blue-50"
              >
                <p className="text-sm font-semibold text-slate-900">{module.label}</p>
                <p className="mt-1 text-sm text-slate-600">{module.description}</p>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </PageShell>
  );
}
