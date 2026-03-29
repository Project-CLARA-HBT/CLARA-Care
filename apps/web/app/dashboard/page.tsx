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
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống"
};

const MODULE_LINKS = [
  { href: "/selfmed", label: "Tủ thuốc cá nhân", description: "Quản lý tủ thuốc permanent, OCR hóa đơn và auto DDI." },
  { href: "/careguard", label: "Kiểm tra an toàn thuốc", description: "Đánh giá nhanh triệu chứng, thuốc và dị ứng." },
  { href: "/scribe", label: "Trợ lý ghi chép y khoa", description: "Tạo SOAP note từ transcript buổi khám." },
  { href: "/research", label: "Không gian hỏi đáp nghiên cứu", description: "Hỏi đáp chuyên sâu với nguồn tham chiếu." },
  { href: "/council", label: "Hội chẩn AI", description: "Điểm truy cập luồng hội chẩn đa chuyên khoa." },
  {
    href: "/dashboard/ecosystem",
    label: "Trung tâm hệ sinh thái",
    description: "Theo dõi tình trạng đối tác, điểm tin cậy dữ liệu và cảnh báo liên thông."
  },
  {
    href: "/dashboard/control-tower",
    label: "Control Tower RAG",
    description: "Quản trị nguồn RAG, bật/tắt fallback DeepSeek và cấu hình flow trả lời."
  },
  {
    href: "/admin/overview",
    label: "Admin Dashboard",
    description: "Dashboard riêng cho quản trị kỹ thuật: RAG sources, answer flow, observability."
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

function toneFromStatus(value: string): {
  label: string;
  badgeClass: string;
  panelClass: string;
} {
  const status = value.toLowerCase();

  if (["ok", "healthy", "up", "pass", "ready"].some((token) => status.includes(token))) {
    return {
      label: "Ổn định",
      badgeClass: "text-emerald-700 bg-emerald-100 border-emerald-200",
      panelClass: "border-emerald-200/70 bg-emerald-50/70"
    };
  }

  if (["warn", "warning", "degraded", "slow", "unstable"].some((token) => status.includes(token))) {
    return {
      label: "Suy giảm",
      badgeClass: "text-amber-700 bg-amber-100 border-amber-200",
      panelClass: "border-amber-200/70 bg-amber-50/70"
    };
  }

  if (["down", "fail", "error", "critical", "unhealthy"].some((token) => status.includes(token))) {
    return {
      label: "Cảnh báo",
      badgeClass: "text-rose-700 bg-rose-100 border-rose-200",
      panelClass: "border-rose-200/70 bg-rose-50/70"
    };
  }

  return {
    label: "Chưa xác định",
    badgeClass: "text-slate-700 bg-slate-100 border-slate-200",
    panelClass: "border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
  };
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

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? "Người dùng cá nhân", [role]);

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
        setHealthError(getErrorText(healthResult.reason, "Không thể lấy trạng thái sức khỏe API."));
      }

      if (metricsResult.status === "fulfilled") {
        const metrics = normalizeSystemMetrics(metricsResult.value);
        setRequestCount(metrics.requestCount);
        setErrorCount(metrics.errorCount);
        setAvgLatencyMs(metrics.avgLatencyMs);
      } else {
        setMetricsError(getErrorText(metricsResult.reason, "Không thể lấy số liệu hệ thống."));
      }

      if (dependenciesResult.status === "fulfilled") {
        const dependencies = normalizeSystemDependencies(dependenciesResult.value);
        setMlStatus(dependencies.mlStatus);
        setMlReachable(dependencies.mlReachable);
      } else {
        setDependenciesError(getErrorText(dependenciesResult.reason, "Không thể lấy trạng thái phụ thuộc hệ thống."));
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

  const healthTone = useMemo(() => toneFromStatus(healthStatus), [healthStatus]);

  const mlStatusLabel =
    mlReachable === true ? "Có thể kết nối" : mlReachable === false ? "Mất kết nối" : mlStatus || "Không xác định";

  const mlTone = useMemo(() => {
    if (mlReachable === true) {
      return {
        label: "Sẵn sàng",
        badgeClass: "text-emerald-700 bg-emerald-100 border-emerald-200",
        panelClass: "border-emerald-200/70 bg-emerald-50/70"
      };
    }

    if (mlReachable === false) {
      return {
        label: "Mất kết nối",
        badgeClass: "text-rose-700 bg-rose-100 border-rose-200",
        panelClass: "border-rose-200/70 bg-rose-50/70"
      };
    }

    return toneFromStatus(mlStatus);
  }, [mlReachable, mlStatus]);

  const errorRate = useMemo(() => {
    if (requestCount === null || errorCount === null || requestCount <= 0) return "--";
    return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format((errorCount / requestCount) * 100)}%`;
  }, [requestCount, errorCount]);

  const alerts = useMemo(() => [healthError, metricsError, dependenciesError].filter(Boolean), [
    healthError,
    metricsError,
    dependenciesError
  ]);

  const metricCards = [
    {
      label: "Tổng request",
      value: formatCount(requestCount),
      hint: "Khối lượng xử lý từ endpoint metrics"
    },
    {
      label: "Tổng lỗi",
      value: formatCount(errorCount),
      hint: "Số request lỗi trong cùng kỳ"
    },
    {
      label: "Latency trung bình",
      value: formatLatencyMs(avgLatencyMs),
      hint: "Độ trễ phản hồi API tổng hợp"
    },
    {
      label: "Error rate",
      value: errorRate,
      hint: "Tỉ lệ lỗi = lỗi / tổng request"
    }
  ];

  return (
    <PageShell
      title="Dashboard"
      description="Bảng điều khiển vận hành CLARA Care với ưu tiên hành động, trạng thái hệ thống và điều hướng module tập trung."
    >
      <div className="space-y-4 lg:space-y-5">
        <section className="relative overflow-hidden rounded-2xl border border-[color:var(--shell-border)] bg-[linear-gradient(120deg,rgba(15,23,42,0.06),rgba(2,132,199,0.08),rgba(13,148,136,0.06))] p-4 sm:p-5">
          <div className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-cyan-400/20 blur-3xl" />
          <div className="pointer-events-none absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-emerald-400/20 blur-3xl" />

          <div className="relative grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div className="space-y-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Command Layer</p>
                  <h2 className="text-xl font-semibold text-[var(--text-primary)] sm:text-2xl">Operational Overview</h2>
                  <p className="text-sm text-[var(--text-secondary)]">Theo dõi hệ thống và điều hướng nhanh đến module đang vận hành.</p>
                </div>
                <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                  Vai trò: {roleLabel}
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-sky-600 bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-70"
                  onClick={onRefreshSystem}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? "Đang làm mới..." : "Làm mới trạng thái"}
                </button>
                <Link
                  href="/role-select"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2 text-sm font-medium text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
                >
                  Đổi vai trò
                </Link>
              </div>

              <div className="grid gap-2 sm:grid-cols-3">
                {MODULE_LINKS.slice(0, 3).map((module) => (
                  <Link
                    key={module.href}
                    href={module.href}
                    className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-brand-soft)]"
                  >
                    <p className="text-xs uppercase tracking-wide text-[var(--text-muted)]">Quick action</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{module.label}</p>
                  </Link>
                ))}
              </div>

              {checkedAt ? (
                <p className="text-xs text-[var(--text-muted)]">Dữ liệu cập nhật: {checkedAt}</p>
              ) : (
                <p className="text-xs text-[var(--text-muted)]">Đang chờ đợt lấy dữ liệu đầu tiên...</p>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <article className={`rounded-xl border p-4 ${healthTone.panelClass}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">API Health</p>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${healthTone.badgeClass}`}>
                    {healthTone.label}
                  </span>
                </div>
                <p className="mt-2 font-mono text-sm font-semibold text-[var(--text-primary)]">{healthStatus}</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{healthMessage}</p>
              </article>

              <article className={`rounded-xl border p-4 ${mlTone.panelClass}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">ML Dependency</p>
                  <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${mlTone.badgeClass}`}>
                    {mlTone.label}
                  </span>
                </div>
                <p className="mt-2 font-mono text-sm font-semibold text-[var(--text-primary)]">{mlStatusLabel}</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">Trạng thái phụ thuộc từ nguồn dependencies hiện có.</p>
              </article>
            </div>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
          {metricCards.map((item) => (
            <article
              key={item.label}
              className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 transition hover:border-[color:var(--shell-border-strong)]"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{item.label}</p>
              <p className="mt-2 font-mono text-2xl font-semibold text-[var(--text-primary)]">{item.value}</p>
              <p className="mt-2 text-xs text-[var(--text-muted)]">{item.hint}</p>
            </article>
          ))}
        </section>

        <section className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
          <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Module Board</p>
                <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Điều hướng tác vụ</h3>
              </div>
              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                {MODULE_LINKS.length} module
              </span>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {MODULE_LINKS.map((module, index) => (
                <Link
                  key={module.href}
                  href={module.href}
                  className="group rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 transition hover:-translate-y-0.5 hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-brand-soft)]"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 font-mono text-xs text-[var(--text-secondary)]">
                      #{String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="text-sm text-[var(--text-muted)] transition group-hover:translate-x-0.5">→</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{module.label}</p>
                  <p className="mt-1 text-sm text-[var(--text-secondary)]">{module.description}</p>
                </Link>
              ))}
            </div>
          </div>

          <aside className="space-y-4">
            <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Watchlist</p>
              <h3 className="mt-1 text-base font-semibold text-[var(--text-primary)]">Cảnh báo vận hành</h3>

              {alerts.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {alerts.map((alert) => (
                    <p key={alert} className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                      {alert}
                    </p>
                  ))}
                </div>
              ) : (
                <p className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  Không có lỗi đồng bộ từ health, metrics, dependencies.
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Data Source</p>
              <div className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
                <p className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  `health`: trạng thái và thông điệp API
                </p>
                <p className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  `metrics`: request count, error count, latency
                </p>
                <p className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2">
                  `dependencies`: tình trạng kết nối dịch vụ ML
                </p>
              </div>
            </section>
          </aside>
        </section>
      </div>
    </PageShell>
  );
}
