"use client";

import { useEffect, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import { InlineError } from "@/components/shared/inline-error";
import { ConflictResolverModal } from "./conflict-resolver-modal";
import {
  apiV2UpdateDemographics,
  ApiV2ClientError,
  type HealthDemographicsDto,
} from "@/lib/api/v2-client";

export interface DemographicsEditorModalProps {
  open: boolean;
  onClose: () => void;
  initialData?: HealthDemographicsDto;
  onSuccess?: (updated: HealthDemographicsDto) => void;
  locale?: "vi" | "en";
}

export function DemographicsEditorModal({
  open,
  onClose,
  initialData,
  onSuccess,
  locale = "vi",
}: DemographicsEditorModalProps) {
  const isEn = locale === "en";

  const [fullName, setFullName] = useState(initialData?.full_name ?? "");
  const [dob, setDob] = useState(initialData?.date_of_birth ?? "");
  const [gender, setGender] = useState(initialData?.gender ?? "other");
  const [bloodType, setBloodType] = useState(initialData?.blood_type ?? "unknown");
  const [phoneNumber, setPhoneNumber] = useState(initialData?.phone_number ?? "");
  const [emergencyName, setEmergencyName] = useState(
    initialData?.emergency_contact?.name ?? "",
  );
  const [emergencyRel, setEmergencyRel] = useState(
    initialData?.emergency_contact?.relationship ?? "",
  );
  const [emergencyPhone, setEmergencyPhone] = useState(
    initialData?.emergency_contact?.phone ?? "",
  );

  const [baseVersion, setBaseVersion] = useState<string | number | undefined>(
    initialData?.base_version ?? "v1",
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Conflict state
  const [conflictServerState, setConflictServerState] = useState<Record<string, unknown> | null>(
    null,
  );
  const [changedFields, setChangedFields] = useState<string[]>([]);
  const [showConflictModal, setShowConflictModal] = useState(false);

  useEffect(() => {
    if (initialData) {
      setFullName(initialData.full_name ?? "");
      setDob(initialData.date_of_birth ?? "");
      setGender(initialData.gender ?? "other");
      setBloodType(initialData.blood_type ?? "unknown");
      setPhoneNumber(initialData.phone_number ?? "");
      setEmergencyName(initialData.emergency_contact?.name ?? "");
      setEmergencyRel(initialData.emergency_contact?.relationship ?? "");
      setEmergencyPhone(initialData.emergency_contact?.phone ?? "");
      setBaseVersion(initialData.base_version ?? "v1");
    }
  }, [initialData, open]);

  const buildPayload = (overrideVersion?: string | number): Partial<HealthDemographicsDto> => {
    return {
      full_name: fullName.trim() || undefined,
      date_of_birth: dob || undefined,
      gender: gender as any,
      blood_type: bloodType as any,
      phone_number: phoneNumber.trim() || undefined,
      emergency_contact:
        emergencyName || emergencyPhone || emergencyRel
          ? {
              name: emergencyName.trim() || undefined,
              relationship: emergencyRel.trim() || undefined,
              phone: emergencyPhone.trim() || undefined,
            }
          : undefined,
      base_version: overrideVersion ?? baseVersion,
    };
  };

  const handleSubmit = async (overrideVersion?: string | number) => {
    setIsSubmitting(true);
    setErrorMessage(null);

    const payload = buildPayload(overrideVersion);

    try {
      const res = await apiV2UpdateDemographics(payload, {
        baseVersion: payload.base_version,
      });
      setIsSubmitting(false);
      setShowConflictModal(false);
      if (onSuccess) onSuccess(res);
      onClose();
    } catch (err) {
      setIsSubmitting(false);
      if (err instanceof ApiV2ClientError && (err.isConflict || err.isPreconditionFailed)) {
        const currentVer = err.currentVersion ?? "v_server";
        const serverMock: Record<string, unknown> = {
          full_name: (err.details as any)?.full_name ?? initialData?.full_name ?? "Máy chủ đã đổi tên",
          date_of_birth: (err.details as any)?.date_of_birth ?? initialData?.date_of_birth ?? "",
          gender: (err.details as any)?.gender ?? initialData?.gender ?? "female",
          blood_type: (err.details as any)?.blood_type ?? initialData?.blood_type ?? "O+",
          phone_number: (err.details as any)?.phone_number ?? initialData?.phone_number ?? "",
          base_version: currentVer,
        };
        setConflictServerState(serverMock);
        setChangedFields(err.changedFields.length ? err.changedFields : ["full_name", "blood_type"]);
        setBaseVersion(currentVer);
        setShowConflictModal(true);
      } else {
        setErrorMessage(
          err instanceof Error ? err.message : isEn ? "Failed to save demographics" : "Không thể lưu thông tin cá nhân",
        );
      }
    }
  };

  return (
    <>
      <Modal
        open={open && !showConflictModal}
        onClose={onClose}
        title={isEn ? "Edit Demographics & Emergency Info" : "Chỉnh sửa thông tin cơ bản & liên hệ khẩn cấp"}
        description={
          isEn
            ? "Update your personal health profile. Changes are saved with version checking to prevent overwriting."
            : "Cập nhật hồ sơ cá nhân. Dữ liệu được bảo vệ bằng cơ chế phiên bản để tránh ghi đè."
        }
        size="md"
        closeLabel={isEn ? "Close" : "Đóng"}
        footer={
          <>
            <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
              {isEn ? "Cancel" : "Hủy"}
            </Button>
            <Button
              variant="primary"
              onClick={() => void handleSubmit()}
              loading={isSubmitting}
              icon="clinical-notes"
            >
              {isEn ? "Save Changes" : "Lưu thay đổi"}
            </Button>
          </>
        }
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleSubmit();
          }}
          className="space-y-4"
          data-testid="demographics-editor-form"
        >
          {errorMessage && (
            <InlineError
              severity="error"
              title={isEn ? "Save Failed" : "Lưu thất bại"}
              message={errorMessage}
              onRetry={() => void handleSubmit()}
            />
          )}

          <Field
            label={isEn ? "Full Name" : "Họ và tên"}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder={isEn ? "e.g. John Doe" : "Ví dụ: Nguyễn Văn A"}
            data-testid="field-demographics-fullname"
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field
              type="date"
              label={isEn ? "Date of Birth" : "Ngày sinh"}
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              data-testid="field-demographics-dob"
            />

            <Select
              label={isEn ? "Gender" : "Giới tính"}
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              data-testid="field-demographics-gender"
            >
              <option value="male">{isEn ? "Male" : "Nam"}</option>
              <option value="female">{isEn ? "Female" : "Nữ"}</option>
              <option value="other">{isEn ? "Other" : "Khác"}</option>
            </Select>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select
              label={isEn ? "Blood Type" : "Nhóm máu"}
              value={bloodType}
              onChange={(e) => setBloodType(e.target.value)}
              data-testid="field-demographics-bloodtype"
            >
              <option value="unknown">{isEn ? "Unknown" : "Chưa rõ"}</option>
              <option value="A+">A+</option>
              <option value="A-">A-</option>
              <option value="B+">B+</option>
              <option value="B-">B-</option>
              <option value="AB+">AB+</option>
              <option value="AB-">AB-</option>
              <option value="O+">O+</option>
              <option value="O-">O-</option>
            </Select>

            <Field
              label={isEn ? "Phone Number" : "Số điện thoại"}
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="0987654321"
              data-testid="field-demographics-phone"
            />
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-3.5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
              {isEn ? "Emergency Contact" : "Người liên hệ khẩn cấp"}
            </h3>

            <Field
              label={isEn ? "Contact Name" : "Tên người liên hệ"}
              value={emergencyName}
              onChange={(e) => setEmergencyName(e.target.value)}
              placeholder={isEn ? "e.g. Mary Doe" : "Ví dụ: Nguyễn Thị B"}
              data-testid="field-demographics-emergency-name"
            />

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field
                label={isEn ? "Relationship" : "Mối quan hệ"}
                value={emergencyRel}
                onChange={(e) => setEmergencyRel(e.target.value)}
                placeholder={isEn ? "e.g. Spouse / Sibling" : "Ví dụ: Vợ / Chồng, Con"}
                data-testid="field-demographics-emergency-rel"
              />

              <Field
                label={isEn ? "Emergency Phone" : "Số điện thoại khẩn cấp"}
                value={emergencyPhone}
                onChange={(e) => setEmergencyPhone(e.target.value)}
                placeholder="0912345678"
                data-testid="field-demographics-emergency-phone"
              />
            </div>
          </div>
        </form>
      </Modal>

      {/* Conflict Resolver Modal */}
      {showConflictModal && conflictServerState && (
        <ConflictResolverModal
          open={showConflictModal}
          onClose={() => {
            setShowConflictModal(false);
          }}
          resourceName={isEn ? "Demographics" : "Thông tin cá nhân"}
          clientDraft={buildPayload()}
          serverState={conflictServerState}
          changedFields={changedFields}
          onKeepClient={() => {
            void handleSubmit(conflictServerState.base_version as string | number);
          }}
          onAcceptServer={() => {
            if (conflictServerState.full_name) setFullName(String(conflictServerState.full_name));
            if (conflictServerState.date_of_birth) setDob(String(conflictServerState.date_of_birth));
            if (conflictServerState.gender) setGender(String(conflictServerState.gender));
            if (conflictServerState.blood_type) setBloodType(String(conflictServerState.blood_type));
            if (conflictServerState.phone_number) setPhoneNumber(String(conflictServerState.phone_number));
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

export default DemographicsEditorModal;
