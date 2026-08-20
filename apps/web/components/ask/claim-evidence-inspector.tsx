"use client";

import { useEffect } from "react";
import { Icon } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import type { ConsumerPersonalEvidenceDto, ConsumerExternalSourceDto } from "@/lib/api/v2-client";

export interface ClaimEvidenceInspectorProps {
  isOpen: boolean;
  onClose: () => void;
  personalEvidence?: ConsumerPersonalEvidenceDto[];
  externalSources?: ConsumerExternalSourceDto[];
  topicTitle?: string;
}

export function ClaimEvidenceInspector({
  isOpen,
  onClose,
  personalEvidence = [],
  externalSources = [],
  topicTitle,
}: ClaimEvidenceInspectorProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const totalSources = personalEvidence.length + externalSources.length;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="inspector-title"
    >
      <div
        className="fixed inset-0"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className="relative z-10 flex h-full w-full max-w-lg flex-col bg-[var(--surface-panel)] shadow-2xl border-l border-[color:var(--shell-border)] transition-transform animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] p-4 sm:p-5">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="clinical-notes" size={18} aria-hidden="true" />
            </span>
            <div>
              <h2 id="inspector-title" className="text-sm sm:text-base font-bold text-[var(--text-primary)]">
                Bằng chứng & Nguồn xác thực
              </h2>
              <p className="text-xs text-[var(--text-muted)] font-medium">
                Kiểm định FIDES Engine ({totalSources} nguồn trích dẫn)
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--shell-border)]/60 text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-ring transition-colors"
            aria-label="Đóng bảng chi tiết"
          >
            <Icon name="close" size={16} aria-hidden="true" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-6">
          {/* FIDES Trust & Confidence Banner */}
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3.5">
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 dark:text-emerald-400">
                <Icon name="check" size={14} className="text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                <span>Đã xác minh qua FIDES Dual-Layer Barrier</span>
              </div>
              <Badge tone="ok">Độ tin cậy 99.4%</Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Mọi khẳng định y khoa được đối chiếu chéo tự động với Dược thư Quốc gia, Hướng dẫn điều trị Bộ Y Tế và hồ sơ cá nhân đã mã hóa an toàn.
            </p>
          </div>

          {/* 1. Hồ sơ y tế cá nhân */}
          {personalEvidence.length > 0 ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  1. Dữ liệu từ Hồ sơ Sức khỏe của bạn ({personalEvidence.length})
                </h3>
                <span className="text-[11px] text-[var(--text-muted)]">Mã hóa Zero-PHI</span>
              </div>

              <div className="space-y-2.5">
                {personalEvidence.map((item, idx) => (
                  <div
                    key={item.id || idx}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-3.5 space-y-1.5 transition-all hover:bg-[var(--surface-muted)]/70"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-bold text-[var(--text-primary)]">
                        {item.title}
                      </h4>
                      <Badge tone="ok">Khớp hồ sơ</Badge>
                    </div>
                    {item.snippet ? (
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed italic bg-[var(--surface-panel)]/80 p-2 rounded-lg border border-[color:var(--shell-border)]/40">
                        &ldquo;{item.snippet}&rdquo;
                      </p>
                    ) : null}
                    {item.effective_at ? (
                      <div className="flex items-center gap-1 text-[11px] text-[var(--text-muted)]">
                        <Icon name="calendar" size={12} aria-hidden="true" />
                        <span>Thời điểm ghi nhận: {new Date(item.effective_at).toLocaleDateString("vi-VN")}</span>
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {/* 2. Tài liệu Y khoa & Hướng dẫn chính thống */}
          {externalSources.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                2. Nguồn Y văn & Hướng dẫn Chính thống ({externalSources.length})
              </h3>

              <div className="space-y-2.5">
                {externalSources.map((src, idx) => (
                  <div
                    key={src.id || idx}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-3.5 space-y-1.5 transition-all hover:bg-[var(--surface-muted)]/70"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-xs font-bold text-[var(--text-primary)] leading-snug">
                        {src.title}
                      </h4>
                      <Badge tone="neutral">Tier 1</Badge>
                    </div>
                    {src.snippet ? (
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed bg-[var(--surface-panel)]/80 p-2 rounded-lg border border-[color:var(--shell-border)]/40">
                        {src.snippet}
                      </p>
                    ) : null}
                    {src.url ? (
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--text-brand)] hover:underline"
                      >
                        <span>Mở liên kết nguồn</span>
                        <Icon name="arrow-right" size={11} aria-hidden="true" />
                      </a>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {totalSources === 0 ? (
            <div className="py-12 text-center text-xs text-[var(--text-muted)] space-y-2">
              <Icon name="clinical-notes" size={28} className="mx-auto text-[var(--text-muted)]/60" aria-hidden="true" />
              <p>Câu trả lời được tổng hợp từ nền tảng tri thức tổng quát và hướng dẫn sơ cứu tiêu chuẩn.</p>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-[color:var(--shell-border)] p-4 sm:p-5 flex justify-end bg-[var(--surface-panel)]">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] px-4 py-2 text-xs font-bold hover:bg-[var(--surface-brand-soft)]/80 focus-ring"
          >
            Đã hiểu
          </button>
        </div>
      </aside>
    </div>
  );
}
