"use client";

import React from "react";
import Modal from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";

export interface RecordingDataModalProps {
  open: boolean;
  onClose: () => void;
  isVi?: boolean;
  onDeleteRecordingData: () => void | Promise<void>;
  isDeleting?: boolean;
  confirmTitle?: string;
  confirmDescription?: string;
  confirmAction?: string;
  cancelAction?: string;
}

/**
 * Recording Data Deletion Modal
 * 
 * Compliant with Vietnamese Decree 13/2023/NĐ-CP right to erasure / data minimization:
 * Permanently deletes raw encounter audio and derived transcription segments,
 * while preserving the finalized signed clinical note and immutable audit trail.
 */
export function RecordingDataModal({
  open,
  onClose,
  isVi = true,
  onDeleteRecordingData,
  isDeleting = false,
  confirmTitle,
  confirmDescription,
  confirmAction,
  cancelAction,
}: RecordingDataModalProps) {
  return (
    <Modal
      open={open}
      title={confirmTitle || (isVi ? "Xác nhận xóa dữ liệu phiên âm" : "Confirm Audio Deletion")}
      onClose={onClose}
      size="sm"
    >
      <div className="p-6 space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-600 flex items-center justify-center mx-auto border border-rose-500/20">
          <Icon name="trash" size="1.5rem" />
        </div>

        <div className="text-center space-y-2">
          <h4 className="font-bold text-base text-[var(--text-primary)]">
            {confirmTitle || (isVi ? "Xóa vĩnh viễn tệp âm thanh gốc?" : "Permanently delete audio data?")}
          </h4>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {confirmDescription ||
              (isVi
                ? "Thao tác này xóa vĩnh viễn bản ghi âm và thông tin đoạn phiên âm khỏi hệ thống để tuân thủ quyền riêng tư (Nghị định 13/2023). Bệnh án SOAP đã ký và nhật ký kiểm toán sẽ được giữ nguyên."
                : "This permanently deletes raw audio and transcript segments to satisfy privacy data rights (Decree 13/2023). Signed notes and audit logs are preserved.")}
          </p>
        </div>

        <div className="pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={onClose}
            disabled={isDeleting}
          >
            {cancelAction || (isVi ? "Hủy" : "Cancel")}
          </Button>
          <Button
            type="button"
            variant="danger"
            size="sm"
            onClick={() => void onDeleteRecordingData()}
            disabled={isDeleting}
          >
            <Icon name="trash" size="0.9rem" />
            <span>{isDeleting ? (isVi ? "Đang xóa..." : "Deleting...") : (confirmAction || (isVi ? "Xóa vĩnh viễn" : "Delete Permanently"))}</span>
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default RecordingDataModal;
