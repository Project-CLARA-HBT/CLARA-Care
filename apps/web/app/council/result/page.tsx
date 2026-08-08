"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import { CouncilList, CouncilMetricCard, CouncilSection } from "@/components/council/council-primitives";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
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

export default function CouncilResultPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
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
        setError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void load();
    }
  }, [language, queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const fmtStrength = (value: number | null): string => {
    if (value == null || Number.isNaN(value)) return "-";
    return value.toFixed(2);
  };
  const medicationSafety = snapshot?.result.medicationSafety ?? null;
  const medicationSafetyLabel = medicationSafety
    ? medicationSafety.state === "checked"
      ? t(language, "council.result.medicationSafety.checked")
      : medicationSafety.state === "requires_clarification"
        ? t(language, "council.result.medicationSafety.clarification")
        : t(language, "council.result.medicationSafety.unavailable")
    : "";
  const medicationSafetyHint = medicationSafety?.drugbankVersion
    ? t(language, "council.result.medicationSafety.version", {
        version: medicationSafety.drugbankVersion,
      })
    : medicationSafety
      ? t(language, "council.result.medicationSafety.noVersion")
      : "";

  return (
    <PageShell
      title={t(language, "council.result.title")}
      description={t(language, "council.result.description")}
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        {!view ? (
          <CouncilEmptyState
            title={t(language, "council.empty.title")}
            description={error || t(language, "council.result.emptyDescription")}
          />
        ) : (
          <>
            <CouncilSection eyebrow={t(language, "council.result.summary")} title={t(language, "council.result.summaryTitle")}>
              <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-6">
                <CouncilMetricCard
                  label={t(language, "council.result.time")}
                  value={snapshot?.createdAt
                    ? formatLocaleDate(language, snapshot.createdAt, {
                      day: "2-digit",
                      month: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                    : view.createdAtLabel}
                />
                <CouncilMetricCard label={t(language, "council.result.urgency")} value={view.urgencyLabel} />
                <CouncilMetricCard label={t(language, "council.result.specialties")} value={String(view.requestSummary.specialists.length)} hint={view.requestSummary.specialists.join(", ")} />
                <CouncilMetricCard label={t(language, "council.result.conflicts")} value={String(view.summary.conflicts.length)} />
                <CouncilMetricCard
                  label={t(language, "council.result.consensus")}
                  value={view.summary.conflicts.length ? t(language, "council.result.consensusReview") : t(language, "council.result.consensusClear")}
                  hint={t(language, "council.result.consensusHint")}
                />
                <CouncilMetricCard
                  label={t(language, "council.result.professionalReview")}
                  value={view.quality.requiresHumanHandoff ? t(language, "council.result.reviewRequired") : t(language, "council.result.reviewBeforeUse")}
                />
              </div>

              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <CouncilMetricCard
                  label={t(language, "council.result.escalationPriority")}
                  value={view.quality.escalationPriority || t(language, "council.result.routine")}
                  hint={
                    view.quality.recommendedSlaMinutes != null
                      ? t(language, "council.result.sla", { minutes: view.quality.recommendedSlaMinutes })
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label={t(language, "council.result.citationQuality")}
                  value={fmtStrength(view.quality.citationAverageStrength)}
                  hint={
                    view.quality.citationTotal != null
                      ? t(language, "council.result.citations", { count: view.quality.citationTotal })
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label={t(language, "council.result.strongestDissent")}
                  value={view.quality.strongestDissent || "-"}
                  hint={
                    view.quality.strongestDissentVotes != null
                      ? t(language, "council.result.votes", { count: view.quality.strongestDissentVotes })
                      : undefined
                  }
                />
                <CouncilMetricCard
                  label={t(language, "council.result.ruleRisk")}
                  value={view.quality.ruleShadowEnabled ? view.quality.ruleShadowBand || t(language, "council.result.ruleRiskPresent") : t(language, "council.result.ruleRiskDisabled")}
                  hint={t(language, "council.result.ruleRiskHint")}
                />
                {medicationSafety ? (
                  <CouncilMetricCard
                    label={t(language, "council.result.medicationSafety.label")}
                    value={medicationSafetyLabel}
                    hint={medicationSafetyHint}
                  />
                ) : null}
              </div>

              {view.summary.escalationReason ? (
                <p className="mt-3 rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-sm text-[var(--status-danger-text)]">
                  {t(language, "council.result.escalationReason", { reason: stripTelemetryLabels(view.summary.escalationReason) })}
                </p>
              ) : null}

              {medicationSafety?.reviewRequired ? (
                <p className="mt-3 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-sm text-[var(--status-warn-text)]">
                  {medicationSafety.state === "requires_clarification"
                    ? t(language, "council.result.medicationSafety.clarificationNotice")
                    : medicationSafety.state === "unavailable"
                      ? t(language, "council.result.medicationSafety.unavailableNotice")
                      : t(language, "council.result.medicationSafety.reviewNotice")}
                </p>
              ) : null}

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{t(language, "council.result.finalRecommendation")}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {stripTelemetryLabels(view.summary.finalRecommendation) || t(language, "council.result.noRecommendation")}
                  </p>
                </article>

                <article className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{t(language, "council.result.consensus")}</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-secondary)]">
                    {stripTelemetryLabels(view.summary.consensus) || t(language, "council.result.noConsensus")}
                  </p>
                </article>
              </div>
            </CouncilSection>

            <CouncilSection eyebrow={t(language, "council.result.processing")} title={t(language, "council.result.processingTitle")}>
                {view.timeline.steps.length ? (
                  <ol className="space-y-2">
                    {view.timeline.steps.map((step) => (
                      <li
                        key={`${step.sequence}-${step.step}`}
                        className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3"
                      >
                        <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">
                          {t(language, "council.result.step", { sequence: step.sequence, step: step.step })}
                        </p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="text-sm text-[var(--text-secondary)]">{t(language, "council.result.noProcessing")}</p>
                )}
            </CouncilSection>

            <CouncilSection eyebrow={t(language, "council.result.riskNotes")} title={t(language, "council.result.riskNotes")}>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{t(language, "council.result.conflictList")}</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.conflicts.map(stripTelemetryLabels)} emptyText={t(language, "council.result.noConflicts")} />
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.13em] text-[var(--text-muted)]">{t(language, "council.result.divergence")}</p>
                  <div className="mt-2">
                    <CouncilList items={view.summary.divergence.map(stripTelemetryLabels)} emptyText={t(language, "council.result.noDivergence")} />
                  </div>
                </div>
              </div>
            </CouncilSection>

            <section className="flex flex-wrap gap-2">
              <Link
                href="/council"
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 text-sm font-semibold text-[var(--text-primary)]"
              >
                {t(language, "council.empty.landing")}
              </Link>
              <Link
                href="/council/new"
                className="inline-flex min-h-[44px] items-center rounded-[var(--radius-md)] border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-4 text-sm font-semibold text-[var(--on-secondary-container)] transition-colors hover:bg-[var(--brand-700)]"
              >
                {t(language, "council.result.newCase")}
              </Link>
              <button
                type="button"
                onClick={() => {
                  router.push("/council/new");
                }}
                className="inline-flex min-h-[44px] items-center rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 text-sm font-semibold text-[var(--status-danger-text)] transition-colors hover:opacity-90"
              >
                {t(language, "council.result.openNewCase")}
              </button>
            </section>
          </>
        )}
      </div>
    </PageShell>
  );
}
