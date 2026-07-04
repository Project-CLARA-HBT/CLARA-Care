"use client";

import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import {
  SocialReport,
  actOnReport,
  listReports,
  SocialUnavailableError
} from "@/lib/social";

// Admin moderation queue for the CLARA community platform.
//
// Lists open reports and lets an admin dismiss (keep content) or remove
// (soft-delete the post/comment). Every action is server-audited PII-free.
// Admin-gated at the API (403 for non-admin) and hidden from nav for others.

function reasonLabel(reason: string): string {
  switch (reason) {
    case "user_report":
      return "Người dùng báo cáo";
    case "spam":
      return "Spam";
    case "harassment":
      return "Quấy rối";
    default:
      return reason || "Khác";
  }
}

export default function CommunityModerationPage() {
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<SocialReport[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setReports(await listReports());
    } catch (err) {
      if (err instanceof SocialUnavailableError) {
        setUnavailable(true);
      } else {
        setError("Không thể tải hàng đợi kiểm duyệt.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = useCallback(
    async (id: number, action: "dismiss" | "remove") => {
      setBusyId(id);
      try {
        await actOnReport(id, action);
        setReports((prev) => prev.filter((r) => r.id !== id));
      } catch {
        setError("Không thể xử lý báo cáo. Vui lòng thử lại.");
      } finally {
        setBusyId(null);
      }
    },
    []
  );

  if (unavailable) {
    return (
      <PageShell title="Kiểm duyệt cộng đồng" description="Hàng đợi báo cáo nội dung cộng đồng.">
        <p className="text-sm text-[var(--text-secondary)]">
          Tính năng cộng đồng đang tắt.
        </p>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Kiểm duyệt cộng đồng"
      description="Xem xét các báo cáo nội dung. Gỡ nội dung vi phạm hoặc bỏ qua báo cáo."
    >
      <div className="space-y-4">
        {error ? (
          <div className="rounded-xl border border-red-300/50 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="text-sm text-[var(--text-secondary)]">Đang tải…</p>
        ) : reports.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">
            Không có báo cáo nào đang chờ xử lý.
          </p>
        ) : (
          <ul className="space-y-3">
            {reports.map((r) => (
              <li
                key={r.id}
                className="flex flex-col gap-3 rounded-2xl border border-[var(--border-subtle)] p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {r.target_type === "post" ? "Bài viết" : "Bình luận"} #{r.target_id}
                  </p>
                  <p className="mt-1 text-xs text-[var(--text-secondary)]">
                    Lý do: {reasonLabel(r.reason)} · {new Date(r.created_at).toLocaleString("vi-VN")}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    disabled={busyId === r.id}
                    onClick={() => act(r.id, "dismiss")}
                    className="rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
                  >
                    Bỏ qua
                  </button>
                  <button
                    type="button"
                    disabled={busyId === r.id}
                    onClick={() => act(r.id, "remove")}
                    className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
                  >
                    Gỡ nội dung
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PageShell>
  );
}
