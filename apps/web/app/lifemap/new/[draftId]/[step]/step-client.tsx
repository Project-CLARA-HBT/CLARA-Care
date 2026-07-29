"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  ErrorSummary,
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowError,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Field, Select, Textarea } from "@/components/ui/field";
import {
  commitLifeMapEpisodeDraft,
  getGuidedFlowDraft,
  updateLifeMapEpisodeDraft,
  type GuidedFlowDraft,
  type LifeMapEpisodeStep,
  type LifeMapPriority,
} from "@/lib/guided-flows";
import {
  LIFEMAP_EPISODE_STEP_IDS,
  adjacentGuidedFlowStep,
  guidedFlowSteps,
  isGuidedFlowStepAhead,
} from "@/lib/guided-flow-registry";

const STEPS = guidedFlowSteps("lifemapEpisode", "vi");
const PRIORITY_LABELS: Record<LifeMapPriority, string> = {
  routine: "Theo dõi thường lệ",
  soon: "Cần chú ý sớm",
  urgent: "Ưu tiên cao",
};

function draftPath(draftId: string, step: LifeMapEpisodeStep): string {
  return `/lifemap/new/${encodeURIComponent(draftId)}/${step}`;
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `lifemap-${Date.now()}-commit`;
}

export default function LifeMapEpisodeStepClient({
  draftId,
  step,
}: {
  draftId: string;
  step: LifeMapEpisodeStep;
}) {
  const router = useRouter();
  const titleRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<GuidedFlowDraft | null>(null);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [priority, setPriority] = useState<LifeMapPriority>("routine");
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);

  const hydrate = useCallback((nextDraft: GuidedFlowDraft) => {
    setDraft(nextDraft);
    setTitle(nextDraft.payload.title ?? "");
    setGoal(nextDraft.payload.goal ?? "");
    setPriority(nextDraft.payload.priority ?? "routine");
  }, []);

  useEffect(() => {
    let active = true;
    void getGuidedFlowDraft(draftId)
      .then((loaded) => {
        if (!active) return;
        if (loaded.status !== "active") {
          router.replace("/lifemap");
          return;
        }
        hydrate(loaded);
        if (
          isGuidedFlowStepAhead(
            "lifemapEpisode",
            step,
            loaded.current_step,
          )
        ) {
          router.replace(draftPath(loaded.id, loaded.current_step));
        }
      })
      .catch(() => {
        if (active) {
          setSaveState({
            kind: "error",
            message:
              "Bản nháp không còn khả dụng hoặc đã thay đổi. Quay lại LifeMap và thử lại.",
          });
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [draftId, hydrate, router, step]);

  const saveAndNavigate = async (target: LifeMapEpisodeStep | null) => {
    if (!draft || !target) return;
    if (step === "title" && title.trim().length < 2) {
      setValidationErrors([
        {
          id: "title-required",
          fieldId: "lifemap-episode-title",
          fieldLabel: "Tên hành trình",
          message: "Nhập ít nhất 2 ký tự.",
        },
      ]);
      titleRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "saving" });
    try {
      const updated = await updateLifeMapEpisodeDraft(
        draft.id,
        draft.revision,
        target,
        {
          title: title.trim(),
          goal: goal.trim(),
          priority,
        },
      );
      hydrate(updated);
      setSaveState({ kind: "saved" });
      router.push(draftPath(updated.id, target));
    } catch {
      setSaveState({
        kind: "error",
        message:
          "Không thể lưu vì bản nháp đã thay đổi hoặc kết nối bị gián đoạn. Tải lại trước khi thử tiếp.",
      });
    }
  };

  const commit = async () => {
    if (!draft) return;
    setSaveState({ kind: "saving" });
    try {
      const committed = await commitLifeMapEpisodeDraft(
        draft.id,
        draft.revision,
        newIdempotencyKey(),
      );
      if (committed.status === "committed") {
        router.replace("/lifemap");
        router.refresh();
      }
    } catch {
      setSaveState({
        kind: "error",
        message:
          "Chưa thể tạo hành trình. Bản nháp vẫn được giữ an toàn để bạn thử lại.",
      });
    }
  };

  const previous = adjacentGuidedFlowStep("lifemapEpisode", step, "previous");
  const next = adjacentGuidedFlowStep("lifemapEpisode", step, "next");
  const saving = saveState.kind === "saving";
  const actions = (
    <StepActions
      saving={saving}
      onNext={() => void saveAndNavigate(next)}
      nextType="button"
      back={
        previous
          ? {
              label: "Quay lại",
              onClick: () => void saveAndNavigate(previous),
            }
          : { label: "Thoát", href: "/lifemap" }
      }
    />
  );

  let content;
  if (loading) {
    content = (
      <div
        aria-label="Đang tải bản nháp"
        className="h-32 animate-pulse rounded-[var(--radius-lg)] bg-[var(--surface-muted)]"
      />
    );
  } else if (!draft) {
    content = (
      <StepActions
        nextLabel="Quay lại LifeMap"
        nextType="button"
        onNext={() => router.replace("/lifemap")}
      />
    );
  } else if (step === "title") {
    content = (
      <div className="space-y-5">
        <ErrorSummary errors={validationErrors} />
        <Field
          ref={titleRef}
          id="lifemap-episode-title"
          label="Bạn muốn gọi hành trình này là gì?"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={255}
          autoFocus
          placeholder="Ví dụ: Ngủ tốt hơn"
        />
        {actions}
      </div>
    );
  } else if (step === "goal") {
    content = (
      <div className="space-y-5">
        <Textarea
          id="lifemap-episode-goal"
          label="Bạn muốn đạt được điều gì?"
          optional
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
          maxLength={4000}
          rows={5}
          placeholder="Mô tả kết quả bạn muốn theo dõi."
        />
        {actions}
      </div>
    );
  } else if (step === "priority") {
    content = (
      <div className="space-y-5">
        <Select
          id="lifemap-episode-priority"
          label="Mức ưu tiên"
          value={priority}
          onChange={(event) => setPriority(event.target.value as LifeMapPriority)}
        >
          <option value="routine">{PRIORITY_LABELS.routine}</option>
          <option value="soon">{PRIORITY_LABELS.soon}</option>
          <option value="urgent">{PRIORITY_LABELS.urgent}</option>
        </Select>
        <p className="text-sm leading-6 text-[var(--text-secondary)]">
          Mức ưu tiên giúp sắp xếp kế hoạch; không phải đánh giá mức độ khẩn cấp y tế.
        </p>
        {actions}
      </div>
    );
  } else {
    content = (
      <div className="space-y-5">
        <ReviewSection
          title="Thông tin hành trình"
          description="Kiểm tra trước khi tạo. Bạn vẫn có thể chỉnh sửa sau."
          edit={{ href: draftPath(draft.id, "title") }}
          items={[
            { label: "Tên", value: title || "Chưa nhập" },
            { label: "Mục tiêu", value: goal || "Chưa nhập" },
            { label: "Ưu tiên", value: PRIORITY_LABELS[priority] },
          ]}
        />
        <StepActions
          nextLabel="Tạo hành trình"
          nextType="button"
          onNext={() => void commit()}
          saving={saving}
          savingLabel="Đang tạo…"
          back={{
            label: "Quay lại",
            onClick: () => void saveAndNavigate("priority"),
          }}
        />
      </div>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow="LifeMap"
      title={
        step === "title"
          ? "Đặt tên cho hành trình"
          : step === "goal"
            ? "Chọn một mục tiêu"
            : step === "priority"
              ? "Xác định mức ưu tiên"
              : "Xem lại hành trình"
      }
      description="Mỗi bước chỉ hỏi một nhóm thông tin. Bản nháp được lưu trên máy chủ và không đưa nội dung sức khoẻ vào URL."
      steps={STEPS}
      currentStep={LIFEMAP_EPISODE_STEP_IDS.indexOf(step)}
      saveState={saveState}
      aside="LifeMap hỗ trợ tự theo dõi và chuẩn bị trao đổi với nhân viên y tế; không thay thế chẩn đoán hoặc chăm sóc khẩn cấp."
    >
      {content}
    </GuidedFlowShell>
  );
}
