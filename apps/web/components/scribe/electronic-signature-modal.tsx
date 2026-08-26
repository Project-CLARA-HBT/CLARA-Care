"use client";

import React, { useState } from "react";
import Modal from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";

export interface ElectronicSignatureModalProps {
  open: boolean;
  onClose: () => void;
  isVi?: boolean;
  onSignNote: () => void | Promise<void>;
  isSigning?: boolean;
  sessionTitle?: string;
  clinicianName?: string;
  hasConsent?: boolean;
  hasSoapData?: boolean;
  fidesPassed?: boolean;
}

/**
 * Electronic Signature Modal for Clinical Encounter Notes
 * 
 * Compliant with:
 * - Decree 130/2018/NĐ-CP (Nghị định 130/2018/NĐ-CP về Chữ ký số và Dịch vụ chứng thực chữ ký điện tử)
 * - Circular 46/2018/TT-BYT (Thông tư 46/2018/TT-BYT quy định Hồ sơ bệnh án điện tử - EMR)
 */
export function ElectronicSignatureModal({
  open,
  onClose,
  isVi = true,
  onSignNote,
  isSigning = false,
  sessionTitle = "Phiên khám lâm sàng",
  clinicianName = "Bác sĩ phụ trách",
  hasConsent = true,
  hasSoapData = true,
  fidesPassed = true,
}: ElectronicSignatureModalProps) {
  const [agreedToSign, setAgreedToSign] = useState(false);

  return (
    <Modal
      open={open}
      title={isVi ? "Ký số & Niêm phong Bệnh án Điện tử" : "Electronic Note Signature"}
      onClose={onClose}
      size="md"
    >
      <div className="p-6 space-y-6">
        <div className="text-center space-y-3">
          <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center mx-auto border border-emerald-500/20">
            <Icon name="check" size="2rem" />
          </div>
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-[var(--text-primary)]">
              {isVi ? "Xác nhận Ký số Bệnh án SOAP" : "Sign Clinical SOAP Encounter Note"}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] max-w-sm mx-auto">
              {isVi
                ? "Bệnh án sẽ được niêm phong tính toàn vẹn y khoa, cập nhật vào hồ sơ bệnh án (PHR) và khóa chỉnh sửa."
                : "The encounter note will be cryptographically locked, committed to PHR, and marked immutable."}
            </p>
          </div>
        </div>

        {/* Pre-sign Checklist */}
        <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] text-xs space-y-2.5">
          <h4 className="font-bold uppercase tracking-wider text-[10px] text-[var(--text-secondary)]">
            {isVi ? "Kiểm tra tiêu chuẩn trước khi ký" : "Pre-signature Validation Checklist"}
          </h4>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-primary)]">
              <Icon name="check" size="1rem" className={hasConsent ? "text-emerald-600" : "text-amber-500"} />
              <span>{isVi ? "Đồng thuận người bệnh (Nghị định 13/2023)" : "Patient encounter consent"}</span>
            </div>
            <Badge tone={hasConsent ? "ok" : "warn"}>{hasConsent ? (isVi ? "Hợp lệ" : "Verified") : (isVi ? "Chưa có" : "Missing")}</Badge>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-primary)]">
              <Icon name="check" size="1rem" className={hasSoapData ? "text-emerald-600" : "text-amber-500"} />
              <span>{isVi ? "4 phân mục SOAP (Subjective, Objective, Assessment, Plan)" : "4 SOAP sections complete"}</span>
            </div>
            <Badge tone={hasSoapData ? "ok" : "warn"}>{hasSoapData ? (isVi ? "Đầy đủ" : "Complete") : (isVi ? "Trống" : "Empty")}</Badge>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--text-primary)]">
              <Icon name="check" size="1rem" className={fidesPassed ? "text-emerald-600" : "text-rose-500"} />
              <span>{isVi ? "An toàn tương tác thuốc & liều lượng FIDES" : "FIDES safety verification"}</span>
            </div>
            <Badge tone={fidesPassed ? "ok" : "danger"}>{fidesPassed ? (isVi ? "Đạt chuẩn" : "Passed") : (isVi ? "Cảnh báo" : "Failed")}</Badge>
          </div>
        </div>

        {/* Legal & Regulatory notice */}
        <div className="p-3 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] text-[11px] text-[var(--text-secondary)] space-y-1">
          <p className="font-semibold text-[var(--text-primary)]">
            {isVi ? "Căn cứ pháp lý y tế:" : "Legal basis:"}
          </p>
          <p>
            {isVi
              ? "Theo Thông tư 46/2018/TT-BYT và Nghị định 130/2018/NĐ-CP, chữ ký điện tử của bác sĩ có giá trị pháp lý tương đương chữ ký tay và con dấu trên bệnh án giấy."
              : "In accordance with Circular 46/2018/TT-BYT and Decree 130/2018/NĐ-CP, clinician electronic signature holds full legal validity."}
          </p>
        </div>

        {/* Confirmation Checkbox */}
        <label className="flex items-start gap-2.5 cursor-pointer text-xs text-[var(--text-primary)] select-none">
          <input
            type="checkbox"
            checked={agreedToSign}
            onChange={(e) => setAgreedToSign(e.target.checked)}
            className="w-4 h-4 mt-0.5 rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-500)]"
          />
          <span>
            {isVi
              ? "Tôi chịu trách nhiệm chuyên môn về nội dung bệnh án này và xác nhận ký số."
              : "I accept clinical responsibility for the contents of this medical note and confirm electronic signature."}
          </span>
        </label>

        {/* Modal Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-[color:var(--shell-border)]/60">
          <Button type="button" variant="secondary" size="sm" onClick={onClose} disabled={isSigning}>
            {isVi ? "Đóng" : "Cancel"}
          </Button>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => void onSignNote()}
            disabled={isSigning || !agreedToSign || !hasConsent || !hasSoapData}
            data-testid="scribe-sign"
          >
            <Icon name="clinical-notes" size="1rem" />
            <span>{isSigning ? (isVi ? "Đang ký số..." : "Signing...") : (isVi ? "Ký số Bệnh án" : "Sign Note")}</span>
          </Button>
        </div>
      </div>
    </Modal>
  );
}

export default ElectronicSignatureModal;
