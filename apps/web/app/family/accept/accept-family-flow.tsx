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
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import {
  acceptFamilyInvitation,
  previewFamilyInvitation,
  type FamilyInvitationPreview,
} from "@/lib/visit-family";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "code" | "review";

function scopeLabel(
  preview: FamilyInvitationPreview,
  language: "vi" | "en",
): string {
  if (preview.object_type === "episode") return t(language, "familyAccept.scope.episode");
  if (preview.object_type === "visit") return t(language, "familyAccept.scope.visit");
  if (preview.object_type === "care_task") return t(language, "familyAccept.scope.task");
  return t(language, "familyAccept.scope.other");
}

function actionsLabel(preview: FamilyInvitationPreview, language: "vi" | "en"): string {
  const labels = preview.allowed_actions.map((action) => {
    if (action === "view") return t(language, "familyAccept.action.view");
    if (action === "add_observation") return t(language, "familyAccept.action.observe");
    if (action === "complete_task") return t(language, "familyAccept.action.complete");
    return t(language, "familyAccept.action.other");
  });
  return labels.length ? labels.join(", ") : t(language, "familyAccept.action.other");
}

export default function AcceptFamilyFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const tokenRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("code");
  const [token, setToken] = useState("");
  const [preview, setPreview] = useState<FamilyInvitationPreview | null>(null);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const saving = saveState.kind === "saving";
  const steps: Array<{ id: Step; label: string }> = [
    { id: "code", label: t(language, "familyAccept.step.code") },
    { id: "review", label: t(language, "familyAccept.step.review") },
  ];

  const previewInvitation = async () => {
    const candidate = token.trim();
    if (candidate.length < 32) {
      setValidationErrors([{
        id: "family-accept-token",
        fieldId: "family-accept-token",
        fieldLabel: t(language, "familyAccept.field.code"),
        message: t(language, "familyAccept.validation.code"),
      }]);
      tokenRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "saving", message: t(language, "familyAccept.previewing") });
    try {
      const next = await previewFamilyInvitation(candidate);
      setPreview(next);
      setStep("review");
      setSaveState({ kind: "idle" });
    } catch {
      setPreview(null);
      setSaveState({ kind: "error", message: t(language, "familyAccept.previewFailed") });
    }
  };

  const accept = async () => {
    if (!preview) {
      setStep("code");
      return;
    }
    setSaveState({ kind: "saving", message: t(language, "familyAccept.accepting") });
    try {
      await acceptFamilyInvitation(token.trim());
      setSaveState({ kind: "saved", message: t(language, "familyAccept.accepted") });
      router.replace("/family");
      router.refresh();
    } catch {
      setSaveState({ kind: "error", message: t(language, "familyAccept.acceptFailed") });
    }
  };

  if (step === "code") {
    return (
      <GuidedFlowShell
        eyebrow={t(language, "familyAccept.eyebrow")}
        title={t(language, "familyAccept.title.code")}
        description={t(language, "familyAccept.description.code")}
        steps={steps}
        currentStep={0}
        saveState={saveState}
        aside={t(language, "familyAccept.safetyNote")}
      >
        <div className="space-y-5">
          <ErrorSummary errors={validationErrors} />
          <Field
            ref={tokenRef}
            id="family-accept-token"
            label={t(language, "familyAccept.field.code")}
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            aria-invalid={validationErrors.length > 0 || undefined}
            aria-describedby={validationErrors.length ? "family-accept-token-error" : undefined}
          />
          {validationErrors.length ? <p id="family-accept-token-error" className="text-sm text-[var(--status-danger-text)]">{validationErrors[0].message}</p> : null}
          <StepActions
            nextLabel={t(language, "familyAccept.preview")}
            nextType="button"
            onNext={() => void previewInvitation()}
            saving={saving}
            savingLabel={t(language, "familyAccept.previewing")}
            back={{ label: t(language, "familyAccept.cancel"), href: "/family" }}
          />
        </div>
      </GuidedFlowShell>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "familyAccept.eyebrow")}
      title={t(language, "familyAccept.title.review")}
      description={t(language, "familyAccept.description.review")}
      steps={steps}
      currentStep={1}
      saveState={saveState}
      aside={t(language, "familyAccept.safetyNote")}
    >
      <div className="space-y-5">
        {preview ? (
          <ReviewSection
            title={t(language, "familyAccept.review.title")}
            description={t(language, "familyAccept.review.description")}
            edit={{ label: t(language, "familyAccept.review.edit"), onClick: () => setStep("code") }}
            items={[
              { label: t(language, "familyAccept.field.scope"), value: scopeLabel(preview, language) },
              { label: t(language, "familyAccept.field.actions"), value: actionsLabel(preview, language) },
              {
                label: t(language, "familyAccept.field.purpose"),
                value: preview.purpose === "visit_support"
                  ? t(language, "familyAccept.purpose.visit")
                  : t(language, "familyAccept.purpose.care"),
              },
              {
                label: t(language, "familyAccept.field.expiry"),
                value: formatLocaleDate(language, preview.expires_at, { dateStyle: "medium", timeStyle: "short" }),
              },
            ]}
          />
        ) : null}
        <StepActions
          nextLabel={t(language, "familyAccept.accept")}
          nextType="button"
          onNext={() => void accept()}
          saving={saving}
          savingLabel={t(language, "familyAccept.accepting")}
          back={{ label: t(language, "familyAccept.back"), onClick: () => setStep("code") }}
        />
      </div>
    </GuidedFlowShell>
  );
}
