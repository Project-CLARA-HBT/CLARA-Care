"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilMetricCard, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { getRole, type UserRole } from "@/lib/auth-store";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

export default function CouncilResultPage() {
  const router = useRouter();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [error, setError] = useState("");
  const [role, setRole] = useState<UserRole>("normal");

  useEffect(() => {
    setRole(getRole());
    // The Council surface was viewed (Req 9.1). No PII — coarse view label only.
    trackCouncilViewed({ view: "result" });
  }, []);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("caseId");
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      setQueryCaseId(Math.trunc(parsed));
      return;
    }
    setQueryCaseId(getActiveCouncilCaseId());
  }, []);

  useEffect(() => {
    const load = async () => {
      setError("");
      try {
        let loaded: CouncilCaseRecord;
        if (queryCaseId) {
          loaded = await getCouncilCase(queryCaseId);
        } else {
          loaded = await getLatestCouncilCase();
        }
        setActiveCouncilCaseId(loaded.id);
        setCaseItem(loaded);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải case.");
      }
    };
    if (queryCaseId !== null) {
      void load();
    }
  }, [queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const fmtStrength = (value: number | null): string => {
    if (value == null || Number.isNaN(value)) return "-";
    return value.toFixed(2);
  };

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
            description={error || "Hãy tạo ca mới để có kết quả hiển thị ở đây."}
          />
        ) : (
          <>
            <CouncilSection eyebrow="Summary" title="Tóm tắt kết quả">
              <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-6">
                <CouncilMetricCard label="Thời gian" value={view.createdAtLabel} />
                <CouncilMetricCard label="Độ khẩn" value={view.urgencyLabel} />
                <CouncilMetricCard label="Chuyên khoa" value={String(view.requestSummary.specialists.length)} hint={view.requestSummary.specialists.join(", ")} />
                <CouncilMetricCard label="Conflict" value={String(view.summary.conflicts.length)} />
                <CouncilMetricCard
                  label="Đồng thuận chuyên khoa"
                  value={view.summary.conflicts.length ? "Cần rà soát" : "Chưa thấy bất đồng trọng yếu"}
                  hint="Không phải xác suất hoặc độ tin cậy lâm sàng"
                />
                <CouncilMetricCard
                  label="Rà soát chuyên môn"
                  value={view.quality.requiresHumanHandoff ? "Bắt buộc" : "Cần trước khi dùng"}
                />
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <CouncilMetricCard
                  label="Escalation Priority"
                  value={view.quality.escalationPriority || "routine"}
                  hint={
                    view.quality.recommendedSlaMinutes != null
                      ? `SLA ${view.quality.recommendedSlaMinutes} phút`
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label="Citation Quality"
                  value={fmtStrength(view.quality.citationAverageStrength)}
                  hint={
                    view.quality.citationTotal != null
                      ? `${view.quality.citationTotal} citation(s)`
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label="Strongest Dissent"
                  value={view.quality.strongestDissent || "-"}
                  hint={
                    view.quality.strongestDissentVotes != null
                      ? `${view.quality.strongestDissentVotes} vote`
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label="Tín hiệu nguy cơ theo quy tắc (chỉ theo dõi)"
                  value={view.quality.neuralEnabled ? view.quality.neuralBand || "có tín hiệu" : "chưa bật"}
                  hint="Đây là điểm heuristic chưa hiệu chuẩn; không thay thế phân luồng an toàn hoặc nhận định chuyên môn."
                />
              </div>

              {view.summary.escalationReason ? (
                <p className="mt-3 rounded-xl border border-red-300/40 bg-red-50/80 px-3 py-2 text-sm text-red-700 dark:border-red-700/45 dark:bg-red-950/20 dark:text-red-300">
                  Lý do leo thang: {stripTelemetryLabels(view.summary.escalationReason)}
                </p>
              ) : null}

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Final Recommendation</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {stripTelemetryLabels(view.summary.finalRecommendation) || "Không có khuyến nghị cuối trong snapshot này."}
                  </p>
                </article>

                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Consensus</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {stripTelemetryLabels(view.summary.consensus) || "Không có nội dung đồng thuận."}
                  </p>
                </article>
              </div>
            </CouncilSection>

            <TelemetryPanel role={role}>
              <CouncilSection eyebrow="Reasoning Timeline" title="Luồng suy luận hội chẩn">
                {view.timeline.steps.length ? (
                  <ol className="space-y-2">
                    {view.timeline.steps.map((step) => (
                      <li
                        key={`${step.sequence}-${step.step}`}
                        className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                      >
                        <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                          Step {step.sequence}: {step.step}
                        </p>
                        <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">{stripTelemetryLabels(step.detail)}</p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-[var(--text-secondary)]">Chưa có reasoning timeline trong snapshot này.</p>
                )}
              </CouncilSection>
            </TelemetryPanel>

            <CouncilSection eyebrow="Risk Notes" title="Điểm cần lưu ý">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Conflict List</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.conflicts.map(stripTelemetryLabels)} emptyText="Không có conflict nổi bật." />
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Divergence</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.divergence.map(stripTelemetryLabels)} emptyText="Không có divergence nổi bật." />
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
                  router.push("/council/new");
                }}
                className="inline-flex min-h-[44px] items-center rounded-xl border border-red-300/55 bg-red-100/80 px-4 text-sm font-semibold text-red-800 dark:border-red-700/45 dark:bg-red-950/30 dark:text-red-200"
              >
                Mở case mới
              </button>
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
