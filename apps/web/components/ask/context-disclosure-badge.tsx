"use client";

import type { ConsumerDisclosureDto } from "@/lib/api/v2-client";
import { Icon } from "@/components/ui/icon";

export interface ContextDisclosureBadgeProps {
  disclosure?: ConsumerDisclosureDto | null;
  personalEvidenceCount?: number;
  onOpenEvidenceDrawer?: () => void;
  className?: string;
}

const DATA_CLASS_LABELS: Record<string, string> = {
  medications: "Thuốc đang dùng",
  allergies: "Dị ứng",
  conditions: "Tiền sử bệnh",
  measurements: "Chỉ số sức khỏe",
  results: "Kết quả xét nghiệm",
  documents: "Tài liệu y tế",
  visits: "Lịch sử khám",
  timeline: "Dòng thời gian",
};

export function mapDataClassLabel(dataClass: string): string {
  const normalized = dataClass.toLowerCase().trim();
  return DATA_CLASS_LABELS[normalized] ?? dataClass;
}

export function ContextDisclosureBadge({
  disclosure,
  personalEvidenceCount = 0,
  onOpenEvidenceDrawer,
  className = "",
}: ContextDisclosureBadgeProps) {
  if (!disclosure || !disclosure.used_personal_context) {
    return null;
  }

  const rawClasses = Array.isArray(disclosure.data_classes)
    ? disclosure.data_classes
    : [];
  const classNames = rawClasses.map(mapDataClassLabel).filter(Boolean);
  const classText = classNames.length > 0 ? classNames.join(", ") : "Hồ sơ sức khỏe cá nhân";

  return (
    <div
      className={`inline-flex flex-wrap items-center gap-2 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/70 px-3 py-1.5 text-xs text-[var(--text-secondary)] transition-colors ${className}`}
      data-testid="context-disclosure-badge"
    >
      <span className="flex items-center gap-1.5 font-medium text-[var(--text-primary)]">
        <Icon name="user-card" size={14} className="text-[var(--brand-500)]" aria-hidden="true" />
        <span>Đã dùng thông tin:</span>
      </span>

      <span className="font-semibold text-[var(--brand-600)] dark:text-[var(--brand-400)]">
        [{classText}]
      </span>

      {onOpenEvidenceDrawer && personalEvidenceCount > 0 ? (
        <button
          type="button"
          onClick={onOpenEvidenceDrawer}
          className="ml-auto inline-flex items-center gap-1 font-semibold text-[var(--text-brand)] hover:underline focus-ring rounded-[var(--radius-sm)]"
          aria-label={`Xem ${personalEvidenceCount} nguồn dữ liệu hồ sơ đã dùng`}
          data-testid="context-disclosure-drawer-trigger"
        >
          <span>Xem chi tiết ({personalEvidenceCount})</span>
          <Icon name="arrow-right" size={12} aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}

export default ContextDisclosureBadge;
