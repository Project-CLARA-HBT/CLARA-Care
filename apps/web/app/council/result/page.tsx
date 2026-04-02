"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilMetricCard, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { clearCouncilSnapshot, CouncilRunSnapshot, loadCouncilSnapshot } from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

export default function CouncilResultPage() {
  const [snapshot, setSnapshot] = useState<CouncilRunSnapshot | null>(null);

  useEffect(() => {
    setSnapshot(loadCouncilSnapshot());
  }, []);

  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);

  return (
    <PageShell
      title="Council Result"
      description="Kết quả hội chẩn gần nhất ở dạng gọn, dễ đọc."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        {!view ? (
          <CouncilEmptyState
            title="Chưa có dữ liệu hội chẩn"
            description="Hãy tạo ca mới để có kết quả hiển thị ở đây."
          />
        ) : (
          <>
            <CouncilSection eyebrow="Summary" title="Tóm tắt kết quả">
              <div className="grid gap-3 md:grid-cols-4">
                <CouncilMetricCard label="Thời gian" value={view.createdAtLabel} />
                <CouncilMetricCard label="Độ khẩn" value={view.urgencyLabel} />
                <CouncilMetricCard label="Chuyên khoa" value={String(view.requestSummary.specialists.length)} hint={view.requestSummary.specialists.join(", ")} />
                <CouncilMetricCard label="Conflict" value={String(view.summary.conflicts.length)} />
              </div>

              {view.summary.escalationReason ? (
                <p className="mt-3 rounded-xl border border-red-300/40 bg-red-50/80 px-3 py-2 text-sm text-red-700 dark:border-red-700/45 dark:bg-red-950/20 dark:text-red-300">
                  Lý do leo thang: {view.summary.escalationReason}
                </p>
              ) : null}

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Final Recommendation</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {view.summary.finalRecommendation || "Không có khuyến nghị cuối trong snapshot này."}
                  </p>
                </article>

                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Consensus</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {view.summary.consensus || "Không có nội dung đồng thuận."}
                  </p>
                </article>
              </div>
            </CouncilSection>

            <CouncilSection eyebrow="Risk Notes" title="Điểm cần lưu ý">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Conflict List</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.conflicts} emptyText="Không có conflict nổi bật." />
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Divergence</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.divergence} emptyText="Không có divergence nổi bật." />
                  </div>
                </div>
              </div>
            </CouncilSection>

            <section className="flex flex-wrap gap-2">
              <Link
                href="/council"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-primary)]"
              >
                Về landing
              </Link>
              <Link
                href="/council/new"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white"
              >
                Hội chẩn ca mới
              </Link>
              <button
                type="button"
                onClick={() => {
                  clearCouncilSnapshot();
                  setSnapshot(null);
                }}
                className="inline-flex min-h-[44px] items-center rounded-xl border border-red-300/55 bg-red-100/80 px-4 text-sm font-semibold text-red-800 dark:border-red-700/45 dark:bg-red-950/30 dark:text-red-200"
              >
                Xóa snapshot cục bộ
              </button>
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
