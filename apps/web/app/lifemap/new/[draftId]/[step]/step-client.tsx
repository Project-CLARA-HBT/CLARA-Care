"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
  type GuidedFlowStep,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  commitLifeMapEpisodeDraft,
  getGuidedFlowDraft,
  updateLifeMapEpisodeDraft,
  type GuidedFlowDraft,
  type LifeMapEpisodeStep,
  type LifeMapPriority,
} from "@/lib/guided-flows";
import { guidedFlowSteps } from "@/lib/guided-flow-registry";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type LifeMapStepIdentifier =
  | "step-1"
  | "step-2"
  | "step-3"
  | "step-4"
  | "step-5"
  | "title"
  | "goal"
  | "priority"
  | "preview"
  | "review";

export function isValidLifeMapStep(step: string): boolean {
  return [
    "step-1",
    "step-2",
    "step-3",
    "step-4",
    "step-5",
    "title",
    "goal",
    "priority",
    "preview",
    "review",
  ].includes(step);
}

export function draftPath(draftId: string, step: string): string {
  return `/lifemap/new/${encodeURIComponent(draftId)}/${step}`;
}

export function getStepIndex(step: string): number {
  switch (step) {
    case "step-1":
    case "title":
      return 0;
    case "step-2":
    case "goal":
      return 1;
    case "step-3":
    case "priority":
      return 2;
    case "step-4":
    case "preview":
      return 3;
    case "step-5":
    case "review":
      return 4;
    default:
      return 0;
  }
}

export function toBackendStep(step: string): LifeMapEpisodeStep {
  switch (step) {
    case "step-1":
    case "title":
      return "title";
    case "step-2":
    case "goal":
      return "goal";
    case "step-3":
    case "priority":
      return "priority";
    case "step-4":
    case "preview":
    case "step-5":
    case "review":
    default:
      return "review";
  }
}

export function getAdjacentStep(
  currentStep: string,
  direction: "next" | "previous",
): string | null {
  if (currentStep.startsWith("step-")) {
    const num = parseInt(currentStep.replace("step-", ""), 10);
    if (direction === "next") {
      return num < 5 ? `step-${num + 1}` : null;
    } else {
      return num > 1 ? `step-${num - 1}` : null;
    }
  }

  if (direction === "next") {
    if (currentStep === "title") return "goal";
    if (currentStep === "goal") return "priority";
    if (currentStep === "priority") return "review";
    if (currentStep === "preview") return "review";
    return null;
  } else {
    if (currentStep === "review") return "priority";
    if (currentStep === "preview") return "priority";
    if (currentStep === "priority") return "goal";
    if (currentStep === "goal") return "title";
    return null;
  }
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `lifemap-${Date.now()}-commit`;
}

const PRIORITY_KEYS: Record<LifeMapPriority, UITranslationKey> = {
  routine: "lifemap.guided.priority.routine",
  soon: "lifemap.guided.priority.soon",
  urgent: "lifemap.guided.priority.urgent",
};

/**
 * Accumulated configuration preview card displayed across wizard steps.
 */
function AccumulatedPreviewCard({
  title,
  goal,
  priority,
  currentStepIndex,
  onEditStep,
}: {
  title: string;
  goal: string;
  priority: LifeMapPriority;
  currentStepIndex: number;
  onEditStep?: (target: string) => void;
}) {
  const language = useUILanguage();
  const priorityLabel = t(language, PRIORITY_KEYS[priority]);
  const notEntered = t(language, "lifemap.guided.review.notEntered");
  const cardHeadingId = useId();

  const priorityTone = priority === "urgent" ? "danger" : priority === "soon" ? "warn" : "brand";

  return (
    <section
      aria-labelledby={cardHeadingId}
      data-testid="accumulated-config-preview"
      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 transition-all duration-150"
    >
      <div className="flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)] pb-2.5">
        <div className="flex items-center gap-2">
          <Icon name="clinical-notes" size="1rem" className="text-[var(--brand-600)]" />
          <h3 id={cardHeadingId} className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
            {t(language, "lifemap.wizard.preview.cardTitle")}
          </h3>
        </div>
        <Badge tone="brand" className="text-[11px]">
          {currentStepIndex + 1}/5
        </Badge>
      </div>

      <div className="mt-3 grid gap-2.5 text-sm sm:grid-cols-3">
        {/* Title preview */}
        <div className="flex flex-col rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)] p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">
              {t(language, "lifemap.guided.title.requiredLabel")}
            </span>
            {onEditStep && currentStepIndex > 0 && title.trim() ? (
              <button
                type="button"
                onClick={() => onEditStep("step-1")}
                className="text-xs text-[var(--text-brand)] hover:underline"
              >
                {t(language, "action.edit")}
              </button>
            ) : null}
          </div>
          <p className="mt-1 font-semibold text-[var(--text-primary)] line-clamp-1">
            {title.trim() || <span className="font-normal italic text-[var(--text-muted)]">{notEntered}</span>}
          </p>
        </div>

        {/* Goal preview */}
        <div className="flex flex-col rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)] p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">
              {t(language, "lifemap.guided.review.goal")}
            </span>
            {onEditStep && currentStepIndex > 1 && goal.trim() ? (
              <button
                type="button"
                onClick={() => onEditStep("step-2")}
                className="text-xs text-[var(--text-brand)] hover:underline"
              >
                {t(language, "action.edit")}
              </button>
            ) : null}
          </div>
          <p className="mt-1 text-[var(--text-primary)] line-clamp-1">
            {goal.trim() || <span className="italic text-[var(--text-muted)]">{notEntered}</span>}
          </p>
        </div>

        {/* Priority preview */}
        <div className="flex flex-col rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)] p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">
              {t(language, "lifemap.guided.review.priority")}
            </span>
            {onEditStep && currentStepIndex > 2 ? (
              <button
                type="button"
                onClick={() => onEditStep("step-3")}
                className="text-xs text-[var(--text-brand)] hover:underline"
              >
                {t(language, "action.edit")}
              </button>
            ) : null}
          </div>
          <div className="mt-1">
            <Badge tone={priorityTone}>{priorityLabel}</Badge>
          </div>
        </div>
      </div>
    </section>
  );
}

export default function LifeMapEpisodeStepClient({
  draftId,
  step,
}: {
  draftId: string;
  step: string;
}) {
  const router = useRouter();
  const language = useUILanguage();
  const titleRef = useRef<HTMLInputElement>(null);
  const goalRef = useRef<HTMLTextAreaElement>(null);
  const priorityRef = useRef<HTMLSelectElement>(null);

  const [draft, setDraft] = useState<GuidedFlowDraft | null>(null);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState<LifeMapPriority>("routine");
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [inlineTitleError, setInlineTitleError] = useState<string | undefined>();
  const [inlineGoalError, setInlineGoalError] = useState<string | undefined>();

  const priorityLabel = (value: LifeMapPriority) => t(language, PRIORITY_KEYS[value]);

  const stepIndex = getStepIndex(step);
  const isNumberedFlow = step.startsWith("step-");

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
        const draftStepIndex = getStepIndex(loaded.current_step);
        if (stepIndex > draftStepIndex) {
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
  }, [draftId, hydrate, language, router, stepIndex]);

  // Live Title input handling with instant feedback
  const handleTitleChange = (value: string) => {
    setTitle(value);
    if (value.trim().length >= 2) {
      setInlineTitleError(undefined);
      setValidationErrors((prev) => prev.filter((err) => err.id !== "title-required"));
    }
  };

  // Live Goal input handling
  const handleGoalChange = (value: string) => {
    setGoal(value);
    if (value.length <= 4000) {
      setInlineGoalError(undefined);
      setValidationErrors((prev) => prev.filter((err) => err.id !== "goal-too-long"));
    } else {
      const errorMsg = "Mục tiêu không được vượt quá 4000 ký tự.";
      setInlineGoalError(errorMsg);
      setValidationErrors([
        {
          id: "goal-too-long",
          fieldId: "lifemap-episode-goal",
          fieldLabel: t(language, "lifemap.guided.review.goal"),
          message: errorMsg,
        },
      ]);
    }
  };

  const validateCurrentStep = (): boolean => {
    if (stepIndex === 0 && title.trim().length < 2) {
      const errorMsg = t(language, "lifemap.guided.title.required");
      setInlineTitleError(errorMsg);
      setValidationErrors([
        {
          id: "title-required",
          fieldId: "lifemap-episode-title",
          fieldLabel: t(language, "lifemap.guided.title.requiredLabel"),
          message: errorMsg,
        },
      ]);
      titleRef.current?.focus();
      return false;
    }

    if (stepIndex === 1 && goal.length > 4000) {
      const errorMsg = "Mục tiêu không được vượt quá 4000 ký tự.";
      setInlineGoalError(errorMsg);
      setValidationErrors([
        {
          id: "goal-too-long",
          fieldId: "lifemap-episode-goal",
          fieldLabel: t(language, "lifemap.guided.review.goal"),
          message: errorMsg,
        },
      ]);
      goalRef.current?.focus();
      return false;
    }

    setInlineTitleError(undefined);
    setInlineGoalError(undefined);
    setValidationErrors([]);
    return true;
  };

  const saveAndNavigate = async (target: string | null) => {
    if (!draft || !target) return;

    // Validate if moving forward
    const targetIndex = getStepIndex(target);
    if (targetIndex > stepIndex) {
      if (!validateCurrentStep()) return;
    } else {
      // Clear validation errors when moving backwards
      setValidationErrors([]);
      setInlineTitleError(undefined);
      setInlineGoalError(undefined);
    }

    setSaveState({ kind: "saving" });
    try {
      const backendTarget = toBackendStep(target);
      const updated = await updateLifeMapEpisodeDraft(
        draft.id,
        draft.revision,
        backendTarget,
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
    if (title.trim().length < 2) {
      const errorMsg = t(language, "lifemap.guided.title.required");
      setInlineTitleError(errorMsg);
      setValidationErrors([
        {
          id: "title-required",
          fieldId: "lifemap-episode-title",
          fieldLabel: t(language, "lifemap.guided.title.requiredLabel"),
          message: errorMsg,
        },
      ]);
      return;
    }

    setSaveState({ kind: "saving", message: t(language, "lifemap.guided.review.creating") });
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

  const previous = getAdjacentStep(step, "previous");
  const next = getAdjacentStep(step, "next");
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
  } else if (stepIndex === 0) {
    // Step 1: Journey Title
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <div className="space-y-1">
          <Field
            ref={titleRef}
            id="lifemap-episode-title"
            label={t(language, "lifemap.guided.title.label")}
            value={title}
            onChange={(event) => handleTitleChange(event.target.value)}
            maxLength={255}
            autoFocus
            aria-invalid={inlineTitleError ? true : undefined}
            placeholder={t(language, "lifemap.guided.title.placeholder")}
          />
          {inlineTitleError ? (
            <p
              id="lifemap-episode-title-inline-error"
              className="text-xs font-medium leading-5 text-[var(--status-danger-text)]"
            >
              {inlineTitleError}
            </p>
          ) : null}
          <div className="flex justify-end text-xs text-[var(--text-muted)]">
            <span>{title.length}/255</span>
          </div>
        </div>

        <AccumulatedPreviewCard
          title={title}
          goal={goal}
          priority={priority}
          currentStepIndex={0}
        />

        {actions}
      </div>
    );
  } else if (stepIndex === 1) {
    // Step 2: Goal
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <div className="space-y-1">
          <Textarea
            ref={goalRef}
            id="lifemap-episode-goal"
            label={t(language, "lifemap.guided.goal.label")}
            optional
            value={goal}
            onChange={(event) => handleGoalChange(event.target.value)}
            maxLength={4000}
            rows={5}
            autoFocus
            aria-invalid={inlineGoalError ? true : undefined}
            placeholder={t(language, "lifemap.guided.goal.placeholder")}
          />
          {inlineGoalError ? (
            <p
              id="lifemap-episode-goal-inline-error"
              className="text-xs font-medium leading-5 text-[var(--status-danger-text)]"
            >
              {inlineGoalError}
            </p>
          ) : null}
          <div className="flex justify-end text-xs text-[var(--text-muted)]">
            <span>{goal.length}/4000</span>
          </div>
        </div>

        <AccumulatedPreviewCard
          title={title}
          goal={goal}
          priority={priority}
          currentStepIndex={1}
          onEditStep={(target) => void saveAndNavigate(isNumberedFlow ? target : "title")}
        />

        {actions}
      </div>
    );
  } else if (stepIndex === 2) {
    // Step 3: Priority
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <div className="space-y-2">
          <Select
            ref={priorityRef}
            id="lifemap-episode-priority"
            label={t(language, "lifemap.guided.priority.label")}
            value={priority}
            onChange={(event) => setPriority(event.target.value as LifeMapPriority)}
            autoFocus
          >
            <option value="routine">{priorityLabel("routine")}</option>
            <option value="soon">{priorityLabel("soon")}</option>
            <option value="urgent">{priorityLabel("urgent")}</option>
          </Select>
          <p className="text-sm leading-6 text-[var(--text-secondary)]">
            {t(language, "lifemap.guided.priority.hint")}
          </p>
        </div>

        <AccumulatedPreviewCard
          title={title}
          goal={goal}
          priority={priority}
          currentStepIndex={2}
          onEditStep={(target) => void saveAndNavigate(isNumberedFlow ? target : target === "step-1" ? "title" : "goal")}
        />

        {actions}
      </div>
    );
  } else if (stepIndex === 3) {
    // Step 4: Step Preview / Configuration summary
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-[var(--text-primary)]">
              {t(language, "lifemap.wizard.preview.title")}
            </h2>
            <Badge tone="brand">
              {t(language, "lifemap.wizard.preview.glhsBadge")}
            </Badge>
          </div>

          <p className="text-sm leading-6 text-[var(--text-secondary)]">
            {t(language, "lifemap.wizard.preview.description")}
          </p>

          <ReviewSection
            title={t(language, "lifemap.wizard.preview.cardTitle")}
            items={[
              {
                label: t(language, "lifemap.guided.review.name"),
                value: title || t(language, "lifemap.guided.review.notEntered"),
              },
              {
                label: t(language, "lifemap.guided.review.goal"),
                value: goal || t(language, "lifemap.guided.review.notEntered"),
              },
              {
                label: t(language, "lifemap.guided.review.priority"),
                value: priorityLabel(priority),
              },
            ]}
          />

          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="edit"
              onClick={() => void saveAndNavigate(isNumberedFlow ? "step-1" : "title")}
            >
              {t(language, "lifemap.guided.title.requiredLabel")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="edit"
              onClick={() => void saveAndNavigate(isNumberedFlow ? "step-2" : "goal")}
            >
              {t(language, "lifemap.guided.review.goal")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="edit"
              onClick={() => void saveAndNavigate(isNumberedFlow ? "step-3" : "priority")}
            >
              {t(language, "lifemap.guided.review.priority")}
            </Button>
          </div>

          <p className="text-xs leading-5 text-[var(--text-secondary)]">
            {t(language, "lifemap.wizard.preview.glhsSecurityNote")}
          </p>
        </div>

        {actions}
      </div>
    );
  } else {
    // Step 5: Review & Commit
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <ReviewSection
          title={t(language, "lifemap.guided.review.title")}
          description={t(language, "lifemap.guided.review.description")}
          edit={{ href: draftPath(draft.id, isNumberedFlow ? "step-1" : "title") }}
          items={[
            {
              label: t(language, "lifemap.guided.review.name"),
              value: title || t(language, "lifemap.guided.review.notEntered"),
            },
            {
              label: t(language, "lifemap.guided.review.goal"),
              value: goal || t(language, "lifemap.guided.review.notEntered"),
            },
            {
              label: t(language, "lifemap.guided.review.priority"),
              value: priorityLabel(priority),
            },
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
            onClick: () => void saveAndNavigate(previous ?? (isNumberedFlow ? "step-4" : "priority")),
          }}
        />
      </div>
    );
  }

  // Flow steps presentation
  const flowSteps: GuidedFlowStep[] = isNumberedFlow || step === "preview"
    ? [
        { id: "step-1", label: t(language, "lifemap.guided.title.requiredLabel") },
        { id: "step-2", label: t(language, "lifemap.guided.review.goal") },
        { id: "step-3", label: t(language, "lifemap.guided.review.priority") },
        { id: "step-4", label: t(language, "lifemap.wizard.preview.title") },
        { id: "step-5", label: t(language, "lifemap.guided.review.title") },
      ]
    : guidedFlowSteps("lifemapEpisode", language);

  const stepTitle =
    stepIndex === 0
      ? t(language, "lifemap.guided.page.title")
      : stepIndex === 1
        ? t(language, "lifemap.guided.page.goal")
        : stepIndex === 2
          ? t(language, "lifemap.guided.page.priority")
          : stepIndex === 3
            ? t(language, "lifemap.wizard.preview.title")
            : t(language, "lifemap.guided.page.review");

  return (
    <GuidedFlowShell
      eyebrow={t(language, "lifemap.guided.eyebrow")}
      title={stepTitle}
      description={t(language, "lifemap.guided.page.description")}
      steps={flowSteps}
      currentStep={stepIndex}
      saveState={saveState}
      aside={t(language, "lifemap.guided.page.aside")}
    >
      {content}
    </GuidedFlowShell>
  );
}
