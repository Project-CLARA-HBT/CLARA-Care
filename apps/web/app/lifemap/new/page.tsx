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
  type GuidedFlowStep,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import {
  createLifeMapEpisode,
  createLifeMapTask,
} from "@/lib/lifemap";
import { type LifeMapPriority } from "@/lib/guided-flows";
import { useUILanguage } from "@/lib/use-ui-language";

export type WizardStep = "goal" | "condition" | "milestones" | "commitment";

export interface GoalTemplate {
  id: string;
  titleKey: "lifemap.wizard.goal.template1" | "lifemap.wizard.goal.template2" | "lifemap.wizard.goal.template3" | "lifemap.wizard.goal.template4";
  descKey: "lifemap.wizard.goal.template1Desc" | "lifemap.wizard.goal.template2Desc" | "lifemap.wizard.goal.template3Desc" | "lifemap.wizard.goal.template4Desc";
  condition: string;
  priority: LifeMapPriority;
  milestone: string;
  cadence: string;
}

const GOAL_TEMPLATES: GoalTemplate[] = [
  {
    id: "bp-cardio",
    titleKey: "lifemap.wizard.goal.template1",
    descKey: "lifemap.wizard.goal.template1Desc",
    condition: "hypertension",
    priority: "soon",
    milestone: "Đo và ghi nhận huyết áp 7 ngày liên tục (sáng & tối)",
    cadence: "daily",
  },
  {
    id: "diabetes-diet",
    titleKey: "lifemap.wizard.goal.template2",
    descKey: "lifemap.wizard.goal.template2Desc",
    condition: "diabetes",
    priority: "soon",
    milestone: "Kiểm tra đường huyết lúc đói & ghi nhật ký bữa ăn 5 ngày/tuần",
    cadence: "daily",
  },
  {
    id: "sleep-stress",
    titleKey: "lifemap.wizard.goal.template3",
    descKey: "lifemap.wizard.goal.template3Desc",
    condition: "sleep",
    priority: "routine",
    milestone: "Theo dõi giờ ngủ và thức dậy đều đặn trong 2 tuần",
    cadence: "daily",
  },
  {
    id: "knee-rehab",
    titleKey: "lifemap.wizard.goal.template4",
    descKey: "lifemap.wizard.goal.template4Desc",
    condition: "arthritis",
    priority: "routine",
    milestone: "Thực hiện bài tập vật lý trị liệu khớp gối 15 phút mỗi ngày",
    cadence: "daily",
  },
];

export default function JourneyCreationWizardPage() {
  const router = useRouter();
  const language = useUILanguage();
  const titleInputRef = useRef<HTMLInputElement>(null);
  const goalInputRef = useRef<HTMLTextAreaElement>(null);
  const milestoneInputRef = useRef<HTMLInputElement>(null);
  const commitmentCheckboxRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<WizardStep>("goal");
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [condition, setCondition] = useState("hypertension");
  const [symptoms, setSymptoms] = useState("");
  const [priority, setPriority] = useState<LifeMapPriority>("routine");
  const [milestone1, setMilestone1] = useState("");
  const [cadence, setCadence] = useState("daily");
  const [targetDate, setTargetDate] = useState("");
  const [milestone2, setMilestone2] = useState("");
  const [committed, setCommitted] = useState(false);

  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const steps: GuidedFlowStep[] = [
    { id: "goal", label: t(language, "lifemap.wizard.step.goal") },
    { id: "condition", label: t(language, "lifemap.wizard.step.condition") },
    { id: "milestones", label: t(language, "lifemap.wizard.step.milestones") },
    { id: "commitment", label: t(language, "lifemap.wizard.step.commitment") },
  ];

  const currentStepIndex = steps.findIndex((s) => s.id === step);
  const saving = saveState.kind === "saving";

  const conditionLabels: Record<string, string> = {
    hypertension: t(language, "lifemap.wizard.condition.optHypertension"),
    diabetes: t(language, "lifemap.wizard.condition.optDiabetes"),
    arthritis: t(language, "lifemap.wizard.condition.optArthritis"),
    sleep: t(language, "lifemap.wizard.condition.optSleep"),
    cardio: t(language, "lifemap.wizard.condition.optCardio"),
    general: t(language, "lifemap.wizard.condition.optGeneral"),
  };

  const priorityLabels: Record<LifeMapPriority, string> = {
    routine: t(language, "lifemap.wizard.condition.priorityRoutine"),
    soon: t(language, "lifemap.wizard.condition.prioritySoon"),
    urgent: t(language, "lifemap.wizard.condition.priorityUrgent"),
  };

  const cadenceLabels: Record<string, string> = {
    daily: t(language, "lifemap.wizard.milestones.cadenceDaily"),
    weekly: t(language, "lifemap.wizard.milestones.cadenceWeekly"),
    monthly: t(language, "lifemap.wizard.milestones.cadenceMonthly"),
    as_needed: t(language, "lifemap.wizard.milestones.cadenceAsNeeded"),
  };

  const handleSelectTemplate = (template: GoalTemplate) => {
    setTitle(t(language, template.titleKey));
    setGoal(t(language, template.descKey));
    setCondition(template.condition);
    setPriority(template.priority);
    setMilestone1(template.milestone);
    setCadence(template.cadence);
    setValidationErrors([]);
  };

  const validateAndAdvance = (targetStep: WizardStep) => {
    if (step === "goal") {
      if (title.trim().length < 2) {
        setValidationErrors([
          {
            id: "title-required",
            fieldId: "wizard-journey-title",
            fieldLabel: t(language, "lifemap.wizard.goal.customTitle"),
            message: t(language, "lifemap.wizard.error.titleRequired"),
          },
        ]);
        titleInputRef.current?.focus();
        return;
      }
      if (goal.trim().length < 2) {
        setValidationErrors([
          {
            id: "goal-required",
            fieldId: "wizard-journey-goal",
            fieldLabel: t(language, "lifemap.wizard.goal.customGoal"),
            message: t(language, "lifemap.wizard.error.goalRequired"),
          },
        ]);
        goalInputRef.current?.focus();
        return;
      }
    }

    if (step === "milestones") {
      if (milestone1.trim().length < 2) {
        setValidationErrors([
          {
            id: "milestone-required",
            fieldId: "wizard-milestone-1",
            fieldLabel: t(language, "lifemap.wizard.milestones.m1Label"),
            message: t(language, "lifemap.wizard.error.goalRequired"),
          },
        ]);
        milestoneInputRef.current?.focus();
        return;
      }
    }

    setValidationErrors([]);
    setStep(targetStep);
  };

  const handleCommitAndSubmit = async () => {
    if (!committed) {
      setValidationErrors([
        {
          id: "commitment-required",
          fieldId: "wizard-commitment-checkbox",
          fieldLabel: t(language, "lifemap.wizard.step.commitment"),
          message: t(language, "lifemap.wizard.error.commitmentRequired"),
        },
      ]);
      commitmentCheckboxRef.current?.focus();
      return;
    }

    setValidationErrors([]);
    setSaveState({ kind: "saving", message: t(language, "lifemap.wizard.commitment.submitting") });

    try {
      const episode = await createLifeMapEpisode({
        title: title.trim(),
        goal: goal.trim(),
        priority,
      });

      if (milestone1.trim()) {
        try {
          await createLifeMapTask(episode.id, {
            title: milestone1.trim(),
            due_at: targetDate || undefined,
          });
        } catch {
          // Task creation failure does not block episode creation success
        }
      }

      setSaveState({ kind: "saved", message: t(language, "lifemap.wizard.commitment.success") });
      router.push("/lifemap/timeline");
    } catch {
      setSaveState({
        kind: "error",
        message: t(language, "lifemap.wizard.error.saveFailed"),
      });
    }
  };

  let content;

  if (step === "goal") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        <div className="space-y-3">
          <label className="text-sm font-semibold text-[var(--text-primary)]">
            {t(language, "lifemap.wizard.goal.templateLabel")}
          </label>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {GOAL_TEMPLATES.map((tpl) => {
              const isSelected = title === t(language, tpl.titleKey);
              return (
                <button
                  key={tpl.id}
                  type="button"
                  onClick={() => handleSelectTemplate(tpl)}
                  className={`flex flex-col items-start p-4 rounded-xl border text-left transition-all ${
                    isSelected
                      ? "border-[var(--brand-500)] bg-[var(--surface-brand-soft,rgba(164,201,255,0.1))] shadow-sm"
                      : "border-[var(--shell-border)] bg-[var(--surface-panel)] hover:border-[var(--brand-300)]"
                  }`}
                >
                  <div className="flex items-center justify-between w-full mb-1">
                    <span className="font-semibold text-sm text-[var(--text-primary)]">
                      {t(language, tpl.titleKey)}
                    </span>
                    {isSelected && (
                      <span className="text-[var(--brand-500)]">
                        <Icon name="check" size="sm" />
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {t(language, tpl.descKey)}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-4 pt-2 border-t border-[var(--shell-border)]">
          <Field
            ref={titleInputRef}
            id="wizard-journey-title"
            label={t(language, "lifemap.wizard.goal.customTitle")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={255}
            autoFocus
            placeholder={t(language, "lifemap.wizard.goal.customTitlePlaceholder")}
          />

          <Textarea
            ref={goalInputRef}
            id="wizard-journey-goal"
            label={t(language, "lifemap.wizard.goal.customGoal")}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            maxLength={2000}
            rows={3}
            placeholder={t(language, "lifemap.wizard.goal.customGoalPlaceholder")}
          />
        </div>

        <StepActions
          saving={saving}
          nextLabel={t(language, "lifemap.guided.page.goal")}
          nextType="button"
          onNext={() => validateAndAdvance("condition")}
          back={{ label: t(language, "lifemap.guided.exit"), href: "/lifemap" }}
        />
      </div>
    );
  } else if (step === "condition") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        <Select
          id="wizard-condition-select"
          label={t(language, "lifemap.wizard.condition.selectLabel")}
          value={condition}
          onChange={(e) => setCondition(e.target.value)}
        >
          <option value="hypertension">{conditionLabels.hypertension}</option>
          <option value="diabetes">{conditionLabels.diabetes}</option>
          <option value="arthritis">{conditionLabels.arthritis}</option>
          <option value="sleep">{conditionLabels.sleep}</option>
          <option value="cardio">{conditionLabels.cardio}</option>
          <option value="general">{conditionLabels.general}</option>
        </Select>

        <Textarea
          id="wizard-symptoms-input"
          label={t(language, "lifemap.wizard.condition.symptomsLabel")}
          optional
          value={symptoms}
          onChange={(e) => setSymptoms(e.target.value)}
          maxLength={2000}
          rows={3}
          placeholder={t(language, "lifemap.wizard.condition.symptomsPlaceholder")}
        />

        <div className="space-y-2">
          <Select
            id="wizard-priority-select"
            label={t(language, "lifemap.wizard.condition.priorityLabel")}
            value={priority}
            onChange={(e) => setPriority(e.target.value as LifeMapPriority)}
          >
            <option value="routine">{priorityLabels.routine}</option>
            <option value="soon">{priorityLabels.soon}</option>
            <option value="urgent">{priorityLabels.urgent}</option>
          </Select>
          <p className="text-xs text-[var(--text-secondary)]">
            {t(language, "lifemap.wizard.condition.priorityHint")}
          </p>
        </div>

        <StepActions
          saving={saving}
          nextType="button"
          onNext={() => validateAndAdvance("milestones")}
          back={{
            label: t(language, "lifemap.guided.back"),
            onClick: () => setStep("goal"),
          }}
        />
      </div>
    );
  } else if (step === "milestones") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        <Field
          ref={milestoneInputRef}
          id="wizard-milestone-1"
          label={t(language, "lifemap.wizard.milestones.m1Label")}
          value={milestone1}
          onChange={(e) => setMilestone1(e.target.value)}
          maxLength={255}
          autoFocus
          placeholder={t(language, "lifemap.wizard.milestones.m1Placeholder")}
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select
            id="wizard-cadence-select"
            label={t(language, "lifemap.wizard.milestones.cadenceLabel")}
            value={cadence}
            onChange={(e) => setCadence(e.target.value)}
          >
            <option value="daily">{cadenceLabels.daily}</option>
            <option value="weekly">{cadenceLabels.weekly}</option>
            <option value="monthly">{cadenceLabels.monthly}</option>
            <option value="as_needed">{cadenceLabels.as_needed}</option>
          </Select>

          <Field
            id="wizard-target-date"
            type="date"
            label={t(language, "lifemap.wizard.milestones.targetDateLabel")}
            optional
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
          />
        </div>

        <Field
          id="wizard-milestone-2"
          label={t(language, "lifemap.wizard.milestones.m2Label")}
          optional
          value={milestone2}
          onChange={(e) => setMilestone2(e.target.value)}
          maxLength={255}
          placeholder={t(language, "lifemap.wizard.milestones.m2Placeholder")}
        />

        <StepActions
          saving={saving}
          nextType="button"
          onNext={() => validateAndAdvance("commitment")}
          back={{
            label: t(language, "lifemap.guided.back"),
            onClick: () => setStep("condition"),
          }}
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        <ReviewSection
          title={t(language, "lifemap.wizard.commitment.reviewTitle")}
          description={t(language, "lifemap.guided.review.description")}
          edit={{ onClick: () => setStep("goal") }}
          items={[
            {
              label: t(language, "lifemap.wizard.commitment.nameLabel"),
              value: title || t(language, "lifemap.guided.review.notEntered"),
            },
            {
              label: t(language, "lifemap.wizard.commitment.goalLabel"),
              value: goal || t(language, "lifemap.guided.review.notEntered"),
            },
            {
              label: t(language, "lifemap.wizard.commitment.conditionLabel"),
              value: conditionLabels[condition] ?? condition,
            },
            {
              label: t(language, "lifemap.wizard.commitment.priorityLabel"),
              value: priorityLabels[priority] ?? priority,
            },
            {
              label: t(language, "lifemap.wizard.commitment.milestoneLabel"),
              value: milestone1 || t(language, "lifemap.guided.review.notEntered"),
            },
            {
              label: t(language, "lifemap.wizard.commitment.cadenceLabel"),
              value: cadenceLabels[cadence] ?? cadence,
            },
            ...(targetDate
              ? [
                  {
                    label: t(language, "lifemap.wizard.commitment.targetDateLabel"),
                    value: targetDate,
                  },
                ]
              : []),
          ]}
        />

        <SurfaceCard className="p-4 bg-[var(--surface-muted)] border border-[var(--shell-border)] rounded-xl space-y-3">
          <label
            htmlFor="wizard-commitment-checkbox"
            className="flex items-start gap-3 cursor-pointer select-none"
          >
            <input
              ref={commitmentCheckboxRef}
              id="wizard-commitment-checkbox"
              type="checkbox"
              checked={committed}
              onChange={(e) => setCommitted(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-[var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-500)]"
            />
            <span className="text-sm font-medium leading-snug text-[var(--text-primary)]">
              {t(language, "lifemap.wizard.commitment.statement")}
            </span>
          </label>

          <p className="text-xs text-[var(--text-secondary)] pl-7">
            {t(language, "lifemap.wizard.commitment.disclaimer")}
          </p>
        </SurfaceCard>

        <StepActions
          saving={saving}
          nextLabel={t(language, "lifemap.wizard.commitment.submit")}
          nextType="button"
          onNext={() => void handleCommitAndSubmit()}
          savingLabel={t(language, "lifemap.wizard.commitment.submitting")}
          back={{
            label: t(language, "lifemap.guided.back"),
            onClick: () => setStep("milestones"),
          }}
        />
      </div>
    );
  }

  const titleByStep: Record<WizardStep, string> = {
    goal: t(language, "lifemap.wizard.goal.title"),
    condition: t(language, "lifemap.wizard.condition.title"),
    milestones: t(language, "lifemap.wizard.milestones.title"),
    commitment: t(language, "lifemap.wizard.commitment.title"),
  };

  const descByStep: Record<WizardStep, string> = {
    goal: t(language, "lifemap.wizard.goal.description"),
    condition: t(language, "lifemap.wizard.condition.description"),
    milestones: t(language, "lifemap.wizard.milestones.description"),
    commitment: t(language, "lifemap.wizard.commitment.description"),
  };

  return (
    <GuidedFlowShell
      eyebrow={t(language, "lifemap.wizard.eyebrow")}
      title={titleByStep[step]}
      description={descByStep[step]}
      steps={steps}
      currentStep={currentStepIndex}
      saveState={saveState}
      aside={t(language, "lifemap.guided.page.aside")}
    >
      {content}
    </GuidedFlowShell>
  );
}
