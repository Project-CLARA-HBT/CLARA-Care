"use client";

import { useCallback, useState } from "react";
import Button from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Select } from "@/components/ui/field";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface ReportModalProps {
  open: boolean;
  target: {
    type: "post" | "comment";
    id: number;
    titleOrSnippet: string;
  } | null;
  onClose: () => void;
  onSuccess: (notice: string) => void;
  onError: (error: string) => void;
  reportFn: (params: {
    targetType: "post" | "comment";
    targetId: number;
    reason: string;
  }) => Promise<unknown>;
}

export function ReportModal({
  open,
  target,
  onClose,
  onSuccess,
  onError,
  reportFn,
}: ReportModalProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language]
  );

  const [reason, setReason] = useState("misinformation");
  const [submitting, setSubmitting] = useState(false);

  if (!open || !target) return null;

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await reportFn({
        targetType: target.type,
        targetId: target.id,
        reason,
      });
      onSuccess(copy("community.report.sent"));
      onClose();
    } catch {
      onError(copy("community.report.error"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        target.type === "post"
          ? copy("community.report.post")
          : copy("community.report.comment")
      }
      description={`"${target.titleOrSnippet}"`}
      size="sm"
      footer={
        <>
          <Button variant="ghost" size="sm" onClick={onClose} disabled={submitting}>
            {copy("community.compose.cancel")}
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleSubmit}
            disabled={submitting}
            loading={submitting}
          >
            {isEn ? "Submit Report" : "Gửi báo cáo"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {isEn
            ? "Please select the primary reason for reporting this content to the clinical moderation team:"
            : "Vui lòng chọn lý do báo cáo nội dung này tới đội ngũ kiểm duyệt:"}
        </p>
        <Select
          label={isEn ? "Report Reason" : "Lý do báo cáo"}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          <option value="misinformation">
            {isEn ? "Medical Misinformation" : "Thông tin sai lệch y tế"}
          </option>
          <option value="unauthorized_prescribing">
            {isEn ? "Unauthorized Drug Prescribing / Dosage" : "Kê đơn / Liều dùng trái phép"}
          </option>
          <option value="pii_disclosure">
            {isEn ? "Personal Identification (PII) Disclosure" : "Tiết lộ thông tin cá nhân"}
          </option>
          <option value="harassment_spam">
            {isEn ? "Harassment or Spam" : "Nội dung quấy rối hoặc spam"}
          </option>
          <option value="emergency_distress">
            {isEn ? "Medical Emergency Distress" : "Dấu hiệu cấp cứu y tế khẩn cấp"}
          </option>
        </Select>
      </div>
    </Modal>
  );
}

export default ReportModal;
