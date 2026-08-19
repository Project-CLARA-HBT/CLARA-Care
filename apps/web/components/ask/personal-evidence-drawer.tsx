"use client";

import { useEffect, useRef } from "react";
import type {
  ConsumerPersonalEvidenceDto,
  ConsumerExternalSourceDto,
} from "@/lib/api/v2-client";
import { Icon } from "@/components/ui/icon";
import { HealthStateBadge, type HealthState } from "@/components/health/health-state-badge";

export interface PersonalEvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  evidence?: ConsumerPersonalEvidenceDto[];
  externalSources?: ConsumerExternalSourceDto[];
  locale?: "vi" | "en";
}

function formatDate(dateStr?: string, locale: "vi" | "en" = "vi"): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(locale === "en" ? "en-US" : "vi-VN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function mapResourceTypeLabel(type?: string): string {
  switch (type?.toLowerCase()) {
    case "medication":
      return "Thuốc";
    case "allergy":
      return "Dị ứng";
    case "condition":
      return "Bệnh nền / Chẩn đoán";
    case "measurement":
      return "Chỉ số đo";
    case "result":
    case "lab":
      return "Kết quả xét nghiệm";
    case "document":
      return "Tài liệu y tế";
    case "visit":
      return "Lần khám";
    default:
      return "Hồ sơ y tế";
  }
}

export function PersonalEvidenceDrawer({
  isOpen,
  onClose,
  evidence = [],
  externalSources = [],
  locale = "vi",
}: PersonalEvidenceDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    closeBtnRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const totalSources = evidence.length + externalSources.length;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity duration-200"
      aria-modal="true"
      role="dialog"
      aria-label="Cơ sở dữ liệu và nguồn thông tin tham khảo"
      data-testid="personal-evidence-drawer"
    >
      {/* Backdrop */}
      <button
        type="button"
        onClick={onClose}
        className="fixed inset-0 h-full w-full cursor-default bg-transparent"
        aria-label="Đóng bảng nguồn tham khảo"
        tabIndex={-1}
      />

      {/* Drawer Content */}
      <div
        ref={drawerRef}
        className="relative z-10 flex h-full w-full max-w-lg flex-col border-l border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-2xl transition-transform duration-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="folder" size={18} aria-hidden="true" />
            </span>
            <div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                Dữ liệu & Nguồn tham khảo
              </h2>
              <p className="text-xs text-[var(--text-muted)]">
                {totalSources} nguồn đã được sử dụng để tạo phản hồi
              </p>
            </div>
          </div>

          <button
            ref={closeBtnRef}
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-ring"
            aria-label="Đóng"
            data-testid="personal-evidence-drawer-close"
          >
            <Icon name="close" size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Body */}
        <div className="clara-scrollbar flex-1 overflow-y-auto p-5 space-y-6">
          {/* 1. Personal Records Section */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Icon name="user-card" size={16} className="text-[var(--brand-500)]" aria-hidden="true" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                Hồ sơ sức khỏe cá nhân ({evidence.length})
              </h3>
            </div>

            {evidence.length === 0 ? (
              <p className="rounded-[var(--radius-md)] border border-dashed border-[color:var(--shell-border)] p-3 text-xs text-[var(--text-muted)]">
                Không sử dụng dữ liệu hồ sơ cá nhân riêng biệt cho câu trả lời này.
              </p>
            ) : (
              <div className="space-y-3" data-testid="personal-evidence-list">
                {evidence.map((item) => {
                  const stateVal = (item.state || item.verification_state || "user_reported") as HealthState;
                  const dateFormatted = formatDate(item.effective_at, locale);
                  const typeLabel = mapResourceTypeLabel(item.resource_type);

                  return (
                    <article
                      key={item.id}
                      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3.5 transition-colors hover:border-[color:var(--shell-border-strong)]"
                      data-testid={`evidence-item-${item.id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="inline-block text-[11px] font-semibold text-[var(--text-brand)] uppercase tracking-wide">
                            {typeLabel}
                          </span>
                          <h4 className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">
                            {item.title}
                          </h4>
                        </div>
                        <HealthStateBadge state={stateVal} locale={locale} />
                      </div>

                      {item.snippet ? (
                        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)] bg-[var(--surface-panel)] p-2.5 rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/50">
                          {item.snippet}
                        </p>
                      ) : null}

                      <div className="mt-2.5 flex flex-wrap items-center gap-3 text-[11px] text-[var(--text-muted)]">
                        {dateFormatted ? (
                          <span className="inline-flex items-center gap-1">
                            <Icon name="calendar" size={13} aria-hidden="true" />
                            <span>Thời điểm: {dateFormatted}</span>
                          </span>
                        ) : null}
                        {item.source_name ? (
                          <span className="inline-flex items-center gap-1">
                            <Icon name="clinical-notes" size={13} aria-hidden="true" />
                            <span>Nguồn: {item.source_name}</span>
                          </span>
                        ) : null}
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>

          {/* 2. External Sources Section */}
          {externalSources.length > 0 ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Icon name="clinical-notes" size={16} className="text-[var(--brand-500)]" aria-hidden="true" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  Tài liệu y khoa & Hướng dẫn ({externalSources.length})
                </h3>
              </div>

              <div className="space-y-3" data-testid="external-sources-list">
                {externalSources.map((src) => (
                  <article
                    key={src.id}
                    className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5"
                    data-testid={`external-source-${src.id}`}
                  >
                    <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                      {src.title}
                    </h4>

                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                      {src.publisher ? <span>{src.publisher}</span> : null}
                      {src.year ? <span>· {src.year}</span> : null}
                    </div>

                    {src.snippet ? (
                      <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                        {src.snippet}
                      </p>
                    ) : null}

                    {src.url ? (
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                      >
                        <span>Xem nguồn gốc</span>
                        <Icon name="arrow-right" size={12} aria-hidden="true" />
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="border-t border-[color:var(--shell-border)] p-4 bg-[var(--surface-muted)]/30 text-xs text-[var(--text-muted)] flex items-center justify-between">
          <span>Quyền riêng tư được bảo vệ</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)] focus-ring"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

export default PersonalEvidenceDrawer;
