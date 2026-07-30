"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Field, Select, Textarea } from "@/components/ui/field";
import {
  commitLifeMapEpisodeDraft,
  getGuidedFlowDraft,
  updateLifeMapEpisodeDraft,
  type GuidedFlowDraft,
  type LifeMapEpisodeStep,
  type LifeMapPriority,
} from "@/lib/guided-flows";
import {
  LIFEMAP_EPISODE_STEP_IDS,
  adjacentGuidedFlowStep,
  guidedFlowSteps,
  isGuidedFlowStepAhead,
} from "@/lib/guided-flow-registry";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

function draftPath(draftId: string, step: LifeMapEpisodeStep): string {
  return `/lifemap/new/${encodeURIComponent(draftId)}/${step}`;
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `lifemap-${Date.now()}-commit`;
}

const PRIORITY_KEYS: Record<LifeMapPriority, UITranslationKey> = {
  routine: "lifemap.guided.priority.routine",
  soon: "lifemap.guided.priority.soon",
  urgent: "lifemap.guided.priority.urgent",
};

export default function LifeMapEpisodeStepClient({
  draftId,
  step,
}: {
  draftId: string;
  step: LifeMapEpisodeStep;
}) {
  const router = useRouter();
  const language = useUILanguage();
  const titleRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<GuidedFlowDraft | null>(null);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState<LifeMapPriority>("routine");
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const priorityLabel = (value: LifeMapPriority) => t(language, PRIORITY_KEYS[value]);

  const hydrate = useCallback((nextDraft: GuidedFlowDraft) => {
    setDraft(nextDraft);
    setTitle(nextDraft.payload.title ?? "");
    setGoal(nextDraft.payload.goal ?? "");
    setPriority(nextDraft.payload.priority ?? "routine");
  }, []);

  useEffect(() => {
    let active = true;
    void getGuidedFlowDraft(draftId)
      .then((loaded) => {
        if (!active) return;
        if (loaded.status !== "active") {
          router.replace("/lifemap");
          return;
        }
        hydrate(loaded);
        if (
          isGuidedFlowStepAhead(
            "lifemapEpisode",
            step,
            loaded.current_step,
          )
        ) {
          router.replace(draftPath(loaded.id, loaded.current_step));
        }
      })
      .catch(() => {
        if (active) {
          setSaveState({
            kind: "error",
            message: t(language, "lifemap.guided.loadError"),
          });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [draftId, hydrate, language, router, step]);

  const saveAndNavigate = async (target: LifeMapEpisodeStep | null) => {
    if (!draft || !target) return;
    if (step === "title" && title.trim().length < 2) {
      setValidationErrors([
        {
          id: "title-required",
          fieldId: "lifemap-episode-title",
          fieldLabel: t(language, "lifemap.guided.title.requiredLabel"),
          message: t(language, "lifemap.guided.title.required"),
        },
      ]);
      titleRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "saving" });
    try {
      const updated = await updateLifeMapEpisodeDraft(
        draft.id,
        draft.revision,
        target,
        {
          title: title.trim(),
          goal: goal.trim(),
          priority,
        },
      );
      hydrate(updated);
      setSaveState({ kind: "saved" });
      router.push(draftPath(updated.id, target));
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "lifemap.guided.saveConflict"),
      });
    }
  };

  const commit = async () => {
    if (!draft) return;
    setSaveState({ kind: "saving" });
    try {
      const committed = await commitLifeMapEpisodeDraft(
        draft.id,
        draft.revision,
        newIdempotencyKey(),
      );
      if (committed.status === "committed") {
        router.replace("/lifemap");
        router.refresh();
      }
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "lifemap.guided.commitError"),
      });
    }
  };

  const previous = adjacentGuidedFlowStep("lifemapEpisode", step, "previous");
  const next = adjacentGuidedFlowStep("lifemapEpisode", step, "next");
  const saving = saveState.kind === "saving";
  const actions = (
    <StepActions
      saving={saving}
      onNext={() => void saveAndNavigate(next)}
      nextType="button"
      back={
        previous
          ? {
              label: t(language, "lifemap.guided.back"),
              onClick: () => void saveAndNavigate(previous),
            }
          : { label: t(language, "lifemap.guided.exit"), href: "/lifemap" }
      }
    />
  );

  let content;
  if (loading) {
    content = (
      <div
        aria-label={t(language, "lifemap.guided.loadingAria")}
        className="h-32 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]"
      />
    );
  } else if (!draft) {
    content = (
      <StepActions
        nextLabel={t(language, "lifemap.guided.backToLifeMap")}
        nextType="button"
        onNext={() => router.replace("/lifemap")}
      />
    );
  } else if (step === "title") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={titleRef}
          id="lifemap-episode-title"
          label={t(language, "lifemap.guided.title.label")}
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={255}
          autoFocus
          placeholder={t(language, "lifemap.guided.title.placeholder")}
        />
        {actions}
      </div>
    );
  } else if (step === "goal") {
    content = (
      <div className="space-y-5">
        <Textarea
          id="lifemap-episode-goal"
          label={t(language, "lifemap.guided.goal.label")}
          optional
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          maxLength={4000}
          rows={5}
          placeholder={t(language, "lifemap.guided.goal.placeholder")}
        />
        {actions}
      </div>
    );
  } else if (step === "priority") {
    content = (
      <div className="space-y-5">
        <Select
          id="lifemap-episode-priority"
          label={t(language, "lifemap.guided.priority.label")}
          value={priority}
          onChange={(event) => setPriority(event.target.value as LifeMapPriority)}
        >
          <option value="routine">{priorityLabel("routine")}</option>
          <option value="soon">{priorityLabel("soon")}</option>
          <option value="urgent">{priorityLabel("urgent")}</option>
        </Select>
        <p className="text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "lifemap.guided.priority.hint")}
        </p>
        {actions}
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title={t(language, "lifemap.guided.review.title")}
          description={t(language, "lifemap.guided.review.description")}
          edit={{ href: draftPath(draft.id, "title") }}
          items={[
            { label: t(language, "lifemap.guided.review.name"), value: title || t(language, "lifemap.guided.review.notEntered") },
            { label: t(language, "lifemap.guided.review.goal"), value: goal || t(language, "lifemap.guided.review.notEntered") },
            { label: t(language, "lifemap.guided.review.priority"), value: priorityLabel(priority) },
          ]}
        />
        <StepActions
          nextLabel={t(language, "lifemap.guided.review.create")}
          nextType="button"
          onNext={() => void commit()}
          saving={saving}
          savingLabel={t(language, "lifemap.guided.review.creating")}
          back={{
            label: t(language, "lifemap.guided.back"),
            onClick: () => void saveAndNavigate("priority"),
          }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "lifemap.guided.eyebrow")}
      title={
        step === "title"
          ? t(language, "lifemap.guided.page.title")
          : step === "goal"
            ? t(language, "lifemap.guided.page.goal")
            : step === "priority"
              ? t(language, "lifemap.guided.page.priority")
              : t(language, "lifemap.guided.page.review")
      }
      description={t(language, "lifemap.guided.page.description")}
      steps={guidedFlowSteps("lifemapEpisode", language)}
      currentStep={LIFEMAP_EPISODE_STEP_IDS.indexOf(step)}
      saveState={saveState}
      aside={t(language, "lifemap.guided.page.aside")}
    >
      {content}
    </GuidedFlowShell>
  );
}
