"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import { CouncilList, CouncilSection } from "@/components/council/council-primitives";
import { Icon } from "@/components/ui/icon";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  clearActiveCouncilCaseId,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

export type WorkspaceTab = "analyze" | "details" | "citations" | "research" | "deepdive";

const TAB_META: Record<
  WorkspaceTab,
  { title: UITranslationKey; description: UITranslationKey; eyebrow: UITranslationKey; heading: UITranslationKey }
> = {
  analyze: {
    title: "council.workspace.analyze.title",
    description: "council.workspace.analyze.description",
    eyebrow: "council.workspace.analyze.eyebrow",
    heading: "council.workspace.analyze.heading",
  },
  details: {
    title: "council.workspace.details.title",
    description: "council.workspace.details.description",
    eyebrow: "council.workspace.details.eyebrow",
    heading: "council.workspace.details.heading",
  },
  citations: {
    title: "council.workspace.citations.title",
    description: "council.workspace.citations.description",
    eyebrow: "council.workspace.citations.eyebrow",
    heading: "council.workspace.citations.heading",
  },
  research: {
    title: "council.workspace.research.title",
    description: "council.workspace.research.description",
    eyebrow: "council.workspace.research.eyebrow",
    heading: "council.workspace.research.heading",
  },
  deepdive: {
    title: "council.workspace.deepdive.title",
    description: "council.workspace.deepdive.description",
    eyebrow: "council.workspace.deepdive.eyebrow",
    heading: "council.workspace.deepdive.heading",
  },
};

export const COUNCIL_SUB_TABS: Array<{ id: WorkspaceTab; labelVi: string; labelEn: string }> = [
  { id: "analyze", labelVi: "Phân tích tín hiệu", labelEn: "Signal Analysis" },
  { id: "details", labelVi: "Chi tiết chuyên khoa", labelEn: "Specialist Logs" },
  { id: "citations", labelVi: "Tra cứu trích dẫn", labelEn: "Citations" },
  { id: "research", labelVi: "Tổng hợp nghiên cứu", labelEn: "Research Synthesis" },
  { id: "deepdive", labelVi: "Đào sâu ca bệnh", labelEn: "Deep Dive" },
];

export default function CouncilWorkspaceScreen({ tab }: { tab: WorkspaceTab }) {
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
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
        let loaded: CouncilCaseRecord | null;
        if (queryCaseId) {
          loaded = await getCouncilCase(queryCaseId);
        } else {
          loaded = await getLatestCouncilCase();
        }
        if (loaded) {
          setActiveCouncilCaseId(loaded.id);
          setCaseItem(loaded);
        } else {
          clearActiveCouncilCaseId();
          setCaseItem(null);
        }
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
    <PageShell title={t(language, meta.title)} description={t(language, meta.description)} variant="plain">
      <div className="space-y-6">
        {/* Step Progress */}
        <CouncilFlowStepper currentStep="result" caseId={caseItem?.id} />

        {/* Retained Decision & Case Context Header Card */}
        {view ? (
          <section className="rounded-[1.55rem] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] border-l-4 border-l-[color:var(--brand-600)] bg-[var(--surface-panel)] p-5 sm:p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {language === "vi" ? "Bối cảnh quyết định hội chẩn" : "Council Decision Context"}
                </span>
                <span className="font-mono text-xs font-bold text-[var(--text-muted)]">
                  #{caseItem?.id}
                </span>
              </div>
              <Link
                href={`/council/result?caseId=${caseItem?.id}`}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--text-brand)] hover:underline"
              >
                <span>{language === "vi" ? "Xem toàn văn kết luận" : "Back to Full Result"}</span>
                <Icon name="arrow-right" size={14} />
              </Link>
            </div>

            <h2 className="text-lg font-bold text-[var(--text-primary)] mt-1">
              {caseItem?.title || t(language, "council.new.caseFallback", { id: caseItem?.id ?? 0 })}
            </h2>

            {view.summary.finalRecommendation ? (
              <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)] line-clamp-2 bg-[var(--surface-muted)] p-3 rounded-xl border border-[color:var(--shell-border)]">
                {stripTelemetryLabels(view.summary.finalRecommendation)}
              </p>
            ) : null}

            {/* Canonical Tab Anchors */}
            <div className="mt-4 flex flex-wrap gap-2 pt-3 border-t border-[color:var(--shell-border)]">
              {COUNCIL_SUB_TABS.map((subTab) => {
                const isActive = subTab.id === tab;
                return (
                  <Link
                    key={subTab.id}
                    href={`/council/${subTab.id}?caseId=${caseItem?.id}`}
                    className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                      isActive
                        ? "border-transparent bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-sm"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                    }`}
                  >
                    {language === "vi" ? subTab.labelVi : subTab.labelEn}
                  </Link>
                );
              })}
            </div>
          </section>
        ) : null}

        {!view ? (
          <CouncilEmptyState
            title={t(language, "council.workspace.empty.title")}
            description={loadError || t(language, "council.workspace.empty.description")}
          />
        ) : null}

        {/* Tab 1: Analyze */}
        {view && tab === "analyze" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="grid gap-4 md:grid-cols-3">
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Icon name="clinical-notes" size={18} className="text-[var(--text-brand)]" />
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {t(language, "council.workspace.analyze.keySignals")}
                  </p>
                </div>
                <div className="mt-2">
                  <CouncilList
                    items={view.analyze.keySignals.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.analyze.keySignalsEmpty")}
                  />
                </div>
              </article>

              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Icon name="warning" size={18} className="text-[var(--status-warn-text)]" />
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {t(language, "council.workspace.analyze.riskDrivers")}
                  </p>
                </div>
                <div className="mt-2">
                  <CouncilList
                    items={view.analyze.riskDrivers.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.analyze.riskDriversEmpty")}
                  />
                </div>
              </article>

              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <Icon name="progress" size={18} className="text-[var(--text-brand)]" />
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {t(language, "council.workspace.analyze.actionItems")}
                  </p>
                </div>
                <div className="mt-2">
                  <CouncilList
                    items={view.analyze.actionItems.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.analyze.actionItemsEmpty")}
                  />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 2: Details */}
        {view && tab === "details" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="grid gap-4 md:grid-cols-2">
              {view.details.specialistLogs.map((item, index) => (
                <article
                  key={`${item.specialist}-${index}`}
                  className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                      {item.specialist}
                    </span>
                  </div>
                  {item.recommendation ? (
                    <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 text-sm font-semibold text-[var(--text-primary)]">
                      {stripTelemetryLabels(item.recommendation)}
                    </div>
                  ) : null}
                  <div className="mt-3">
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                      {language === "vi" ? "Ghi nhận chuyên môn:" : "Specialist Findings:"}
                    </p>
                    <CouncilList
                      items={item.findings.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.details.empty")}
                    />
                  </div>
                </article>
              ))}
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 3: Citations */}
        {view && tab === "citations" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            {view.citations.length ? (
              <div className="grid gap-4 md:grid-cols-2">
                {view.citations.map((item, index) => (
                  <article
                    key={`${item.title}-${index}`}
                    className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] font-mono text-[10px] font-bold text-[var(--text-brand)]">
                          [{index + 1}]
                        </span>
                        <h4 className="text-sm font-bold text-[var(--text-primary)]">{item.title}</h4>
                      </div>
                      <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-bold text-[var(--text-brand)]">
                        {item.source || t(language, "council.workspace.citations.sourceFallback")}
                      </span>
                    </div>

                    {item.snippet ? (
                      <p className="mt-3 text-xs leading-relaxed text-[var(--text-secondary)] bg-[var(--surface-muted)] p-3 rounded-xl">
                        {stripTelemetryLabels(item.snippet)}
                      </p>
                    ) : null}

                    {item.url ? (
                      <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)] flex justify-end">
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-brand)] hover:underline"
                        >
                          <span>{t(language, "council.workspace.citations.openSource")}</span>
                          <Icon name="arrow-right" size={13} />
                        </a>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.workspace.citations.empty")}</p>
            )}
          </CouncilSection>
        ) : null}

        {/* Tab 4: Research */}
        {view && tab === "research" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="grid gap-4 md:grid-cols-3">
              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mb-3">
                  {t(language, "council.workspace.research.highlights")}
                </p>
                <div className="mt-2">
                  <CouncilList
                    items={view.research.highlights.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.research.highlightsEmpty")}
                  />
                </div>
              </article>

              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mb-3">
                  {t(language, "council.workspace.research.openQuestions")}
                </p>
                <div className="mt-2">
                  <CouncilList
                    items={view.research.openQuestions.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.research.openQuestionsEmpty")}
                  />
                </div>
              </article>

              <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] mb-3">
                  {t(language, "council.workspace.research.nextSteps")}
                </p>
                <div className="mt-2">
                  <CouncilList
                    items={view.research.nextSteps.map(stripTelemetryLabels)}
                    emptyText={t(language, "council.workspace.research.nextStepsEmpty")}
                  />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 5: Deep Dive */}
        {view && tab === "deepdive" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-4">
              {view.deepDive.sections.map((section, index) => (
                <article
                  key={`${section.title}-${index}`}
                  className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
                >
                  <p className="text-sm font-bold text-[var(--text-primary)] mb-3">{section.title}</p>
                  <div className="mt-2">
                    <CouncilList
                      items={section.items.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.deepdive.empty")}
                    />
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
