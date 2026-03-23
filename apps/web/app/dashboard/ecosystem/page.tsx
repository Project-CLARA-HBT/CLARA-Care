"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { SystemEcosystemSnapshot, getSystemEcosystem, isAccessDeniedError, normalizeSystemEcosystem } from "@/lib/system";

const EMPTY_SNAPSHOT: SystemEcosystemSnapshot = {
  generatedAt: null,
  summary: {
    partnersTotal: null,
    partnersDown: null,
    trustLowCount: null,
    criticalAlertCount: null
  },
  partnerHealth: [],
  dataTrustScores: [],
  federationAlerts: []
};

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value)}%`;
}

function formatMs(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value)} ms`;
}

function formatDateTime(value: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("vi-VN");
}

function statusClass(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "ok" || normalized === "healthy") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (normalized === "degraded" || normalized === "warning") return "border-amber-200 bg-amber-50 text-amber-700";
  if (normalized === "down" || normalized === "unreachable" || normalized === "error") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function severityClass(severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === "critical") return "border-red-200 bg-red-50 text-red-700";
  if (normalized === "warning") return "border-amber-200 bg-amber-50 text-amber-700";
  if (normalized === "info") return "border-blue-200 bg-blue-50 text-blue-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

export default function EcosystemCenterPage() {
  const [snapshot, setSnapshot] = useState<SystemEcosystemSnapshot>(EMPTY_SNAPSHOT);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);

  const summaryCards = useMemo(
    () => [
      { label: "Partners Total", value: formatCount(snapshot.summary.partnersTotal) },
      { label: "Partners Down", value: formatCount(snapshot.summary.partnersDown) },
      { label: "Trust Low Count", value: formatCount(snapshot.summary.trustLowCount) },
      { label: "Critical Alert Count", value: formatCount(snapshot.summary.criticalAlertCount) }
    ],
    [
      snapshot.summary.criticalAlertCount,
      snapshot.summary.partnersDown,
      snapshot.summary.partnersTotal,
      snapshot.summary.trustLowCount
    ]
  );

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    setError("");
    setForbidden(false);

    try {
      const response = await getSystemEcosystem();
      setSnapshot(normalizeSystemEcosystem(response));
    } catch (refreshError) {
      if (isAccessDeniedError(refreshError)) {
        setForbidden(true);
      } else if (refreshError instanceof Error && refreshError.message.trim()) {
        setError(refreshError.message);
      } else {
        setError("Khong the tai ecosystem center. Vui long thu lai.");
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void onRefresh();
  }, [onRefresh]);

  return (
    <PageShell title="Ecosystem Center">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm text-slate-600">
            Tong hop suc khoe partner, data trust score va federation alerts cho he sinh thai lien thong.
          </p>
          <div className="flex items-center gap-2">
            <Link href="/dashboard" className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100">
              Ve Dashboard
            </Link>
            <button
              type="button"
              onClick={onRefresh}
              disabled={isRefreshing}
              className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isRefreshing ? "Dang lam moi..." : "Refresh"}
            </button>
          </div>
        </div>

        {snapshot.generatedAt ? (
          <p className="text-xs text-slate-500">Generated at: {formatDateTime(snapshot.generatedAt)}</p>
        ) : null}

        {isLoading ? (
          <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            Dang tai ecosystem center...
          </div>
        ) : null}

        {forbidden ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Ban khong du quyen truy cap Ecosystem Center. Endpoint nay chi cho role doctor (403).
          </div>
        ) : null}

        {error && !forbidden ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
        ) : null}

        {!isLoading && !forbidden ? (
          <>
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {summaryCards.map((card) => (
                <article key={card.label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{card.label}</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-900">{card.value}</p>
                </article>
              ))}
            </section>

            <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Partner Health</p>
              {snapshot.partnerHealth.length ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead>
                      <tr className="text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-3 py-2">Partner</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Latency</th>
                        <th className="px-3 py-2">Error Rate</th>
                        <th className="px-3 py-2">Last Check</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 bg-white">
                      {snapshot.partnerHealth.map((row) => (
                        <tr key={`${row.partner}-${row.lastCheck}`}>
                          <td className="px-3 py-2 font-medium text-slate-900">{row.partner}</td>
                          <td className="px-3 py-2">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(row.status)}`}>
                              {row.status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-slate-700">{formatMs(row.latencyMs)}</td>
                          <td className="px-3 py-2 text-slate-700">{formatPercent(row.errorRatePct)}</td>
                          <td className="px-3 py-2 text-slate-700">{formatDateTime(row.lastCheck)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-600">Khong co du lieu partner health.</p>
              )}
            </section>

            <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Data Trust Score</p>
              {snapshot.dataTrustScores.length ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                    <thead>
                      <tr className="text-xs uppercase tracking-wide text-slate-500">
                        <th className="px-3 py-2">Source</th>
                        <th className="px-3 py-2">Trust Score</th>
                        <th className="px-3 py-2">Freshness</th>
                        <th className="px-3 py-2">Drift Risk</th>
                        <th className="px-3 py-2">Last Refresh</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 bg-white">
                      {snapshot.dataTrustScores.map((row) => (
                        <tr key={`${row.source}-${row.lastRefresh}`}>
                          <td className="px-3 py-2 font-medium text-slate-900">{row.source}</td>
                          <td className="px-3 py-2 text-slate-700">{formatCount(row.trustScore)}</td>
                          <td className="px-3 py-2 text-slate-700">
                            {row.freshnessHours === null
                              ? "--"
                              : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(row.freshnessHours)} h`}
                          </td>
                          <td className="px-3 py-2 text-slate-700">{row.driftRisk}</td>
                          <td className="px-3 py-2 text-slate-700">{formatDateTime(row.lastRefresh)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-600">Khong co du lieu data trust score.</p>
              )}
            </section>

            <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Federation Alerts</p>
              {snapshot.federationAlerts.length ? (
                <ul className="space-y-2">
                  {snapshot.federationAlerts.map((alert) => (
                    <li key={alert.id} className="rounded-md border border-slate-200 bg-white p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${severityClass(alert.severity)}`}>
                          {alert.severity}
                        </span>
                        <p className="text-sm font-medium text-slate-800">{alert.id}</p>
                        <span className="text-xs text-slate-500">{formatDateTime(alert.createdAt)}</span>
                      </div>
                      <p className="mt-2 text-sm text-slate-700">{alert.message}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        source: {alert.source} | acknowledged: {alert.acknowledged === null ? "--" : alert.acknowledged ? "yes" : "no"}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-600">Khong co federation alerts.</p>
              )}
            </section>
          </>
        ) : null}
      </div>
    </PageShell>
  );
}
