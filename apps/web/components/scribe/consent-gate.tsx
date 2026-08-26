"use client";

import React, { useState } from "react";
import { SurfaceCard } from "@/components/ui/surface";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";

export interface ConsentGateProps {
  isVi?: boolean;
  onConfirmConsent: () => void | Promise<void>;
  isLoading?: boolean;
  className?: string;
}

/**
 * Patient Encounter Consent Gate
 * 
 * Compliant with Vietnamese Decree 13/2023/NĐ-CP (Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân):
 * 1. Minh bạch mục đích thu âm: Hỗ trợ bác sĩ soạn thảo bệnh án SOAP lâm sàng.
 * 2. Xác nhận sự đồng thuận tự nguyện: Bằng lời nói (Verbal Consent) hoặc văn bản từ người bệnh/đại diện.
 * 3. Quyền của chủ thể dữ liệu: Quyền được giải thích, quyền rút lại đồng thuận, quyền yêu cầu xóa dữ liệu âm thanh thô.
 * 4. Không rò rỉ dữ liệu cá nhân (No PII leakage): Dữ liệu được mã hóa và bảo vệ nghiêm ngặt.
 */
export function ConsentGate({
  isVi = true,
  onConfirmConsent,
  isLoading = false,
  className = "",
}: ConsentGateProps) {
  const [hasConfirmedCheckbox, setHasConfirmedCheckbox] = useState(false);

  return (
    <SurfaceCard
      className={`p-6 sm:p-8 space-y-6 relative overflow-hidden bg-[var(--surface-panel)] border border-[color:var(--shell-border)] ${className}`}
      data-testid="scribe-consent-gate"
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[color:var(--shell-border)]/60 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center border border-amber-500/20 shrink-0">
            <Icon name="warning" size="1.6rem" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-[var(--text-primary)]">
                {isVi ? "Đồng thuận Thu âm Phiên khám Lâm sàng" : "Patient Clinical Encounter Consent"}
              </h3>
              <Badge tone="warn">
                {isVi ? "Nghị định 13/2023/NĐ-CP" : "Decree 13/2023 Compliant"}
              </Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {isVi
                ? "Bắt buộc xác nhận sự đồng thuận của người bệnh trước khi kích hoạt micro hoặc phiên âm hội thoại."
                : "Explicit patient consent is legally required prior to microphone capture or dialogue transcription."}
            </p>
          </div>
        </div>
      </div>

      {/* Vietnamese Clinical & Legal Guidance */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
          <div className="flex items-center gap-2 text-[var(--text-brand)] font-bold text-xs">
            <Icon name="chat" size="1rem" />
            <span>{isVi ? "1. Lời nói đồng thuận" : "1. Verbal Consent"}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {isVi
              ? "Bác sĩ thông báo rõ: 'Tôi xin phép ghi âm buổi khám để hỗ trợ ghi chép bệnh án chính xác hơn, anh/chị có đồng ý không?'"
              : "Clinician clearly states recording purpose and receives verbal agreement from the patient."}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
          <div className="flex items-center gap-2 text-emerald-600 font-bold text-xs">
            <Icon name="check" size="1rem" />
            <span>{isVi ? "2. Bảo mật & Giảm thiểu Dữ liệu" : "2. Privacy & Data Minimization"}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {isVi
              ? "Âm thanh được xử lý an toàn, không lưu trữ vĩnh viễn tệp âm thanh thô. Bác sĩ có thể xóa dữ liệu ghi âm bất cứ lúc nào."
              : "Raw audio is processed securely and can be permanently erased by the clinician at any time."}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-1.5">
          <div className="flex items-center gap-2 text-sky-600 font-bold text-xs">
            <Icon name="clinical-notes" size="1rem" />
            <span>{isVi ? "3. Quyền rút lại đồng thuận" : "3. Consent Revocation"}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            {isVi
              ? "Người bệnh có quyền yêu cầu dừng ghi âm hoặc rút lại sự đồng thuận trong suốt quá trình thăm khám."
              : "Patients reserve the right to revoke consent or stop recording at any point during consultation."}
          </p>
        </div>
      </div>

      {/* Confirmation Checkbox & Action */}
      <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex flex-col sm:flex-row items-center justify-between gap-4">
        <label className="flex items-center gap-3 cursor-pointer text-xs font-semibold text-[var(--text-primary)] select-none">
          <input
            type="checkbox"
            checked={hasConfirmedCheckbox}
            onChange={(e) => setHasConfirmedCheckbox(e.target.checked)}
            className="w-4 h-4 rounded border-[color:var(--shell-border)] text-[var(--brand-600)] focus:ring-[var(--brand-500)]"
          />
          <span>
            {isVi
              ? "Tôi đã thông báo và xác nhận người bệnh đồng ý ghi âm phiên khám này."
              : "I confirm the patient has been informed and verbally consented to audio recording."}
          </span>
        </label>

        <Button
          type="button"
          variant="primary"
          size="md"
          onClick={() => void onConfirmConsent()}
          disabled={isLoading || !hasConfirmedCheckbox}
          data-testid="scribe-capture-consent"
          className="w-full sm:w-auto px-6"
        >
          <Icon name="check" size="1.1rem" />
          <span>{isLoading ? (isVi ? "Đang ghi nhận..." : "Capturing...") : (isVi ? "Xác nhận & Bắt đầu" : "Confirm Consent & Proceed")}</span>
        </Button>
      </div>
    </SurfaceCard>
  );
}

export default ConsentGate;
