"use client";

import { useId } from "react";

import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type GuidedFlowStep = {
  id: string;
  label: string;
};

export function StepProgress({
  steps,
  currentStep,
  label,
}: {
  steps: GuidedFlowStep[];
  currentStep: number;
  label?: string;
}) {
  const language = useUILanguage();
  const descriptionId = useId();
  const safeStep = Math.min(
    Math.max(currentStep, 0),
    Math.max(steps.length - 1, 0),
  );
  const active = steps[safeStep];

  if (steps.length === 0) return null;

  return (
    <nav
      aria-label={label ?? t(language, "flow.progress")}
      aria-describedby={descriptionId}
    >
      <p
        id={descriptionId}
        className="text-xs font-medium text-[var(--text-secondary)]"
      >
        {t(language, "flow.stepOf", {
          current: safeStep + 1,
          total: steps.length,
        })}
        <span aria-hidden="true"> · {active.label}</span>
        <span className="sr-only">: {active.label}</span>
      </p>
      <ol className="mt-2 flex gap-2" aria-label={active.label}>
        {steps.map((step, index) => {
          const complete = index < safeStep;
          const current = index === safeStep;
          return (
            <li
              key={step.id}
              className="min-w-0 flex-1"
              aria-current={current ? "step" : undefined}
            >
              <span
                className={`block h-1.5 rounded-[var(--radius-pill)] ${
                  complete || current
                    ? "bg-[var(--brand-600)]"
                    : "bg-[var(--surface-muted)]"
                }`}
                aria-hidden="true"
              />
              <span
                aria-hidden="true"
                className={`mt-1.5 hidden truncate text-[0.6875rem] sm:block ${
                  current
                    ? "font-semibold text-[var(--text-primary)]"
                    : "text-[var(--text-muted)]"
                }`}
              >
                {step.label}
              </span>
              <span className="sr-only">
                {step.label}:{" "}
                {t(
                  language,
                  complete
                    ? "flow.complete"
                    : current
                      ? "flow.current"
                      : "flow.notStarted",
                )}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default StepProgress;
