"use client";

import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

type WorkspaceTab = "analyze" | "details" | "citations" | "research" | "deepdive";

const TAB_META: Record<WorkspaceTab, { title: string; description: string; eyebrow: string }> = {
  analyze: {
    title: "Council Analyze",
    description: "Tín hiệu chính, risk drivers và action items từ kết quả hội chẩn.",
    eyebrow: "Analyze",
  },
  details: {
    title: "Council Details",
    description: "Tín hiệu và khuyến nghị có cấu trúc theo từng chuyên khoa.",
    eyebrow: "Details",
  },
  citations: {
    title: "Council Citations",
    description: "Nguồn chứng cứ và quality signal cho từng citation.",
    eyebrow: "Citations",
  },
  research: {
    title: "Council Research",
    description: "Highlights, open questions và next steps cho vòng phân tích tiếp theo.",
    eyebrow: "Research",
  },
  deepdive: {
    title: "Council Deepdive",
    description: "Tổng hợp sâu theo các phần chuyên môn có thể rà soát.",
    eyebrow: "Deepdive",
  },
};

export default function CouncilWorkspaceScreen({ tab }: { tab: WorkspaceTab }) {
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    // The Council surface was viewed (Req 9.1). No PII — coarse tab label only.
    trackCouncilViewed({ view: tab });
  }, [tab]);
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
      setLoadError("");
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
        setLoadError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void load();
    }
  }, [language, queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const meta = TAB_META[tab];

  return (
    <PageShell title={meta.title} description={meta.description} variant="plain">
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        {!view ? (
          <CouncilEmptyState
            title="Chưa có dữ liệu hội chẩn"
            description={loadError || "Hãy tạo ca mới để mở khóa các tab workspace."}
          />
        ) : null}

        {view && tab === "analyze" ? (
          <CouncilSection eyebrow={meta.eyebrow} title="Phân tích tín hiệu hội chẩn">
            <div className="grid gap-3 md:grid-cols-3">
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Key Signals</p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.keySignals.map(stripTelemetryLabels)} emptyText="Không có key signal." />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Risk Drivers</p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.riskDrivers.map(stripTelemetryLabels)} emptyText="Không có risk driver nổi bật." />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Action Items</p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.actionItems.map(stripTelemetryLabels)} emptyText="Không có action item." />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {view && tab === "details" ? (
          <CouncilSection eyebrow={meta.eyebrow} title="Chi tiết theo chuyên khoa">
            <div className="grid gap-3 md:grid-cols-2">
              {view.details.specialistLogs.map((item, index) => (
                <article
                  key={`${item.specialist}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{item.specialist}</p>
                  <div className="mt-2">
                    <CouncilList
                      items={item.findings.map(stripTelemetryLabels)}
                      emptyText="Chưa có tín hiệu có cấu trúc để hiển thị."
                    />
                  </div>
                  {item.recommendation ? (
                    <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">{stripTelemetryLabels(item.recommendation)}</p>
                  ) : null}
                </article>
              ))}
            </div>
          </CouncilSection>
        ) : null}

        {view && tab === "citations" ? (
          <CouncilSection eyebrow={meta.eyebrow} title="Nguồn chứng cứ">
            {view.citations.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {view.citations.map((item, index) => (
                  <article
                    key={`${item.title}-${index}`}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                  >
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{item.title}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">{item.source || "Clinical source"}</p>
                    {item.snippet ? (
                      <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">{stripTelemetryLabels(item.snippet)}</p>
                    ) : null}
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 inline-flex text-xs font-semibold text-cyan-600 hover:underline dark:text-cyan-300"
                      >
                        Mở nguồn
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">Không có citation trong snapshot này.</p>
            )}
          </CouncilSection>
        ) : null}

        {view && tab === "research" ? (
          <CouncilSection eyebrow={meta.eyebrow} title="Research slices">
            <div className="grid gap-3 md:grid-cols-3">
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Highlights</p>
                <div className="mt-2">
                  <CouncilList items={view.research.highlights.map(stripTelemetryLabels)} emptyText="Không có highlights." />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Open Questions</p>
                <div className="mt-2">
                  <CouncilList items={view.research.openQuestions.map(stripTelemetryLabels)} emptyText="Không có open questions." />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">Next Steps</p>
                <div className="mt-2">
                  <CouncilList items={view.research.nextSteps.map(stripTelemetryLabels)} emptyText="Không có next steps." />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {view && tab === "deepdive" ? (
          <CouncilSection eyebrow={meta.eyebrow} title="Deepdive sections">
            <div className="space-y-3">
              {view.deepDive.sections.map((section, index) => (
                <article
                  key={`${section.title}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{section.title}</p>
                  <div className="mt-2">
                    <CouncilList items={section.items.map(stripTelemetryLabels)} emptyText="Không có dữ liệu cho section này." />
                  </div>
                </article>
              ))}
            </div>
          </CouncilSection>
        ) : null}
      </div>
    </PageShell>
  );
}
