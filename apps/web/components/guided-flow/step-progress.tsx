"use client";

import { useId } from "react";

export type GuidedFlowStep = {
  id: string;
  label: string;
};

export function StepProgress({
  steps,
  currentStep,
  label = "Tiến trình",
}: {
  steps: GuidedFlowStep[];
  currentStep: number;
  label?: string;
}) {
  const descriptionId = useId();
  const safeStep = Math.min(Math.max(currentStep, 0), Math.max(steps.length - 1, 0));
  const active = steps[safeStep];

  if (steps.length === 0) return null;

  return (
    <nav aria-label={label} aria-describedby={descriptionId}>
      <p id={descriptionId} className="text-xs font-medium text-[var(--text-secondary)]">
        Bước {safeStep + 1} / {steps.length}
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
                {step.label}: {complete ? "đã hoàn tất" : current ? "hiện tại" : "chưa bắt đầu"}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default StepProgress;
