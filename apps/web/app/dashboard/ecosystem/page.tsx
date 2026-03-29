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

function formatHours(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value)} h`;
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

function severityAccentClass(severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === "critical") return "border-l-red-500";
  if (normalized === "warning") return "border-l-amber-500";
  if (normalized === "info") return "border-l-blue-500";
  return "border-l-slate-400";
}

function trustScoreClass(score: number | null): string {
  if (score === null || !Number.isFinite(score)) return "border-slate-200 bg-slate-100 text-slate-700";
  if (score >= 85) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (score >= 70) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-red-200 bg-red-50 text-red-700";
}

function driftRiskClass(value: string): string {
  const normalized = value.toLowerCase();
  if (normalized === "low" || normalized === "thap") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (normalized === "medium" || normalized === "trung binh" || normalized === "trung bình") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (normalized === "high" || normalized === "cao" || normalized === "critical") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function acknowledgedClass(value: boolean | null): string {
  if (value === true) return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (value === false) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function barWidth(value: number | null, max: number): string {
  if (value === null || !Number.isFinite(value) || value <= 0) return "0%";
  return `${Math.max(6, Math.min(100, (value / max) * 100))}%`;
}

export default function EcosystemCenterPage() {
  const [snapshot, setSnapshot] = useState<SystemEcosystemSnapshot>(EMPTY_SNAPSHOT);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);

  const summaryCards = useMemo(() => {
    const partnerDown = snapshot.summary.partnersDown ?? 0;
    const trustLow = snapshot.summary.trustLowCount ?? 0;
    const criticalAlerts = snapshot.summary.criticalAlertCount ?? 0;
    return [
      {
        label: "Tổng đối tác",
        value: formatCount(snapshot.summary.partnersTotal),
        helper: "Endpoint được monitor liên tục",
        tone: "neutral"
      },
      {
        label: "Đối tác đang lỗi",
        value: formatCount(snapshot.summary.partnersDown),
        helper: partnerDown > 0 ? "Cần xử lý ngay" : "Không phát hiện downtime",
        tone: partnerDown > 0 ? "danger" : "good"
      },
      {
        label: "Nguồn có trust thấp",
        value: formatCount(snapshot.summary.trustLowCount),
        helper: trustLow > 0 ? "Ưu tiên kiểm tra đồng bộ" : "Mức tin cậy ổn định",
        tone: trustLow > 0 ? "warning" : "good"
      },
      {
        label: "Cảnh báo nghiêm trọng",
        value: formatCount(snapshot.summary.criticalAlertCount),
        helper: criticalAlerts > 0 ? "Yêu cầu phản ứng khẩn cấp" : "Không có critical alert",
        tone: criticalAlerts > 0 ? "danger" : "good"
      }
    ];
  }, [
    snapshot.summary.criticalAlertCount,
    snapshot.summary.partnersDown,
    snapshot.summary.partnersTotal,
    snapshot.summary.trustLowCount
  ]);

  const partnerHealthOverview = useMemo(() => {
    let healthy = 0;
    let degraded = 0;
    let down = 0;

    snapshot.partnerHealth.forEach((row) => {
      const normalized = row.status.toLowerCase();
      if (normalized === "ok" || normalized === "healthy") {
        healthy += 1;
        return;
      }
      if (normalized === "degraded" || normalized === "warning") {
        degraded += 1;
        return;
      }
      if (normalized === "down" || normalized === "unreachable" || normalized === "error") {
        down += 1;
        return;
      }
      degraded += 1;
    });

    return { healthy, degraded, down };
  }, [snapshot.partnerHealth]);

  const alertOverview = useMemo(() => {
    let critical = 0;
    let warning = 0;
    let info = 0;
    let unacknowledged = 0;

    snapshot.federationAlerts.forEach((alert) => {
      const normalized = alert.severity.toLowerCase();
      if (normalized === "critical") critical += 1;
      else if (normalized === "warning") warning += 1;
      else info += 1;

      if (alert.acknowledged === false || alert.acknowledged === null) {
        unacknowledged += 1;
      }
    });

    return { critical, warning, info, unacknowledged };
  }, [snapshot.federationAlerts]);

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
        setError("Không thể tải trung tâm hệ sinh thái. Vui lòng thử lại.");
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
    <PageShell title="Technical Monitoring Hub">
      <div className="space-y-5">
        <section className="rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 text-slate-100 shadow-lg shadow-slate-900/10 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-200">Ecosystem Control Plane</p>
              <h2 className="text-xl font-semibold tracking-tight text-white sm:text-2xl">Technical Monitoring Hub</h2>
              <p className="max-w-3xl text-sm leading-6 text-slate-300">
                Quan sát sức khỏe liên thông toàn hệ thống với 4 vùng trọng tâm: summary vận hành, partner health, trust scores
                và hàng đợi alerts cần phản ứng.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/dashboard"
                className="inline-flex min-h-11 items-center rounded-lg border border-slate-500 px-3 py-1.5 text-sm font-medium text-slate-100 transition hover:border-slate-300 hover:bg-slate-700/70"
              >
                Về bảng điều khiển
              </Link>
              <button
                type="button"
                onClick={onRefresh}
                disabled={isRefreshing}
                className="inline-flex min-h-11 items-center rounded-lg bg-cyan-500 px-3 py-1.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
              >
                {isRefreshing ? "Đang làm mới..." : "Làm mới snapshot"}
              </button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-300">
            <span className="rounded-full border border-slate-600 bg-slate-800/70 px-2.5 py-1">
              Cập nhật: {snapshot.generatedAt ? formatDateTime(snapshot.generatedAt) : "chưa có dữ liệu"}
            </span>
            <span className="rounded-full border border-slate-600 bg-slate-800/70 px-2.5 py-1">
              Partners: {formatCount(snapshot.summary.partnersTotal)}
            </span>
            <span className="rounded-full border border-slate-600 bg-slate-800/70 px-2.5 py-1">
              Unacknowledged alerts: {formatCount(alertOverview.unacknowledged)}
            </span>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((card) => (
              <article
                key={card.label}
                className={`rounded-xl border bg-white/95 p-3 text-slate-900 ${
                  card.tone === "danger"
                    ? "border-red-200"
                    : card.tone === "warning"
                      ? "border-amber-200"
                      : card.tone === "good"
                        ? "border-emerald-200"
                        : "border-slate-200"
                }`}
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{card.label}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-slate-900">{card.value}</p>
                <p className="mt-2 text-xs text-slate-600">{card.helper}</p>
              </article>
            ))}
          </div>
        </section>

        {isLoading ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Đang tải dữ liệu monitoring hub...
          </div>
        ) : null}

        {forbidden ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Bạn không đủ quyền truy cập Trung tâm hệ sinh thái. Tính năng này chỉ dành cho vai trò bác sĩ (403).
          </div>
        ) : null}

        {error && !forbidden ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        ) : null}

        {!isLoading && !forbidden ? (
          <>
            <div className="grid gap-4 xl:grid-cols-[1.45fr_1fr]">
              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Partner Health Matrix</p>
                    <h3 className="mt-1 text-base font-semibold text-slate-900">Tình trạng đối tác tích hợp</h3>
                  </div>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 font-medium text-emerald-700">
                      Healthy: {formatCount(partnerHealthOverview.healthy)}
                    </span>
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 font-medium text-amber-700">
                      Degraded: {formatCount(partnerHealthOverview.degraded)}
                    </span>
                    <span className="rounded-full border border-red-200 bg-red-50 px-2 py-1 font-medium text-red-700">
                      Down: {formatCount(partnerHealthOverview.down)}
                    </span>
                  </div>
                </div>

                {snapshot.partnerHealth.length ? (
                  <div className="mt-4 space-y-3">
                    <div className="space-y-2 md:hidden">
                      {snapshot.partnerHealth.map((row) => (
                        <article key={`${row.partner}-${row.lastCheck}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-900">{row.partner}</p>
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(row.status)}`}>
                              {row.status}
                            </span>
                          </div>
                          <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                            <div>
                              <dt>Độ trễ</dt>
                              <dd className="font-medium text-slate-800">{formatMs(row.latencyMs)}</dd>
                            </div>
                            <div>
                              <dt>Tỷ lệ lỗi</dt>
                              <dd className="font-medium text-slate-800">{formatPercent(row.errorRatePct)}</dd>
                            </div>
                            <div className="col-span-2">
                              <dt>Kiểm tra gần nhất</dt>
                              <dd className="font-medium text-slate-800">{formatDateTime(row.lastCheck)}</dd>
                            </div>
                          </dl>
                        </article>
                      ))}
                    </div>

                    <div className="hidden md:block">
                      <div className="overflow-x-auto rounded-xl border border-slate-200">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
                            <tr>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Đối tác
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Trạng thái
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Độ trễ
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Tỷ lệ lỗi
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Kiểm tra gần nhất
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 bg-white">
                            {snapshot.partnerHealth.map((row) => (
                              <tr key={`${row.partner}-${row.lastCheck}`} className="align-top odd:bg-white even:bg-slate-50/45">
                                <td className="px-3 py-2.5 font-medium text-slate-900">{row.partner}</td>
                                <td className="px-3 py-2.5">
                                  <span
                                    className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClass(row.status)}`}
                                  >
                                    {row.status}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-slate-700">
                                  <div className="space-y-1.5">
                                    <p className="font-medium tabular-nums text-slate-900">{formatMs(row.latencyMs)}</p>
                                    <div className="h-1.5 rounded-full bg-slate-200">
                                      <div
                                        className="h-1.5 rounded-full bg-cyan-500"
                                        style={{ width: barWidth(row.latencyMs, 1500) }}
                                        aria-hidden
                                      />
                                    </div>
                                  </div>
                                </td>
                                <td className="px-3 py-2.5 font-medium tabular-nums text-slate-700">{formatPercent(row.errorRatePct)}</td>
                                <td className="px-3 py-2.5 text-slate-700">{formatDateTime(row.lastCheck)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">Chưa có dữ liệu tình trạng đối tác.</p>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Data Trust Scores</p>
                  <h3 className="mt-1 text-base font-semibold text-slate-900">Độ tin cậy nguồn dữ liệu</h3>
                  <p className="mt-1 text-xs text-slate-500">Theo dõi score, freshness và drift risk để phát hiện lệch dữ liệu sớm.</p>
                </div>

                {snapshot.dataTrustScores.length ? (
                  <div className="mt-4 space-y-3">
                    <div className="space-y-2 md:hidden">
                      {snapshot.dataTrustScores.map((row) => (
                        <article key={`${row.source}-${row.lastRefresh}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-slate-900">{row.source}</p>
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${trustScoreClass(row.trustScore)}`}>
                              score: {formatCount(row.trustScore)}
                            </span>
                          </div>
                          <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                            <div>
                              <dt>Freshness</dt>
                              <dd className="font-medium text-slate-800">{formatHours(row.freshnessHours)}</dd>
                            </div>
                            <div>
                              <dt>Drift risk</dt>
                              <dd>
                                <span
                                  className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase ${driftRiskClass(row.driftRisk)}`}
                                >
                                  {row.driftRisk}
                                </span>
                              </dd>
                            </div>
                            <div className="col-span-2">
                              <dt>Lần refresh gần nhất</dt>
                              <dd className="font-medium text-slate-800">{formatDateTime(row.lastRefresh)}</dd>
                            </div>
                          </dl>
                        </article>
                      ))}
                    </div>

                    <div className="hidden md:block">
                      <div className="overflow-x-auto rounded-xl border border-slate-200">
                        <table className="min-w-full text-left text-sm">
                          <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
                            <tr>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Nguồn dữ liệu
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Điểm trust
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Freshness
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Drift risk
                              </th>
                              <th scope="col" className="px-3 py-2.5 font-semibold">
                                Lần refresh gần nhất
                              </th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 bg-white">
                            {snapshot.dataTrustScores.map((row) => (
                              <tr key={`${row.source}-${row.lastRefresh}`} className="align-top odd:bg-white even:bg-slate-50/45">
                                <td className="px-3 py-2.5 font-medium text-slate-900">{row.source}</td>
                                <td className="px-3 py-2.5">
                                  <div className="space-y-1.5">
                                    <span
                                      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${trustScoreClass(row.trustScore)}`}
                                    >
                                      {formatCount(row.trustScore)}
                                    </span>
                                    <div className="h-1.5 rounded-full bg-slate-200">
                                      <div
                                        className="h-1.5 rounded-full bg-violet-500"
                                        style={{ width: barWidth(row.trustScore, 100) }}
                                        aria-hidden
                                      />
                                    </div>
                                  </div>
                                </td>
                                <td className="px-3 py-2.5 font-medium tabular-nums text-slate-700">{formatHours(row.freshnessHours)}</td>
                                <td className="px-3 py-2.5">
                                  <span
                                    className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${driftRiskClass(row.driftRisk)}`}
                                  >
                                    {row.driftRisk}
                                  </span>
                                </td>
                                <td className="px-3 py-2.5 text-slate-700">{formatDateTime(row.lastRefresh)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">Chưa có dữ liệu điểm tin cậy.</p>
                )}
              </section>
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Federation Alerts</p>
                  <h3 className="mt-1 text-base font-semibold text-slate-900">Alert queue theo mức độ ưu tiên</h3>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full border border-red-200 bg-red-50 px-2 py-1 font-medium text-red-700">
                    Critical: {formatCount(alertOverview.critical)}
                  </span>
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-1 font-medium text-amber-700">
                    Warning: {formatCount(alertOverview.warning)}
                  </span>
                  <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 font-medium text-blue-700">
                    Info: {formatCount(alertOverview.info)}
                  </span>
                  <span className="rounded-full border border-slate-200 bg-slate-100 px-2 py-1 font-medium text-slate-700">
                    Chưa xác nhận: {formatCount(alertOverview.unacknowledged)}
                  </span>
                </div>
              </div>

              {snapshot.federationAlerts.length ? (
                <ul className="mt-4 space-y-2.5">
                  {snapshot.federationAlerts.map((alert) => (
                    <li key={alert.id} className={`rounded-xl border border-slate-200 border-l-4 bg-slate-50 p-3 ${severityAccentClass(alert.severity)}`}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${severityClass(alert.severity)}`}
                          >
                            {alert.severity}
                          </span>
                          <p className="text-sm font-semibold text-slate-900">{alert.id}</p>
                          <span className="text-xs text-slate-500">{formatDateTime(alert.createdAt)}</span>
                        </div>
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold uppercase ${acknowledgedClass(alert.acknowledged)}`}
                        >
                          {alert.acknowledged === null ? "unknown" : alert.acknowledged ? "acknowledged" : "unacknowledged"}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">{alert.message}</p>
                      <p className="mt-1 text-xs text-slate-500">Nguồn cảnh báo: {alert.source}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-slate-600">Chưa có cảnh báo liên thông.</p>
              )}
            </section>
          </>
        ) : null}
      </div>
    </PageShell>
  );
}
