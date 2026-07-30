"use client";

import { useId, type ReactNode } from "react";

import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

import { StepProgress, type GuidedFlowStep } from "./step-progress";

export type GuidedFlowSaveState =
  | { kind: "idle" }
  | { kind: "saving"; message?: string }
  | { kind: "saved"; message?: string }
  | { kind: "error"; message: string };

function SaveState({ state }: { state: GuidedFlowSaveState }) {
  const language = useUILanguage();
  if (state.kind === "idle") return null;

  if (state.kind === "error") {
    return (
      <div
        role="alert"
        className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]"
      >
        <p className="font-semibold">{t(language, "flow.saveFailed")}</p>
        <p className="mt-1 leading-5">{state.message}</p>
      </div>
    );
  }

  return (
    <p
      role="status"
      aria-live="polite"
      className="flex min-h-6 items-center gap-2 text-sm text-[var(--text-secondary)]"
    >
      <span className="material-symbols-outlined text-base" aria-hidden="true">
        {state.kind === "saving" ? "progress_activity" : "check_circle"}
      </span>
      {state.message ??
        t(
          language,
          state.kind === "saving" ? "flow.savingDraft" : "flow.savedDraft",
        )}
    </p>
  );
}

export function GuidedFlowShell({
  eyebrow,
  title,
  description,
  steps,
  currentStep,
  saveState = { kind: "idle" },
  children,
  aside,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  steps: GuidedFlowStep[];
  currentStep: number;
  saveState?: GuidedFlowSaveState;
  children: ReactNode;
  aside?: ReactNode;
}) {
  const headingId = useId();

  return (
    <section
      aria-labelledby={headingId}
      className="mx-auto w-full max-w-3xl py-2 sm:py-4"
    >
      <header>
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-brand)]">
            {eyebrow}
          </p>
        ) : null}
        <h1
          id={headingId}
          className="mt-2 text-[var(--text-title)] font-semibold leading-tight tracking-[-0.025em] text-[var(--text-primary)]"
        >
          {title}
        </h1>
        {description ? (
          <p className="mt-2 max-w-[62ch] text-sm leading-6 text-[var(--text-secondary)]">
            {description}
          </p>
        ) : null}
        <div className="mt-5">
          <StepProgress steps={steps} currentStep={currentStep} />
        </div>
      </header>

      <div className="mt-6 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-[var(--shadow-soft)] sm:p-7">
        <SaveState state={saveState} />
        <div className={saveState.kind === "idle" ? "" : "mt-4"}>
          {children}
        </div>
      </div>

      {aside ? (
        <aside className="mt-5 text-sm leading-6 text-[var(--text-secondary)]">
          {aside}
        </aside>
      ) : null}
    </section>
  );
}

export default GuidedFlowShell;
