"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  GuidedFlowShell,
  ReviewSection,
  StepActions,
  type GuidedFlowSaveState,
} from "@/components/guided-flow";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import {
  isDsarEnabled,
  listDsarRequests,
  requestDsarDelete,
  type DsarRequestRecord,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

import type { DeleteFlowStep } from "./page";

const STEPS = [
  { id: "review", label: "Hệ quả" },
  { id: "confirm", label: "Xác nhận" },
  { id: "status", label: "Biên nhận" },
];

const COPY = {
  vi: {
    title: "Xóa dữ liệu cá nhân",
    reviewTitle: "Trước khi gửi yêu cầu xóa",
    reviewDescription:
      "Hãy đọc hệ quả trước. Bạn vẫn có thể quay lại Dữ liệu của tôi mà chưa gửi yêu cầu.",
    confirmTitle: "Xác nhận yêu cầu xóa",
    confirmDescription:
      "Chỉ gửi khi bạn hiểu đây là yêu cầu không thể hoàn tác.",
    statusTitle: "Biên nhận yêu cầu xóa",
    statusDescription: "Bạn có thể theo dõi tiến độ tại Dữ liệu của tôi.",
    consequenceTitle: "Điều gì sẽ xảy ra",
    consequence:
      "CLARA sẽ xử lý yêu cầu xóa hoặc ẩn danh hóa dữ liệu cá nhân của bạn theo thời hạn luật định.",
    retentionTitle: "Dữ liệu được giữ lại",
    retention:
      "Một số bản ghi audit/tuân thủ không chứa dữ liệu định danh vẫn có thể được giữ theo nghĩa vụ pháp lý.",
    confirmation:
      "Tôi hiểu yêu cầu này có thể xóa hoặc ẩn danh hóa dữ liệu cá nhân và không thể hoàn tác.",
    continue: "Tiếp tục",
    confirm: "Gửi yêu cầu xóa",
    sending: "Đang gửi yêu cầu…",
    back: "Quay lại",
    cancel: "Hủy, quay lại dữ liệu của tôi",
    receipt: "Yêu cầu đã được ghi nhận.",
    unknownReceipt: "Không tìm thấy biên nhận này. Bạn có thể xem lịch sử yêu cầu của mình.",
    unavailable: "Yêu cầu quyền dữ liệu hiện chưa được bật cho môi trường này.",
    loading: "Đang tải biên nhận…",
    loadError: "Không thể tải biên nhận lúc này. Vui lòng thử lại.",
    submitError: "Không thể gửi yêu cầu lúc này. Vui lòng thử lại.",
    requestId: "Mã yêu cầu",
    submittedAt: "Gửi lúc",
    dueAt: "Hạn xử lý",
    status: "Trạng thái",
  },
  en: {
    title: "Delete personal data",
    reviewTitle: "Before you request deletion",
    reviewDescription:
      "Read the consequences first. You can still return to My data without sending a request.",
    confirmTitle: "Confirm your deletion request",
    confirmDescription: "Only submit when you understand this request cannot be undone.",
    statusTitle: "Deletion request receipt",
    statusDescription: "You can follow progress from My data.",
    consequenceTitle: "What will happen",
    consequence:
      "CLARA will process a request to delete or anonymize your personal data within the statutory window.",
    retentionTitle: "Data retained",
    retention:
      "Some audit or compliance records without identifying data may still be retained under legal obligations.",
    confirmation:
      "I understand this request may delete or anonymize my personal data and cannot be undone.",
    continue: "Continue",
    confirm: "Submit deletion request",
    sending: "Submitting request…",
    back: "Back",
    cancel: "Cancel and return to My data",
    receipt: "Your request has been recorded.",
    unknownReceipt: "This receipt could not be found. You can review your request history.",
    unavailable: "Data-subject requests are not enabled for this environment yet.",
    loading: "Loading receipt…",
    loadError: "Could not load the receipt. Please try again.",
    submitError: "Could not submit your request. Please try again.",
    requestId: "Request ID",
    submittedAt: "Submitted",
    dueAt: "Due",
    status: "Status",
  },
} as const;

const STATUS_LABELS = {
  received: { vi: "Đã tiếp nhận", en: "Received" },
  in_progress: { vi: "Đang xử lý", en: "In progress" },
  fulfilled: { vi: "Đã hoàn tất", en: "Fulfilled" },
  rejected: { vi: "Đã từ chối", en: "Rejected" },
} as const;

function flowPath(step: DeleteFlowStep, requestId?: string | number) {
  const base = `/account/data/delete/${step}`;
  return requestId === undefined ? base : `${base}?request=${encodeURIComponent(String(requestId))}`;
}

export default function DeleteDataFlowClient({ step }: { step: DeleteFlowStep }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [acknowledged, setAcknowledged] = useState(false);
  const [saveState, setSaveState] = useState<GuidedFlowSaveState>({ kind: "idle" });
  const [receipt, setReceipt] = useState<DsarRequestRecord | null>(null);
  const [loadingReceipt, setLoadingReceipt] = useState(step === "status");

  const text = useMemo(() => COPY[uiLanguage], [uiLanguage]);
  const currentStep = STEPS.findIndex((candidate) => candidate.id === step);
  const requestId = searchParams.get("request");
  const available = isDsarEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  useEffect(() => {
    if (step !== "status" || !available) {
      setLoadingReceipt(false);
      return;
    }
    let active = true;
    setLoadingReceipt(true);
    void listDsarRequests()
      .then((response) => {
        if (!active) return;
        const match = response.requests.find(
          (request) => String(request.id) === requestId && request.kind === "delete",
        );
        setReceipt(match ?? null);
        if (!match) {
          setSaveState({ kind: "error", message: text.unknownReceipt });
        }
      })
      .catch(() => {
        if (active) setSaveState({ kind: "error", message: text.loadError });
      })
      .finally(() => {
        if (active) setLoadingReceipt(false);
      });
    return () => {
      active = false;
    };
  }, [available, requestId, step, text.loadError, text.unknownReceipt]);

  const submit = useCallback(async () => {
    if (!acknowledged) return;
    setSaveState({ kind: "saving" });
    try {
      const record = await requestDsarDelete();
      router.replace(flowPath("status", record.id));
    } catch {
      // Never surface raw infrastructure details on a data-rights screen.
      setSaveState({ kind: "error", message: text.submitError });
    }
  }, [acknowledged, router, text.submitError]);

  const title =
    step === "review"
      ? text.reviewTitle
      : step === "confirm"
        ? text.confirmTitle
        : text.statusTitle;
  const description =
    step === "review"
      ? text.reviewDescription
      : step === "confirm"
        ? text.confirmDescription
        : text.statusDescription;

  if (!available) {
    return (
      <GuidedFlowShell title={text.title} description={text.unavailable} steps={STEPS} currentStep={0}>
        <StepActions
          nextLabel={text.cancel}
          nextType="button"
          onNext={() => router.push("/account/data")}
        />
      </GuidedFlowShell>
    );
  }

  return (
    <GuidedFlowShell
      eyebrow={text.title}
      title={title}
      description={description}
      steps={STEPS}
      currentStep={currentStep}
      saveState={saveState}
    >
      {step === "review" ? (
        <div className="space-y-6">
          <ReviewSection
            title={text.consequenceTitle}
            items={[{ label: text.consequenceTitle, value: text.consequence }]}
          />
          <ReviewSection
            title={text.retentionTitle}
            items={[{ label: text.retentionTitle, value: text.retention }]}
          />
          <StepActions
            nextLabel={text.continue}
            nextType="button"
            onNext={() => router.push(flowPath("confirm"))}
            back={{ label: text.cancel, href: "/account/data" }}
          />
        </div>
      ) : step === "confirm" ? (
        <div className="space-y-6">
          <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]">
            {text.consequence}
          </p>
          <Toggle
            checked={acknowledged}
            onChange={setAcknowledged}
            label={text.confirmation}
          />
          <StepActions
            nextLabel={text.confirm}
            nextType="button"
            onNext={() => void submit()}
            nextDisabled={!acknowledged}
            saving={saveState.kind === "saving"}
            savingLabel={text.sending}
            back={{ label: text.back, href: flowPath("review") }}
          />
        </div>
      ) : loadingReceipt ? (
        <p role="status" className="text-sm text-[var(--text-secondary)]">
          {text.loading}
        </p>
      ) : receipt ? (
        <div className="space-y-6">
          <p role="status" className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm font-medium text-[var(--status-ok-text)]">
            {text.receipt}
          </p>
          <ReviewSection
            title={text.statusTitle}
            items={[
              { label: text.requestId, value: String(receipt.id) },
              {
                label: text.submittedAt,
                value: receipt.created_at
                  ? new Date(receipt.created_at).toLocaleString()
                  : "–",
              },
              {
                label: text.dueAt,
                value: receipt.due_at ? new Date(receipt.due_at).toLocaleDateString() : "–",
              },
            ]}
          />
          <Badge tone="neutral">
            {text.status}: {STATUS_LABELS[receipt.status][uiLanguage]}
          </Badge>
          <StepActions
            nextLabel={text.cancel}
            nextType="button"
            onNext={() => router.push("/account/data")}
          />
        </div>
      ) : (
        <StepActions
          nextLabel={text.cancel}
          nextType="button"
          onNext={() => router.push("/account/data")}
        />
      )}
    </GuidedFlowShell>
  );
}
