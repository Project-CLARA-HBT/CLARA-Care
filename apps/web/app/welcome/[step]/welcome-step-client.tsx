"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  GuidedFlowShell,
  ErrorSummary,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Field, Select } from "@/components/ui/field";
import { Toggle } from "@/components/ui/toggle";
import { getRole } from "@/lib/auth-store";
import { getRoleHomePath } from "@/lib/navigation.config";
import {
  getPhrOnboarding,
  updatePhrOnboarding,
  type PhrOnboarding,
  type PhrOnboardingPatch,
} from "@/lib/phr-onboarding";
import {
  adjacentGuidedFlowStep,
  guidedFlowPath,
  guidedFlowSteps,
  WELCOME_STEP_IDS,
} from "@/lib/guided-flow-registry";
import {
  type WelcomeStepId,
} from "../welcome-steps";

type WelcomeDraftPatch = Omit<PhrOnboardingPatch, "action">;

const FLOW_STEPS = guidedFlowSteps("welcome", "vi");

const GENDERS = [
  ["", "Không muốn nói"],
  ["female", "Nữ"],
  ["male", "Nam"],
  ["other", "Khác"],
] as const;
const BLOOD_TYPES = ["", "A", "B", "AB", "O"] as const;

function path(step: WelcomeStepId) {
  return guidedFlowPath("welcome", step);
}

function numeric(value: string): number | null {
  const parsed = Number(value.replace(",", "."));
  return value.trim() && Number.isFinite(parsed) ? parsed : null;
}

function measurementError(
  value: string,
  maximum: number,
  fieldId: string,
  fieldLabel: string,
): GuidedFlowError | null {
  if (!value.trim()) return null;
  const parsed = numeric(value);
  if (parsed !== null && parsed >= 0 && parsed <= maximum) return null;
  return {
    id: `${fieldId}-invalid`,
    fieldId,
    fieldLabel,
    message: `Nhập một số từ 0 đến ${maximum}.`,
  };
}

export default function WelcomeStepClient({ step }: { step: WelcomeStepId }) {
  const router = useRouter();
  const stepIndex = WELCOME_STEP_IDS.indexOf(step);
  const previous = adjacentGuidedFlowStep("welcome", step, "previous");
  const next = adjacentGuidedFlowStep("welcome", step, "next");

  const [onboarding, setOnboarding] = useState<PhrOnboarding | null>(null);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({
    kind: "idle",
  });
  const [fullName, setFullName] = useState("");
  const [dob, setDob] = useState("");
  const [gender, setGender] = useState("");
  const [bloodType, setBloodType] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [consent, setConsent] = useState(false);
  const [selfDeclaredConfirmed, setSelfDeclaredConfirmed] = useState(false);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const heightRef = useRef<HTMLInputElement>(null);
  const weightRef = useRef<HTMLInputElement>(null);

  const hydrate = useCallback((data: PhrOnboarding) => {
    setOnboarding(data);
    setFullName(data.record.full_name ?? "");
    setDob(data.record.date_of_birth ?? "");
    setGender(data.record.gender ?? "");
    setBloodType(data.record.blood_type ?? "");
    setHeightCm(
      data.record.height_cm == null ? "" : String(data.record.height_cm),
    );
    setWeightKg(
      data.record.weight_kg == null ? "" : String(data.record.weight_kg),
    );
    setConsent(Boolean(data.personalization_consent));
  }, []);

  useEffect(() => {
    let active = true;
    void getPhrOnboarding()
      .then((data) => {
        if (!active) return;
        hydrate(data);
        if (!data.needs_onboarding) {
          router.replace(getRoleHomePath(getRole()));
        }
      })
      .catch(() => {
        if (active) {
          setSaveState({
            kind: "error",
            message:
              "Chưa thể tải bản thiết lập. Bạn có thể thử lại hoặc quay lại sau.",
          });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [hydrate, router]);

  const saveAndNavigate = async (
    patch: WelcomeDraftPatch,
    target: WelcomeStepId | null,
  ) => {
    if (!target) return;
    setValidationErrors([]);
    setSaveState({ kind: "saving" });
    try {
      const updated = await updatePhrOnboarding({ ...patch, action: "save" });
      hydrate(updated);
      setSaveState({ kind: "saved" });
      router.push(path(target));
    } catch {
      setSaveState({
        kind: "error",
        message: "Không thể lưu thay đổi lúc này. Vui lòng thử lại.",
      });
    }
  };

  const finish = async (action: "complete" | "skip") => {
    if (action === "complete" && !selfDeclaredConfirmed) return;
    setSaveState({ kind: "saving" });
    try {
      await updatePhrOnboarding(
        action === "skip"
          ? { action: "skip" }
          : { action: "complete", confirm_self_declared: true },
      );
      router.replace(getRoleHomePath(getRole()));
      router.refresh();
    } catch {
      setSaveState({
        kind: "error",
        message: "Không thể hoàn tất lúc này. Vui lòng thử lại.",
      });
    }
  };

  const saving = saveState.kind === "saving";
  const actions = (patch: WelcomeDraftPatch) => (
    <StepActions
      saving={saving}
      onNext={() => void saveAndNavigate(patch, next)}
      nextType="button"
      back={
        previous
          ? {
              label: "Quay lại",
              onClick: () => void saveAndNavigate(patch, previous),
            }
          : undefined
      }
      skip={
        next ? { label: "Bỏ qua", href: path(next) } : undefined
      }
    />
  );
  const bodyPatch = {
    height_cm: numeric(heightCm),
    weight_kg: numeric(weightKg),
  };
  const navigateFromBody = (target: WelcomeStepId | null) => {
    const errors = [
      measurementError(heightCm, 300, "welcome-height", "Chiều cao"),
      measurementError(weightKg, 800, "welcome-weight", "Cân nặng"),
    ].filter((error): error is GuidedFlowError => error !== null);
    setValidationErrors(errors);
    if (errors.length) {
      if (errors[0].fieldId === "welcome-height") heightRef.current?.focus();
      else weightRef.current?.focus();
      return;
    }
    void saveAndNavigate(bodyPatch, target);
  };

  let content;
  if (loading) {
    content = (
      <div className="space-y-3" aria-label="Đang tải thiết lập">
        <div className="h-5 w-1/2 animate-pulse rounded bg-[var(--surface-muted)]" />
        <div className="h-28 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
      </div>
    );
  } else if (step === "start") {
    content = (
      <div className="space-y-6">
        <Badge tone="brand" icon="spa">
          The Clara Care
        </Badge>
        <p className="leading-7 text-[var(--text-secondary)]">
          Thiết lập gồm các bước ngắn và tất cả thông tin sức khoẻ đều không bắt
          buộc. Mỗi lựa chọn được lưu an toàn để bạn có thể quay lại sau.
        </p>
        <ul className="space-y-2 text-sm text-[var(--text-secondary)]">
          <li>• Một nhóm thông tin ở mỗi bước.</li>
          <li>• Xem lại trước khi hoàn tất.</li>
          <li>• Có thể chỉnh sửa hoặc xoá trong Hồ sơ.</li>
        </ul>
        <StepActions
          nextLabel="Bắt đầu"
          nextType="button"
          onNext={() => router.push(path("name"))}
          skip={{
            label: "Bỏ qua, để sau",
            onClick: () => void finish("skip"),
            disabled: saving,
          }}
          saving={saving}
        />
      </div>
    );
  } else if (step === "name") {
    content = (
      <div className="space-y-5">
        <Field
          label="Tên hiển thị"
          optional
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder="Ví dụ: Nguyễn An"
          autoComplete="name"
        />
        {actions({ full_name: fullName.trim() })}
      </div>
    );
  } else if (step === "birth") {
    content = (
      <div className="space-y-5">
        <Field
          label="Ngày sinh"
          optional
          type="date"
          value={dob}
          onChange={(event) => setDob(event.target.value)}
        />
        {actions({ date_of_birth: dob || null })}
      </div>
    );
  } else if (step === "gender") {
    content = (
      <div className="space-y-5">
        <Select
          label="Giới tính"
          optional
          value={gender}
          onChange={(event) => setGender(event.target.value)}
        >
          {GENDERS.map(([value, label]) => (
            <option key={value || "none"} value={value}>
              {label}
            </option>
          ))}
        </Select>
        {actions({ gender })}
      </div>
    );
  } else if (step === "blood-type") {
    content = (
      <div className="space-y-5">
        <Select
          label="Nhóm máu"
          optional
          value={bloodType}
          onChange={(event) => setBloodType(event.target.value)}
        >
          {BLOOD_TYPES.map((value) => (
            <option key={value || "none"} value={value}>
              {value || "Chưa rõ"}
            </option>
          ))}
        </Select>
        {actions({ blood_type: bloodType })}
      </div>
    );
  } else if (step === "body") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={heightRef}
          id="welcome-height"
          label="Chiều cao"
          optional
          hint="cm"
          inputMode="decimal"
          min={0}
          max={300}
          aria-invalid={
            validationErrors.some((error) => error.fieldId === "welcome-height") ||
            undefined
          }
          value={heightCm}
          onChange={(event) => setHeightCm(event.target.value)}
          placeholder="170"
        />
        <Field
          ref={weightRef}
          id="welcome-weight"
          label="Cân nặng"
          optional
          hint="kg"
          inputMode="decimal"
          min={0}
          max={800}
          aria-invalid={
            validationErrors.some((error) => error.fieldId === "welcome-weight") ||
            undefined
          }
          value={weightKg}
          onChange={(event) => setWeightKg(event.target.value)}
          placeholder="62"
        />
        <StepActions
          saving={saving}
          nextType="button"
          onNext={() => navigateFromBody(next)}
          back={
            previous
              ? {
                  label: "Quay lại",
                  onClick: () => navigateFromBody(previous),
                }
              : undefined
          }
          skip={
            next ? { label: "Bỏ qua", href: path(next) } : undefined
          }
        />
      </div>
    );
  } else if (step === "personalization") {
    content = (
      <div className="space-y-5">
        <Toggle
          checked={consent}
          onChange={setConsent}
          label="Cho phép cá nhân hoá"
          description="Dùng hồ sơ sức khoẻ để gợi ý phù hợp hơn. Không bắt buộc và có thể thu hồi."
        />
        <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
          CLARA là trợ lý tham khảo, không chẩn đoán hoặc thay thế bác sĩ.
        </p>
        {actions({ personalization_consent: consent })}
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title="Thông tin tự khai báo"
          description="Thông tin trống vẫn có thể bổ sung sau."
          edit={{ href: path("name") }}
          items={[
            { label: "Tên", value: onboarding?.record.full_name || "Chưa cung cấp" },
            {
              label: "Ngày sinh",
              value: onboarding?.record.date_of_birth || "Chưa cung cấp",
            },
            {
              label: "Giới tính",
              value:
                GENDERS.find(([value]) => value === onboarding?.record.gender)?.[1] ||
                "Chưa cung cấp",
            },
            {
              label: "Nhóm máu",
              value: onboarding?.record.blood_type || "Chưa rõ",
            },
            {
              label: "Chiều cao",
              value:
                onboarding?.record.height_cm == null
                  ? "Chưa cung cấp"
                  : `${onboarding.record.height_cm} cm`,
            },
            {
              label: "Cân nặng",
              value:
                onboarding?.record.weight_kg == null
                  ? "Chưa cung cấp"
                  : `${onboarding.record.weight_kg} kg`,
            },
            {
              label: "Cá nhân hoá",
              value: onboarding?.personalization_consent
                ? "Đã cho phép"
                : "Không cho phép",
            },
          ]}
        />
        <p className="text-sm leading-6 text-[var(--text-secondary)]">
          Bạn vẫn có thể sửa hoặc xoá các thông tin này trong Hồ sơ.
        </p>
        <label className="focus-within:shadow-[var(--shadow-focus)] flex min-h-[var(--touch-target-min)] cursor-pointer items-start gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
          <input
            type="checkbox"
            checked={selfDeclaredConfirmed}
            onChange={(event) => setSelfDeclaredConfirmed(event.target.checked)}
            className="mt-0.5 h-5 w-5 shrink-0 rounded border-[color:var(--shell-border-strong)] accent-[var(--brand-600)]"
          />
          <span className="text-sm leading-6 text-[var(--text-primary)]">
            Tôi xác nhận các thông tin trên là do chính tôi tự khai báo.
          </span>
        </label>
        <StepActions
          nextLabel="Hoàn tất thiết lập"
          nextType="button"
          onNext={() => void finish("complete")}
          nextDisabled={!selfDeclaredConfirmed}
          saving={saving}
          back={{ label: "Quay lại", href: path("personalization") }}
        />
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-1rem)] px-4 py-8 sm:py-12">
      <GuidedFlowShell
        eyebrow="Thiết lập CLARA"
        title={FLOW_STEPS[stepIndex].label}
        description={
          step === "start"
            ? "Bắt đầu nhẹ nhàng, bạn luôn nắm quyền kiểm soát."
            : "Bước này không bắt buộc. Bạn có thể bỏ qua và cập nhật sau."
        }
        steps={FLOW_STEPS}
        currentStep={stepIndex}
        saveState={saveState}
        aside={
          <p className="text-center">
            Dữ liệu được lưu vào hồ sơ của bạn, không nằm trong URL hoặc phân
            tích hành vi.
          </p>
        }
      >
        {content}
      </GuidedFlowShell>
    </div>
  );
}
