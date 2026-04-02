"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { CouncilRunSnapshot, loadCouncilSnapshot } from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

export default function CouncilPage() {
  const [snapshot, setSnapshot] = useState<CouncilRunSnapshot | null>(null);

  useEffect(() => {
    setSnapshot(loadCouncilSnapshot());
  }, []);

  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);

  return (
    <PageShell
      title="Council Workspace"
      description="Giao diện rút gọn: tạo ca mới theo từng bước, sau đó xem kết quả hội chẩn."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <CouncilSection eyebrow="Simple Flow" title="Bắt đầu nhanh">
          <div className="flex flex-wrap gap-2">
            <Link
              href="/council/new"
              className="inline-flex min-h-[46px] items-center rounded-xl border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white"
            >
              Tạo ca mới
            </Link>
            <Link
              href="/council/result"
              className="inline-flex min-h-[46px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-5 text-sm font-semibold text-[var(--text-primary)]"
            >
              Xem kết quả gần nhất
            </Link>
          </div>
          <p className="mt-3 text-sm text-[var(--text-secondary)]">
            Luồng đề xuất: `New Case` -&gt; `Result`. Các tab phụ đã được gom lại để tránh rối giao diện.
          </p>
        </CouncilSection>

        <CouncilSection eyebrow="Latest Snapshot" title="Ca gần nhất">
          {!view ? (
            <p className="text-sm text-[var(--text-secondary)]">
              Chưa có dữ liệu hội chẩn. Hãy tạo ca mới để bắt đầu.
            </p>
          ) : (
            <div className="space-y-3 text-sm text-[var(--text-secondary)]">
              <p>
                <span className="font-semibold text-[var(--text-primary)]">Thời gian:</span> {view.createdAtLabel}
              </p>
              <p>
                <span className="font-semibold text-[var(--text-primary)]">Độ khẩn:</span> {view.urgencyLabel}
              </p>
              <p>
                <span className="font-semibold text-[var(--text-primary)]">Chuyên khoa:</span> {view.requestSummary.specialists.join(", ") || "Không có"}
              </p>
              <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 whitespace-pre-wrap">
                <span className="font-semibold text-[var(--text-primary)]">Khuyến nghị:</span>{" "}
                {view.summary.finalRecommendation || "Không có khuyến nghị cuối trong snapshot này."}
              </p>
            </div>
          )}
        </CouncilSection>
      </div>
    </PageShell>
  );
}
