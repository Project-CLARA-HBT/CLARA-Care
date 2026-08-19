"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { InlineError } from "@/components/shared/inline-error";
import { ConflictResolverModal } from "./conflict-resolver-modal";
import {
  apiV2AddCondition,
  apiV2UpdateCondition,
  apiV2DeleteCondition,
  ApiV2ClientError,
  type HealthConditionDto,
} from "@/lib/api/v2-client";

export interface ConditionEditorModalProps {
  open: boolean;
  onClose: () => void;
  condition?: HealthConditionDto | null;
  onSuccess?: () => void;
  locale?: "vi" | "en";
}

export function ConditionEditorModal({
  open,
  onClose,
  condition,
  onSuccess,
  locale = "vi",
}: ConditionEditorModalProps) {
  const isEn = locale === "en";
  const isEdit = Boolean(condition?.id);

  const [name, setName] = useState(condition?.name ?? "");
  const [clinicalStatus, setClinicalStatus] = useState(
    condition?.clinical_status ?? "active",
  );
  const [verificationStatus, setVerificationStatus] = useState(
    condition?.verification_status ?? "confirmed",
  );
  const [onsetDate, setOnsetDate] = useState(condition?.onset_date ?? "");
  const [notes, setNotes] = useState(condition?.notes ?? "");
  const [baseVersion, setBaseVersion] = useState<string | number | undefined>(
    condition?.base_version ?? "v1",
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
    if (condition) {
      setName(condition.name ?? "");
      setClinicalStatus(condition.clinical_status ?? "active");
      setVerificationStatus(condition.verification_status ?? "confirmed");
      setOnsetDate(condition.onset_date ?? "");
      setNotes(condition.notes ?? "");
      setBaseVersion(condition.base_version ?? "v1");
    } else {
      setName("");
      setClinicalStatus("active");
      setVerificationStatus("confirmed");
      setOnsetDate("");
      setNotes("");
      setBaseVersion("v1");
    }
  }, [condition, open]);

  const buildPayload = (overrideVersion?: string | number): Partial<HealthConditionDto> => {
    return {
      name: name.trim(),
      clinical_status: clinicalStatus as any,
      verification_status: verificationStatus as any,
      onset_date: onsetDate || undefined,
      notes: notes.trim() || undefined,
      base_version: overrideVersion ?? baseVersion,
    };
  };

  const handleSubmit = async (overrideVersion?: string | number) => {
    if (!name.trim()) {
      setErrorMessage(isEn ? "Please enter a condition name" : "Vui lòng nhập tên bệnh nền / tình trạng sức khỏe");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const payload = buildPayload(overrideVersion);

    try {
      if (isEdit && condition?.id) {
        await apiV2UpdateCondition(condition.id, payload, {
          baseVersion: payload.base_version,
        });
      } else {
        await apiV2AddCondition({
          name: name.trim(),
          clinical_status: clinicalStatus as any,
          verification_status: verificationStatus as any,
          onset_date: onsetDate || null,
          notes: notes.trim() || null,
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
          name: (err.details as any)?.name ?? condition?.name ?? "Bệnh nền đã cập nhật",
          clinical_status: (err.details as any)?.clinical_status ?? condition?.clinical_status ?? "resolved",
          verification_status: (err.details as any)?.verification_status ?? "confirmed",
          onset_date: (err.details as any)?.onset_date ?? condition?.onset_date ?? "",
          notes: (err.details as any)?.notes ?? condition?.notes ?? "",
          base_version: currentVer,
        };
        setConflictServerState(serverMock);
        setChangedFields(err.changedFields.length ? err.changedFields : ["clinical_status", "notes"]);
        setBaseVersion(currentVer);
        setShowConflictModal(true);
      } else {
        setErrorMessage(
          err instanceof Error ? err.message : isEn ? "Failed to save condition" : "Không thể lưu tình trạng sức khỏe",
        );
      }
    }
  };

  const handleDelete = async () => {
    if (!condition?.id) return;
    const confirmDelete = window.confirm(
      isEn
        ? "Are you sure you want to delete this condition record?"
        : "Bạn có chắc chắn muốn xóa bản ghi bệnh nền này không?",
    );
    if (!confirmDelete) return;

    setIsDeleting(true);
    setErrorMessage(null);
    try {
      await apiV2DeleteCondition(condition.id);
      setIsDeleting(false);
      if (onSuccess) onSuccess();
      onClose();
    } catch (err) {
      setIsDeleting(false);
      setErrorMessage(
        err instanceof Error ? err.message : isEn ? "Failed to delete condition" : "Không thể xóa tình trạng sức khỏe",
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
              ? "Edit Health Condition"
              : "Chỉnh sửa bệnh nền / tình trạng"
            : isEn
              ? "Add Health Condition"
              : "Thêm bệnh nền / Tình trạng sức khỏe"
        }
        description={
          isEn
            ? "Manage active diagnoses and medical conditions for personalized health guidance."
            : "Quản lý chẩn đoán và bệnh lý đang theo dõi để nhận hướng dẫn y tế an toàn và phù hợp."
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
          data-testid="condition-editor-form"
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
            label={isEn ? "Condition / Diagnosis Name *" : "Tên bệnh lý / Chẩn đoán *"}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={isEn ? "e.g. Hypertension, Type 2 Diabetes, Asthma..." : "Ví dụ: Tăng huyết áp, Đái tháo đường type 2, Hen suyễn..."}
            required
            data-testid="field-condition-name"
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select
              label={isEn ? "Clinical Status" : "Trạng thái tiến triển"}
              value={clinicalStatus}
              onChange={(e) => setClinicalStatus(e.target.value)}
              data-testid="field-condition-status"
            >
              <option value="active">{isEn ? "Active (Đang điều trị / theo dõi)" : "Đang theo dõi / điều trị (Active)"}</option>
              <option value="resolved">{isEn ? "Resolved (Đã khỏi / ổn định)" : "Đã khỏi / Ổn định (Resolved)"}</option>
              <option value="inactive">{isEn ? "Inactive (Tạm ngưng)" : "Tạm ngưng (Inactive)"}</option>
              <option value="remission">{isEn ? "Remission (Thuyên giảm)" : "Thuyên giảm (Remission)"}</option>
            </Select>

            <Select
              label={isEn ? "Verification Status" : "Mức độ xác minh"}
              value={verificationStatus}
              onChange={(e) => setVerificationStatus(e.target.value)}
              data-testid="field-condition-verification"
            >
              <option value="confirmed">{isEn ? "Clinician Confirmed" : "Bác sĩ xác nhận (Confirmed)"}</option>
              <option value="provisional">{isEn ? "Provisional / Suspected" : "Nghi ngờ / Theo dõi (Provisional)"}</option>
              <option value="unconfirmed">{isEn ? "Self-Reported" : "Tự ghi nhận (Unconfirmed)"}</option>
            </Select>
          </div>

          <Field
            type="date"
            label={isEn ? "Onset / Diagnosis Date" : "Ngày phát hiện / Ngày chẩn đoán"}
            value={onsetDate}
            onChange={(e) => setOnsetDate(e.target.value)}
            data-testid="field-condition-onset"
          />

          <Textarea
            label={isEn ? "Clinical Notes / Advice" : "Ghi chú & lời dặn của bác sĩ"}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder={isEn ? "e.g. Follow-up every 3 months, monitor BP daily..." : "Ví dụ: Tái khám định kỳ 3 tháng, đo huyết áp mỗi sáng..."}
            data-testid="field-condition-notes"
          />
        </form>
      </Modal>

      {/* Conflict Resolver Modal */}
      {showConflictModal && conflictServerState && (
        <ConflictResolverModal
          open={showConflictModal}
          onClose={() => setShowConflictModal(false)}
          resourceName={isEn ? "Condition Record" : "Bản ghi bệnh nền"}
          clientDraft={buildPayload()}
          serverState={conflictServerState}
          changedFields={changedFields}
          onKeepClient={() => {
            void handleSubmit(conflictServerState.base_version as string | number);
          }}
          onAcceptServer={() => {
            if (conflictServerState.name) setName(String(conflictServerState.name));
            if (conflictServerState.clinical_status) setClinicalStatus(String(conflictServerState.clinical_status));
            if (conflictServerState.verification_status) setVerificationStatus(String(conflictServerState.verification_status));
            if (conflictServerState.onset_date) setOnsetDate(String(conflictServerState.onset_date));
            if (conflictServerState.notes) setNotes(String(conflictServerState.notes));
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

export default ConditionEditorModal;
