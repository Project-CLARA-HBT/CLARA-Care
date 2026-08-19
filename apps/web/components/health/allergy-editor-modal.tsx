"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { InlineError } from "@/components/shared/inline-error";
import { ConflictResolverModal } from "./conflict-resolver-modal";
import {
  apiV2AddAllergy,
  apiV2UpdateAllergy,
  apiV2DeleteAllergy,
  ApiV2ClientError,
  type HealthAllergyDto,
} from "@/lib/api/v2-client";

export interface AllergyEditorModalProps {
  open: boolean;
  onClose: () => void;
  allergy?: HealthAllergyDto | null;
  onSuccess?: () => void;
  locale?: "vi" | "en";
}

export function AllergyEditorModal({
  open,
  onClose,
  allergy,
  onSuccess,
  locale = "vi",
}: AllergyEditorModalProps) {
  const isEn = locale === "en";
  const isEdit = Boolean(allergy?.id);

  const [substance, setSubstance] = useState(allergy?.substance ?? "");
  const [reaction, setReaction] = useState(allergy?.reaction ?? "");
  const [severity, setSeverity] = useState(allergy?.severity ?? "moderate");
  const [verificationState, setVerificationState] = useState(
    allergy?.verification_state ?? "user-reported",
  );
  const [baseVersion, setBaseVersion] = useState<string | number | undefined>(
    allergy?.base_version ?? "v1",
  );

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Conflict state
  const [conflictServerState, setConflictServerState] = useState<Record<string, unknown> | null>(
    null,
  );
  const [changedFields, setChangedFields] = useState<string[]>([]);
  const [showConflictModal, setShowConflictModal] = useState(false);

  useEffect(() => {
    if (allergy) {
      setSubstance(allergy.substance ?? "");
      setReaction(allergy.reaction ?? "");
      setSeverity(allergy.severity ?? "moderate");
      setVerificationState(allergy.verification_state ?? "user-reported");
      setBaseVersion(allergy.base_version ?? "v1");
    } else {
      setSubstance("");
      setReaction("");
      setSeverity("moderate");
      setVerificationState("user-reported");
      setBaseVersion("v1");
    }
  }, [allergy, open]);

  const buildPayload = (overrideVersion?: string | number): Partial<HealthAllergyDto> => {
    return {
      substance: substance.trim(),
      reaction: reaction.trim() || undefined,
      severity: severity as any,
      verification_state: verificationState,
      base_version: overrideVersion ?? baseVersion,
    };
  };

  const handleSubmit = async (overrideVersion?: string | number) => {
    if (!substance.trim()) {
      setErrorMessage(isEn ? "Please enter an allergy substance" : "Vui lòng nhập tên dị ứng / tác nhân");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const payload = buildPayload(overrideVersion);

    try {
      if (isEdit && allergy?.id) {
        await apiV2UpdateAllergy(allergy.id, payload, {
          baseVersion: payload.base_version,
        });
      } else {
        await apiV2AddAllergy({
          substance: substance.trim(),
          reaction: reaction.trim() || null,
          severity: severity as any,
          verification_state: verificationState,
          source_kind: "patient",
        });
      }

      setIsSubmitting(false);
      setShowConflictModal(false);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setIsSubmitting(false);
      if (err instanceof ApiV2ClientError && (err.isConflict || err.isPreconditionFailed)) {
        const currentVer = err.currentVersion ?? "v_server";
        const serverMock: Record<string, unknown> = {
          substance: (err.details as any)?.substance ?? allergy?.substance ?? "Dị ứng đã cập nhật",
          reaction: (err.details as any)?.reaction ?? allergy?.reaction ?? "",
          severity: (err.details as any)?.severity ?? allergy?.severity ?? "severe",
          verification_state: (err.details as any)?.verification_state ?? "confirmed",
          base_version: currentVer,
        };
        setConflictServerState(serverMock);
        setChangedFields(err.changedFields.length ? err.changedFields : ["severity", "reaction"]);
        setBaseVersion(currentVer);
        setShowConflictModal(true);
      } else {
        setErrorMessage(
          err instanceof Error ? err.message : isEn ? "Failed to save allergy" : "Không thể lưu thông tin dị ứng",
        );
      }
    }
  };

  const handleDelete = async () => {
    if (!allergy?.id) return;
    const confirmDelete = window.confirm(
      isEn
        ? "Are you sure you want to remove this allergy record?"
        : "Bạn có chắc chắn muốn xóa mục dị ứng này không?",
    );
    if (!confirmDelete) return;

    setIsDeleting(true);
    setErrorMessage(null);
    try {
      await apiV2DeleteAllergy(allergy.id);
      setIsDeleting(false);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setIsDeleting(false);
      setErrorMessage(
        err instanceof Error ? err.message : isEn ? "Failed to delete allergy" : "Không thể xóa dị ứng",
      );
    }
  };

  return (
    <>
      <Modal
        open={open && !showConflictModal}
        onClose={onClose}
        title={
          isEdit
            ? isEn
              ? "Edit Allergy"
              : "Chỉnh sửa thông tin dị ứng"
            : isEn
              ? "Add Allergy / Intolerance"
              : "Thêm dị ứng / Không dung nạp"
        }
        description={
          isEn
            ? "Record known drug or substance allergies to protect against contraindicated medications."
            : "Ghi nhận dị ứng thuốc hoặc thực phẩm để hệ thống tự động kiểm tra chống chỉ định an toàn."
        }
        size="md"
        closeLabel={isEn ? "Close" : "Đóng"}
        footer={
          <div className="flex w-full flex-wrap items-center justify-between gap-2">
            <div>
              {isEdit && (
                <Button
                  variant="danger"
                  onClick={() => void handleDelete()}
                  loading={isDeleting}
                  disabled={isSubmitting}
                  icon="trash"
                >
                  {isEn ? "Delete" : "Xóa"}
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={onClose} disabled={isSubmitting || isDeleting}>
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button
                variant="primary"
                onClick={() => void handleSubmit()}
                loading={isSubmitting}
                disabled={isDeleting}
                icon="clinical-notes"
              >
                {isEn ? "Save" : "Lưu"}
              </Button>
            </div>
          </div>
        }
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleSubmit();
          }}
          className="space-y-4"
          data-testid="allergy-editor-form"
        >
          {errorMessage && (
            <InlineError
              severity="error"
              title={isEn ? "Operation Failed" : "Thao tác thất bại"}
              message={errorMessage}
              onRetry={() => void handleSubmit()}
            />
          )}

          <Field
            label={isEn ? "Allergy Substance / Trigger *" : "Tác nhân / Tên thuốc / Thực phẩm gây dị ứng *"}
            value={substance}
            onChange={(e) => setSubstance(e.target.value)}
            placeholder={isEn ? "e.g. Penicillin, Aspirin, Seafood..." : "Ví dụ: Penicillin, Paracetamol, Hải sản..."}
            required
            data-testid="field-allergy-substance"
          />

          <Field
            label={isEn ? "Reaction / Symptoms" : "Biểu hiện / Triệu chứng khi dị ứng"}
            value={reaction}
            onChange={(e) => setReaction(e.target.value)}
            placeholder={isEn ? "e.g. Skin rash, swelling, shortness of breath..." : "Ví dụ: Nổi mề đay, sưng phù, khó thở..."}
            data-testid="field-allergy-reaction"
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select
              label={isEn ? "Severity Level" : "Mức độ nghiêm trọng"}
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              data-testid="field-allergy-severity"
            >
              <option value="mild">{isEn ? "Mild (Nhẹ)" : "Nhẹ (Mild)"}</option>
              <option value="moderate">{isEn ? "Moderate (Vừa)" : "Vừa (Moderate)"}</option>
              <option value="severe">{isEn ? "Severe / Anaphylaxis (Nặng / Sốc)" : "Nặng / Nguy kịch (Severe)"}</option>
              <option value="unknown">{isEn ? "Unknown" : "Chưa rõ (Unknown)"}</option>
            </Select>

            <Select
              label={isEn ? "Verification State" : "Trạng thái xác minh"}
              value={verificationState}
              onChange={(e) => setVerificationState(e.target.value)}
              data-testid="field-allergy-verification"
            >
              <option value="user-reported">{isEn ? "Self-reported" : "Tự ghi nhận"}</option>
              <option value="confirmed">{isEn ? "Clinician confirmed" : "Bác sĩ xác nhận"}</option>
              <option value="imported">{isEn ? "Imported from hospital" : "Nhập từ bệnh viện"}</option>
            </Select>
          </div>
        </form>
      </Modal>

      {/* Conflict Resolver Modal */}
      {showConflictModal && conflictServerState && (
        <ConflictResolverModal
          open={showConflictModal}
          onClose={() => setShowConflictModal(false)}
          resourceName={isEn ? "Allergy Record" : "Bản ghi dị ứng"}
          clientDraft={buildPayload()}
          serverState={conflictServerState}
          changedFields={changedFields}
          onKeepClient={() => {
            void handleSubmit(conflictServerState.base_version as string | number);
          }}
          onAcceptServer={() => {
            if (conflictServerState.substance) setSubstance(String(conflictServerState.substance));
            if (conflictServerState.reaction) setReaction(String(conflictServerState.reaction));
            if (conflictServerState.severity) setSeverity(String(conflictServerState.severity));
            if (conflictServerState.verification_state) setVerificationState(String(conflictServerState.verification_state));
            setBaseVersion(conflictServerState.base_version as string | number);
            setShowConflictModal(false);
          }}
          locale={locale}
          isSubmitting={isSubmitting}
        />
      )}
    </>
  );
}

export default AllergyEditorModal;
