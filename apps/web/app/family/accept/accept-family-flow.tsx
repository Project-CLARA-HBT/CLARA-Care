"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { WorkflowLayout, type WorkflowStep } from "@/components/page/workflow-layout";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Icon, type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { ErrorSummary, type GuidedFlowError } from "@/components/guided-flow";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import {
  acceptFamilyInvitation,
  previewFamilyInvitation,
  type FamilyInvitationPreview,
} from "@/lib/visit-family";
import { useUILanguage } from "@/lib/use-ui-language";

type Step = "code" | "review";

function scopeLabel(
  preview: FamilyInvitationPreview,
  language: "vi" | "en",
): string {
  if (preview.object_type === "episode") return t(language, "familyAccept.scope.episode");
  if (preview.object_type === "visit") return t(language, "familyAccept.scope.visit");
  if (preview.object_type === "care_task") return t(language, "familyAccept.scope.task");
  return t(language, "familyAccept.scope.other");
}

function scopeIcon(objectType: string): IconName {
  if (objectType === "episode") return "progress";
  if (objectType === "visit") return "calendar";
  if (objectType === "care_task") return "check";
  return "share";
}

function actionsLabel(preview: FamilyInvitationPreview, language: "vi" | "en"): string {
  const labels = preview.allowed_actions.map((action) => {
    if (action === "view") return t(language, "familyAccept.action.view");
    if (action === "add_observation") return t(language, "familyAccept.action.observe");
    if (action === "complete_task") return t(language, "familyAccept.action.complete");
    return t(language, "familyAccept.action.other");
  });
  return labels.length ? labels.join(", ") : t(language, "familyAccept.action.other");
}

export default function AcceptFamilyFlow() {
  const router = useRouter();
  const language = useUILanguage();
  const isEn = language === "en";
  const tokenRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<Step>("code");
  const [token, setToken] = useState("");
  const [preview, setPreview] = useState<FamilyInvitationPreview | null>(null);
  const [validationErrors, setValidationErrors] = useState<GuidedFlowError[]>([]);
  const [saveState, setSaveState] = useState<
    { kind: "idle" } | { kind: "saving"; message?: string } | { kind: "saved"; message?: string } | { kind: "error"; message: string }
  >({ kind: "idle" });
  const saving = saveState.kind === "saving";

  const steps: WorkflowStep[] = [
    { id: "code", label: t(language, "familyAccept.step.code") },
    { id: "review", label: t(language, "familyAccept.step.review") },
  ];

  const previewInvitation = async () => {
    const candidate = token.trim();
    if (candidate.length < 32) {
      setValidationErrors([
        {
          id: "family-accept-token",
          fieldId: "family-accept-token",
          fieldLabel: t(language, "familyAccept.field.code"),
          message: t(language, "familyAccept.validation.code"),
        },
      ]);
      tokenRef.current?.focus();
      return;
    }
    setValidationErrors([]);
    setSaveState({ kind: "saving", message: t(language, "familyAccept.previewing") });
    try {
      const next = await previewFamilyInvitation(candidate);
      setPreview(next);
      setStep("review");
      setSaveState({ kind: "idle" });
    } catch {
      setPreview(null);
      setSaveState({ kind: "error", message: t(language, "familyAccept.previewFailed") });
    }
  };

  const accept = async () => {
    if (!preview) {
      setStep("code");
      return;
    }
    setSaveState({ kind: "saving", message: t(language, "familyAccept.accepting") });
    try {
      await acceptFamilyInvitation(token.trim());
      setSaveState({ kind: "saved", message: t(language, "familyAccept.accepted") });
      router.replace("/family");
      router.refresh();
    } catch {
      setSaveState({ kind: "error", message: t(language, "familyAccept.acceptFailed") });
    }
  };

  const handlePaste = async () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      try {
        const text = await navigator.clipboard.readText();
        if (text) {
          setToken(text.trim());
        }
      } catch {
        // clipboard permission might be denied
      }
    }
  };

  const asideContent = (
    <div className="space-y-4">
      <div className="rounded-[var(--radius-xl)] border border-[color:var(--brand-300)]/60 bg-[var(--brand-50)]/20 p-5 space-y-3">
        <div className="flex items-center gap-2 text-[var(--text-brand)]">
          <Icon name="check" size="1.25rem" />
          <h3 className="font-bold text-sm text-[var(--text-primary)]">
            {isEn ? "Caregiver Safety & Privacy" : "Minh bạch & An toàn"}
          </h3>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {t(language, "familyAccept.safetyNote")}
        </p>
        <ul className="text-[11px] text-[var(--text-muted)] space-y-2 pt-2 border-t border-[color:var(--shell-border)]/60">
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Zero AI reasoning (CoT) is ever exposed" : "Không bao giờ để lộ chuỗi tư duy suy luận của AI"}</span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Access is strictly bounded to the authorized scope" : "Chỉ truy cập đúng nội dung được người thân cấp phép"}</span>
          </li>
          <li className="flex items-start gap-2">
            <Icon name="check" size="0.9rem" className="text-[var(--status-ok-text)] shrink-0 mt-0.5" />
            <span>{isEn ? "Audit logged and can be revoked at any moment" : "Ghi nhận nhật ký kiểm toán và có thể thu hồi bất cứ lúc nào"}</span>
          </li>
        </ul>
      </div>

      <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-xs text-[var(--text-secondary)] space-y-1.5">
        <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
          <Icon name="check" size="1rem" className="text-[var(--text-brand)]" />
          <span>{isEn ? "Preview before accepting" : "Xem trước trước khi xác nhận"}</span>
        </div>
        <p className="text-[11px] leading-relaxed">
          {isEn
            ? "Entering a code lets you preview the exact permissions and time window before accepting."
            : "Nhập mã cho phép bạn xem trước chính xác quyền hạn và thời hạn trước khi đồng ý nhận."}
        </p>
      </div>
    </div>
  );

  return (
    <WorkflowLayout
      workspace="personal"
      title={step === "code" ? t(language, "familyAccept.title.code") : t(language, "familyAccept.title.review")}
      subtitle={step === "code" ? t(language, "familyAccept.description.code") : t(language, "familyAccept.description.review")}
      eyebrow={t(language, "familyAccept.eyebrow")}
      steps={steps}
      currentStep={step === "code" ? 0 : 1}
      saveState={saveState}
      aside={asideContent}
      backAction={{
        label: t(language, "familyAccept.cancel"),
        href: "/family",
      }}
    >
      <div className="space-y-6" data-testid="accept-redemption-canvas">
        <ErrorSummary errors={validationErrors} />

        {/* STEP 1: Code Input Canvas */}
        {step === "code" ? (
          <div className="space-y-5">
            <div className="space-y-2">
              <div className="flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => void handlePaste()}
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                >
                  <Icon name="upload" size="0.85rem" />
                  <span>{isEn ? "Paste from clipboard" : "Dán từ bộ nhớ tạm"}</span>
                </button>
              </div>

              <Field
                ref={tokenRef}
                id="family-accept-token"
                label={t(language, "familyAccept.field.code")}
                autoComplete="off"
                autoCapitalize="none"
                spellCheck={false}
                placeholder={isEn ? "Paste or enter 32+ character invitation code..." : "Dán hoặc nhập mã mời từ 32 ký tự trở lên..."}
                value={token}
                onChange={(event) => setToken(event.target.value)}
                aria-invalid={validationErrors.length > 0 || undefined}
                aria-describedby={
                  validationErrors.length ? "family-accept-token-error" : undefined
                }
                className="font-mono text-xs sm:text-sm"
              />
              {validationErrors.length ? (
                <p
                  id="family-accept-token-error"
                  className="text-xs text-[var(--status-danger-text)] font-semibold"
                >
                  {validationErrors[0].message}
                </p>
              ) : null}
            </div>

            <div className="rounded-[var(--radius-xl)] bg-[var(--surface-muted)]/50 border border-[color:var(--shell-border)]/60 p-4 text-xs text-[var(--text-secondary)] space-y-1.5">
              <p className="font-semibold text-[var(--text-primary)]">
                {isEn ? "Where do I find this code?" : "Lấy mã mời ở đâu?"}
              </p>
              <p className="text-[11px] leading-relaxed">
                {isEn
                  ? "The patient or family member who invited you generated a one-time invitation token. Ask them to share it with you."
                  : "Người thân hoặc bệnh nhân đã tạo một mã mời bảo mật. Hãy liên hệ với người thân để nhận mã này."}
              </p>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                as="link"
                href="/family"
              >
                {t(language, "familyAccept.cancel")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => void previewInvitation()}
                loading={saving}
                disabled={saving || token.trim().length < 10}
                icon="arrow-right"
              >
                {saving ? t(language, "familyAccept.previewing") : t(language, "familyAccept.preview")}
              </Button>
            </div>
          </div>
        ) : null}

        {/* STEP 2: Review Preview & Accept */}
        {step === "review" && preview ? (
          <div className="space-y-6">
            <div className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-300)]/60 bg-[var(--surface-panel)] p-5 space-y-4 shadow-sm">
              <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name={scopeIcon(preview.object_type)} size="1.25rem" />
                  <h3 className="font-bold text-sm text-[var(--text-primary)]">
                    {t(language, "familyAccept.review.title")}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setStep("code")}
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline"
                >
                  {t(language, "familyAccept.review.edit")}
                </button>
              </div>

              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyAccept.field.scope")}
                  </dt>
                  <dd className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-50)] text-[var(--brand-700)] px-2.5 py-1 font-bold mt-1 border border-[color:var(--brand-200)]">
                    <Icon name={scopeIcon(preview.object_type)} size="0.85rem" />
                    <span>{scopeLabel(preview, language)}</span>
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyAccept.field.purpose")}
                  </dt>
                  <dd className="font-bold text-[var(--text-primary)] mt-1">
                    {preview.purpose === "visit_support"
                      ? t(language, "familyAccept.purpose.visit")
                      : t(language, "familyAccept.purpose.care")}
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyAccept.field.actions")}
                  </dt>
                  <dd className="mt-1">
                    <span className="inline-flex items-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-medium text-[var(--text-primary)] border border-[color:var(--shell-border)]/60">
                      {actionsLabel(preview, language)}
                    </span>
                  </dd>
                </div>

                <div>
                  <dt className="text-[11px] text-[var(--text-secondary)] font-semibold">
                    {t(language, "familyAccept.field.expiry")}
                  </dt>
                  <dd className="font-medium text-[var(--text-primary)] mt-1">
                    {formatLocaleDate(language, preview.expires_at, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-[var(--radius-xl)] bg-[var(--surface-muted)]/50 border border-[color:var(--shell-border)]/60 p-4 text-xs text-[var(--text-secondary)]">
              <p>
                {isEn
                  ? "By accepting, you agree to access this medical information strictly for care coordination or visit support purposes."
                  : "Bằng việc chấp nhận, bạn đồng ý sử dụng thông tin y tế này thuần túy vì mục đích phối hợp chăm sóc hoặc hỗ trợ khám bệnh."}
              </p>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setStep("code")}
                disabled={saving}
                icon="arrow-left"
              >
                {t(language, "familyAccept.back")}
              </Button>
              <Button
                type="button"
                variant="primary"
                onClick={() => void accept()}
                loading={saving}
                disabled={saving}
                icon="check"
              >
                {saving ? t(language, "familyAccept.accepting") : t(language, "familyAccept.accept")}
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </WorkflowLayout>
  );
}
