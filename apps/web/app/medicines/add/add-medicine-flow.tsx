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
import { Field } from "@/components/ui/field";
import { t } from "@/lib/i18n/catalog";
import { createMedicationCourse } from "@/lib/medication-courses";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "identity" | "details" | "schedule" | "review";

type MedicineDraft = {
  medicationName: string;
  dose: string;
  route: string;
  form: string;
  schedule: string;
  drugbankId: string;
};

const EMPTY_DRAFT: MedicineDraft = {
  medicationName: "",
  dose: "",
  route: "",
  form: "",
  schedule: "",
  drugbankId: "",
};

function clean(value: string): string | undefined {
  const next = value.trim();
  return next || undefined;
}

export default function AddMedicineFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const steps: Array<{ id: Step; label: string }> = [
    { id: "identity", label: t(language, "medicineAdd.step.identity") },
    { id: "details", label: t(language, "medicineAdd.step.details") },
    { id: "schedule", label: t(language, "medicineAdd.step.schedule") },
    { id: "review", label: t(language, "medicineAdd.step.review") },
  ];
  const titleByStep: Record<Step, string> = {
    identity: t(language, "medicineAdd.title.identity"),
    details: t(language, "medicineAdd.title.details"),
    schedule: t(language, "medicineAdd.title.schedule"),
    review: t(language, "medicineAdd.title.review"),
  };
  const descriptionByStep: Record<Step, string> = {
    identity: t(language, "medicineAdd.description.identity"),
    details: t(language, "medicineAdd.description.details"),
    schedule: t(language, "medicineAdd.description.schedule"),
    review: t(language, "medicineAdd.description.review"),
  };
  const nameRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("identity");
  const [draft, setDraft] = useState<MedicineDraft>(EMPTY_DRAFT);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const update = <K extends keyof MedicineDraft>(key: K, value: MedicineDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const advance = () => {
    if (step === "identity" && draft.medicationName.trim().length < 2) {
      setValidationErrors([
        {
          id: "medicine-name-required",
          fieldId: "medicine-name",
          fieldLabel: t(language, "medicineAdd.step.identity"),
          message: t(language, "medicineAdd.validation.name"),
        },
      ]);
      nameRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const stepIndex = steps.findIndex((candidate) => candidate.id === step);
    const next = steps[stepIndex + 1]?.id ?? null;
    if (next) setStep(next);
  };

  const commit = async () => {
    setValidationErrors([]);
    setSaveState({ kind: "saving", message: t(language, "medicineAdd.saving") });
    try {
      await createMedicationCourse({
        medication_name: draft.medicationName.trim(),
        dose_text: clean(draft.dose),
        route_text: clean(draft.route),
        form_text: clean(draft.form),
        schedule_text: clean(draft.schedule),
        drugbank_id: clean(draft.drugbankId),
      });
      router.replace("/medicines?tab=list");
      router.refresh();
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "medicineAdd.saveFailed"),
      });
    }
  };

  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id ?? null;
  const saving = saveState.kind === "saving";
  let content;

  if (step === "identity") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={nameRef}
          id="medicine-name"
          label={t(language, "medicineAdd.field.name")}
          value={draft.medicationName}
          onChange={(event) => update("medicationName", event.target.value)}
          autoFocus
          autoComplete="off"
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.name")}
          aria-invalid={validationErrors.length > 0 || undefined}
          aria-describedby={validationErrors.length ? "medicine-name-error" : undefined}
        />
        {validationErrors.length ? (
          <p id="medicine-name-error" className="text-sm text-[var(--status-danger-text)]">
            {validationErrors[0].message}
          </p>
        ) : null}
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.backToList"), href: "/medicines?tab=list" }}
        />
      </div>
    );
  } else if (step === "details") {
    content = (
      <div className="space-y-5">
        <Field
          id="medicine-dose"
          label={t(language, "medicineAdd.field.dose")}
          optional
          value={draft.dose}
          onChange={(event) => update("dose", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.dose")}
        />
        <Field
          id="medicine-route"
          label={t(language, "medicineAdd.field.route")}
          optional
          value={draft.route}
          onChange={(event) => update("route", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.route")}
        />
        <Field
          id="medicine-form"
          label={t(language, "medicineAdd.field.form")}
          optional
          value={draft.form}
          onChange={(event) => update("form", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.form")}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep(back ?? "identity") }}
        />
      </div>
    );
  } else if (step === "schedule") {
    content = (
      <div className="space-y-5">
        <Field
          id="medicine-schedule"
          label={t(language, "medicineAdd.field.schedule")}
          optional
          value={draft.schedule}
          onChange={(event) => update("schedule", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.schedule")}
        />
        <Field
          id="medicine-drugbank-id"
          label={t(language, "medicineAdd.field.drugbankId")}
          optional
          value={draft.drugbankId}
          onChange={(event) => update("drugbankId", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.drugbankId")}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep(back ?? "details") }}
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title={t(language, "medicineAdd.review.title")}
          description={t(language, "medicineAdd.review.description")}
          edit={{ label: t(language, "medicineAdd.review.editName"), onClick: () => setStep("identity") }}
          items={[
            { label: t(language, "medicineAdd.field.name"), value: draft.medicationName.trim() },
            { label: t(language, "medicineAdd.field.dose"), value: clean(draft.dose) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.route"), value: clean(draft.route) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.form"), value: clean(draft.form) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.schedule"), value: clean(draft.schedule) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.drugbankId"), value: clean(draft.drugbankId) ?? t(language, "medicineAdd.review.empty") },
          ]}
        />
        <StepActions
          nextLabel={t(language, "medicineAdd.save")}
          nextType="button"
          onNext={() => void commit()}
          saving={saving}
          savingLabel={t(language, "flow.saving")}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep("schedule") }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "medicineAdd.eyebrow")}
      title={titleByStep[step]}
      description={descriptionByStep[step]}
      steps={steps}
      currentStep={steps.findIndex((candidate) => candidate.id === step)}
      saveState={saveState}
      aside={t(language, "medicineAdd.safetyNote")}
    >
      {content}
    </GuidedFlowShell>
  );
}
