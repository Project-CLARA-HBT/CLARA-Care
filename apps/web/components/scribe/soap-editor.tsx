"use client";

import React, { useState } from "react";
import { SurfaceCard } from "@/components/ui/surface";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import { type UITranslationKey, t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

export interface SoapSections {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
}

export interface SoapEditorProps {
  isVi?: boolean;
  language: UILanguage;
  soap: SoapSections;
  onSoapChange: (updated: SoapSections) => void;
  isSaving?: boolean;
  isRegenerating?: boolean;
  onRegenerate?: () => void | Promise<void>;
  onProceedToSign?: () => void;
  readOnly?: boolean;
  copy: (key: UITranslationKey, values?: Record<string, string | number>) => string;
  className?: string;
}

export function SoapEditor({
  isVi = true,
  language,
  soap,
  onSoapChange,
  isSaving = false,
  isRegenerating = false,
  onRegenerate,
  onProceedToSign,
  readOnly = false,
  copy,
  className = "",
}: SoapEditorProps) {
  const [isEditing, setIsEditing] = useState(false);

  const sectionsConfig: Array<{
    key: keyof SoapSections;
    title: string;
    description: string;
    placeholder: string;
  }> = [
    {
      key: "subjective",
      title: isVi ? "S — Bệnh Sử & Lý Do Khám (Subjective)" : "S — Subjective (History of Present Illness)",
      description: isVi ? "Triệu chứng cơ năng, lời khai của người bệnh, tiền sử bệnh liên quan." : "Patient-reported symptoms, history, and chief complaint.",
      placeholder: isVi ? "Nhập thông tin bệnh sử, lý do khám..." : "Enter subjective history...",
    },
    {
      key: "objective",
      title: isVi ? "O — Khám Thực Thể & Cận Lâm Sàng (Objective)" : "O — Objective (Physical Exam & Labs)",
      description: isVi ? "Dấu hiệu sinh tồn, kết quả khám lâm sàng, cận lâm sàng, xét nghiệm." : "Vital signs, physical examination findings, diagnostic tests.",
      placeholder: isVi ? "Nhập kết quả khám, dấu hiệu sinh tồn, cận lâm sàng..." : "Enter objective findings...",
    },
    {
      key: "assessment",
      title: isVi ? "A — Đánh Giá & Chẩn Đoán Sơ Bộ (Assessment)" : "A — Assessment (Clinical Diagnosis)",
      description: isVi ? "Nhận định y khoa của bác sĩ, chẩn đoán xác định hoặc chẩn đoán phân biệt." : "Clinical evaluation, primary or differential diagnoses.",
      placeholder: isVi ? "Nhập đánh giá lâm sàng, chẩn đoán..." : "Enter clinical assessment...",
    },
    {
      key: "plan",
      title: isVi ? "P — Kế Hoạch Điều Trị & Dặn Dò (Plan)" : "P — Plan (Treatment & Follow-up)",
      description: isVi ? "Đơn thuốc, chỉ định cận lâm sàng tiếp theo, hướng dẫn chăm sóc và hẹn tái khám." : "Therapeutic orders, medications, diagnostic tests, patient instructions.",
      placeholder: isVi ? "Nhập phác đồ điều trị, đơn thuốc, hẹn tái khám..." : "Enter treatment plan...",
    },
  ];

  const handleSectionUpdate = (key: keyof SoapSections, value: string) => {
    onSoapChange({
      ...soap,
      [key]: value,
    });
  };

  return (
    <div className={`space-y-6 ${className}`} data-testid="scribe-step-panel-4">
      <SurfaceCard className="p-6 sm:p-8 space-y-6 relative overflow-hidden bg-[var(--surface-panel)] border border-[color:var(--shell-border)]">
        {/* Header with Title and FIDES status */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[color:var(--shell-border)]/60 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xl font-bold text-[var(--text-primary)]">
                {isVi ? "Hồ sơ Khám Bệnh Án SOAP" : "SOAP Clinical Document"}
              </h3>
              <Badge tone="ok">{isVi ? "FIDES Verified" : "FIDES Verified"}</Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {isVi
                ? "Dự thảo tổng hợp tự động từ lời thoại phiên khám với xác minh an toàn tương tác thuốc."
                : "Synthesized encounter summary note with clinical safety verification."}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {!readOnly && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setIsEditing(!isEditing)}
              >
                <Icon name={isEditing ? "check" : "edit"} size="0.9rem" />
                <span>{isEditing ? (isVi ? "Xem trước" : "Preview") : (isVi ? "Chỉnh sửa" : "Edit")}</span>
              </Button>
            )}
            {onRegenerate && !readOnly && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => void onRegenerate()}
                disabled={isRegenerating}
                data-testid="scribe-generate-note"
              >
                <Icon name="refresh" size="0.9rem" />
                <span>{isRegenerating ? (isVi ? "Đang tạo lại..." : "Regenerating...") : (isVi ? "Tạo lại SOAP" : "Regenerate")}</span>
              </Button>
            )}
          </div>
        </div>

        {/* 4 Core SOAP Sections */}
        <div className="space-y-6">
          {sectionsConfig.map((section) => {
            const rawContent = soap[section.key] ?? "";
            const sanitizedContent = stripTelemetryLabels(rawContent);

            return (
              <section key={section.key} className="space-y-2 border-l-2 border-[var(--brand-500)] pl-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-sm text-[var(--text-primary)] uppercase tracking-wide">
                    {section.title}
                  </h4>
                  <span className="text-[10px] text-[var(--text-muted)] font-mono">
                    {sanitizedContent.trim().length} {isVi ? "ký tự" : "chars"}
                  </span>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  {section.description}
                </p>

                {isEditing && !readOnly ? (
                  <textarea
                    value={rawContent}
                    onChange={(e) => handleSectionUpdate(section.key, e.target.value)}
                    placeholder={section.placeholder}
                    className="w-full min-h-[100px] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-sm font-sans leading-relaxed text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]"
                  />
                ) : (
                  <div className="p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] text-sm text-[var(--text-primary)] leading-relaxed min-h-[56px] whitespace-pre-wrap">
                    {sanitizedContent.trim() ? (
                      sanitizedContent
                    ) : (
                      <span className="text-[var(--text-muted)] italic">
                        {isVi ? "Chưa có thông tin ghi nhận trong phân mục này" : "No content recorded in this section"}
                      </span>
                    )}
                  </div>
                )}
              </section>
            );
          })}
        </div>

        {/* Clinical Governance Disclaimers */}
        <div className="p-4 rounded-xl bg-[var(--surface-muted)] border border-[color:var(--shell-border)] space-y-2 text-xs text-[var(--text-secondary)]">
          <div className="flex items-start gap-2">
            <Icon name="help" size="1.1rem" className="text-[var(--text-brand)] shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p>{copy("scribe.review.statusDescription")}</p>
              <p>{copy("scribe.review.codingDescription")}</p>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        {onProceedToSign && (
          <div className="pt-4 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
            <span className="text-xs text-[var(--text-secondary)]">
              {isSaving ? (isVi ? "Đang lưu thay đổi..." : "Saving changes...") : (isVi ? "Đã đồng bộ tự động" : "Changes synced")}
            </span>
            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={onProceedToSign}
            >
              <span>{isVi ? "Chuyển sang Bước Ký & Hoàn tất" : "Proceed to Finalize & Sign"}</span>
              <Icon name="arrow-right" size="1rem" />
            </Button>
          </div>
        )}
      </SurfaceCard>
    </div>
  );
}

export default SoapEditor;
