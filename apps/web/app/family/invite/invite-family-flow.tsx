"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { WorkflowLayout, type WorkflowStep } from "@/components/page/workflow-layout";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { ErrorSummary, type GuidedFlowError } from "@/components/guided-flow";
import { t } from "@/lib/i18n/catalog";
import { createFamilyInvitation, getFamilyShareOptions } from "@/lib/visit-family";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "recipient" | "scope" | "purpose" | "review";
type ObjectType = "episode" | "visit" | "care_task";
type Purpose = "care_coordination" | "visit_support";

type ShareableItems = Record<ObjectType, Array<{ id: string; label: string }>>;

type InviteDraft = {
  email: string;
  objectType: ObjectType;
  objectId: string;
  purpose: Purpose;
};

const EMPTY_ITEMS: ShareableItems = { episode: [], visit: [], care_task: [] };
const EMPTY_DRAFT: InviteDraft = {
  email: "",
  objectType: "episode",
  objectId: "",
  purpose: "care_coordination",
};

function expiryIso(): string {
  return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
}

export default function InviteFamilyFlow() {
  const language = useUILanguage();
  const isEn = language === "en";
  const emailRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("recipient");
  const [draft, setDraft] = useState<InviteDraft>(EMPTY_DRAFT);
  const [items, setItems] = useState<ShareableItems>(EMPTY_ITEMS);
  const [loadingItems, setLoadingItems] = useState(true);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<
    { kind: "idle" } | { kind: "saving"; message?: string } | { kind: "saved"; message?: string } | { kind: "error"; message: string }
  >({ kind: "idle" });
  const [createdToken, setCreatedToken] = useState("");
  const [copiedToken, setCopiedToken] = useState(false);

  const steps: WorkflowStep[] = [
    { id: "recipient", label: t(language, "familyInvite.step.recipient") },
    { id: "scope", label: t(language, "familyInvite.step.scope") },
    { id: "purpose", label: t(language, "familyInvite.step.purpose") },
    { id: "review", label: t(language, "familyInvite.step.review") },
  ];

  const titleByStep: Record<Step, string> = {
    recipient: t(language, "familyInvite.title.recipient"),
    scope: t(language, "familyInvite.title.scope"),
    purpose: t(language, "familyInvite.title.purpose"),
    review: t(language, "familyInvite.title.review"),
  };

  const descriptionByStep: Record<Step, string> = {
    recipient: t(language, "familyInvite.description.recipient"),
    scope: t(language, "familyInvite.description.scope"),
    purpose: t(language, "familyInvite.description.purpose"),
    review: t(language, "familyInvite.description.review"),
  };

  const stepIndex = steps.findIndex((candidate) => candidate.id === step);
  const back = steps[stepIndex - 1]?.id as Step | undefined;
  const saving = saveState.kind === "saving";
  const selectedItem = items[draft.objectType]?.find((item) => item.id === draft.objectId);

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoadingItems(true);
      try {
        const options = await getFamilyShareOptions();
        if (!active) return;
        setItems({
          episode: options.episodes ?? [],
          visit: options.visits ?? [],
          care_task: options.care_tasks ?? [],
        });
      } catch {
        if (active) {
          setSaveState({ kind: "error", message: t(language, "familyInvite.loadFailed") });
        }
      } finally {
        if (active) setLoadingItems(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [language]);

  const setObjectType = (objectType: ObjectType) => {
    setDraft((current) => ({ ...current, objectType, objectId: "" }));
  };

  const advance = () => {
    if (step === "recipient") {
      if (!draft.email.trim() || !/^\S+@\S+\.\S+$/.test(draft.email.trim())) {
        setValidationErrors([
          {
            id: "family-invite-email",
            fieldId: "family-invite-email",
            fieldLabel: t(language, "familyInvite.field.email"),
            message: t(language, "familyInvite.validation.email"),
          },
        ]);
        emailRef.current?.focus();
        return;
      }
    }
    if (step === "scope" && (!draft.objectId || !selectedItem)) {
      setValidationErrors([
        {
          id: "family-invite-scope",
          fieldId: "family-invite-item",
          fieldLabel: t(language, "familyInvite.field.item"),
          message: t(language, "familyInvite.validation.scope"),
        },
      ]);
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "idle" });
    const next = steps[stepIndex + 1]?.id;
    if (next) setStep(next as Step);
  };

  const save = async () => {
    if (!selectedItem) {
      setStep("scope");
      setValidationErrors([
        {
          id: "family-invite-scope",
          fieldId: "family-invite-item",
          fieldLabel: t(language, "familyInvite.field.item"),
          message: t(language, "familyInvite.validation.scope"),
        },
      ]);
      return;
    }
    setSaveState({ kind: "saving", message: t(language, "familyInvite.saving") });
    try {
      const allowedActions =
        draft.objectType === "episode"
          ? ["view", "add_observation"]
          : draft.objectType === "care_task"
            ? ["view", "complete_task"]
            : ["view"];

      const result = await createFamilyInvitation({
        recipient_email: draft.email.trim(),
        scope: {
          object_type: draft.objectType,
          object_id: selectedItem.id,
          allowed_actions: allowedActions,
        },
        purpose: draft.purpose,
        expires_at: expiryIso(),
      });
      setCreatedToken(result.token);
      setSaveState({ kind: "saved", message: t(language, "familyInvite.saved") });
    } catch {
      setSaveState({ kind: "error", message: t(language, "familyInvite.saveFailed") });
    }
  };

  const handleCopyToken = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard && createdToken) {
      navigator.clipboard.writeText(createdToken);
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  const getScopeCategoryLabel = (type: ObjectType) => {
    if (type === "episode") return isEn ? "Health Journey (Episode)" : t(language, "familyInvite.scope.episode");
    if (type === "visit") return isEn ? "Clinical Visit" : t(language, "familyInvite.scope.visit");
    return isEn ? "Delegated Care Task" : "Nhiệm vụ chăm sóc";
  };

  const getScopeCategoryIcon = (type: ObjectType): IconName => {
    if (type === "episode") return "progress";
    if (type === "visit") return "calendar";
    return "check";
  };

  const categoryOptions: Array<{
    type: ObjectType;
    icon: IconName;
    title: string;
    description: string;
    badgeText: string;
  }> = [
    {
      type: "episode",
      icon: "progress",
      title: isEn ? "Health Journey (Episode)" : "Hành trình sức khỏe",
      description: isEn
        ? "Share chronic condition timeline, doctor progress notes, and ongoing care plan."
        : "Chia sẻ diễn tiến theo dõi, ghi chú bác sĩ và phác đồ điều trị lâu dài.",
      badgeText: isEn ? "View + Observations" : "Xem + Ghi nhận",
    },
    {
      type: "visit",
      icon: "calendar",
      title: isEn ? "Clinical Visit" : "Buổi khám bệnh",
      description: isEn
        ? "Share consultation summary, doctor notes, and prescriptions for a single visit."
        : "Chia sẻ tóm tắt buổi khám, dặn dò của bác sĩ và đơn thuốc.",
      badgeText: isEn ? "View Only" : "Chỉ xem",
    },
    {
      type: "care_task",
      icon: "check",
      title: isEn ? "Delegated Care Task" : "Nhiệm vụ chăm sóc",
      description: isEn
        ? "Delegate medication reminders, measurement logging, or daily adherence checks."
        : "Ủy thác nhắc uống thuốc, ghi nhận chỉ số hoặc hỗ trợ tuân thủ.",
      badgeText: isEn ? "View + Complete" : "Xem + Hoàn thành",
    },
  ];

  const asideContent = (
    <div className="space-y-4">
      <div className="rounded-[var(--radius-xl)] border border-[color:var(--brand-300)]/60 bg-[var(--brand-50)]/20 p-5 space-y-3">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="check" size="1.25rem" />
          <h3 className="font-bold text-sm text-[var(--text-primary)]">
            {isEn ? "Strict Data Protections" : "Bảo vệ quyền riêng tư"}
          </h3>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {t(language, "familyInvite.safetyNote")}
        </p>
        <ul className="text-[11px] text-[var(--text-muted)] space-y-2 pt-2 border-t border-[color:var(--shell-border)]/60">
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Zero AI reasoning (CoT) is ever shared" : "Tuyệt đối không để lộ chuỗi suy luận nội bộ AI"}</span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Access is strictly bounded to chosen category" : "Chỉ truy cập đúng danh mục được phê duyệt"}</span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Self-expires in 7 days or instant 1-click revoke" : "Hết hạn sau 7 ngày hoặc thu hồi tức thì 1 chạm"}</span>
          </li>
        </ul>
      </div>

      <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-xs text-[var(--text-secondary)] space-y-2">
        <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
          <Icon name="warning" size="1rem" className="text-[var(--text-brand)]" />
          <span>{isEn ? "One-time invitation code" : "Mã mời dùng một lần"}</span>
        </div>
        <p className="text-[11px] leading-relaxed">
          {isEn
            ? "When created, a secure token will be generated. You can share it via Zalo or messaging directly with your caregiver."
            : "Sau khi tạo, hệ thống sinh mã ủy quyền bảo mật. Bạn có thể gửi mã qua Zalo hoặc tin nhắn cho người thân."}
        </p>
      </div>
    </div>
  );

  if (createdToken) {
    return (
      <WorkflowLayout
        workspace="personal"
        title={t(language, "familyInvite.created.title")}
        subtitle={t(language, "familyInvite.created.description")}
        eyebrow={t(language, "familyInvite.eyebrow")}
        steps={steps}
        currentStep={steps.length - 1}
        saveState={saveState}
        aside={asideContent}
        backAction={{
          label: isEn ? "Back to Family Hub" : "Quay lại Vòng tròn gia đình",
          href: "/family",
        }}
      >
        <div className="space-y-6" data-testid="invite-created-view">
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-6 space-y-4 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-[var(--surface-panel)] flex items-center justify-center text-[var(--status-ok-text)] shrink-0 shadow-xs">
                <Icon name="check" size="1.4rem" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-[var(--status-ok-text)]">
                  {t(language, "familyInvite.created.notice")}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  {isEn
                    ? "Share this secure authorization token with your recipient:"
                    : "Gửi mã ủy quyền bảo mật này cho người nhận:"}
                </p>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center gap-2 pt-2">
              <code className="block flex-1 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-xs sm:text-sm font-mono break-all text-[var(--text-primary)] select-all">
                {createdToken}
              </code>
              <Button
                type="button"
                variant="primary"
                size="md"
                onClick={handleCopyToken}
                icon={copiedToken ? "check" : "share"}
                className="shrink-0"
              >
                {copiedToken ? (isEn ? "Copied!" : "Đã sao chép") : isEn ? "Copy Code" : "Sao chép mã"}
              </Button>
            </div>
          </div>

          <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-4 text-xs text-[var(--text-secondary)] space-y-1.5">
            <p className="font-semibold text-[var(--text-primary)]">
              {isEn ? "Next Steps:" : "Các bước tiếp theo:"}
            </p>
            <p>
              {isEn
                ? "1. Send the invitation code to your family member or doctor."
                : "1. Gửi mã mời này cho người thân hoặc bác sĩ."}
            </p>
            <p>
              {isEn
                ? "2. They should open the Family Hub, click 'Accept Invitation', and enter this code."
                : "2. Người nhận truy cập mục 'Vòng tròn gia đình', bấm 'Xem mã mời' và nhập mã này."}
            </p>
          </div>

          <div className="flex items-center justify-end pt-4 border-t border-[color:var(--shell-border)]/60">
            <Button
              type="button"
              variant="secondary"
              as="link"
              href="/family"
              icon="arrow-left"
            >
              {t(language, "familyInvite.created.done")}
            </Button>
          </div>
        </div>
      </WorkflowLayout>
    );
  }

  return (
    <WorkflowLayout
      workspace="personal"
      title={titleByStep[step]}
      subtitle={descriptionByStep[step]}
      eyebrow={t(language, "familyInvite.eyebrow")}
      steps={steps}
      currentStep={stepIndex}
      saveState={saveState}
      aside={asideContent}
      backAction={{
        label: t(language, "familyInvite.cancel"),
        href: "/family",
      }}
    >
      <div className="space-y-6" data-testid="invite-wizard-step">
        <ErrorSummary errors={validationErrors} />

        {/* STEP 1: Recipient */}
        {step === "recipient" ? (
          <div className="space-y-5">
            <Field
              ref={emailRef}
              id="family-invite-email"
              label={t(language, "familyInvite.field.email")}
              type="email"
              autoComplete="email"
              autoFocus
              placeholder="e.g. bacsi.nam@gmail.com"
              value={draft.email}
              onChange={(event) =>
                setDraft((current) => ({ ...current, email: event.target.value }))
              }
              aria-invalid={validationErrors.length > 0 || undefined}
              aria-describedby={
                validationErrors.length ? "family-invite-email-error" : undefined
              }
            />
            {validationErrors.length ? (
              <p
                id="family-invite-email-error"
                className="text-xs text-[var(--status-danger-text)] font-semibold"
              >
                {validationErrors[0].message}
              </p>
            ) : null}

            <div className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-secondary)]">
              <p>
                {isEn
                  ? "We only use this email to associate and verify the invitation recipient."
                  : "Email này được dùng để xác định và xác thực danh tính người nhận lời mời."}
              </p>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                as="link"
                href="/family"
              >
                {t(language, "familyInvite.cancel")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={advance}
                icon="arrow-right"
              >
                {isEn ? "Continue" : "Tiếp tục"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* STEP 2: Category Scope Selection */}
        {step === "scope" ? (
          <div className="space-y-6">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-2.5">
                {isEn ? "1. Select Category Scope" : "1. Chọn danh mục chia sẻ"}
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {categoryOptions.map((opt) => {
                  const isSelected = draft.objectType === opt.type;
                  return (
                    <button
                      key={opt.type}
                      type="button"
                      onClick={() => setObjectType(opt.type)}
                      className={`flex flex-col justify-between p-4 rounded-[var(--radius-xl)] border text-left transition-all ${
                        isSelected
                          ? "border-[color:var(--brand-500)] bg-[var(--brand-50)]/20 shadow-xs ring-1 ring-[var(--brand-400)]"
                          : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--shell-border-strong)]"
                      }`}
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div
                            className={`w-9 h-9 rounded-[var(--radius-lg)] flex items-center justify-center ${
                              isSelected
                                ? "bg-[var(--brand-500)] text-white"
                                : "bg-[var(--surface-muted)] text-[var(--text-brand)]"
                            }`}
                          >
                            <Icon name={opt.icon} size="1.2rem" />
                          </div>
                          <Badge tone={isSelected ? "brand" : "neutral"}>
                            {opt.badgeText}
                          </Badge>
                        </div>
                        <div>
                          <h4 className="font-bold text-sm text-[var(--text-primary)]">
                            {opt.title}
                          </h4>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-1 line-clamp-2">
                            {opt.description}
                          </p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <label
                htmlFor="family-invite-item"
                className="block text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-2.5"
              >
                {isEn ? "2. Choose Specific Item" : "2. Chọn nội dung cụ thể"}
              </label>
              <Select
                id="family-invite-item"
                label={t(language, "familyInvite.field.item")}
                value={draft.objectId}
                onChange={(event) =>
                  setDraft((current) => ({ ...current, objectId: event.target.value }))
                }
                disabled={loadingItems}
                aria-invalid={validationErrors.length > 0 || undefined}
              >
                <option value="">
                  {loadingItems
                    ? t(language, "familyInvite.loading")
                    : t(language, "familyInvite.chooseItem")}
                </option>
                {items[draft.objectType]?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </Select>

              {!loadingItems && (!items[draft.objectType] || items[draft.objectType].length === 0) ? (
                <p className="mt-2 text-xs leading-5 text-[var(--status-warn-text)] bg-[var(--status-warn-bg)] p-2.5 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)]">
                  {t(language, "familyInvite.noItems")}
                </p>
              ) : null}
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep(back ?? "recipient")}
                icon="arrow-left"
              >
                {t(language, "familyInvite.back")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={advance}
                disabled={loadingItems || !items[draft.objectType]?.length || !draft.objectId}
                icon="arrow-right"
              >
                {isEn ? "Continue" : "Tiếp tục"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* STEP 3: Purpose & Permissions */}
        {step === "purpose" ? (
          <div className="space-y-6">
            <div>
              <label
                htmlFor="family-invite-purpose"
                className="block text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)] mb-2.5"
              >
                {t(language, "familyInvite.field.purpose")}
              </label>
              <Select
                id="family-invite-purpose"
                label={t(language, "familyInvite.field.purpose")}
                value={draft.purpose}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    purpose: event.target.value as Purpose,
                  }))
                }
              >
                <option value="care_coordination">
                  {t(language, "familyInvite.purpose.care")}
                </option>
                <option value="visit_support">
                  {t(language, "familyInvite.purpose.visit")}
                </option>
              </Select>
            </div>

            <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 space-y-3">
              <h4 className="font-bold text-xs text-[var(--text-primary)]">
                {isEn ? "Permissions summary for this grant:" : "Tóm tắt quyền hạn được cấp:"}
              </h4>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1 text-[var(--text-primary)] border border-[color:var(--shell-border)]/60 font-medium">
                  <Icon name="check" size="0.85rem" className="text-[var(--status-ok-text)]" />
                  <span>{isEn ? "Read scoped data" : "Xem dữ liệu được phân quyền"}</span>
                </span>
                {draft.objectType === "episode" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1 text-[var(--text-primary)] border border-[color:var(--shell-border)]/60 font-medium">
                    <Icon name="check" size="0.85rem" className="text-[var(--status-ok-text)]" />
                    <span>{isEn ? "Add caregiver observations" : "Thêm ghi nhận hỗ trợ"}</span>
                  </span>
                ) : null}
                {draft.objectType === "care_task" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1 text-[var(--text-primary)] border border-[color:var(--shell-border)]/60 font-medium">
                    <Icon name="check" size="0.85rem" className="text-[var(--status-ok-text)]" />
                    <span>{isEn ? "Acknowledge / complete tasks" : "Xác nhận hoàn thành nhiệm vụ"}</span>
                  </span>
                ) : null}
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep(back ?? "scope")}
                icon="arrow-left"
              >
                {t(language, "familyInvite.back")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={advance}
                icon="arrow-right"
              >
                {isEn ? "Review & Confirm" : "Kiểm tra thông tin"}
              </Button>
            </div>
          </div>
        ) : null}

        {/* STEP 4: Review & Create */}
        {step === "review" ? (
          <div className="space-y-6">
            <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
              <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {t(language, "familyInvite.review.title")}
                </h3>
                <button
                  type="button"
                  onClick={() => setStep("recipient")}
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {t(language, "familyInvite.review.edit")}
                </button>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyInvite.field.email")}
                  </dt>
                  <dd className="font-bold text-[var(--text-primary)] mt-0.5">
                    {draft.email.trim()}
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {isEn ? "Category Scope" : "Danh mục phân quyền"}
                  </dt>
                  <dd className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-50)] text-[var(--brand-700)] px-2 py-0.5 font-semibold mt-0.5 border border-[color:var(--brand-200)]">
                    <Icon name={getScopeCategoryIcon(draft.objectType)} size="0.85rem" />
                    <span>{getScopeCategoryLabel(draft.objectType)}</span>
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyInvite.field.item")}
                  </dt>
                  <dd className="font-bold text-[var(--text-primary)] mt-0.5">
                    {selectedItem?.label ?? t(language, "familyInvite.review.empty")}
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyInvite.field.purpose")}
                  </dt>
                  <dd className="font-bold text-[var(--text-primary)] mt-0.5">
                    {draft.purpose === "care_coordination"
                      ? t(language, "familyInvite.purpose.care")
                      : t(language, "familyInvite.purpose.visit")}
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyInvite.review.expiry")}
                  </dt>
                  <dd className="font-medium text-[var(--text-primary)] mt-0.5">
                    {t(language, "familyInvite.review.sevenDays")}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep(back ?? "purpose")}
                disabled={saving}
                icon="arrow-left"
              >
                {t(language, "familyInvite.back")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => void save()}
                loading={saving}
                disabled={saving}
                icon="check"
              >
                {saving ? t(language, "familyInvite.saving") : t(language, "familyInvite.create")}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </WorkflowLayout>
  );
}
