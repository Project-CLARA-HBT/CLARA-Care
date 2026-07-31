"use client";

import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
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

const TAB_META: Record<
  WorkspaceTab,
  { title: UITranslationKey; description: UITranslationKey; eyebrow: UITranslationKey }
> = {
  analyze: {
    title: "council.workspace.analyze.title",
    description: "council.workspace.analyze.description",
    eyebrow: "council.workspace.analyze.eyebrow",
  },
  details: {
    title: "council.workspace.details.title",
    description: "council.workspace.details.description",
    eyebrow: "council.workspace.details.eyebrow",
  },
  citations: {
    title: "council.workspace.citations.title",
    description: "council.workspace.citations.description",
    eyebrow: "council.workspace.citations.eyebrow",
  },
  research: {
    title: "council.workspace.research.title",
    description: "council.workspace.research.description",
    eyebrow: "council.workspace.research.eyebrow",
  },
  deepdive: {
    title: "council.workspace.deepdive.title",
    description: "council.workspace.deepdive.description",
    eyebrow: "council.workspace.deepdive.eyebrow",
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
    <PageShell title={t(language, meta.title)} description={t(language, meta.description)} variant="plain">
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        {!view ? (
          <CouncilEmptyState
            title={t(language, "council.workspace.empty.title")}
            description={loadError || t(language, "council.workspace.empty.description")}
          />
        ) : null}

        {view && tab === "analyze" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, "council.workspace.analyze.heading")}>
            <div className="grid gap-3 md:grid-cols-3">
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.analyze.keySignals")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.keySignals.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.analyze.keySignalsEmpty")} />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.analyze.riskDrivers")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.riskDrivers.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.analyze.riskDriversEmpty")} />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.analyze.actionItems")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.analyze.actionItems.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.analyze.actionItemsEmpty")} />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {view && tab === "details" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, "council.workspace.details.heading")}>
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
                      emptyText={t(language, "council.workspace.details.empty")}
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
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, "council.workspace.citations.heading")}>
            {view.citations.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {view.citations.map((item, index) => (
                  <article
                    key={`${item.title}-${index}`}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                  >
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{item.title}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {item.source || t(language, "council.workspace.citations.sourceFallback")}
                    </p>
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
                        {t(language, "council.workspace.citations.openSource")}
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.workspace.citations.empty")}</p>
            )}
          </CouncilSection>
        ) : null}

        {view && tab === "research" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, "council.workspace.research.heading")}>
            <div className="grid gap-3 md:grid-cols-3">
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.research.highlights")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.research.highlights.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.research.highlightsEmpty")} />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.research.openQuestions")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.research.openQuestions.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.research.openQuestionsEmpty")} />
                </div>
              </article>
              <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  {t(language, "council.workspace.research.nextSteps")}
                </p>
                <div className="mt-2">
                  <CouncilList items={view.research.nextSteps.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.research.nextStepsEmpty")} />
                </div>
              </article>
            </div>
          </CouncilSection>
        ) : null}

        {view && tab === "deepdive" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, "council.workspace.deepdive.heading")}>
            <div className="space-y-3">
              {view.deepDive.sections.map((section, index) => (
                <article
                  key={`${section.title}-${index}`}
                  className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{section.title}</p>
                  <div className="mt-2">
                    <CouncilList items={section.items.map(stripTelemetryLabels)} emptyText={t(language, "council.workspace.deepdive.empty")} />
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
