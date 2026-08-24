"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { WorkflowLayout } from "@/components/page/workflow-layout";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { addVisitConcern, createVisit, type Visit } from "@/lib/visit-family";

export type Step = "reason" | "symptoms" | "medications" | "summary";

export type MedicationItem = {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  adherence: string;
};

export type VisitDraft = {
  // Step 1: Reason for visit
  title: string;
  goal: string;
  doctorName: string;
  specialty: string;
  facilityName: string;
  scheduledAt: string;

  // Step 2: Symptoms & Timeline
  symptoms: string[];
  timeline: string;
  severity: "mild" | "moderate" | "severe" | "";
  triggers: string;

  // Step 3: Current Medications & Allergies
  medications: MedicationItem[];
  allergies: string[];
  medicationNotes: string;

  // Step 4: Generated Questions & Goals
  questions: string[];
  patientGoals: string[];
};

const COMMON_SYMPTOMS_VI = [
  "Đau tức ngực",
  "Khó thở khi gắng sức",
  "Chóng mặt / Choáng váng",
  "Mệt mỏi kéo dài",
  "Đau đầu âm ỉ",
  "Hồi hộp / Tim đập nhanh",
  "Đầy hơi / Khó tiêu",
  "Đau nhức khớp",
];

const COMMON_SYMPTOMS_EN = [
  "Chest tightness / pain",
  "Shortness of breath on exertion",
  "Dizziness / Lightheadedness",
  "Persistent fatigue",
  "Dull headache",
  "Palpitations",
  "Bloating / Indigestion",
  "Joint pain",
];

const COMMON_ALLERGIES_VI = [
  "Penicillin / Beta-lactam",
  "Aspirin / NSAIDs",
  "Kháng sinh Sulfa",
  "Hải sản",
  "Không ghi nhận dị ứng",
];

const COMMON_ALLERGIES_EN = [
  "Penicillin / Beta-lactams",
  "Aspirin / NSAIDs",
  "Sulfa antibiotics",
  "Seafood",
  "No known drug allergies",
];

const DEFAULT_QUESTIONS_VI = [
  "Thuốc hiện tại có cần tăng hoặc giảm liều lượng không?",
  "Triệu chứng gần đây có phải là tác dụng phụ của thuốc không?",
  "Tôi có cần thực hiện thêm xét nghiệm cận lâm sàng nào không?",
  "Những dấu hiệu cảnh báo nào tôi cần đến bệnh viện kiểm tra ngay?",
  "Khoảng bao lâu nữa tôi nên quay lại tái khám?",
];

const DEFAULT_QUESTIONS_EN = [
  "Should any of my current medications be adjusted or discontinued?",
  "Could my recent symptoms be medication side effects?",
  "Do I need any additional lab tests or diagnostic imaging?",
  "What red flag symptoms should prompt emergency care?",
  "When should my next follow-up appointment be scheduled?",
];

const INITIAL_DRAFT: VisitDraft = {
  title: "",
  goal: "",
  doctorName: "",
  specialty: "",
  facilityName: "",
  scheduledAt: "",
  symptoms: [],
  timeline: "",
  severity: "moderate",
  triggers: "",
  medications: [
    {
      id: "med-1",
      name: "Amlodipine 5mg",
      dosage: "1 viên/ngày",
      frequency: "Uống buổi sáng sau ăn",
      adherence: "Đều đặn",
    },
  ],
  allergies: [],
  medicationNotes: "",
  questions: [],
  patientGoals: [],
};

function displayScheduledAt(value: string, language: "vi" | "en"): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return formatLocaleDate(language, parsed, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function NewVisitFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const isEn = language === "en";

  const titleRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("reason");
  const [draft, setDraft] = useState<VisitDraft>(() => ({
    ...INITIAL_DRAFT,
    questions: isEn ? [...DEFAULT_QUESTIONS_EN.slice(0, 3)] : [...DEFAULT_QUESTIONS_VI.slice(0, 3)],
  }));

  const [customSymptomInput, setCustomSymptomInput] = useState("");
  const [customAllergyInput, setCustomAllergyInput] = useState("");
  const [customQuestionInput, setCustomQuestionInput] = useState("");
  const [newMedName, setNewMedName] = useState("");
  const [newMedDose, setNewMedDose] = useState("");

  const [copiedSummary, setCopiedSummary] = useState(false);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const steps: Array<{ id: Step; label: string }> = [
    { id: "reason", label: t(language, "visitWizard.step.reason") },
    { id: "symptoms", label: t(language, "visitWizard.step.symptoms") },
    { id: "medications", label: t(language, "visitWizard.step.medications") },
    { id: "summary", label: t(language, "visitWizard.step.summary") },
  ];

  const titleByStep: Record<Step, string> = {
    reason: t(language, "visitWizard.title.reason"),
    symptoms: t(language, "visitWizard.title.symptoms"),
    medications: t(language, "visitWizard.title.medications"),
    summary: t(language, "visitWizard.title.summary"),
  };

  const descriptionByStep: Record<Step, string> = {
    reason: t(language, "visitWizard.desc.reason"),
    symptoms: t(language, "visitWizard.desc.symptoms"),
    medications: t(language, "visitWizard.desc.medications"),
    summary: t(language, "visitWizard.desc.summary"),
  };

  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id;
  const saving = saveState.kind === "saving";

  const update = <K extends keyof VisitDraft>(key: K, value: VisitDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const toggleSymptom = (symptom: string) => {
    setDraft((prev) => {
      const exists = prev.symptoms.includes(symptom);
      return {
        ...prev,
        symptoms: exists
          ? prev.symptoms.filter((s) => s !== symptom)
          : [...prev.symptoms, symptom],
      };
    });
  };

  const addCustomSymptom = () => {
    const trimmed = customSymptomInput.trim();
    if (!trimmed) return;
    if (!draft.symptoms.includes(trimmed)) {
      setDraft((prev) => ({ ...prev, symptoms: [...prev.symptoms, trimmed] }));
    }
    setCustomSymptomInput("");
  };

  const toggleAllergy = (allergy: string) => {
    setDraft((prev) => {
      const exists = prev.allergies.includes(allergy);
      return {
        ...prev,
        allergies: exists
          ? prev.allergies.filter((a) => a !== allergy)
          : [...prev.allergies, allergy],
      };
    });
  };

  const addCustomAllergy = () => {
    const trimmed = customAllergyInput.trim();
    if (!trimmed) return;
    if (!draft.allergies.includes(trimmed)) {
      setDraft((prev) => ({ ...prev, allergies: [...prev.allergies, trimmed] }));
    }
    setCustomAllergyInput("");
  };

  const addMedication = () => {
    const name = newMedName.trim();
    if (!name) return;
    const item: MedicationItem = {
      id: `med-${Date.now()}`,
      name,
      dosage: newMedDose.trim() || "Theo đơn bác sĩ",
      frequency: "Hằng ngày",
      adherence: "Đang dùng",
    };
    setDraft((prev) => ({ ...prev, medications: [...prev.medications, item] }));
    setNewMedName("");
    setNewMedDose("");
  };

  const removeMedication = (id: string) => {
    setDraft((prev) => ({
      ...prev,
      medications: prev.medications.filter((m) => m.id !== id),
    }));
  };

  const toggleQuestion = (question: string) => {
    setDraft((prev) => {
      const exists = prev.questions.includes(question);
      return {
        ...prev,
        questions: exists
          ? prev.questions.filter((q) => q !== question)
          : [...prev.questions, question],
      };
    });
  };

  const addCustomQuestion = () => {
    const trimmed = customQuestionInput.trim();
    if (!trimmed) return;
    if (!draft.questions.includes(trimmed)) {
      setDraft((prev) => ({ ...prev, questions: [...prev.questions, trimmed] }));
    }
    setCustomQuestionInput("");
  };

  const advance = () => {
    if (step === "reason") {
      if (draft.title.trim().length < 2) {
        setValidationErrors([
          {
            id: "visit-title-required",
            fieldId: "visit-title",
            fieldLabel: t(language, "visitWizard.field.title"),
            message: isEn
              ? "Please enter at least 2 characters for the visit name."
              : "Vui lòng nhập ít nhất 2 ký tự cho tên buổi khám.",
          },
        ]);
        titleRef.current?.focus();
        return;
      }
    }

    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const next = steps[stepIndex + 1]?.id;
    if (next) setStep(next);
  };

  const generatedSummaryText = useMemo(() => {
    const lines = [
      `=== CLARA CLINICIAN HANDOFF PACK ===`,
      `Mục đích khám: ${draft.title || "Khám bệnh"}`,
      draft.goal ? `Mục tiêu: ${draft.goal}` : "",
      draft.specialty ? `Chuyên khoa: ${draft.specialty}` : "",
      draft.doctorName ? `Bác sĩ: ${draft.doctorName}` : "",
      draft.facilityName ? `Cơ sở y tế: ${draft.facilityName}` : "",
      draft.scheduledAt ? `Thời gian: ${draft.scheduledAt}` : "",
      "",
      `--- TRIỆU CHỨNG & DIỄN TIẾN ---`,
      draft.symptoms.length ? `Triệu chứng: ${draft.symptoms.join(", ")}` : "Không có triệu chứng cấp tính.",
      draft.timeline ? `Thời gian: ${draft.timeline}` : "",
      draft.severity ? `Mức độ: ${draft.severity}` : "",
      draft.triggers ? `Yếu tố liên quan: ${draft.triggers}` : "",
      "",
      `--- THUỐC & DỊ ỨNG ---`,
      `Thuốc đang dùng: ${
        draft.medications.length
          ? draft.medications.map((m) => `${m.name} (${m.dosage})`).join("; ")
          : "Chưa ghi nhận"
      }`,
      `Dị ứng: ${draft.allergies.length ? draft.allergies.join(", ") : "Không ghi nhận dị ứng"}`,
      draft.medicationNotes ? `Ghi chú thuốc: ${draft.medicationNotes}` : "",
      "",
      `--- CÂU HỎI CHO BÁC SĨ ---`,
      ...draft.questions.map((q, i) => `${i + 1}. ${q}`),
    ];
    return lines.filter(Boolean).join("\n");
  }, [draft]);

  const copySummaryToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(generatedSummaryText);
      setCopiedSummary(true);
      setTimeout(() => setCopiedSummary(false), 2500);
    } catch {
      // Fallback
    }
  };

  const save = async () => {
    setSaveState({ kind: "saving", message: t(language, "visitWizard.saving") });
    try {
      const created = await createVisit({
        title: draft.title.trim(),
        goal: draft.goal.trim() || draft.symptoms.join(", "),
        visit_type: draft.specialty.trim() || "specialty_consultation",
        scheduled_at: draft.scheduledAt
          ? new Date(draft.scheduledAt).toISOString()
          : undefined,
      });

      // Save concerns if symptoms or questions exist
      if (created?.id) {
        try {
          if (draft.goal.trim()) {
            await addVisitConcern(created.id, draft.goal.trim(), "routine");
          }
          for (const s of draft.symptoms) {
            await addVisitConcern(created.id, s, "routine");
          }
        } catch {
          // Non-fatal concern association
        }
      }

      const targetId = created?.id ?? "latest";
      setSaveState({ kind: "saved", message: t(language, "visitWizard.savedNotice") });
      router.replace(`/visits/${encodeURIComponent(targetId)}`);
      router.refresh();
    } catch {
      setSaveState({
        kind: "error",
        message: isEn
          ? "Failed to save visit preparation. Please verify your connection and try again."
          : "Chưa thể lưu bản chuẩn bị buổi khám. Vui lòng kiểm tra lại kết nối và thử lại.",
      });
    }
  };

  // Step 1: Reason for visit
  let stepContent;
  if (step === "reason") {
    stepContent = (
      <div className="space-y-6" data-testid="wizard-step-reason">
        <ErrorSummary errors={validationErrors} />

        <Field
          ref={titleRef}
          id="visit-title"
          label={t(language, "visitWizard.field.title")}
          value={draft.title}
          onChange={(event) => update("title", event.target.value)}
          autoFocus
          autoComplete="off"
          maxLength={255}
          placeholder={
            isEn
              ? "e.g., Cardiology follow-up & Blood Pressure check"
              : "Ví dụ: Tái khám Tim mạch & Kiểm tra huyết áp"
          }
          aria-invalid={validationErrors.length > 0 || undefined}
          aria-describedby={validationErrors.length ? "visit-title-error" : undefined}
          required
        />

        {validationErrors.length ? (
          <p id="visit-title-error" className="text-sm text-[var(--status-danger-text)]">
            {validationErrors[0].message}
          </p>
        ) : null}

        <Textarea
          id="visit-goal"
          label={t(language, "visitWizard.field.goal")}
          value={draft.goal}
          onChange={(event) => update("goal", event.target.value)}
          maxLength={2000}
          className="min-h-24"
          placeholder={
            isEn
              ? "What is the primary reason or main outcome you want from this visit?"
              : "Mục đích chính của buổi khám là gì? (Ví dụ: Hỏi kết quả xét nghiệm máu, xin đổi thuốc do tác dụng phụ)"
          }
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="visit-specialty"
            label={t(language, "visitWizard.field.specialty")}
            value={draft.specialty}
            onChange={(event) => update("specialty", event.target.value)}
            placeholder={isEn ? "e.g., Cardiology, Endocrinology" : "Ví dụ: Tim mạch, Nội tiết, Thần kinh"}
          />

          <Field
            id="visit-doctor"
            label={t(language, "visitWizard.field.doctor")}
            value={draft.doctorName}
            onChange={(event) => update("doctorName", event.target.value)}
            placeholder={isEn ? "e.g., Dr. Nguyen Van An" : "Ví dụ: BSCKII Nguyễn Văn An"}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="visit-facility"
            label={t(language, "visitWizard.field.facility")}
            value={draft.facilityName}
            onChange={(event) => update("facilityName", event.target.value)}
            placeholder={
              isEn
                ? "e.g., University Medical Center"
                : "Ví dụ: Bệnh viện Đại học Y Dược, BV Chợ Rẫy"
            }
          />

          <Field
            id="visit-scheduled-at"
            label={t(language, "visitWizard.field.scheduledAt")}
            type="datetime-local"
            value={draft.scheduledAt}
            onChange={(event) => update("scheduledAt", event.target.value)}
          />
        </div>

        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.cancel"), href: "/visits" }}
        />
      </div>
    );
  } else if (step === "symptoms") {
    // Step 2: Symptoms & Timeline
    const symptomsPool = isEn ? COMMON_SYMPTOMS_EN : COMMON_SYMPTOMS_VI;

    stepContent = (
      <div className="space-y-6" data-testid="wizard-step-symptoms">
        <div>
          <label className="block text-sm font-semibold text-[var(--text-primary)]">
            {t(language, "visitWizard.field.symptomsList")}
          </label>
          <p className="mt-1 text-xs text-[var(--text-secondary)]">
            {isEn
              ? "Select any symptoms you have been feeling recently or add custom ones."
              : "Chọn các triệu chứng bạn cảm thấy gần đây hoặc tự nhập thêm bên dưới."}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {symptomsPool.map((symptom) => {
              const isSelected = draft.symptoms.includes(symptom);
              return (
                <button
                  key={symptom}
                  type="button"
                  onClick={() => toggleSymptom(symptom)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors border ${
                    isSelected
                      ? "bg-[var(--brand-600)] text-white border-[var(--brand-600)] shadow-xs"
                      : "bg-[var(--surface-panel)] text-[var(--text-secondary)] border-[color:var(--shell-border)] hover:border-[var(--brand-400)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid={`symptom-chip-${symptom}`}
                >
                  {isSelected ? "✓ " : "+ "}
                  {symptom}
                </button>
              );
            })}
          </div>

          <div className="mt-3 flex gap-2">
            <Field
              id="custom-symptom"
              value={customSymptomInput}
              onChange={(e) => setCustomSymptomInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustomSymptom();
                }
              }}
              placeholder={isEn ? "Add another symptom..." : "Nhập triệu chứng khác..."}
              className="flex-1"
            />
            <Button type="button" variant="secondary" onClick={addCustomSymptom} className="shrink-0">
              {isEn ? "Add" : "Thêm"}
            </Button>
          </div>
        </div>

        <Field
          id="symptoms-timeline"
          label={t(language, "visitWizard.field.timeline")}
          value={draft.timeline}
          onChange={(e) => update("timeline", e.target.value)}
          placeholder={
            isEn
              ? "e.g., Started 5 days ago, happens mostly in the morning"
              : "Ví dụ: Bắt đầu 5 ngày trước, xuất hiện nhiều vào buổi sáng"
          }
        />

        <div className="space-y-1.5">
          <label className="block text-sm font-semibold text-[var(--text-primary)]">
            {t(language, "visitWizard.field.severity")}
          </label>
          <div className="grid grid-cols-3 gap-2.5">
            {[
              { id: "mild", label: isEn ? "Mild (Noticeable)" : "Nhẹ (Nhận biết được)" },
              { id: "moderate", label: isEn ? "Moderate (Intermittent)" : "Vừa phải (Thỉnh thoảng)" },
              { id: "severe", label: isEn ? "Severe (Disruptive)" : "Nhiều (Ảnh hưởng sinh hoạt)" },
            ].map((lvl) => (
              <button
                key={lvl.id}
                type="button"
                onClick={() => update("severity", lvl.id as any)}
                className={`rounded-[var(--radius-md)] border p-2.5 text-center text-xs font-medium transition-colors ${
                  draft.severity === lvl.id
                    ? "border-[var(--brand-600)] bg-[var(--brand-50,#eef4ff)] dark:bg-[var(--brand-950,#0f1f38)] text-[var(--brand-700)] dark:text-[var(--brand-300)] font-semibold"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                }`}
              >
                {lvl.label}
              </button>
            ))}
          </div>
        </div>

        <Textarea
          id="symptoms-triggers"
          label={t(language, "visitWizard.field.triggers")}
          value={draft.triggers}
          onChange={(e) => update("triggers", e.target.value)}
          placeholder={
            isEn
              ? "e.g., Triggered when climbing stairs or eating heavy dinner"
              : "Ví dụ: Xuất hiện khi leo cầu thang hoặc sau khi ăn no"
          }
          className="min-h-20"
        />

        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep(back ?? "reason") }}
          skip={{ label: t(language, "visitCreate.skip"), onClick: advance }}
        />
      </div>
    );
  } else if (step === "medications") {
    // Step 3: Current Medications & Allergies
    const allergiesPool = isEn ? COMMON_ALLERGIES_EN : COMMON_ALLERGIES_VI;

    stepContent = (
      <div className="space-y-6" data-testid="wizard-step-medications">
        {/* Active Medications List */}
        <div className="space-y-3">
          <label className="block text-sm font-semibold text-[var(--text-primary)]">
            {t(language, "visitWizard.field.medicationsList")}
          </label>
          <div className="space-y-2">
            {draft.medications.map((med) => (
              <div
                key={med.id}
                className="flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-3 text-xs"
              >
                <div className="flex items-center gap-2.5">
                  <Icon name="medication" size="1rem" className="text-[var(--text-brand)] shrink-0" />
                  <div>
                    <p className="font-bold text-[var(--text-primary)]">{med.name}</p>
                    <p className="text-[var(--text-secondary)]">
                      {med.dosage} • {med.frequency}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => removeMedication(med.id)}
                  className="rounded px-2 py-1 text-[11px] font-medium text-[var(--status-danger-text)] hover:bg-[var(--status-danger-bg)]"
                >
                  {isEn ? "Remove" : "Xoá"}
                </button>
              </div>
            ))}
          </div>

          {/* Add Medicine inline */}
          <div className="rounded-[var(--radius-lg)] border border-dashed border-[color:var(--shell-border)] p-3 space-y-2">
            <p className="text-xs font-semibold text-[var(--text-primary)]">
              {isEn ? "+ Add another medication" : "+ Thêm thuốc đang dùng"}
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              <Field
                id="new-med-name"
                value={newMedName}
                onChange={(e) => setNewMedName(e.target.value)}
                placeholder={isEn ? "Medication name (e.g. Metformin)" : "Tên thuốc (ví dụ: Metformin 500mg)"}
              />
              <div className="flex gap-2">
                <Field
                  id="new-med-dose"
                  value={newMedDose}
                  onChange={(e) => setNewMedDose(e.target.value)}
                  placeholder={isEn ? "Dosage / Instructions" : "Liều lượng / Cách dùng"}
                  className="flex-1"
                />
                <Button type="button" size="sm" variant="secondary" onClick={addMedication} className="shrink-0">
                  {isEn ? "Add" : "Thêm"}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Known Allergies */}
        <div className="space-y-2">
          <label className="block text-sm font-semibold text-[var(--text-primary)]">
            {t(language, "visitWizard.field.allergiesList")}
          </label>
          <div className="flex flex-wrap gap-2">
            {allergiesPool.map((allergy) => {
              const isSelected = draft.allergies.includes(allergy);
              return (
                <button
                  key={allergy}
                  type="button"
                  onClick={() => toggleAllergy(allergy)}
                  className={`rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors border ${
                    isSelected
                      ? "bg-[var(--status-warning-bg)] text-[var(--status-warning-text)] border-[var(--status-warning-border)] font-semibold"
                      : "bg-[var(--surface-panel)] text-[var(--text-secondary)] border-[color:var(--shell-border)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid={`allergy-chip-${allergy}`}
                >
                  {isSelected ? "⚠ " : "+ "}
                  {allergy}
                </button>
              );
            })}
          </div>

          <div className="flex gap-2 pt-1">
            <Field
              id="custom-allergy"
              value={customAllergyInput}
              onChange={(e) => setCustomAllergyInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustomAllergy();
                }
              }}
              placeholder={isEn ? "Add other allergy..." : "Nhập dị ứng khác..."}
              className="flex-1"
            />
            <Button type="button" variant="secondary" onClick={addCustomAllergy} className="shrink-0">
              {isEn ? "Add" : "Thêm"}
            </Button>
          </div>
        </div>

        <Textarea
          id="med-notes"
          label={t(language, "visitWizard.field.medNotes")}
          value={draft.medicationNotes}
          onChange={(e) => update("medicationNotes", e.target.value)}
          placeholder={
            isEn
              ? "e.g., Experiencing dry cough since starting Amlodipine, missed doses twice last week"
              : "Ví dụ: Cảm thấy ho khan nhẹ, thỉnh thoảng quên uống liều tối"
          }
          className="min-h-20"
        />

        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep(back ?? "symptoms") }}
          skip={{ label: t(language, "visitCreate.skip"), onClick: advance }}
        />
      </div>
    );
  } else {
    // Step 4: Generated Visit Summary & Questions pack
    const questionsPool = isEn ? DEFAULT_QUESTIONS_EN : DEFAULT_QUESTIONS_VI;

    stepContent = (
      <div className="space-y-6" data-testid="wizard-step-summary">
        {/* Clinician Handoff Pack Preview Card */}
        <SurfaceCard className="p-4 sm:p-5 border-l-4 border-l-[var(--brand-600)] space-y-3" data-testid="handoff-pack-preview">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="clinical-notes" size="1.2rem" className="text-[var(--text-brand)]" />
              <h3 className="font-bold text-sm sm:text-base text-[var(--text-primary)]">
                {t(language, "visitWizard.handoffPreview")}
              </h3>
            </div>
            <Badge tone="brand">CLARA Handoff Pack</Badge>
          </div>

          <div className="space-y-2 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]/60 p-3.5 text-xs">
            <div>
              <span className="font-bold text-[var(--text-primary)]">
                {isEn ? "Visit:" : "Buổi khám:"}{" "}
              </span>
              <span className="text-[var(--text-secondary)]">{draft.title}</span>
              {draft.specialty ? ` (${draft.specialty})` : ""}
            </div>
            {draft.goal ? (
              <div>
                <span className="font-bold text-[var(--text-primary)]">
                  {isEn ? "Primary Goal:" : "Mục tiêu chính:"}{" "}
                </span>
                <span className="text-[var(--text-secondary)]">{draft.goal}</span>
              </div>
            ) : null}
            {draft.symptoms.length > 0 ? (
              <div>
                <span className="font-bold text-[var(--text-primary)]">
                  {isEn ? "Symptoms:" : "Triệu chứng:"}{" "}
                </span>
                <span className="text-[var(--text-secondary)]">
                  {draft.symptoms.join(", ")}
                  {draft.timeline ? ` (${draft.timeline})` : ""}
                </span>
              </div>
            ) : null}
            {draft.medications.length > 0 ? (
              <div>
                <span className="font-bold text-[var(--text-primary)]">
                  {isEn ? "Current Medications:" : "Thuốc đang dùng:"}{" "}
                </span>
                <span className="text-[var(--text-secondary)]">
                  {draft.medications.map((m) => `${m.name} (${m.dosage})`).join(", ")}
                </span>
              </div>
            ) : null}
            {draft.allergies.length > 0 ? (
              <div>
                <span className="font-bold text-[var(--text-primary)]">
                  {isEn ? "Allergies:" : "Tiền sử dị ứng:"}{" "}
                </span>
                <span className="text-[var(--status-warning-text)]">
                  {draft.allergies.join(", ")}
                </span>
              </div>
            ) : null}
          </div>

          <div className="flex justify-end pt-1">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              icon={copiedSummary ? "check" : "copy"}
              onClick={copySummaryToClipboard}
            >
              {copiedSummary
                ? t(language, "visitWizard.copiedHandoff")
                : t(language, "visitWizard.copyHandoff")}
            </Button>
          </div>
        </SurfaceCard>

        {/* Suggested Questions Pack */}
        <div className="space-y-3" data-testid="questions-pack-section">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-semibold text-[var(--text-primary)]">
              {t(language, "visitWizard.suggestedQuestions")}
            </label>
            <span className="text-xs text-[var(--text-secondary)]">
              {isEn
                ? `${draft.questions.length} selected`
                : `Đã chọn ${draft.questions.length} câu`}
            </span>
          </div>

          <div className="space-y-2">
            {questionsPool.map((q) => {
              const isSelected = draft.questions.includes(q);
              return (
                <div
                  key={q}
                  onClick={() => toggleQuestion(q)}
                  className={`flex items-start gap-2.5 rounded-[var(--radius-lg)] border p-3 text-xs cursor-pointer transition-colors ${
                    isSelected
                      ? "border-[var(--brand-600)] bg-[var(--surface-lowest,#0b0e13)]/40 shadow-xs"
                      : "border-[color:var(--shell-border)]/60 bg-[var(--surface-panel)] hover:bg-[var(--surface-muted)]/40 opacity-80"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    className="mt-0.5 rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-400)]"
                  />
                  <span className={`flex-1 ${isSelected ? "font-medium text-[var(--text-primary)]" : "text-[var(--text-secondary)]"}`}>
                    {q}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Custom Question input */}
          <div className="flex gap-2 pt-1">
            <Field
              id="custom-question"
              value={customQuestionInput}
              onChange={(e) => setCustomQuestionInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addCustomQuestion();
                }
              }}
              placeholder={isEn ? "Add custom question for doctor..." : "Thêm câu hỏi riêng cho bác sĩ..."}
              className="flex-1"
            />
            <Button type="button" variant="secondary" onClick={addCustomQuestion} className="shrink-0">
              {isEn ? "Add" : "Thêm"}
            </Button>
          </div>
        </div>

        <StepActions
          nextLabel={t(language, "visitWizard.saveAndFinish")}
          nextType="button"
          onNext={save}
          saving={saving}
          savingLabel={t(language, "visitWizard.saving")}
          back={{ label: t(language, "visitCreate.back"), onClick: () => setStep(back ?? "medications") }}
        />
      </div>
    );
  }

  return (
    <WorkflowLayout
      workspace="personal"
      maxWidth="narrow"
      data-testid="visit-prep-wizard"
      data-shell-mode="FOCUS"
      data-layout-archetype="Visit Prep Wizard"
      eyebrow={t(language, "visitWizard.eyebrow")}
      title={titleByStep[step]}
      description={descriptionByStep[step]}
      steps={steps}
      currentStep={stepIndex}
      saveState={saveState}
      aside={t(language, "visitCreate.safetyNote")}
    >
      {stepContent}
    </WorkflowLayout>
  );
}
