"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Field, Textarea } from "@/components/ui/field";
import { t } from "@/lib/i18n/catalog";
import { createVisit } from "@/lib/visit-family";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "name" | "purpose" | "time" | "review";

type VisitDraft = {
  title: string;
  goal: string;
  scheduledAt: string;
};

const EMPTY_DRAFT: VisitDraft = { title: "", goal: "", scheduledAt: "" };

function displayScheduledAt(value: string, language: "vi" | "en"): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat(language, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export default function NewVisitFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const nameRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("name");
  const [draft, setDraft] = useState<VisitDraft>(EMPTY_DRAFT);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const steps: Array<{ id: Step; label: string }> = [
    { id: "name", label: t(language, "visitCreate.step.name") },
    { id: "purpose", label: t(language, "visitCreate.step.purpose") },
    { id: "time", label: t(language, "visitCreate.step.time") },
    { id: "review", label: t(language, "visitCreate.step.review") },
  ];
  const titleByStep: Record<Step, string> = {
    name: t(language, "visitCreate.title.name"),
    purpose: t(language, "visitCreate.title.purpose"),
    time: t(language, "visitCreate.title.time"),
    review: t(language, "visitCreate.title.review"),
  };
  const descriptionByStep: Record<Step, string> = {
    name: t(language, "visitCreate.description.name"),
    purpose: t(language, "visitCreate.description.purpose"),
    time: t(language, "visitCreate.description.time"),
    review: t(language, "visitCreate.description.review"),
  };
  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id;
  const saving = saveState.kind === "saving";

  const update = <K extends keyof VisitDraft>(key: K, value: VisitDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const advance = () => {
    if (step === "name" && draft.title.trim().length < 2) {
      setValidationErrors([
        {
          id: "visit-title-required",
          fieldId: "visit-title",
          fieldLabel: t(language, "visitCreate.field.name"),
          message: t(language, "visitCreate.validation.name"),
        },
      ]);
      nameRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const next = steps[stepIndex + 1]?.id;
    if (next) setStep(next);
  };

  const save = async () => {
    setSaveState({ kind: "saving", message: t(language, "visitCreate.saving") });
    try {
      const created = await createVisit({
        title: draft.title.trim(),
        goal: draft.goal.trim(),
        visit_type: "other",
        scheduled_at: draft.scheduledAt
          ? new Date(draft.scheduledAt).toISOString()
          : undefined,
      });
      router.replace(`/visits?visit=${encodeURIComponent(created.id)}`);
      router.refresh();
    } catch {
      setSaveState({ kind: "error", message: t(language, "visitCreate.saveFailed") });
    }
  };

  let content;
  if (step === "name") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={nameRef}
          id="visit-title"
          label={t(language, "visitCreate.field.name")}
          value={draft.title}
          onChange={(event) => update("title", event.target.value)}
          autoFocus
          autoComplete="off"
          maxLength={255}
          placeholder={t(language, "visitCreate.placeholder.name")}
          aria-invalid={validationErrors.length > 0 || undefined}
          aria-describedby={validationErrors.length ? "visit-title-error" : undefined}
        />
        {validationErrors.length ? (
          <p id="visit-title-error" className="text-sm text-[var(--status-danger-text)]">
            {validationErrors[0].message}
          </p>
        ) : null}
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.cancel"), href: "/visits" }}
        />
      </div>
    );
  } else if (step === "purpose") {
    content = (
      <div className="space-y-5">
        <Textarea
          id="visit-goal"
          label={t(language, "visitCreate.field.purpose")}
          optional
          value={draft.goal}
          onChange={(event) => update("goal", event.target.value)}
          maxLength={2000}
          className="min-h-32"
          placeholder={t(language, "visitCreate.placeholder.purpose")}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep(back ?? "name") }}
          skip={{ label: t(language, "visitCreate.skip"), onClick: advance }}
        />
      </div>
    );
  } else if (step === "time") {
    content = (
      <div className="space-y-5">
        <Field
          id="visit-time"
          label={t(language, "visitCreate.field.time")}
          optional
          type="datetime-local"
          value={draft.scheduledAt}
          onChange={(event) => update("scheduledAt", event.target.value)}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep(back ?? "purpose") }}
          skip={{ label: t(language, "visitCreate.skip"), onClick: advance }}
        />
      </div>
    );
  } else {
    const noValue = t(language, "visitCreate.review.empty");
    content = (
      <div className="space-y-5">
        <ReviewSection
          title={t(language, "visitCreate.review.title")}
          description={t(language, "visitCreate.review.description")}
          edit={{ label: t(language, "visitCreate.review.edit"), onClick: () => setStep("name") }}
          items={[
            { label: t(language, "visitCreate.field.name"), value: draft.title.trim() },
            { label: t(language, "visitCreate.field.purpose"), value: draft.goal.trim() || noValue },
            {
              label: t(language, "visitCreate.field.time"),
              value: displayScheduledAt(draft.scheduledAt, language) ?? noValue,
            },
          ]}
        />
        <StepActions
          nextLabel={t(language, "visitCreate.save")}
          nextType="button"
          onNext={() => void save()}
          saving={saving}
          savingLabel={t(language, "visitCreate.saving")}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep("time") }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "visitCreate.eyebrow")}
      title={titleByStep[step]}
      description={descriptionByStep[step]}
      steps={steps}
      currentStep={stepIndex}
      saveState={saveState}
      aside={t(language, "visitCreate.safetyNote")}
    >
      {content}
    </GuidedFlowShell>
  );
}
