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
} from "@/components/guided-flow";
import { Field } from "@/components/ui/field";
import { createMedicationCourse } from "@/lib/medication-courses";

type Step = "identity" | "details" | "schedule" | "review";

const STEPS: Array<{ id: Step; label: string }> = [
  { id: "identity", label: "Tên thuốc" },
  { id: "details", label: "Chi tiết" },
  { id: "schedule", label: "Lịch dùng" },
  { id: "review", label: "Kiểm tra" },
];

type MedicineDraft = {
  medicationName: string;
  dose: string;
  route: string;
  form: string;
  schedule: string;
  drugbankId: string;
};

const EMPTY_DRAFT: MedicineDraft = {
  medicationName: "",
  dose: "",
  route: "",
  form: "",
  schedule: "",
  drugbankId: "",
};

const TITLES: Record<Step, string> = {
  identity: "Thuốc nào bạn muốn theo dõi?",
  details: "Ghi lại thông tin trên nhãn",
  schedule: "Thuốc được dùng khi nào?",
  review: "Kiểm tra trước khi lưu",
};

function descriptionFor(step: Step): string {
  if (step === "identity") return "Nhập đúng tên trên nhãn hoặc đơn của bạn.";
  if (step === "details") return "Liều, đường dùng và dạng bào chế đều có thể bỏ qua nếu bạn chưa rõ.";
  if (step === "schedule") return "Ghi lại lịch dùng từ nhãn hoặc đơn; CLARA không đề xuất liều hay lịch dùng.";
  return "Xác nhận thông tin bạn đã nhập. Bạn luôn có thể chỉnh sửa bản ghi sau đó.";
}

function nextStep(step: Step): Step | null {
  const index = STEPS.findIndex((candidate) => candidate.id === step);
  return STEPS[index + 1]?.id ?? null;
}

function previousStep(step: Step): Step | null {
  const index = STEPS.findIndex((candidate) => candidate.id === step);
  return STEPS[index - 1]?.id ?? null;
}

function clean(value: string): string | undefined {
  const next = value.trim();
  return next || undefined;
}

export default function AddMedicineFlow() {
  const router = useRouter();
  const nameRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("identity");
  const [draft, setDraft] = useState<MedicineDraft>(EMPTY_DRAFT);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  const update = <K extends keyof MedicineDraft>(key: K, value: MedicineDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const advance = () => {
    if (step === "identity" && draft.medicationName.trim().length < 2) {
      setValidationErrors([
        {
          id: "medicine-name-required",
          fieldId: "medicine-name",
          fieldLabel: "Tên thuốc",
          message: "Nhập ít nhất 2 ký tự từ nhãn hoặc đơn của bạn.",
        },
      ]);
      nameRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const next = nextStep(step);
    if (next) setStep(next);
  };

  const commit = async () => {
    setValidationErrors([]);
    setSaveState({ kind: "saving", message: "Đang lưu thuốc đã xác nhận…" });
    try {
      await createMedicationCourse({
        medication_name: draft.medicationName.trim(),
        dose_text: clean(draft.dose),
        route_text: clean(draft.route),
        form_text: clean(draft.form),
        schedule_text: clean(draft.schedule),
        drugbank_id: clean(draft.drugbankId),
      });
      router.replace("/medicines?tab=list");
      router.refresh();
    } catch {
      setSaveState({
        kind: "error",
        message: "Chưa thể lưu thuốc lúc này. Thông tin trên trang vẫn giữ nguyên để bạn thử lại.",
      });
    }
  };

  const back = previousStep(step);
  const saving = saveState.kind === "saving";
  let content;

  if (step === "identity") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={nameRef}
          id="medicine-name"
          label="Tên thuốc trên nhãn hoặc đơn"
          value={draft.medicationName}
          onChange={(event) => update("medicationName", event.target.value)}
          autoFocus
          autoComplete="off"
          maxLength={255}
          placeholder="Ví dụ: Metformin"
          aria-invalid={validationErrors.length > 0 || undefined}
          aria-describedby={validationErrors.length ? "medicine-name-error" : undefined}
        />
        {validationErrors.length ? (
          <p id="medicine-name-error" className="text-sm text-[var(--status-danger-text)]">
            {validationErrors[0].message}
          </p>
        ) : null}
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: "Quay lại thuốc của tôi", href: "/medicines?tab=list" }}
        />
      </div>
    );
  } else if (step === "details") {
    content = (
      <div className="space-y-5">
        <Field
          id="medicine-dose"
          label="Liều ghi trên nhãn"
          optional
          value={draft.dose}
          onChange={(event) => update("dose", event.target.value)}
          maxLength={255}
          placeholder="Ví dụ: 500 mg"
        />
        <Field
          id="medicine-route"
          label="Đường dùng"
          optional
          value={draft.route}
          onChange={(event) => update("route", event.target.value)}
          maxLength={255}
          placeholder="Ví dụ: uống"
        />
        <Field
          id="medicine-form"
          label="Dạng bào chế"
          optional
          value={draft.form}
          onChange={(event) => update("form", event.target.value)}
          maxLength={255}
          placeholder="Ví dụ: viên nén"
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: "Quay lại", onClick: () => setStep(back ?? "identity") }}
        />
      </div>
    );
  } else if (step === "schedule") {
    content = (
      <div className="space-y-5">
        <Field
          id="medicine-schedule"
          label="Lịch dùng ghi trên nhãn hoặc đơn"
          optional
          value={draft.schedule}
          onChange={(event) => update("schedule", event.target.value)}
          maxLength={255}
          placeholder="Ví dụ: buổi tối"
        />
        <Field
          id="medicine-drugbank-id"
          label="DrugBank ID"
          optional
          value={draft.drugbankId}
          onChange={(event) => update("drugbankId", event.target.value)}
          maxLength={255}
          placeholder="Nếu bạn đã có"
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: "Quay lại", onClick: () => setStep(back ?? "details") }}
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title="Thuốc đã xác nhận"
          description="CLARA lưu đúng nội dung bạn xác nhận, không tự suy đoán thuốc hoặc hướng dẫn dùng thuốc."
          edit={{ label: "Sửa tên", onClick: () => setStep("identity") }}
          items={[
            { label: "Tên thuốc", value: draft.medicationName.trim() },
            { label: "Liều", value: clean(draft.dose) ?? "Chưa nhập" },
            { label: "Đường dùng", value: clean(draft.route) ?? "Chưa nhập" },
            { label: "Dạng bào chế", value: clean(draft.form) ?? "Chưa nhập" },
            { label: "Lịch dùng", value: clean(draft.schedule) ?? "Chưa nhập" },
            { label: "DrugBank ID", value: clean(draft.drugbankId) ?? "Chưa nhập" },
          ]}
        />
        <StepActions
          nextLabel="Lưu thuốc đã xác nhận"
          nextType="button"
          onNext={() => void commit()}
          saving={saving}
          savingLabel="Đang lưu…"
          back={{ label: "Quay lại", onClick: () => setStep("schedule") }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow="Thuốc của tôi"
      title={TITLES[step]}
      description={descriptionFor(step)}
      steps={STEPS}
      currentStep={STEPS.findIndex((candidate) => candidate.id === step)}
      saveState={saveState}
      aside="Đây là bản ghi cá nhân, không thay thế đơn thuốc, tư vấn dược sĩ, bác sĩ hoặc chăm sóc khẩn cấp. Nội dung chỉ ở trong phiên này cho đến khi bạn xác nhận lưu."
    >
      {content}
    </GuidedFlowShell>
  );
}
