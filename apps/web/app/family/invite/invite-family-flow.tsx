"use client";

import { useEffect, useRef, useState } from "react";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Field, Select } from "@/components/ui/field";
import { t } from "@/lib/i18n/catalog";
import { createFamilyInvitation, getFamilyShareOptions } from "@/lib/visit-family";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "recipient" | "scope" | "purpose" | "review";
type ObjectType = "episode" | "visit";
type Purpose = "care_coordination" | "visit_support";

type ShareableItems = Record<ObjectType, Array<{ id: string; label: string }>>;

type InviteDraft = {
  email: string;
  objectType: ObjectType;
  objectId: string;
  purpose: Purpose;
};

const EMPTY_ITEMS: ShareableItems = { episode: [], visit: [] };
const EMPTY_DRAFT: InviteDraft = {
  email: "",
  objectType: "episode",
  objectId: "",
  purpose: "care_coordination",
};

function expiryIso(): string {
  return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

export default function InviteFamilyFlow() {
  const language = useUILanguage();
  const emailRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("recipient");
  const [draft, setDraft] = useState<InviteDraft>(EMPTY_DRAFT);
  const [items, setItems] = useState<ShareableItems>(EMPTY_ITEMS);
  const [loadingItems, setLoadingItems] = useState(true);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [createdToken, setCreatedToken] = useState("");

  const steps: Array<{ id: Step; label: string }> = [
    { id: "recipient", label: t(language, "familyInvite.step.recipient") },
    { id: "scope", label: t(language, "familyInvite.step.scope") },
    { id: "purpose", label: t(language, "familyInvite.step.purpose") },
    { id: "review", label: t(language, "familyInvite.step.review") },
  ];
  const titleByStep: Record<Step, string> = {
    recipient: t(language, "familyInvite.title.recipient"),
    scope: t(language, "familyInvite.title.scope"),
    purpose: t(language, "familyInvite.title.purpose"),
    review: t(language, "familyInvite.title.review"),
  };
  const descriptionByStep: Record<Step, string> = {
    recipient: t(language, "familyInvite.description.recipient"),
    scope: t(language, "familyInvite.description.scope"),
    purpose: t(language, "familyInvite.description.purpose"),
    review: t(language, "familyInvite.description.review"),
  };
  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id;
  const saving = saveState.kind === "saving";
  const selectedItem = items[draft.objectType].find((item) => item.id === draft.objectId);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoadingItems(true);
      try {
        const options = await getFamilyShareOptions();
        if (!active) return;
        setItems({ episode: options.episodes, visit: options.visits });
      } catch {
        if (active) {
          setSaveState({ kind: "error", message: t(language, "familyInvite.loadFailed") });
        }
      } finally {
        if (active) setLoadingItems(false);
      }
    };
    void load();
    return () => { active = false; };
  }, [language]);

  const setObjectType = (objectType: ObjectType) => {
    setDraft((current) => ({ ...current, objectType, objectId: "" }));
  };

  const advance = () => {
    if (step === "recipient" && !/^\S+@\S+\.\S+$/.test(draft.email.trim())) {
      setValidationErrors([{
        id: "family-invite-email",
        fieldId: "family-invite-email",
        fieldLabel: t(language, "familyInvite.field.email"),
        message: t(language, "familyInvite.validation.email"),
      }]);
      emailRef.current?.focus();
      return;
    }
    if (step === "scope" && (!draft.objectId || !selectedItem)) {
      setValidationErrors([{
        id: "family-invite-scope",
        fieldId: "family-invite-item",
        fieldLabel: t(language, "familyInvite.field.item"),
        message: t(language, "familyInvite.validation.scope"),
      }]);
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const next = steps[stepIndex + 1]?.id;
    if (next) setStep(next);
  };

  const save = async () => {
    if (!selectedItem) {
      setStep("scope");
      setValidationErrors([{
        id: "family-invite-scope",
        fieldId: "family-invite-item",
        fieldLabel: t(language, "familyInvite.field.item"),
        message: t(language, "familyInvite.validation.scope"),
      }]);
      return;
    }
    setSaveState({ kind: "saving", message: t(language, "familyInvite.saving") });
    try {
      const result = await createFamilyInvitation({
        recipient_email: draft.email.trim(),
        scope: {
          object_type: draft.objectType,
          object_id: selectedItem.id,
          allowed_actions: draft.objectType === "episode" ? ["view", "add_observation"] : ["view"],
        },
        purpose: draft.purpose,
        expires_at: expiryIso(),
      });
      setCreatedToken(result.token);
      setSaveState({ kind: "saved", message: t(language, "familyInvite.saved") });
    } catch {
      setSaveState({ kind: "error", message: t(language, "familyInvite.saveFailed") });
    }
  };

  if (createdToken) {
    return (
      <GuidedFlowShell
        eyebrow={t(language, "familyInvite.eyebrow")}
        title={t(language, "familyInvite.created.title")}
        description={t(language, "familyInvite.created.description")}
        steps={steps}
        currentStep={steps.length - 1}
        saveState={saveState}
      >
        <div className="space-y-5">
          <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4">
            <p className="text-sm font-semibold text-[var(--status-warn-text)]">
              {t(language, "familyInvite.created.notice")}
            </p>
            <code className="mt-3 block break-all rounded-[var(--radius-md)] bg-[var(--surface-panel)] p-3 text-sm text-[var(--status-warn-text)]">
              {createdToken}
            </code>
          </div>
          <StepActions
            nextLabel={t(language, "familyInvite.created.done")}
            nextType="button"
            onNext={() => { window.location.assign("/family"); }}
          />
        </div>
      </GuidedFlowShell>
    );
  }

  let content;
  if (step === "recipient") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={emailRef}
          id="family-invite-email"
          label={t(language, "familyInvite.field.email")}
          type="email"
          autoComplete="email"
          autoFocus
          value={draft.email}
          onChange={(event) => setDraft((current) => ({ ...current, email: event.target.value }))}
          aria-invalid={validationErrors.length > 0 || undefined}
          aria-describedby={validationErrors.length ? "family-invite-email-error" : undefined}
        />
        {validationErrors.length ? <p id="family-invite-email-error" className="text-sm text-[var(--status-danger-text)]">{validationErrors[0].message}</p> : null}
        <StepActions nextType="button" onNext={advance} back={{ label: t(language, "familyInvite.cancel"), href: "/family" }} />
      </div>
    );
  } else if (step === "scope") {
    const available = items[draft.objectType];
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Select label={t(language, "familyInvite.field.scope")} value={draft.objectType} onChange={(event) => setObjectType(event.target.value as ObjectType)}>
          <option value="episode">{t(language, "familyInvite.scope.episode")}</option>
          <option value="visit">{t(language, "familyInvite.scope.visit")}</option>
        </Select>
        <Select id="family-invite-item" label={t(language, "familyInvite.field.item")} value={draft.objectId} onChange={(event) => setDraft((current) => ({ ...current, objectId: event.target.value }))} disabled={loadingItems} aria-invalid={validationErrors.length > 0 || undefined}>
          <option value="">{loadingItems ? t(language, "familyInvite.loading") : t(language, "familyInvite.chooseItem")}</option>
          {available.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </Select>
        {!loadingItems && !available.length ? <p className="text-sm leading-6 text-[var(--text-secondary)]">{t(language, "familyInvite.noItems")}</p> : null}
        <StepActions nextType="button" onNext={advance} nextDisabled={loadingItems || !available.length} back={{ label: t(language, "familyInvite.back"), onClick: () => setStep(back ?? "recipient") }} />
      </div>
    );
  } else if (step === "purpose") {
    content = (
      <div className="space-y-5">
        <Select label={t(language, "familyInvite.field.purpose")} value={draft.purpose} onChange={(event) => setDraft((current) => ({ ...current, purpose: event.target.value as Purpose }))}>
          <option value="care_coordination">{t(language, "familyInvite.purpose.care")}</option>
          <option value="visit_support">{t(language, "familyInvite.purpose.visit")}</option>
        </Select>
        <StepActions nextType="button" onNext={advance} back={{ label: t(language, "familyInvite.back"), onClick: () => setStep(back ?? "scope") }} />
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title={t(language, "familyInvite.review.title")}
          description={t(language, "familyInvite.review.description")}
          edit={{ label: t(language, "familyInvite.review.edit"), onClick: () => setStep("recipient") }}
          items={[
            { label: t(language, "familyInvite.field.email"), value: draft.email.trim() },
            { label: t(language, "familyInvite.field.item"), value: selectedItem?.label ?? t(language, "familyInvite.review.empty") },
            { label: t(language, "familyInvite.field.purpose"), value: draft.purpose === "care_coordination" ? t(language, "familyInvite.purpose.care") : t(language, "familyInvite.purpose.visit") },
            { label: t(language, "familyInvite.review.expiry"), value: t(language, "familyInvite.review.sevenDays") },
          ]}
        />
        <StepActions nextLabel={t(language, "familyInvite.create")} nextType="button" onNext={() => void save()} saving={saving} savingLabel={t(language, "familyInvite.saving")} back={{ label: t(language, "familyInvite.back"), onClick: () => setStep("purpose") }} />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "familyInvite.eyebrow")}
      title={titleByStep[step]}
      description={descriptionByStep[step]}
      steps={steps}
      currentStep={stepIndex}
      saveState={saveState}
      aside={t(language, "familyInvite.safetyNote")}
    >
      {content}
    </GuidedFlowShell>
  );
}
