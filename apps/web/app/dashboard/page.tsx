"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import api from "@/lib/http-client";
import { listResearchConversations } from "@/lib/research";
import { getCabinet } from "@/lib/selfmed";
import {
  getApiHealth,
  getSystemDependencies,
  getSystemMetrics,
  normalizeApiHealth,
  normalizeSystemDependencies,
  normalizeSystemMetrics
} from "@/lib/system";

type AuthMePayload = {
  subject?: string;
  role?: UserRole;
  full_name?: string;
};

type QuickAction = {
  href: string;
  tag: string;
  label: string;
  detail: string;
};

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống"
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: "/selfmed/add",
    tag: "SelfMed",
    label: "Thêm thuốc mới",
    detail: "Nhập tay hoặc OCR để cập nhật tủ thuốc."
  },
  {
    href: "/careguard",
    tag: "CareGuard",
    label: "Check tương tác DDI",
    detail: "Kiểm tra rủi ro tương tác theo tủ thuốc hiện tại."
  },
  {
    href: "/research",
    tag: "Research",
    label: "Nghiên cứu chuyên sâu",
    detail: "Hỏi đáp có citation và flow verification."
  },
  {
    href: "/selfmed",
    tag: "Cabinet",
    label: "Rà soát tủ thuốc",
    detail: "Xem thuốc sắp hết hạn hoặc dữ liệu thiếu liều dùng."
  }
];

function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(value);
}

function formatDateTime(value: number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("vi-VN", {
    hour12: false,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function getGreeting(now: Date): { title: string; subtitle: string } {
  const hour = now.getHours();
  if (hour < 12) {
    return {
      title: "Good morning",
      subtitle: "Bắt đầu ngày mới: rà soát thuốc và ưu tiên an toàn trước khi dùng."
    };
  }
  if (hour < 18) {
    return {
      title: "Good afternoon",
      subtitle: "Giữ điều trị ổn định: kiểm tra tương tác và cập nhật tủ thuốc hôm nay."
    };
  }
  return {
    title: "Good evening",
    subtitle: "Tổng kết cuối ngày: xác nhận thuốc đã dùng và kế hoạch ngày mai."
  };
}

function toneFromStatus(status: string): "ok" | "warn" | "error" | "neutral" {
  const normalized = status.toLowerCase();
  if (["ok", "healthy", "up", "pass", "ready"].some((token) => normalized.includes(token))) return "ok";
  if (["warn", "warning", "degraded", "slow", "unstable"].some((token) => normalized.includes(token))) return "warn";
  if (["down", "fail", "error", "critical", "unhealthy"].some((token) => normalized.includes(token))) return "error";
  return "neutral";
}

function badgeClassForTone(tone: "ok" | "warn" | "error" | "neutral"): string {
  if (tone === "ok") return "border-emerald-200 bg-emerald-100 text-emerald-700";
  if (tone === "warn") return "border-amber-200 bg-amber-100 text-amber-700";
  if (tone === "error") return "border-rose-200 bg-rose-100 text-rose-700";
  return "border-slate-200 bg-slate-100 text-slate-700";
}

function panelClassForTone(tone: "ok" | "warn" | "error" | "neutral"): string {
  if (tone === "ok") return "border-emerald-200/70 bg-emerald-50/70";
  if (tone === "warn") return "border-amber-200/70 bg-amber-50/70";
  if (tone === "error") return "border-rose-200/70 bg-rose-50/70";
  return "border-[color:var(--shell-border)] bg-[var(--surface-panel)]";
}

export default function DashboardPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [displayName, setDisplayName] = useState("bạn");
  const [userSubject, setUserSubject] = useState("");

  const [healthStatus, setHealthStatus] = useState("unknown");
  const [healthMessage, setHealthMessage] = useState("Chưa có dữ liệu health.");
  const [mlStatus, setMlStatus] = useState("unknown");
  const [mlReachable, setMlReachable] = useState<boolean | null>(null);

  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [errorCount, setErrorCount] = useState<number | null>(null);
  const [avgLatencyMs, setAvgLatencyMs] = useState<number | null>(null);

  const [cabinetCount, setCabinetCount] = useState<number | null>(null);
  const [expiringSoonCount, setExpiringSoonCount] = useState<number | null>(null);
  const [expiredCount, setExpiredCount] = useState<number | null>(null);
  const [missingDosageCount, setMissingDosageCount] = useState<number | null>(null);

  const [recentQueries, setRecentQueries] = useState<Array<{ id: string; query: string; createdAt: number }>>([]);
  const [alerts, setAlerts] = useState<string[]>([]);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? ROLE_LABELS.normal, [role]);
  const greeting = useMemo(() => getGreeting(new Date()), []);

  const ddiRiskLabel = useMemo(() => {
    const total = cabinetCount ?? 0;
    if (total < 2) return "Thấp";
    if (total < 5) return "Trung bình";
    return "Cao";
  }, [cabinetCount]);

  const pendingActions = useMemo(() => {
    let count = 0;
    if ((cabinetCount ?? 0) >= 2) count += 1;
    if ((expiringSoonCount ?? 0) > 0) count += expiringSoonCount ?? 0;
    if ((expiredCount ?? 0) > 0) count += expiredCount ?? 0;
    if ((missingDosageCount ?? 0) > 0) count += missingDosageCount ?? 0;
    return count;
  }, [cabinetCount, expiringSoonCount, expiredCount, missingDosageCount]);

  const refreshDashboard = useCallback(async () => {
    setIsRefreshing(true);
    const nextAlerts: string[] = [];

    try {
      const [healthResult, metricsResult, dependenciesResult, cabinetResult, meResult, conversationsResult] = await Promise.allSettled([
        getApiHealth(),
        getSystemMetrics(),
        getSystemDependencies(),
        getCabinet(),
        api.get<AuthMePayload>("/auth/me"),
        listResearchConversations(5)
      ]);

      if (healthResult.status === "fulfilled") {
        const health = normalizeApiHealth(healthResult.value);
        setHealthStatus(health.status);
        setHealthMessage(health.message);
      } else {
        nextAlerts.push("Không thể lấy trạng thái sức khỏe API.");
      }

      if (metricsResult.status === "fulfilled") {
        const metrics = normalizeSystemMetrics(metricsResult.value);
        setRequestCount(metrics.requestCount);
        setErrorCount(metrics.errorCount);
        setAvgLatencyMs(metrics.avgLatencyMs);
      } else {
        nextAlerts.push("Không thể lấy số liệu hệ thống.");
      }

      if (dependenciesResult.status === "fulfilled") {
        const dependencies = normalizeSystemDependencies(dependenciesResult.value);
        setMlStatus(dependencies.mlStatus);
        setMlReachable(dependencies.mlReachable);
      } else {
        nextAlerts.push("Không thể lấy trạng thái phụ thuộc hệ thống.");
      }

      if (cabinetResult.status === "fulfilled") {
        const items = cabinetResult.value.items ?? [];
        const now = Date.now();
        const dayMs = 24 * 60 * 60 * 1000;
        const soonBoundary = now + 30 * dayMs;

        let soon = 0;
        let expired = 0;
        let missingDosage = 0;

        items.forEach((item) => {
          if (!String(item.dosage ?? "").trim()) {
            missingDosage += 1;
          }
          if (!item.expires_on) return;
          const expireMs = Date.parse(item.expires_on);
          if (!Number.isFinite(expireMs)) return;
          if (expireMs < now) {
            expired += 1;
          } else if (expireMs <= soonBoundary) {
            soon += 1;
          }
        });

        setCabinetCount(items.length);
        setExpiringSoonCount(soon);
        setExpiredCount(expired);
        setMissingDosageCount(missingDosage);
      } else {
        nextAlerts.push("Không thể tải dữ liệu tủ thuốc.");
      }

      if (meResult.status === "fulfilled") {
        const me = meResult.value.data ?? {};
        if (me.role) {
          setRole(me.role);
        }
        const subject = String(me.subject ?? "");
        const fullName = String(me.full_name ?? "").trim();
        const inferredName = subject.includes("@") ? subject.split("@")[0] : "bạn";
        setDisplayName(fullName || inferredName || "bạn");
        setUserSubject(subject);
      }

      if (conversationsResult.status === "fulfilled") {
        const mapped = conversationsResult.value
          .map((item) => ({
            id: String(item.id),
            query: String(item.query ?? "").trim(),
            createdAt: Number(item.createdAt ?? Date.now())
          }))
          .filter((item) => item.query);
        setRecentQueries(mapped);
      } else {
        nextAlerts.push("Không thể tải lịch sử research gần đây.");
      }

      setAlerts(nextAlerts);
      setCheckedAt(new Date().toLocaleString("vi-VN"));
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    setRole(getRole());
    void refreshDashboard();
  }, [refreshDashboard]);

  const healthTone = toneFromStatus(healthStatus);
  const mlTone = toneFromStatus(
    mlReachable === true ? "ok" : mlReachable === false ? "error" : mlStatus
  );

  const medicationCards = [
    {
      label: "Số lượng thuốc",
      value: formatCount(cabinetCount),
      hint: "Đang quản lý trong tủ thuốc"
    },
    {
      label: "Sắp hết hạn (30 ngày)",
      value: formatCount(expiringSoonCount),
      hint: "Nên ưu tiên thay thế"
    },
    {
      label: "Đã hết hạn",
      value: formatCount(expiredCount),
      hint: "Cần loại bỏ để tránh nhầm"
    },
    {
      label: "Thiếu liều dùng",
      value: formatCount(missingDosageCount),
      hint: "Nên bổ sung để check DDI chính xác"
    }
  ];

  return (
    <PageShell
      title="Dashboard"
      description="Trung tâm điều phối hàng ngày cho CLARA: tủ thuốc, cảnh báo tương tác và tác vụ ưu tiên."
    >
      <div className="space-y-5 lg:space-y-6">
        <section className="relative overflow-hidden rounded-3xl border border-[color:var(--shell-border)] bg-[linear-gradient(120deg,rgba(2,132,199,0.10),rgba(15,23,42,0.08),rgba(13,148,136,0.08))] p-5 sm:p-6">
          <div className="pointer-events-none absolute -right-16 -top-16 h-44 w-44 rounded-full bg-sky-400/25 blur-3xl" />
          <div className="pointer-events-none absolute -left-10 bottom-0 h-36 w-36 rounded-full bg-emerald-400/20 blur-3xl" />

          <div className="relative grid gap-4 xl:grid-cols-[1.45fr_1fr]">
            <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Daily Command Center</p>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)] sm:text-3xl">
                {greeting.title}, {displayName}
              </h2>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{greeting.subtitle}</p>

              <div className="mt-4 flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                  Vai trò: {roleLabel}
                </span>
                <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                  DDI risk: {ddiRiskLabel}
                </span>
                {userSubject ? (
                  <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                    {userSubject}
                  </span>
                ) : null}
                <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs font-medium text-[var(--text-secondary)]">
                  {checkedAt ? `Cập nhật: ${checkedAt}` : "Đang đồng bộ dữ liệu..."}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={refreshDashboard}
                  disabled={isRefreshing}
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-sky-600 bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-70"
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
            </div>

            <aside className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Bạn muốn làm gì hôm nay?</p>
              <div className="mt-3 space-y-2">
                {QUICK_ACTIONS.map((action) => (
                  <Link
                    key={action.href}
                    href={action.href}
                    className="block rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-brand-soft)]"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
                        {action.tag}
                      </span>
                      <span className="text-sm text-[var(--text-muted)]">→</span>
                    </div>
                    <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{action.label}</p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">{action.detail}</p>
                  </Link>
                ))}
              </div>
            </aside>
          </div>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
          {medicationCards.map((item) => (
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

        <section className="grid gap-4 xl:grid-cols-[1.45fr_0.55fr]">
          <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">Recent Research Activity</p>
            <div className="mt-3 space-y-2">
              {recentQueries.length > 0 ? (
                recentQueries.map((query) => (
                  <article
                    key={query.id}
                    className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                  >
                    <p className="line-clamp-2 text-sm text-[var(--text-primary)]">{query.query}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{formatDateTime(query.createdAt)}</p>
                  </article>
                ))
              ) : (
                <p className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-secondary)]">
                  Chưa có lịch sử research gần đây.
                </p>
              )}
            </div>
          </div>

          <aside className="space-y-4">
            <section className={`rounded-2xl border p-4 ${panelClassForTone(healthTone)}`}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">API Health</p>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClassForTone(healthTone)}`}>
                  {healthStatus}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{healthMessage}</p>
            </section>

            <section className={`rounded-2xl border p-4 ${panelClassForTone(mlTone)}`}>
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">ML Runtime</p>
                <span className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeClassForTone(mlTone)}`}>
                  {mlReachable === true ? "reachable" : mlReachable === false ? "offline" : mlStatus}
                </span>
              </div>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                {mlReachable === true ? "Sẵn sàng cho DDI/Research pipeline." : "Kiểm tra service ML hoặc bật fallback mode."}
              </p>
            </section>

            <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">System Metrics</p>
              <div className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
                <p>Request tổng: <span className="font-semibold text-[var(--text-primary)]">{formatCount(requestCount)}</span></p>
                <p>Error tổng: <span className="font-semibold text-[var(--text-primary)]">{formatCount(errorCount)}</span></p>
                <p>Latency TB: <span className="font-semibold text-[var(--text-primary)]">{avgLatencyMs === null ? "--" : `${avgLatencyMs.toFixed(2)} ms`}</span></p>
                <p>Pending actions: <span className="font-semibold text-[var(--text-primary)]">{formatCount(pendingActions)}</span></p>
              </div>
            </section>
          </aside>
        </section>

        {alerts.length > 0 ? (
          <section className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-rose-700">Watchlist</p>
            <div className="mt-3 space-y-2">
              {alerts.map((alert) => (
                <p key={alert} className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm text-rose-700">
                  {alert}
                </p>
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </PageShell>
  );
}
