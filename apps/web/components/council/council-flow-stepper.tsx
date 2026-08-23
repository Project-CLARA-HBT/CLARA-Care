"use client";

import Link from "next/link";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { Icon } from "@/components/ui/icon";

export type CouncilStepId = "case" | "question" | "context" | "review" | "run" | "result";

export type CouncilFlowStep = {
  id: CouncilStepId;
  labelKey: UITranslationKey;
  icon: string;
};

export const COUNCIL_FLOW_STEPS: CouncilFlowStep[] = [
  { id: "case", labelKey: "council.flow.step.case", icon: "clinical-notes" },
  { id: "question", labelKey: "council.flow.step.question", icon: "clinical-notes" },
  { id: "context", labelKey: "council.flow.step.context", icon: "medication" },
  { id: "review", labelKey: "council.flow.step.review", icon: "progress" },
  { id: "run", labelKey: "council.flow.step.run", icon: "progress" },
  { id: "result", labelKey: "council.flow.step.result", icon: "progress" },
];

function stepIndex(id: CouncilStepId): number {
  return COUNCIL_FLOW_STEPS.findIndex((item) => item.id === id);
}

function resolveStepHref(stepId: CouncilStepId, caseId?: number | null): string {
  if (!caseId) {
    if (stepId === "case") return "/council/new";
    if (stepId === "result") return "/council/result";
    return "/council/new";
  }
  switch (stepId) {
    case "case":
      return `/council/new?caseId=${caseId}`;
    case "question":
      return `/council/new/intake?caseId=${caseId}&section=question`;
    case "context":
      return `/council/new/specialists?caseId=${caseId}`;
    case "review":
      return `/council/new/review?caseId=${caseId}`;
    case "run":
      return `/council/new/review?caseId=${caseId}`;
    case "result":
      return `/council/result?caseId=${caseId}`;
  }
}

export default function CouncilFlowStepper({
  currentStep,
  caseId,
  className = "",
}: {
  currentStep: CouncilStepId;
  caseId?: number | null;
  className?: string;
}) {
  const language = useUILanguage();
  const currentIdx = stepIndex(currentStep);

  return (
    <nav
      aria-label="Council deliberation flow"
      className={`overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-3 ${className}`.trim()}
    >
      <div className="flex items-center justify-between px-1 pb-2">
        <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-[color:var(--text-muted)]">
          {language === "vi" ? "Quy trình hội chẩn đa chuyên khoa" : "Multi-specialty Council Flow"}
          {caseId ? ` · Ca #${caseId}` : ""}
        </p>
        <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]">
          {language === "vi" ? `Bước ${currentIdx + 1}/6` : `Step ${currentIdx + 1}/6`}
        </span>
      </div>

      <ol className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-6">
        {COUNCIL_FLOW_STEPS.map((step, idx) => {
          const isCurrent = step.id === currentStep;
          const isPassed = idx < currentIdx;
          const isUpcoming = idx > currentIdx;
          const href = resolveStepHref(step.id, caseId);

          const stepLabel = t(language, step.labelKey);

          return (
            <li key={step.id}>
              <Link
                href={href}
                aria-current={isCurrent ? "step" : undefined}
                className={`flex min-h-[44px] items-center gap-2 rounded-xl border px-3 py-2 text-xs font-bold transition-colors ${
                  isCurrent
                    ? "border-[color:var(--brand-600)] bg-[color:var(--surface-brand-soft)] text-[color:var(--text-brand)] shadow-sm"
                    : isPassed
                      ? "border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] text-[color:var(--text-primary)] hover:border-[color:var(--shell-border-strong)] hover:bg-[color:var(--surface-muted)]"
                      : "border-[color:var(--shell-border)] bg-[color:var(--surface-muted)]/50 text-[color:var(--text-muted)] hover:text-[color:var(--text-secondary)]"
                }`}
              >
                <span
                  className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-black ${
                    isCurrent
                      ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)]"
                      : isPassed
                        ? "bg-[var(--surface-muted)] text-[var(--text-brand)]"
                        : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
                  }`}
                >
                  {isPassed ? <Icon name="check" size={12} /> : idx + 1}
                </span>
                <span className="truncate">{stepLabel}</span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
