"use client";

import React, {
  forwardRef,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Stepper, type StepItem } from "@/components/ui/stepper";
import { SurfaceCard } from "@/components/ui/surface";
import { StepProgress, type GuidedFlowStep } from "@/components/guided-flow/step-progress";
import { PageFrame, type PageCanvasBg, type PageGutter, type PageMaxWidth } from "./page-frame";
import { PageHeader, type BreadcrumbItem, type PageHeaderBackAction } from "./page-header";

export interface WorkflowStep extends StepItem {
  id: string;
  label: string;
  description?: string;
  optional?: boolean;
  completed?: boolean;
}

export type WorkflowSaveState =
  | { kind: "idle" }
  | { kind: "saving"; message?: string }
  | { kind: "saved"; message?: string }
  | { kind: "error"; message: string };

export interface WorkflowLayoutProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  /** Page header node or uses PageHeader props */
  header?: ReactNode;
  eyebrow?: ReactNode;
  title?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  badges?: ReactNode;
  breadcrumbs?: BreadcrumbItem[] | ReactNode;
  headerActions?: ReactNode;
  backAction?: PageHeaderBackAction;
  /** Wizard step definitions */
  steps: WorkflowStep[];
  /** Zero-indexed active step */
  currentStep: number;
  /** Step navigation callback */
  onStepClick?: (stepIndex: number) => void;
  /** Background draft saving status */
  saveState?: WorkflowSaveState;
  /** Custom action bar node at the bottom of the card */
  actions?: ReactNode;
  /** Previous step action callback */
  onBack?: () => void;
  /** Next step action callback */
  onNext?: () => void;
  /** Previous step button label */
  backLabel?: string;
  /** Next step button label */
  nextLabel?: string;
  /** Disables the next action button */
  isNextDisabled?: boolean;
  /** Shows loading spinner on next button */
  isSubmitting?: boolean;
  /** Optional summary rail / preflight status on the side */
  summaryRail?: ReactNode;
  /** Alias for summaryRail */
  aside?: ReactNode;
  /** Orientation for step navigation */
  orientation?: "horizontal" | "vertical";
  /** Card container styling */
  cardClassName?: string;
  /** Max width */
  maxWidth?: PageMaxWidth;
  /** Gutter padding */
  gutter?: PageGutter;
  /** Canvas background */
  canvasBg?: PageCanvasBg;
  /** Step body content */
  children?: ReactNode;
}

function SaveStateBanner({ saveState }: { saveState: WorkflowSaveState }) {
  if (saveState.kind === "idle") return null;

  if (saveState.kind === "error") {
    return (
      <div
        role="alert"
        className="mb-4 rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]"
      >
        <p className="font-semibold">Lưu bản nháp không thành công</p>
        <p className="mt-1 leading-5">{saveState.message}</p>
      </div>
    );
  }

  return (
    <p
      role="status"
      aria-live="polite"
      className="mb-4 flex min-h-6 items-center gap-2 text-xs text-[var(--text-secondary)]"
    >
      <Icon
        name={saveState.kind === "saving" ? "progress" : "check"}
        size="0.875rem"
        className={saveState.kind === "saving" ? "animate-spin" : "text-[var(--status-ok-text)]"}
      />
      {saveState.message ??
        (saveState.kind === "saving"
          ? "Đang lưu bản nháp..."
          : "Đã lưu bản nháp an toàn")}
    </p>
  );
}

/**
 * Workflow archetype layout primitive (multi-step wizard).
 * Integrates step progress, draft persistence status, and review summary rail.
 */
export const WorkflowLayout = forwardRef<HTMLElement, WorkflowLayoutProps>(
  (
    {
      header,
      eyebrow,
      title,
      subtitle,
      description,
      badges,
      breadcrumbs,
      headerActions,
      backAction,
      steps,
      currentStep,
      onStepClick,
      saveState = { kind: "idle" },
      actions,
      onBack,
      onNext,
      backLabel = "Quay lại",
      nextLabel,
      isNextDisabled = false,
      isSubmitting = false,
      summaryRail,
      aside,
      orientation = "horizontal",
      cardClassName = "",
      maxWidth = "narrow",
      gutter = "default",
      canvasBg = "canvas",
      className = "",
      children,
      ...rest
    },
    ref
  ) => {
    const desc = subtitle ?? description;
    const resolvedAside = summaryRail ?? aside;
    const isLastStep = currentStep === steps.length - 1;
    const resolvedNextLabel = nextLabel ?? (isLastStep ? "Hoàn thành" : "Tiếp tục");

    const renderedHeader =
      header ??
      (title ? (
        <PageHeader
          eyebrow={eyebrow}
          title={title}
          subtitle={desc}
          badges={badges}
          breadcrumbs={breadcrumbs}
          actions={headerActions}
          backAction={backAction}
        />
      ) : null);

    const renderDefaultActions = () => {
      if (actions) return actions;
      if (!onBack && !onNext) return null;

      return (
        <div className="mt-8 flex items-center justify-between border-t border-[color:var(--shell-border)]/60 pt-5">
          {onBack ? (
            <Button
              type="button"
              variant="secondary"
              onClick={onBack}
              disabled={isSubmitting || currentStep === 0}
              icon="arrow-left"
            >
              {backLabel}
            </Button>
          ) : (
            <div />
          )}

          {onNext ? (
            <Button
              type="button"
              variant="primary"
              onClick={onNext}
              disabled={isNextDisabled || isSubmitting}
            >
              {isSubmitting ? (
                <span className="flex items-center gap-2">
                  <Icon name="progress" size="1rem" className="animate-spin" />
                  <span>Đang xử lý...</span>
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <span>{resolvedNextLabel}</span>
                  {!isLastStep && <Icon name="arrow-right" size="1rem" />}
                </span>
              )}
            </Button>
          ) : null}
        </div>
      );
    };

    const guidedFlowSteps: GuidedFlowStep[] = steps.map((s) => ({
      id: s.id,
      label: s.label,
    }));

    return (
      <PageFrame
        ref={ref}
        archetype="workflow"
        header={renderedHeader}
        aside={resolvedAside}
        maxWidth={maxWidth}
        gutter={gutter}
        bg={canvasBg}
        className={className}
        {...rest}
      >
        <div className="space-y-6">
          {orientation === "vertical" ? (
            <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
              <Stepper
                steps={steps}
                currentStepIndex={currentStep}
                onStepClick={onStepClick}
                orientation="vertical"
              />
            </div>
          ) : (
            <div className="mb-6">
              <StepProgress steps={guidedFlowSteps} currentStep={currentStep} />
            </div>
          )}

          <SurfaceCard className={`p-5 sm:p-7 ${cardClassName}`}>
            <SaveStateBanner saveState={saveState} />
            <div className="min-w-0">{children}</div>
            {renderDefaultActions()}
          </SurfaceCard>
        </div>
      </PageFrame>
    );
  }
);

WorkflowLayout.displayName = "WorkflowLayout";

export default WorkflowLayout;
