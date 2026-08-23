"use client";

import React from "react";

export interface StepItem {
  id: string;
  label: string;
  description?: string;
  optional?: boolean;
}

interface StepperProps {
  steps: StepItem[];
  currentStepIndex: number;
  onStepClick?: (index: number) => void;
  orientation?: "horizontal" | "vertical";
  className?: string;
}

export function Stepper({
  steps,
  currentStepIndex,
  onStepClick,
  orientation = "horizontal",
  className = "",
}: StepperProps) {
  if (orientation === "vertical") {
    return (
      <div className={`space-y-4 ${className}`}>
        {steps.map((step, index) => {
          const isCompleted = index < currentStepIndex;
          const isCurrent = index === currentStepIndex;
          const isClickable = onStepClick && index <= currentStepIndex;

          return (
            <div
              key={step.id}
              onClick={() => isClickable && onStepClick(index)}
              className={`flex items-start gap-3.5 ${
                isClickable ? "cursor-pointer" : ""
              }`}
            >
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-150 ${
                    isCompleted
                      ? "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border border-[var(--status-success-border)]"
                      : isCurrent
                      ? "bg-[var(--action-primary)] text-white shadow-sm"
                      : "bg-[var(--surface-2)] text-[var(--text-tertiary)] border border-[var(--border-subtle)]"
                  }`}
                >
                  {isCompleted ? "✓" : index + 1}
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={`h-8 w-0.5 mt-1 transition-colors duration-150 ${
                      isCompleted
                        ? "bg-[var(--status-success-border)]"
                        : "bg-[var(--border-subtle)]"
                    }`}
                  />
                )}
              </div>
              <div className="pt-0.5">
                <div
                  className={`text-sm font-medium ${
                    isCurrent
                      ? "text-[var(--text-primary)] font-semibold"
                      : isCompleted
                      ? "text-[var(--text-primary)]"
                      : "text-[var(--text-secondary)]"
                  }`}
                >
                  {step.label}
                  {step.optional && (
                    <span className="ml-1.5 text-xs text-[var(--text-tertiary)] font-normal">
                      (Không bắt buộc)
                    </span>
                  )}
                </div>
                {step.description && (
                  <div className="text-xs text-[var(--text-tertiary)] mt-0.5">
                    {step.description}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <nav aria-label="Progress" className={`w-full ${className}`}>
      <ol className="flex items-center justify-between w-full">
        {steps.map((step, index) => {
          const isCompleted = index < currentStepIndex;
          const isCurrent = index === currentStepIndex;
          const isClickable = onStepClick && index <= currentStepIndex;

          return (
            <li
              key={step.id}
              className="relative flex-1 flex flex-col items-center group"
            >
              {index > 0 && (
                <div
                  className={`absolute top-4 -left-1/2 w-full h-0.5 -translate-y-1/2 transition-colors duration-150 ${
                    isCompleted
                      ? "bg-[var(--status-success-border)]"
                      : "bg-[var(--border-subtle)]"
                  }`}
                  aria-hidden="true"
                />
              )}
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onStepClick(index)}
                className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full text-xs font-semibold transition-colors duration-150 ${
                  isCompleted
                    ? "bg-[var(--status-success-bg)] text-[var(--status-success-text)] border border-[var(--status-success-border)]"
                    : isCurrent
                    ? "bg-[var(--action-primary)] text-white shadow-sm ring-4 ring-[var(--clara-brand-100)] dark:ring-[var(--clara-brand-900)]/40"
                    : "bg-[var(--surface-2)] text-[var(--text-tertiary)] border border-[var(--border-subtle)]"
                } ${isClickable ? "cursor-pointer" : "cursor-default"}`}
              >
                {isCompleted ? "✓" : index + 1}
              </button>
              <span
                className={`mt-2 text-xs text-center max-w-[100px] truncate ${
                  isCurrent
                    ? "font-semibold text-[var(--text-primary)]"
                    : "text-[var(--text-secondary)]"
                }`}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Stepper;
