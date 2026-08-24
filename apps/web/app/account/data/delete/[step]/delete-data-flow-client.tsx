"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import {
  isDsarEnabled,
  listDsarRequests,
  requestDsarDelete,
  type DsarRequestRecord,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";

import type { DeleteFlowStep } from "./page";

const STEPS: ReadonlyArray<{ id: DeleteFlowStep; label: UITranslationKey }> = [
  { id: "review", label: "account.dataDelete.step.review" },
  { id: "confirm", label: "account.dataDelete.step.confirm" },
  { id: "status", label: "account.dataDelete.step.status" },
];

const STATUS_LABEL_KEYS: Record<DsarRequestRecord["status"], UITranslationKey> = {
  received: "account.dataDelete.status.received",
  in_progress: "account.dataDelete.status.inProgress",
  fulfilled: "account.dataDelete.status.fulfilled",
  rejected: "account.dataDelete.status.rejected",
};

function flowPath(step: DeleteFlowStep, requestId?: string | number) {
  const base = `/account/data/delete/${step}`;
  return requestId === undefined ? base : `${base}?request=${encodeURIComponent(String(requestId))}`;
}

export default function DeleteDataFlowClient({ step }: { step: DeleteFlowStep }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [acknowledged, setAcknowledged] = useState(false);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [receipt, setReceipt] = useState<DsarRequestRecord | null>(null);
  const [loadingReceipt, setLoadingReceipt] = useState(step === "status");

  const copy = (key: UITranslationKey) => t(uiLanguage, key);
  const flowSteps = STEPS.map((item) => ({ ...item, label: copy(item.label) }));
  const unknownReceiptText = copy("account.dataDelete.unknownReceipt");
  const loadErrorText = copy("account.dataDelete.loadError");
  const submitErrorText = copy("account.dataDelete.submitError");
  const isReviewOrWarning = step === "review" || step === "warning";
  const currentStep = isReviewOrWarning ? 0 : STEPS.findIndex((candidate) => candidate.id === step);
  const requestId = searchParams.get("request");
  const available = isDsarEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    if (step !== "status" || !available) {
      setLoadingReceipt(false);
      return;
    }
    let active = true;
    setLoadingReceipt(true);
    void listDsarRequests()
      .then((response) => {
        if (!active) return;
        const match = response.requests.find(
          (request) => String(request.id) === requestId && request.kind === "delete",
        );
        setReceipt(match ?? null);
        if (!match) {
          setSaveState({ kind: "error", message: unknownReceiptText });
        }
      })
      .catch(() => {
        if (active) setSaveState({ kind: "error", message: loadErrorText });
      })
      .finally(() => {
        if (active) setLoadingReceipt(false);
      });
    return () => {
      active = false;
    };
  }, [available, loadErrorText, requestId, step, unknownReceiptText]);

  const submit = useCallback(async () => {
    if (!acknowledged) return;
    setSaveState({ kind: "saving" });
    try {
      const record = await requestDsarDelete();
      router.replace(flowPath("status", record.id));
    } catch {
      // Never surface raw infrastructure details on a data-rights screen.
      setSaveState({ kind: "error", message: submitErrorText });
    }
  }, [acknowledged, router, submitErrorText]);

  const title =
    isReviewOrWarning
      ? copy("account.dataDelete.reviewTitle")
      : step === "confirm"
        ? copy("account.dataDelete.confirmTitle")
        : copy("account.dataDelete.statusTitle");
  const description =
    isReviewOrWarning
      ? copy("account.dataDelete.reviewDescription")
      : step === "confirm"
        ? copy("account.dataDelete.confirmDescription")
        : copy("account.dataDelete.statusDescription");

  if (!available) {
    return (
      <GuidedFlowShell
        title={copy("account.dataDelete.title")}
        description={copy("account.dataDelete.unavailable")}
        steps={flowSteps}
        currentStep={0}
      >
        <StepActions
          nextLabel={copy("account.dataDelete.cancel")}
          nextType="button"
          onNext={() => router.push("/account/data")}
        />
      </GuidedFlowShell>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={copy("account.dataDelete.title")}
      title={title}
      description={description}
      steps={flowSteps}
      currentStep={currentStep}
      saveState={saveState}
    >
      {isReviewOrWarning ? (
        <div className="space-y-6">
          <ReviewSection
            title={copy("account.dataDelete.consequenceTitle")}
            items={[
              {
                label: copy("account.dataDelete.consequenceTitle"),
                value: copy("account.dataDelete.consequence"),
              },
            ]}
          />
          <ReviewSection
            title={copy("account.dataDelete.retentionTitle")}
            items={[
              {
                label: copy("account.dataDelete.retentionTitle"),
                value: copy("account.dataDelete.retention"),
              },
            ]}
          />
          <StepActions
            nextLabel={copy("account.dataDelete.continue")}
            nextType="button"
            onNext={() => router.push(flowPath("confirm"))}
            back={{ label: copy("account.dataDelete.cancel"), href: "/account/data" }}
          />
        </div>
      ) : step === "confirm" ? (
        <div className="space-y-6">
          <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]">
            {copy("account.dataDelete.consequence")}
          </p>
          <Toggle
            checked={acknowledged}
            onChange={setAcknowledged}
            label={copy("account.dataDelete.confirmation")}
          />
          <StepActions
            nextLabel={copy("account.dataDelete.confirm")}
            nextType="button"
            onNext={() => void submit()}
            nextDisabled={!acknowledged}
            saving={saveState.kind === "saving"}
            savingLabel={copy("account.dataDelete.sending")}
            back={{ label: copy("account.dataDelete.back"), href: flowPath("review") }}
          />
        </div>
      ) : loadingReceipt ? (
        <p role="status" className="text-sm text-[var(--text-secondary)]">
          {copy("account.dataDelete.loading")}
        </p>
      ) : receipt ? (
        <div className="space-y-6">
          <p role="status" className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm font-medium text-[var(--status-ok-text)]">
            {copy("account.dataDelete.receipt")}
          </p>
          <ReviewSection
            title={copy("account.dataDelete.statusTitle")}
            items={[
              { label: copy("account.dataDelete.requestId"), value: String(receipt.id) },
              {
                label: copy("account.dataDelete.submittedAt"),
                value: receipt.created_at
                  ? formatLocaleDate(uiLanguage, receipt.created_at, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })
                  : "–",
              },
              {
                label: copy("account.dataDelete.dueAt"),
                value: receipt.due_at
                  ? formatLocaleDate(uiLanguage, receipt.due_at)
                  : "–",
              },
            ]}
          />
          <Badge tone="neutral">
            {copy("account.dataDelete.status")}: {copy(STATUS_LABEL_KEYS[receipt.status])}
          </Badge>
          <StepActions
            nextLabel={copy("account.dataDelete.cancel")}
            nextType="button"
            onNext={() => router.push("/account/data")}
          />
        </div>
      ) : (
        <StepActions
          nextLabel={copy("account.dataDelete.cancel")}
          nextType="button"
          onNext={() => router.push("/account/data")}
        />
      )}
    </GuidedFlowShell>
  );
}
