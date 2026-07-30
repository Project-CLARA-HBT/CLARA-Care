"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { Textarea } from "@/components/ui/field";
import {
  createLifeMapVisitPreparationDraft,
  getLifeMapV2Capabilities,
  type LifeMapVisitPreparationDraft,
} from "@/lib/lifemap";
import { getProfileContext } from "@/lib/profile-context-api";
import { t } from "@/lib/i18n/catalog";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

function renderDraftForCopy(draft: LifeMapVisitPreparationDraft): string {
  const summary = draft.plain_language_summary;
  return [
    draft.title,
    summary?.important_now,
    summary?.next_step,
    ...draft.questions_to_consider.map((question) => `- ${question.text}`),
  ]
    .filter((value): value is string => Boolean(value?.trim()))
    .join("\n\n");
}

export default function LifeMapVisitPreparationPage() {
  const [language, setLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [goal, setGoal] = useState("");
  const [draft, setDraft] = useState<LifeMapVisitPreparationDraft | null>(null);
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
      setError(cause instanceof Error ? cause.message : t(language, "visitPrep.error"));
    } finally {
      setLoading(false);
    }
  }, [goal, language]);

  const copyDraft = useCallback(async () => {
    if (!draft || !navigator.clipboard) return;
    await navigator.clipboard.writeText(renderDraftForCopy(draft));
    setCopied(true);
  }, [draft]);

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
            {!draft && !loading ? <EmptyState title={t(language, "visitPrep.noDraft")} /> : null}
            {draft ? <VisitPreparationDraftView draft={draft} language={language} copied={copied} onCopy={() => void copyDraft()} /> : null}
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
  onCopy,
}: {
  draft: LifeMapVisitPreparationDraft;
  language: UILanguage;
  copied: boolean;
  onCopy: () => void;
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
      <Button variant="secondary" onClick={onCopy}>{copied ? t(language, "visitPrep.copied") : t(language, "visitPrep.copy")}</Button>
    </div>
  );
}

function DraftSection({ title, children }: { title: string; children: React.ReactNode }) {
  return <SurfaceCard className="space-y-2 p-5"><h2 className="font-semibold text-[var(--text-primary)]">{title}</h2><div className="text-sm leading-6 text-[var(--text-secondary)]">{children}</div></SurfaceCard>;
}
