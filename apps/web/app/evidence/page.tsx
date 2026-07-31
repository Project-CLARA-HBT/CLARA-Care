"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/ui/surface";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import {
  confirmEvidenceQuestion,
  createEvidenceQuestion,
  deleteEvidenceSubscription,
  getEvidenceDetails,
  isEvidenceRunTerminal,
  listEvidenceChangeNotifications,
  listEvidenceSubscriptions,
  markEvidenceChangeNotificationRead,
  pollEvidenceRun,
  runEvidenceQuestion,
  subscribeToEvidenceRun,
  updateEvidenceSubscription,
  type EvidenceApplicability,
  type EvidenceChangeNotification,
  type EvidenceContradictions,
  type EvidenceMatrix,
  type EvidenceQuestion,
  type EvidenceRun,
  type EvidenceSubscription,
} from "@/lib/living-evidence";
import { getLifeMapToday, type LifeMapEpisode } from "@/lib/lifemap";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

const sourceClassLabel: Record<string, UITranslationKey> = {
  guideline: "evidence.source.guideline",
  primary_randomized_trial: "evidence.source.primaryRandomizedTrial",
  primary_observational: "evidence.source.primaryObservational",
  primary_diagnostic: "evidence.source.primaryDiagnostic",
  primary_prognostic: "evidence.source.primaryPrognostic",
  systematic_review: "evidence.source.systematicReview",
  review: "evidence.source.review",
  editorial_commentary: "evidence.source.editorialCommentary",
};

const missingContextLabel: Record<string, UITranslationKey> = {
  population_context: "evidence.missing.population",
  outcomes: "evidence.missing.outcomes",
  time_horizon: "evidence.missing.timeHorizon",
  validated_study_eligibility_rules_unavailable: "evidence.missing.eligibility",
};

function labelForSourceClass(language: UILanguage, value: string) {
  const key = sourceClassLabel[value];
  return key ? t(language, key) : value;
}

function labelForUnknown(language: UILanguage, value: string) {
  const key = missingContextLabel[value];
  return key ? t(language, key) : value;
}

function toMessage(cause: unknown, fallback: string) {
  return safeUserFacingError(cause, fallback);
}

function EvidenceMatrixView({ matrix, language }: { matrix: EvidenceMatrix; language: UILanguage }) {
  const groups = Object.entries(matrix.source_classes);
  if (groups.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
        {matrix.unavailable_reason ?? t(language, "evidence.matrix.empty")}
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {groups.map(([sourceClass, records]) => (
        <section key={sourceClass} className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)]">
          <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/65 px-4 py-3">
            <h3 className="font-semibold text-[var(--text-primary)]">{labelForSourceClass(language, sourceClass)}</h3>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{t(language, "evidence.matrix.provenance", { count: records.length })}</p>
          </div>
          <ul className="divide-y divide-[color:var(--shell-border)]">
            {records.map((record) => (
              <li key={record.evidence_id} className="px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium leading-6 text-[var(--text-primary)]">{record.title}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {[record.provider, record.study_design, record.published_at].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  {record.url ? (
                    <a
                      href={record.url}
                      target="_blank"
                      rel="noreferrer"
                      className="focus-ring inline-flex items-center gap-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:bg-[var(--surface-brand-soft)]"
                    >
                      {t(language, "evidence.matrix.openSource")} <span className="material-symbols-outlined text-sm" aria-hidden="true">open_in_new</span>
                    </a>
                  ) : null}
                </div>
                {Object.keys(record.identifiers).length ? (
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                    {Object.entries(record.identifiers).map(([key, value]) => `${key.toUpperCase()}: ${value}`).join(" · ")}
                  </p>
                ) : null}
                {record.excerpt ? <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{record.excerpt}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function InterpretationView({
  applicability,
  contradictions,
  language,
}: {
  applicability: EvidenceApplicability;
  contradictions: EvidenceContradictions;
  language: UILanguage;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] p-4">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined mt-0.5 text-[var(--text-brand)]" aria-hidden="true">person_search</span>
          <div>
            <h3 className="font-semibold text-[var(--text-primary)]">{t(language, "evidence.interpretation.applicability")}</h3>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{applicability.safe_message}</p>
          </div>
        </div>
        {applicability.unknowns.length ? (
          <ul className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
            {applicability.unknowns.map((item) => <li key={item} className="flex gap-2"><span className="material-symbols-outlined text-base text-[var(--status-warn-text)]" aria-hidden="true">help</span><span>{t(language, "evidence.interpretation.missing", { item: labelForUnknown(language, item) })}</span></li>)}
          </ul>
        ) : null}
      </section>
      <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] p-4">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined mt-0.5 text-[var(--text-brand)]" aria-hidden="true">compare_arrows</span>
          <div>
            <h3 className="font-semibold text-[var(--text-primary)]">{t(language, "evidence.interpretation.contradictions")}</h3>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{contradictions.safe_message}</p>
          </div>
        </div>
        {contradictions.items.length ? (
          <ul className="mt-3 space-y-2">
            {contradictions.items.map((item, index) => <li key={`${item.claim}-${index}`} className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]"><p className="font-medium">{item.claim || t(language, "evidence.interpretation.defaultContradiction")}</p><p className="mt-1 text-xs opacity-80">{t(language, "evidence.interpretation.relatedSources", { sources: item.citation_ids.join(", ") })}</p></li>)}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

export default function LivingEvidencePage() {
  const language = useUILanguage();
  const [episodes, setEpisodes] = useState<LifeMapEpisode[]>([]);
  const [loadingEpisodes, setLoadingEpisodes] = useState(true);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [population, setPopulation] = useState("");
  const [outcomes, setOutcomes] = useState("");
  const [timeHorizon, setTimeHorizon] = useState("");
  const [question, setQuestion] = useState<EvidenceQuestion | null>(null);
  const [run, setRun] = useState<EvidenceRun | null>(null);
  const [matrix, setMatrix] = useState<EvidenceMatrix | null>(null);
  const [applicability, setApplicability] = useState<EvidenceApplicability | null>(null);
  const [contradictions, setContradictions] = useState<EvidenceContradictions | null>(null);
  const [subscription, setSubscription] = useState<EvidenceSubscription | null>(null);
  const [subscriptions, setSubscriptions] = useState<EvidenceSubscription[]>([]);
  const [notifications, setNotifications] = useState<EvidenceChangeNotification[]>([]);
  const [intervalHours, setIntervalHours] = useState("168");
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [error, setError] = useState("");
  const pollControllerRef = useRef<AbortController | null>(null);

  const loadEpisodes = useCallback(async () => {
    setLoadingEpisodes(true);
    setError("");
    try {
      const today = await getLifeMapToday();
      setEpisodes(today.episodes);
      setSelectedEpisodeId((current) => current || today.episodes[0]?.id || "");
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.loadEpisodes")));
    } finally {
      setLoadingEpisodes(false);
    }
  }, [language]);

  useEffect(() => { void loadEpisodes(); }, [loadEpisodes]);
  useEffect(() => {
    void Promise.all([
      listEvidenceSubscriptions(),
      listEvidenceChangeNotifications(),
    ]).then(([activeSubscriptions, evidenceNotifications]) => {
      setSubscriptions(activeSubscriptions);
      setNotifications(evidenceNotifications);
    }).catch(() => {
      // The primary evidence flow remains usable if monitor metadata is unavailable.
    });
  }, []);
  useEffect(() => () => pollControllerRef.current?.abort(), []);
  useEffect(() => {
    if (!run) return;
    const current = subscriptions.find(
      (item) => item.evidence_run_id === run.id && item.status === "active",
    ) ?? null;
    setSubscription(current);
    if (current) setIntervalHours(String(current.interval_hours));
  }, [run, subscriptions]);

  const createQuestion = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedEpisodeId || !questionText.trim()) return;
    pollControllerRef.current?.abort();
    setSaving(true);
    setError("");
    try {
      const created = await createEvidenceQuestion(selectedEpisodeId, {
        question: questionText.trim(),
        population_context: population.trim() || undefined,
        outcomes: outcomes.split("\n").map((item) => item.trim()).filter(Boolean),
        time_horizon: timeHorizon.trim() || undefined,
      });
      setQuestion(created);
      setRun(null);
      setMatrix(null);
      setApplicability(null);
      setContradictions(null);
      setSubscription(null);
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.saveQuestion")));
    } finally {
      setSaving(false);
    }
  };

  const confirmQuestion = async () => {
    if (!question) return;
    setSaving(true);
    setError("");
    try {
      setQuestion(await confirmEvidenceQuestion(question.id));
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.confirmQuestion")));
    } finally {
      setSaving(false);
    }
  };

  const runResearch = async () => {
    if (!question?.confirmed) return;
    pollControllerRef.current?.abort();
    const controller = new AbortController();
    pollControllerRef.current = controller;
    setRunning(true);
    setPollAttempt(0);
    setError("");
    setMatrix(null);
    setApplicability(null);
    setContradictions(null);
    try {
      const createdRun = await runEvidenceQuestion(question.id);
      setRun(createdRun);
      const completedRun = isEvidenceRunTerminal(createdRun)
        ? createdRun
        : await pollEvidenceRun(createdRun.id, {
          signal: controller.signal,
          onUpdate: (updatedRun, attempt) => {
            setRun(updatedRun);
            setPollAttempt(attempt);
          },
        });
      setRun(completedRun);
      if (completedRun.status.toLowerCase() !== "completed") {
        throw new Error(t(language, "evidence.error.runIncomplete"));
      }
      const details = await getEvidenceDetails(completedRun.id);
      setMatrix(details.matrix);
      setApplicability(details.applicability);
      setContradictions(details.contradictions);
    } catch (cause) {
      if (!(cause instanceof Error && cause.name === "AbortError")) {
        setRun((current) => current && isEvidenceRunTerminal(current) ? current : null);
        setError(toMessage(cause, t(language, "evidence.error.run")));
      }
    } finally {
      if (pollControllerRef.current === controller) {
        pollControllerRef.current = null;
        setRunning(false);
      }
    }
  };

  const toggleSubscription = async () => {
    if (!run) return;
    setSaving(true);
    setError("");
    try {
      if (subscription) {
        await deleteEvidenceSubscription(subscription.id);
        setSubscription(null);
        setSubscriptions((items) => items.map((item) => (
          item.id === subscription.id ? { ...item, status: "revoked" } : item
        )));
      } else {
        const created = await subscribeToEvidenceRun(run.id, Number(intervalHours));
        setSubscription(created);
        setSubscriptions((items) => [
          created,
          ...items.filter((item) => item.id !== created.id),
        ]);
      }
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.subscription")));
    } finally {
      setSaving(false);
    }
  };

  const changeInterval = async (value: string) => {
    setIntervalHours(value);
    if (!subscription) return;
    setSaving(true);
    setError("");
    try {
      const updated = await updateEvidenceSubscription(
        subscription.id,
        Number(value),
      );
      setSubscription(updated);
      setSubscriptions((items) => items.map((item) => (
        item.id === updated.id ? updated : item
      )));
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.interval")));
    } finally {
      setSaving(false);
    }
  };

  const markNotificationRead = async (item: EvidenceChangeNotification) => {
    if (item.status === "read") return;
    try {
      await markEvidenceChangeNotificationRead(item.id);
      setNotifications((items) => items.map((current) => (
        current.id === item.id ? { ...current, status: "read" } : current
      )));
    } catch (cause) {
      setError(toMessage(cause, t(language, "evidence.error.notification")));
    }
  };

  const selectedEpisode = episodes.find((episode) => episode.id === selectedEpisodeId);
  const evidenceAvailable = run?.release_status === "evidence_available";

  return (
    <PageShell
      variant="plain"
      title={t(language, "evidence.page.title")}
      description={t(language, "evidence.page.description")}
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="space-y-5">
          {error ? <InlineError message={error} onRetry={() => void (question?.confirmed ? runResearch() : loadEpisodes())} /> : null}
          {running ? (
            <SurfaceCard className="overflow-hidden">
              <div role="status" aria-live="polite">
                <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)]/55 px-5 py-4">
                  <div className="flex items-start gap-3">
                    <span className="material-symbols-outlined mt-0.5 animate-spin text-[var(--text-brand)]" aria-hidden="true">progress_activity</span>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "evidence.run.processing")}</p>
                      <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{question?.question}</h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        {pollAttempt === 0
                          ? t(language, "evidence.run.starting")
                          : pollAttempt < 15
                            ? t(language, "evidence.run.retrieving")
                            : pollAttempt < 60
                              ? t(language, "evidence.run.verifying")
                              : t(language, "evidence.run.finishing")}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-5">
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-muted)]" aria-hidden="true">
                    <div className="h-full w-2/5 animate-pulse rounded-full bg-[var(--brand-500)]" />
                  </div>
                  <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">
                    {pollAttempt > 0 ? t(language, "evidence.run.updated", { count: pollAttempt }) : ""}
                    {t(language, "evidence.run.wait")}
                  </p>
                </div>
              </div>
            </SurfaceCard>
          ) : run ? (
            <SurfaceCard className="overflow-hidden">
              <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "evidence.result.title")}</p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{question?.question}</h2>
                  </div>
                  {evidenceAvailable ? (
                    <Badge tone="ok">{t(language, "evidence.result.verifiedSources", { count: run.evidence_count })}</Badge>
                  ) : (
                    <Badge tone="warn">{t(language, "evidence.result.notReleased")}</Badge>
                  )}
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{run.safe_message}</p>
              </div>
              <div className="space-y-5 p-5">
                {evidenceAvailable && matrix ? <EvidenceMatrixView matrix={matrix} language={language} /> : <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-sm leading-6 text-[var(--status-warn-text)]"><p className="font-semibold">{t(language, "evidence.result.safeStopTitle")}</p><p className="mt-1">{t(language, "evidence.result.safeStopBody")}</p></div>}
                {applicability && contradictions ? <InterpretationView applicability={applicability} contradictions={contradictions} language={language} /> : null}
                <details className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                  <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">{t(language, "evidence.result.uncertainty")}</summary>
                  <ul className="mt-3 space-y-2 leading-6">{run.uncertainty.map((item, index) => <li key={`${item.dimension}-${index}`}><span className="font-medium text-[var(--text-primary)]">{item.dimension}:</span> {item.reason}</li>)}</ul>
                </details>
              </div>
            </SurfaceCard>
          ) : (
            <SurfaceCard className="p-5">
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)]" aria-hidden="true">fact_check</span>
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">{t(language, "evidence.intro.title")}</h2>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">{t(language, "evidence.intro.body")}</p>
                </div>
              </div>
            </SurfaceCard>
          )}
        </main>

        <aside className="space-y-5">
          {notifications.length ? (
            <SurfaceCard className="p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                {t(language, "evidence.notifications.title")}
              </p>
              <ul className="mt-3 space-y-3">
                {notifications.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"
                  >
                    <div className="flex items-start gap-2">
                      <span
                        className="material-symbols-outlined text-lg text-[var(--text-brand)]"
                        aria-hidden="true"
                      >
                        verified
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm leading-6 text-[var(--text-secondary)]">
                          {item.payload.message}
                        </p>
                        {item.status === "unread" ? (
                          <button
                            type="button"
                            className="focus-ring mt-2 rounded-[var(--radius-md)] text-xs font-semibold text-[var(--text-brand)] hover:underline"
                            onClick={() => void markNotificationRead(item)}
                          >
                            {t(language, "evidence.notifications.markRead")}
                          </button>
                        ) : (
                          <p className="mt-2 text-xs text-[var(--text-muted)]">{t(language, "evidence.notifications.read")}</p>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </SurfaceCard>
          ) : null}
          <SurfaceCard className="p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "evidence.step.question")}</p>
            <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{t(language, "evidence.question.title")}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{t(language, "evidence.question.description")}</p>
            {loadingEpisodes ? <div className="mt-4"><LoadingCards count={1} /></div> : episodes.length === 0 ? <EmptyState icon="route" title={t(language, "evidence.question.emptyTitle")} description={t(language, "evidence.question.emptyDescription")} ><Link href="/lifemap" className="focus-ring text-sm font-semibold text-[var(--text-brand)] hover:underline">{t(language, "evidence.question.openLifeMap")}</Link></EmptyState> : <form className="mt-4 space-y-3" onSubmit={(event) => void createQuestion(event)}>
              <Select label={t(language, "evidence.question.episode")} value={selectedEpisodeId} onChange={(event) => setSelectedEpisodeId(event.target.value)}>{episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.title}</option>)}</Select>
              <Textarea label={t(language, "evidence.question.text")} required value={questionText} onChange={(event) => setQuestionText(event.target.value)} placeholder={t(language, "evidence.question.textPlaceholder")} className="min-h-28 leading-6" />
              <Textarea label={t(language, "evidence.question.population")} optional value={population} onChange={(event) => setPopulation(event.target.value)} placeholder={t(language, "evidence.question.populationPlaceholder")} />
              <Textarea label={t(language, "evidence.question.outcomes")} hint={t(language, "evidence.question.outcomesHint")} value={outcomes} onChange={(event) => setOutcomes(event.target.value)} placeholder={t(language, "evidence.question.outcomesPlaceholder")} />
              <Field label={t(language, "evidence.question.horizon")} optional value={timeHorizon} onChange={(event) => setTimeHorizon(event.target.value)} placeholder={t(language, "evidence.question.horizonPlaceholder")} />
              <Button type="submit" block loading={saving} loadingLabel={t(language, "evidence.question.saving")} disabled={!selectedEpisodeId}>{t(language, "evidence.question.save")}</Button>
            </form>}
          </SurfaceCard>

          {question ? <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "evidence.step.confirm")}</p><h2 className="mt-1 font-semibold text-[var(--text-primary)]">{question.question}</h2><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{question.confirmed ? t(language, "evidence.confirm.confirmed") : t(language, "evidence.confirm.pending")}</p>{question.compiled.missing_dimensions?.length ? <p className="mt-3 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]">{t(language, "evidence.confirm.missing", { items: question.compiled.missing_dimensions.map((item) => labelForUnknown(language, item)).join(", ") })}</p> : null}{!question.confirmed ? <Button type="button" variant="secondary" block className="mt-4" disabled={saving} onClick={() => void confirmQuestion()}>{t(language, "evidence.confirm.action")}</Button> : <Button type="button" block className="mt-4" loading={running} loadingLabel={t(language, "evidence.confirm.searching")} onClick={() => void runResearch()}>{t(language, "evidence.confirm.search")}</Button>}</SurfaceCard> : null}

          {run ? <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">{t(language, "evidence.subscription.title")}</h2><p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{t(language, "evidence.subscription.description")}</p><div className="mt-4"><Select label={t(language, "evidence.subscription.interval")} value={intervalHours} disabled={saving} onChange={(event) => void changeInterval(event.target.value)}><option value="24">{t(language, "evidence.subscription.daily")}</option><option value="168">{t(language, "evidence.subscription.weekly")}</option><option value="720">{t(language, "evidence.subscription.monthly")}</option></Select></div><Button type="button" variant="secondary" block className="mt-4" disabled={saving} onClick={() => void toggleSubscription()}>{subscription ? t(language, "evidence.subscription.stop") : t(language, "evidence.subscription.start")}</Button>{subscription && !subscription.monitor_enabled ? <p className="mt-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-xs leading-5 text-[var(--text-secondary)]">{t(language, "evidence.subscription.disabled")}</p> : null}{selectedEpisode ? <p className="mt-3 text-xs text-[var(--text-muted)]">{t(language, "evidence.subscription.attached", { title: selectedEpisode.title })}</p> : null}</SurfaceCard> : null}
        </aside>
      </div>
    </PageShell>
  );
}
