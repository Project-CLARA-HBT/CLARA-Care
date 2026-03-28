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
  admin: "Quản trị hệ thống",
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
  },
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

  const mlStatusLabel =
    mlReachable === true ? "Có thể kết nối" : mlReachable === false ? "Mất kết nối" : mlStatus || "Không xác định";

  const mlStatusColor =
    mlReachable === true
      ? "text-emerald-700"
      : mlReachable === false
        ? "text-red-700"
        : "text-slate-700";

  return (
    <PageShell title="Bảng điều khiển">
      <div className="grid gap-4 md:grid-cols-2">
        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Vai trò truy cập</p>
          <p className="text-xl font-semibold text-slate-900">{roleLabel}</p>
          <p className="text-sm text-slate-600">Vai trò hiện tại quyết định menu và quyền truy cập tính năng.</p>
          <Link href="/role-select" className="inline-block text-sm font-medium text-blue-600 hover:underline">
            Đổi vai trò
          </Link>
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Giám sát hệ thống</p>
          <p className="text-sm text-slate-600">Theo dõi nhanh trạng thái API, số liệu vận hành và phụ thuộc ML.</p>
          {checkedAt ? <p className="text-xs text-slate-500">Cập nhật gần nhất: {checkedAt}</p> : null}
          <button
            type="button"
            className="rounded bg-primary px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
            onClick={onRefreshSystem}
            disabled={isRefreshing}
          >
            {isRefreshing ? "Đang làm mới..." : "Làm mới"}
          </button>
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Trạng thái sức khỏe API</p>
          <p className="text-lg font-semibold text-slate-900">{healthStatus}</p>
          <p className="text-sm text-slate-600">{healthMessage}</p>
          {healthError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{healthError}</p>
          ) : null}
        </section>

        <section className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tóm tắt số liệu hệ thống</p>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Số yêu cầu</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatCount(requestCount)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Số lỗi</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatCount(errorCount)}</p>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">Độ trễ trung bình</p>
              <p className="mt-1 text-lg font-semibold text-slate-900">{formatLatencyMs(avgLatencyMs)}</p>
            </div>
          </div>
          {metricsError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{metricsError}</p>
          ) : null}
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Trạng thái phụ thuộc hệ thống</p>
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Dịch vụ ML</p>
            <p className={`mt-1 text-lg font-semibold ${mlStatusColor}`}>{mlStatusLabel}</p>
          </div>
          {dependenciesError ? (
            <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {dependenciesError}
            </p>
          ) : null}
        </section>

        <section className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 md:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Tính năng</p>
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
