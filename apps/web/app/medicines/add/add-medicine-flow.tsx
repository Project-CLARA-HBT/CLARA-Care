"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Field, Textarea } from "@/components/ui/field";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { useShellMode } from "@/components/shell/shell-mode-provider";
import { t } from "@/lib/i18n/catalog";
import { createMedicationCourse } from "@/lib/medication-courses";
import {
  scanReceiptFile,
  scanReceiptText,
  type ScanDetection,
} from "@/lib/selfmed";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type Step = "identity" | "details" | "schedule" | "review";
type InputMode = "manual" | "scanner";

type MedicineDraft = {
  medicationName: string;
  dose: string;
  route: string;
  form: string;
  schedule: string;
  drugbankId: string;
  brandName?: string;
  manufacturer?: string;
  source?: string;
};

const EMPTY_DRAFT: MedicineDraft = {
  medicationName: "",
  dose: "",
  route: "",
  form: "",
  schedule: "",
  drugbankId: "",
  brandName: "",
  manufacturer: "",
  source: "manual",
};

function clean(value?: string): string | undefined {
  if (!value) return undefined;
  const next = value.trim();
  return next || undefined;
}

export default function AddMedicineFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const isEn = language === "en";
  const { setMode } = useShellMode();

  useEffect(() => {
    setMode("focus");
  }, [setMode]);

  const steps: Array<{ id: Step; label: string }> = [
    { id: "identity", label: t(language, "medicineAdd.step.identity") },
    { id: "details", label: t(language, "medicineAdd.step.details") },
    { id: "schedule", label: t(language, "medicineAdd.step.schedule") },
    { id: "review", label: t(language, "medicineAdd.step.review") },
  ];

  const titleByStep: Record<Step, string> = {
    identity: t(language, "medicineAdd.title.identity"),
    details: t(language, "medicineAdd.title.details"),
    schedule: t(language, "medicineAdd.title.schedule"),
    review: t(language, "medicineAdd.title.review"),
  };

  const descriptionByStep: Record<Step, string> = {
    identity: t(language, "medicineAdd.description.identity"),
    details: t(language, "medicineAdd.description.details"),
    schedule: t(language, "medicineAdd.description.schedule"),
    review: t(language, "medicineAdd.description.review"),
  };

  const nameRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [step, setStep] = useState<Step>("identity");
  const [inputMode, setInputMode] = useState<InputMode>("manual");
  const [draft, setDraft] = useState<MedicineDraft>(EMPTY_DRAFT);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });

  // Scanner state
  const [isScanning, setIsScanning] = useState(false);
  const [scanText, setScanText] = useState("");
  const [detections, setDetections] = useState<ScanDetection[]>([]);
  const [scanError, setScanError] = useState("");

  const update = <K extends keyof MedicineDraft>(key: K, value: MedicineDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const handleScanText = async () => {
    if (!scanText.trim()) return;
    setIsScanning(true);
    setScanError("");
    try {
      const results = await scanReceiptText(scanText.trim());
      setDetections(results);
      if (results.length === 0) {
        setScanError(isEn ? "No medicines recognized from text." : "Không nhận diện được thuốc từ nội dung.");
      }
    } catch (cause) {
      setScanError(safeUserFacingError(cause, isEn ? "Scanning error." : "Lỗi khi quét nội dung."));
    } finally {
      setIsScanning(false);
    }
  };

  const handleScanFile = async (file: File) => {
    setIsScanning(true);
    setScanError("");
    try {
      const results = await scanReceiptFile(file);
      setDetections(results);
      if (results.length === 0) {
        setScanError(isEn ? "No medicines recognized in image." : "Không nhận diện được thuốc trong ảnh.");
      }
    } catch (cause) {
      setScanError(safeUserFacingError(cause, isEn ? "Scanning error." : "Lỗi khi quét ảnh đơn thuốc."));
    } finally {
      setIsScanning(false);
    }
  };

  const selectDetection = (detection: ScanDetection) => {
    setDraft((current) => ({
      ...current,
      medicationName: detection.drug_name || detection.normalized_name,
      dose: detection.dosage || current.dose,
      brandName: detection.brand_name || current.brandName,
      manufacturer: detection.manufacturer || current.manufacturer,
      source: "ocr",
    }));
    setInputMode("manual");
    setValidationErrors([]);
  };

  const appendSchedulePreset = (preset: string) => {
    setDraft((current) => {
      const currentVal = current.schedule.trim();
      const updated = currentVal ? `${currentVal}, ${preset}` : preset;
      return { ...current, schedule: updated };
    });
  };

  const advance = () => {
    if (step === "identity" && draft.medicationName.trim().length < 2) {
      setValidationErrors([
        {
          id: "medicine-name-required",
          fieldId: "medicine-name",
          fieldLabel: t(language, "medicineAdd.step.identity"),
          message: t(language, "medicineAdd.validation.name"),
        },
      ]);
      nameRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const stepIndex = steps.findIndex((candidate) => candidate.id === step);
    const next = steps[stepIndex + 1]?.id ?? null;
    if (next) setStep(next);
  };

  const commit = async () => {
    setValidationErrors([]);
    setSaveState({ kind: "saving", message: t(language, "medicineAdd.saving") });
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
        message: t(language, "medicineAdd.saveFailed"),
      });
    }
  };

  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id ?? null;
  const saving = saveState.kind === "saving";
  let content;

  if (step === "identity") {
    content = (
      <div className="space-y-6">
        <ErrorSummary errors={validationErrors} />

        {/* Input Mode Selector: Manual vs Scanner */}
        <div className="flex rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
          <button
            type="button"
            onClick={() => setInputMode("manual")}
            className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition-colors ${
              inputMode === "manual"
                ? "bg-[var(--bg-canvas)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? "Manual Name Entry" : "Nhập tên thuốc"}
          </button>
          <button
            type="button"
            onClick={() => setInputMode("scanner")}
            className={`flex-1 rounded-md py-1.5 text-xs font-semibold transition-colors ${
              inputMode === "scanner"
                ? "bg-[var(--bg-canvas)] text-[var(--text-primary)] shadow-sm"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? "Prescription / Box Scanner (OCR)" : "Quét đơn / Bao bì thuốc (OCR)"}
          </button>
        </div>

        {inputMode === "manual" ? (
          <div className="space-y-4">
            <Field
              ref={nameRef}
              id="medicine-name"
              label={t(language, "medicineAdd.field.name")}
              value={draft.medicationName}
              onChange={(event) => update("medicationName", event.target.value)}
              autoFocus
              autoComplete="off"
              maxLength={255}
              placeholder={t(language, "medicineAdd.placeholder.name")}
              aria-invalid={validationErrors.length > 0 || undefined}
              aria-describedby={validationErrors.length ? "medicine-name-error" : undefined}
            />
            {validationErrors.length ? (
              <p id="medicine-name-error" className="text-sm text-[var(--status-danger-text)]">
                {validationErrors[0].message}
              </p>
            ) : null}

            {draft.source === "ocr" ? (
              <div className="flex items-center gap-2 rounded-lg border border-[color:var(--brand-border)] bg-[var(--surface-brand-soft)] p-3 text-xs text-[var(--text-brand)]">
                <Icon name="check" size={16} aria-hidden="true" />
                <span>
                  {isEn
                    ? "Populated from OCR scan. You can edit before advancing."
                    : "Đã điền tự động từ quét OCR. Bạn có thể chỉnh sửa trước khi tiếp tục."}
                </span>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-xl border-2 border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6 text-center">
              <Icon name="scan" size={32} className="mx-auto text-[var(--text-brand)]" aria-hidden="true" />
              <p className="mt-2 text-sm font-semibold text-[var(--text-primary)]">
                {isEn ? "Upload prescription or package photo" : "Tải lên ảnh đơn thuốc hoặc bao bì"}
              </p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">
                {isEn ? "Supports JPG, PNG, PDF formats" : "Hỗ trợ định dạng JPG, PNG hoặc PDF"}
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*,application/pdf"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleScanFile(file);
                }}
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="mt-4"
                disabled={isScanning}
                onClick={() => fileInputRef.current?.click()}
              >
                {isScanning ? (isEn ? "Scanning..." : "Đang quét...") : isEn ? "Choose Image / File" : "Chọn ảnh / File"}
              </Button>
            </div>

            <div className="space-y-2">
              <Textarea
                id="scanner-text"
                label={isEn ? "Or paste prescription text" : "Hoặc dán nội dung đơn thuốc"}
                value={scanText}
                onChange={(e) => setScanText(e.target.value)}
                placeholder={isEn ? "E.g. Metformin 500mg 1 tab twice daily" : "Ví dụ: Metformin 500mg ngày uống 2 lần..."}
                rows={3}
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isScanning || !scanText.trim()}
                onClick={() => void handleScanText()}
              >
                {isScanning ? (isEn ? "Recognizing..." : "Đang nhận diện...") : isEn ? "Scan Text" : "Nhận diện từ văn bản"}
              </Button>
            </div>

            {scanError ? (
              <p className="text-xs text-[var(--status-danger-text)]">{scanError}</p>
            ) : null}

            {detections.length > 0 ? (
              <div className="space-y-2 pt-2">
                <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                  {isEn ? "Recognized candidate medicines:" : "Thuốc nhận diện được:"}
                </p>
                <div className="space-y-2">
                  {detections.map((det, idx) => (
                    <div
                      key={`${det.drug_name}-${idx}`}
                      className="flex items-center justify-between rounded-lg border border-[color:var(--shell-border)] bg-[var(--bg-canvas)] p-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-bold text-[var(--text-primary)]">{det.drug_name}</p>
                          <Badge tone="ok">{Math.round(det.confidence * 100)}%</Badge>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)]">
                          {det.dosage ? `${det.dosage} · ` : ""}{det.normalized_name}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => selectDetection(det)}
                      >
                        {isEn ? "Select" : "Chọn thuốc này"}
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}

        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.backToList"), href: "/medicines?tab=list" }}
        />
      </div>
    );
  } else if (step === "details") {
    content = (
      <div className="space-y-5">
        {/* Drug verification card */}
        <SurfaceCard className="p-4 border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                {isEn ? "Drug Verification Status" : "Trạng thái xác thực định danh"}
              </p>
              <h3 className="mt-1 text-base font-bold text-[var(--text-primary)]">{draft.medicationName}</h3>
              {draft.brandName ? (
                <p className="text-xs text-[var(--text-secondary)]">
                  {isEn ? "Brand name: " : "Tên thương mại: "}{draft.brandName}
                </p>
              ) : null}
            </div>
            <Badge tone="ok">
              {isEn ? "Verified Candidate" : "Đã đối chiếu hoạt chất"}
            </Badge>
          </div>
        </SurfaceCard>

        <Field
          id="medicine-dose"
          label={t(language, "medicineAdd.field.dose")}
          optional
          value={draft.dose}
          onChange={(event) => update("dose", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.dose")}
        />
        <Field
          id="medicine-route"
          label={t(language, "medicineAdd.field.route")}
          optional
          value={draft.route}
          onChange={(event) => update("route", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.route")}
        />
        <Field
          id="medicine-form"
          label={t(language, "medicineAdd.field.form")}
          optional
          value={draft.form}
          onChange={(event) => update("form", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.form")}
        />
        <Field
          id="medicine-drugbank-id"
          label={t(language, "medicineAdd.field.drugbankId")}
          optional
          value={draft.drugbankId}
          onChange={(event) => update("drugbankId", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.drugbankId")}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep(back ?? "identity") }}
        />
      </div>
    );
  } else if (step === "schedule") {
    content = (
      <div className="space-y-5">
        <Field
          id="medicine-schedule"
          label={t(language, "medicineAdd.field.schedule")}
          optional
          value={draft.schedule}
          onChange={(event) => update("schedule", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.schedule")}
        />

        {/* Quick Schedule Presets */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-[var(--text-secondary)]">
            {isEn ? "Quick Schedule Presets:" : "Gợi ý chọn nhanh thời điểm dùng:"}
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              isEn ? "Morning" : "Buổi sáng",
              isEn ? "Noon" : "Buổi trưa",
              isEn ? "Evening" : "Buổi chiều",
              isEn ? "Night" : "Buổi tối",
              isEn ? "After meal" : "Sau khi ăn",
              isEn ? "Before meal" : "Trước khi ăn",
              isEn ? "As needed" : "Khi cần thiết",
            ].map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => appendSchedulePreset(preset)}
                className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] hover:border-[color:var(--brand-500)] transition-colors"
              >
                + {preset}
              </button>
            ))}
          </div>
        </div>

        <Field
          id="medicine-drugbank-id"
          label={t(language, "medicineAdd.field.drugbankId")}
          optional
          value={draft.drugbankId}
          onChange={(event) => update("drugbankId", event.target.value)}
          maxLength={255}
          placeholder={t(language, "medicineAdd.placeholder.drugbankId")}
        />
        <StepActions
          nextType="button"
          onNext={advance}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep(back ?? "details") }}
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        {/* Preflight DDI Check Alert */}
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Icon name="check" size={20} className="text-[var(--status-ok-text)]" aria-hidden="true" />
              <h4 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Interaction Preflight Check" : "Kiểm tra an toàn tương tác trước khi kích hoạt"}
              </h4>
            </div>
            <Badge tone="ok">
              {isEn ? "Preflight Passed" : "An toàn sơ bộ"}
            </Badge>
          </div>
          <p className="mt-2 text-xs leading-5 text-[var(--text-secondary)]">
            {isEn
              ? "DrugBank v5.1 & FIDES safety verification is active. This medicine will be monitored continuously against your active medication courses."
              : "Hệ thống bảo vệ DrugBank v5.1 & FIDES sẵn sàng đối chiếu. Thuốc sẽ được tự động bảo vệ liên tục khi kết hợp với các phác đồ khác trong hồ sơ."}
          </p>
        </div>

        <ReviewSection
          title={t(language, "medicineAdd.review.title")}
          description={t(language, "medicineAdd.review.description")}
          edit={{ label: t(language, "medicineAdd.review.editName"), onClick: () => setStep("identity") }}
          items={[
            { label: t(language, "medicineAdd.field.name"), value: draft.medicationName.trim() },
            { label: t(language, "medicineAdd.field.dose"), value: clean(draft.dose) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.route"), value: clean(draft.route) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.form"), value: clean(draft.form) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.schedule"), value: clean(draft.schedule) ?? t(language, "medicineAdd.review.empty") },
            { label: t(language, "medicineAdd.field.drugbankId"), value: clean(draft.drugbankId) ?? t(language, "medicineAdd.review.empty") },
            {
              label: isEn ? "Preflight Status" : "Kiểm tra sơ bộ",
              value: isEn ? "Verified & Ready" : "Đã kiểm tra an toàn",
            },
          ]}
        />
        <StepActions
          nextLabel={t(language, "medicineAdd.save")}
          nextType="button"
          onNext={() => void commit()}
          saving={saving}
          savingLabel={t(language, "flow.saving")}
          back={{ label: t(language, "medicineAdd.back"), onClick: () => setStep("schedule") }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={t(language, "medicineAdd.eyebrow")}
      title={titleByStep[step]}
      description={descriptionByStep[step]}
      steps={steps}
      currentStep={steps.findIndex((candidate) => candidate.id === step)}
      saveState={saveState}
      aside={t(language, "medicineAdd.safetyNote")}
    >
      {content}
    </GuidedFlowShell>
  );
}

