"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { useRouter } from "next/navigation";

import {
  GuidedFlowShell,
  ErrorSummary,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Field, Select } from "@/components/ui/field";
import { Toggle } from "@/components/ui/toggle";
import { getRole } from "@/lib/auth-store";
import { getRoleHomePath } from "@/lib/navigation.config";
import {
  getPhrOnboarding,
  updatePhrOnboarding,
  type PhrOnboarding,
  type PhrOnboardingPatch,
} from "@/lib/phr-onboarding";
import {
  adjacentGuidedFlowStep,
  guidedFlowPath,
  guidedFlowSteps,
  WELCOME_STEP_IDS,
} from "@/lib/guided-flow-registry";
import {
  type WelcomeStepId,
} from "../welcome-steps";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

type WelcomeDraftPatch = Omit<PhrOnboardingPatch, "action">;

function genderOptions(language: UILanguage) {
  return [
    ["", t(language, "welcome.gender.none")],
    ["female", t(language, "welcome.gender.female")],
    ["male", t(language, "welcome.gender.male")],
    ["other", t(language, "welcome.gender.other")],
  ] as const;
}
const BLOOD_TYPES = ["", "A", "B", "AB", "O"] as const;

function path(step: WelcomeStepId) {
  return guidedFlowPath("welcome", step);
}

function numeric(value: string): number | null {
  const parsed = Number(value.replace(",", "."));
  return value.trim() && Number.isFinite(parsed) ? parsed : null;
}

function measurementError(
  value: string,
  maximum: number,
  fieldId: string,
  fieldLabel: string,
  language: UILanguage,
): GuidedFlowError | null {
  if (!value.trim()) return null;
  const parsed = numeric(value);
  if (parsed !== null && parsed >= 0 && parsed <= maximum) return null;
  return {
    id: `${fieldId}-invalid`,
    fieldId,
    fieldLabel,
    message: t(language, "welcome.measurementError", { maximum }),
  };
}

export default function WelcomeStepClient({ step }: { step: WelcomeStepId }) {
  const router = useRouter();
  const language = useUILanguage();
  const flowSteps = guidedFlowSteps("welcome", language);
  const genders = genderOptions(language);
  const stepIndex = WELCOME_STEP_IDS.indexOf(step);
  const previous = adjacentGuidedFlowStep("welcome", step, "previous");
  const next = adjacentGuidedFlowStep("welcome", step, "next");

  const [onboarding, setOnboarding] = useState<PhrOnboarding | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({
    kind: "idle",
  });
  const [fullName, setFullName] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [bloodType, setBloodType] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [consent, setConsent] = useState(false);
  const [selfDeclaredConfirmed, setSelfDeclaredConfirmed] = useState(false);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const heightRef = useRef<HTMLInputElement>(null);
  const weightRef = useRef<HTMLInputElement>(null);

  const hydrate = useCallback((data: PhrOnboarding) => {
    setOnboarding(data);
    setFullName(data.record.full_name ?? "");
    setDob(data.record.date_of_birth ?? "");
    setGender(data.record.gender ?? "");
    setBloodType(data.record.blood_type ?? "");
    setHeightCm(
      data.record.height_cm == null ? "" : String(data.record.height_cm),
    );
    setWeightKg(
      data.record.weight_kg == null ? "" : String(data.record.weight_kg),
    );
    setConsent(Boolean(data.personalization_consent));
  }, []);

  useEffect(() => {
    let active = true;
    void getPhrOnboarding()
      .then((data) => {
        if (!active) return;
        hydrate(data);
        if (!data.needs_onboarding) {
          router.replace(getRoleHomePath(getRole()));
        }
      })
      .catch(() => {
        if (active) {
          setSaveState({
            kind: "error",
            message:
              t(language, "welcome.loadError"),
          });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [hydrate, language, router]);

  const saveAndNavigate = async (
    patch: WelcomeDraftPatch,
    target: WelcomeStepId | null,
  ) => {
    if (!target) return;
    setValidationErrors([]);
    setSaveState({ kind: "saving" });
    try {
      const updated = await updatePhrOnboarding({ ...patch, action: "save" });
      hydrate(updated);
      setSaveState({ kind: "saved" });
      router.push(path(target));
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "welcome.saveError"),
      });
    }
  };

  const finish = async (action: "complete" | "skip") => {
    if (action === "complete" && !selfDeclaredConfirmed) return;
    setSaveState({ kind: "saving" });
    try {
      await updatePhrOnboarding(
        action === "skip"
          ? { action: "skip" }
          : { action: "complete", confirm_self_declared: true },
      );
      router.replace(getRoleHomePath(getRole()));
      router.refresh();
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "welcome.completeError"),
      });
    }
  };

  const saving = saveState.kind === "saving";
  const actions = (patch: WelcomeDraftPatch) => (
    <StepActions
      saving={saving}
      nextLabel={t(language, "welcome.continue")}
      savingLabel={t(language, "welcome.saving")}
      onNext={() => void saveAndNavigate(patch, next)}
      nextType="button"
      back={
        previous
          ? {
              label: t(language, "welcome.back"),
              onClick: () => void saveAndNavigate(patch, previous),
            }
          : undefined
      }
      skip={
        next ? { label: t(language, "welcome.skip"), href: path(next) } : undefined
      }
    />
  );
  const navigateWithMeasurement = ({
    value,
    maximum,
    fieldId,
    fieldLabel,
    ref,
    patch,
    target,
  }: {
    value: string;
    maximum: number;
    fieldId: string;
    fieldLabel: string;
    ref: RefObject<HTMLInputElement | null>;
    patch: WelcomeDraftPatch;
    target: WelcomeStepId | null;
  }) => {
    const error = measurementError(value, maximum, fieldId, fieldLabel, language);
    setValidationErrors(error ? [error] : []);
    if (error) {
      ref.current?.focus();
      return;
    }
    void saveAndNavigate(patch, target);
  };

  let content;
  if (loading) {
    content = (
      <div className="space-y-3" aria-label={t(language, "welcome.loading")}>
        <div className="h-5 w-1/2 animate-pulse rounded bg-[var(--surface-muted)]" />
        <div className="h-28 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
      </div>
    );
  } else if (step === "start") {
    content = (
      <div className="space-y-6">
        <Badge tone="brand" icon="spa">
          {t(language, "auth.brand")}
        </Badge>
        <p className="leading-7 text-[var(--text-secondary)]">
          {t(language, "welcome.start.intro")}
        </p>
        <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
          <li>• {t(language, "welcome.start.itemOne")}</li>
          <li>• {t(language, "welcome.start.itemTwo")}</li>
          <li>• {t(language, "welcome.start.itemThree")}</li>
        </ul>
        <StepActions
          nextLabel={t(language, "welcome.start.begin")}
          nextType="button"
          onNext={() => router.push(path("name"))}
          skip={{
            label: t(language, "welcome.start.skip"),
            onClick: () => void finish("skip"),
            disabled: saving,
          }}
          saving={saving}
          savingLabel={t(language, "welcome.saving")}
        />
      </div>
    );
  } else if (step === "name") {
    content = (
      <div className="space-y-5">
        <Field
          label={t(language, "welcome.name.label")}
          optional
          maxLength={100}
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder={t(language, "welcome.name.placeholder")}
          autoComplete="name"
        />
        {actions({ full_name: fullName.trim() })}
      </div>
    );
  } else if (step === "birth") {
    content = (
      <div className="space-y-5">
        <Field
          label={t(language, "welcome.birth.label")}
          optional
          type="date"
          max={new Date().toISOString().split("T")[0]}
          value={dob}
          onChange={(event) => setDob(event.target.value)}
        />
        {actions({ date_of_birth: dob || null })}
      </div>
    );
  } else if (step === "gender") {
    content = (
      <div className="space-y-5">
        <Select
          label={t(language, "welcome.gender.label")}
          optional
          value={gender}
          onChange={(event) => setGender(event.target.value)}
        >
          {genders.map(([value, label]) => (
            <option key={value || "none"} value={value}>
              {label}
            </option>
          ))}
        </Select>
        {actions({ gender })}
      </div>
    );
  } else if (step === "blood-type") {
    content = (
      <div className="space-y-5">
        <Select
          label={t(language, "welcome.bloodType.label")}
          optional
          value={bloodType}
          onChange={(event) => setBloodType(event.target.value)}
        >
          {BLOOD_TYPES.map((value) => (
            <option key={value || "none"} value={value}>
              {value || t(language, "welcome.bloodType.unknown")}
            </option>
          ))}
        </Select>
        {actions({ blood_type: bloodType })}
      </div>
    );
  } else if (step === "height") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={heightRef}
          id="welcome-height"
          label={t(language, "welcome.height.label")}
          optional
          hint="cm"
          inputMode="decimal"
          min={0}
          max={300}
          aria-invalid={
            validationErrors.some((error) => error.fieldId === "welcome-height") ||
            undefined
          }
          value={heightCm}
          onChange={(event) => setHeightCm(event.target.value)}
          placeholder="170"
        />
        <StepActions
          saving={saving}
          nextLabel={t(language, "welcome.continue")}
          savingLabel={t(language, "welcome.saving")}
          nextType="button"
          onNext={() =>
            navigateWithMeasurement({
              value: heightCm,
              maximum: 300,
              fieldId: "welcome-height",
              fieldLabel: t(language, "welcome.height.label"),
              ref: heightRef,
              patch: { height_cm: numeric(heightCm) },
              target: next,
            })
          }
          back={
            previous
              ? {
                  label: t(language, "welcome.back"),
                  onClick: () =>
                    navigateWithMeasurement({
                      value: heightCm,
                      maximum: 300,
                      fieldId: "welcome-height",
                      fieldLabel: t(language, "welcome.height.label"),
                      ref: heightRef,
                      patch: { height_cm: numeric(heightCm) },
                      target: previous,
                    }),
                }
              : undefined
          }
          skip={
            next ? { label: t(language, "welcome.skip"), href: path(next) } : undefined
          }
        />
      </div>
    );
  } else if (step === "weight") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={weightRef}
          id="welcome-weight"
          label={t(language, "welcome.weight.label")}
          optional
          hint="kg"
          inputMode="decimal"
          min={0}
          max={800}
          aria-invalid={
            validationErrors.some((error) => error.fieldId === "welcome-weight") ||
            undefined
          }
          value={weightKg}
          onChange={(event) => setWeightKg(event.target.value)}
          placeholder="62"
        />
        <StepActions
          saving={saving}
          nextLabel={t(language, "welcome.continue")}
          savingLabel={t(language, "welcome.saving")}
          nextType="button"
          onNext={() =>
            navigateWithMeasurement({
              value: weightKg,
              maximum: 800,
              fieldId: "welcome-weight",
              fieldLabel: t(language, "welcome.weight.label"),
              ref: weightRef,
              patch: { weight_kg: numeric(weightKg) },
              target: next,
            })
          }
          back={
            previous
              ? {
                  label: t(language, "welcome.back"),
                  onClick: () =>
                    navigateWithMeasurement({
                      value: weightKg,
                      maximum: 800,
                      fieldId: "welcome-weight",
                      fieldLabel: t(language, "welcome.weight.label"),
                      ref: weightRef,
                      patch: { weight_kg: numeric(weightKg) },
                      target: previous,
                    }),
                }
              : undefined
          }
          skip={
            next ? { label: t(language, "welcome.skip"), href: path(next) } : undefined
          }
        />
      </div>
    );
  } else if (step === "personalization") {
    content = (
      <div className="space-y-5">
        <Toggle
          checked={consent}
          onChange={setConsent}
          label={t(language, "welcome.personalization.label")}
          description={t(language, "welcome.personalization.description")}
        />
        <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "welcome.medicalDisclaimer")}
        </p>
        {actions({ personalization_consent: consent })}
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title={t(language, "welcome.review.title")}
          description={t(language, "welcome.review.description")}
          edit={{ href: path("name") }}
          items={[
            { label: t(language, "welcome.review.name"), value: onboarding?.record.full_name || t(language, "welcome.review.notProvided") },
            {
              label: t(language, "welcome.review.dateOfBirth"),
              value: onboarding?.record.date_of_birth || t(language, "welcome.review.notProvided"),
            },
            {
              label: t(language, "welcome.review.gender"),
              value:
                genders.find(([value]) => value === onboarding?.record.gender)?.[1] ||
                t(language, "welcome.review.notProvided"),
            },
            {
              label: t(language, "welcome.review.bloodType"),
              value: onboarding?.record.blood_type || t(language, "welcome.bloodType.unknown"),
            },
            {
              label: t(language, "welcome.review.height"),
              value:
                onboarding?.record.height_cm == null
                  ? t(language, "welcome.review.notProvided")
                  : `${onboarding.record.height_cm} cm`,
            },
            {
              label: t(language, "welcome.review.weight"),
              value:
                onboarding?.record.weight_kg == null
                  ? t(language, "welcome.review.notProvided")
                  : `${onboarding.record.weight_kg} kg`,
            },
            {
              label: t(language, "welcome.review.personalization"),
              value: onboarding?.personalization_consent
                ? t(language, "welcome.review.allowed")
                : t(language, "welcome.review.notAllowed"),
            },
          ]}
        />
        <p className="text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "welcome.review.editAfter")}
        </p>
        <label className="focus-within:shadow-[var(--shadow-focus)] flex min-h-[var(--touch-target-min)] cursor-pointer items-start gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <input
            type="checkbox"
            checked={selfDeclaredConfirmed}
            onChange={(event) => setSelfDeclaredConfirmed(event.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 rounded border-[color:var(--shell-border-strong)] accent-[var(--brand-600)]"
          />
          <span className="text-sm leading-6 text-[var(--text-primary)]">
            {t(language, "welcome.review.confirm")}
          </span>
        </label>
        <StepActions
          nextLabel={t(language, "welcome.review.complete")}
          savingLabel={t(language, "welcome.saving")}
          nextType="button"
          onNext={() => void finish("complete")}
          nextDisabled={!selfDeclaredConfirmed}
          saving={saving}
          back={{ label: t(language, "welcome.back"), href: path("personalization") }}
        />
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-1rem)] px-4 py-8 sm:py-12">
      <GuidedFlowShell
        eyebrow={t(language, "welcome.eyebrow")}
        title={flowSteps[stepIndex].label}
        description={
          step === "start"
            ? t(language, "welcome.description.start")
            : t(language, "welcome.description.step")
        }
        steps={flowSteps}
        currentStep={stepIndex}
        saveState={saveState}
        aside={
          <p className="text-center">
            {t(language, "welcome.privacy")}
          </p>
        }
      >
        {content}
      </GuidedFlowShell>
    </div>
  );
}
