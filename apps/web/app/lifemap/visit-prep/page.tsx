"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { Textarea } from "@/components/ui/field";
import { StepProgress, type GuidedFlowStep } from "@/components/guided-flow";
import {
  createLifeMapVisitPreparationDraft,
  getLifeMapV2Capabilities,
  type LifeMapVisitPreparationDraft,
} from "@/lib/lifemap";
import { getProfileContext } from "@/lib/profile-context-api";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

function renderDraftForCopy(
  draft: LifeMapVisitPreparationDraft,
  notes: string,
  notesTitle: string,
): string {
  const summary = draft.plain_language_summary;
  const localNotes = notes.trim();
  return [
    draft.title,
    summary?.important_now,
    summary?.next_step,
    ...draft.questions_to_consider.map((question) => `- ${question.text}`),
    localNotes ? `${notesTitle}\n${localNotes}` : undefined,
  ]
    .filter((value): value is string => Boolean(value?.trim()))
    .join("\n\n");
}

export default function LifeMapVisitPreparationPage() {
  const [language, setLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [goal, setGoal] = useState("");
  const [draft, setDraft] = useState<LifeMapVisitPreparationDraft | null>(null);
  // Deliberately React-only state: personal visit notes must not become a
  // LifeMap event, an API payload, or a persistent browser record.
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLanguage(getStoredUILanguage());
    return onUILanguageChange(setLanguage);
  }, []);

  useEffect(() => {
    void getProfileContext()
      .then(async (context) => {
        if (!context.active_profile_id) {
          setEnabled(false);
          return;
        }
        const capabilities = await getLifeMapV2Capabilities(context.active_profile_id);
        setEnabled(Boolean(capabilities.lifemap_vietnamese_drafts));
      })
      .catch(() => setEnabled(false));
  }, []);

  const buildDraft = useCallback(async () => {
    setLoading(true);
    setError("");
    setCopied(false);
    try {
      setDraft(await createLifeMapVisitPreparationDraft(goal.trim(), language));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "visitPrep.error")));
    } finally {
      setLoading(false);
    }
  }, [goal, language]);

  const copyDraft = useCallback(async () => {
    if (!draft || !navigator.clipboard) return;
    await navigator.clipboard.writeText(
      renderDraftForCopy(draft, notes, t(language, "visitPrep.localNotes.copyHeading")),
    );
    setCopied(true);
  }, [draft, language, notes]);

  const steps: GuidedFlowStep[] = [
    { id: "scope", label: t(language, "visitPrep.step.scope") },
    { id: "review", label: t(language, "visitPrep.step.review") },
  ];
  const reviewing = Boolean(draft);

  const returnToScope = useCallback(() => {
    setDraft(null);
    setCopied(false);
  }, []);

  return (
    <PageShell
      variant="plain"
      title={t(language, "visitPrep.title")}
      description={t(language, "visitPrep.description")}
    >
      <div className="mx-auto max-w-3xl space-y-5">
        <Link className="focus-ring inline-flex text-sm font-medium text-[var(--text-brand)]" href="/visits">
          ← {t(language, "visitPrep.back")}
        </Link>
        {enabled === null ? <LoadingCards count={2} /> : null}
        {enabled === false ? (
          <EmptyState title={t(language, "visitPrep.unavailable")} />
        ) : null}
        {enabled ? (
          <>
            <StepProgress steps={steps} currentStep={reviewing ? 1 : 0} />
            {draft ? (
              <VisitPreparationDraftView
                draft={draft}
                language={language}
                copied={copied}
                notes={notes}
                onNotesChange={setNotes}
                onCopy={() => void copyDraft()}
                onAdjustScope={returnToScope}
              />
            ) : (
              <>
                <SurfaceCard className="space-y-4 p-5">
                  <div>
                    <label className="text-sm font-semibold text-[var(--text-primary)]" htmlFor="visit-prep-goal">
                      {t(language, "visitPrep.goalLabel")}
                    </label>
                    <p className="mt-1 text-sm text-[var(--text-secondary)]">{t(language, "visitPrep.goalHint")}</p>
                  </div>
                  <Textarea
                    id="visit-prep-goal"
                    value={goal}
                    onChange={(event) => setGoal(event.target.value)}
                    rows={4}
                  />
                  <Button loading={loading} loadingLabel={t(language, "visitPrep.building")} onClick={() => void buildDraft()}>
                    {t(language, "visitPrep.build")}
                  </Button>
                </SurfaceCard>

                {error ? <InlineError message={error} onRetry={() => void buildDraft()} /> : null}
                {!loading ? <EmptyState title={t(language, "visitPrep.noDraft")} /> : null}
              </>
            )}
          </>
        ) : null}
      </div>
    </PageShell>
  );
}

function VisitPreparationDraftView({
  draft,
  language,
  copied,
  notes,
  onNotesChange,
  onCopy,
  onAdjustScope,
}: {
  draft: LifeMapVisitPreparationDraft;
  language: UILanguage;
  copied: boolean;
  notes: string;
  onNotesChange: (value: string) => void;
  onCopy: () => void;
  onAdjustScope: () => void;
}) {
  const summary = draft.plain_language_summary;
  return (
    <div className="space-y-4">
      <SurfaceCard className="border-[color:var(--status-warning-border)] bg-[var(--status-warning-soft)] p-4 text-sm text-[var(--text-primary)]">
        {t(language, "visitPrep.reviewNotice")}
      </SurfaceCard>
      {summary ? (
        <>
          <DraftSection title={t(language, "visitPrep.importantNow")}>{summary.important_now}</DraftSection>
          <DraftSection title={t(language, "visitPrep.basedOn")}>
            <ul className="space-y-2">
              {summary.based_on.map((row) => <li key={row.citation_ids.join("-")}>{row.text}</li>)}
            </ul>
          </DraftSection>
          {summary.uncertainty.length ? <DraftSection title={t(language, "visitPrep.uncertainty")}><ul>{summary.uncertainty.map((item) => <li key={item}>{item}</li>)}</ul></DraftSection> : null}
          <DraftSection title={t(language, "visitPrep.nextStep")}>{summary.next_step}</DraftSection>
          <DraftSection title={t(language, "visitPrep.urgent")}>{summary.urgent_help}</DraftSection>
        </>
      ) : null}
      <DraftSection title={t(language, "visitPrep.questions")}>
        {draft.questions_to_consider.length ? (
          <ol className="list-decimal space-y-3 pl-5">{draft.questions_to_consider.map((question) => <li key={question.citation_ids.join("-")}>{question.text}</li>)}</ol>
        ) : <p>{t(language, "visitPrep.noQuestions")}</p>}
      </DraftSection>
      <SurfaceCard className="space-y-3 p-5">
        <div>
          <h2 className="font-semibold text-[var(--text-primary)]">{t(language, "visitPrep.localNotes.label")}</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{t(language, "visitPrep.localNotes.hint")}</p>
        </div>
        <Textarea
          id="visit-prep-local-notes"
          value={notes}
          onChange={(event) => onNotesChange(event.target.value)}
          rows={5}
          maxLength={2500}
          autoComplete="off"
          placeholder={t(language, "visitPrep.localNotes.placeholder")}
        />
      </SurfaceCard>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Button variant="secondary" onClick={onCopy}>{copied ? t(language, "visitPrep.copied") : t(language, "visitPrep.copy")}</Button>
        <Button variant="ghost" onClick={onAdjustScope}>{t(language, "visitPrep.adjustScope")}</Button>
      </div>
    </div>
  );
}

function DraftSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <SurfaceCard className="space-y-2 p-5"><h2 className="font-semibold text-[var(--text-primary)]">{title}</h2><div className="text-sm leading-6 text-[var(--text-secondary)]">{children}</div></SurfaceCard>;
}
