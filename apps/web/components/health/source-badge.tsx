import type { ReactNode } from "react";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";

export type SourceKind =
  | "clinician"
  | "doctor"
  | "hospital"
  | "clinic"
  | "device"
  | "patient"
  | "self"
  | "imported"
  | "prescription"
  | "lab";

export type SourceVerificationState =
  | "verified"
  | "self-reported"
  | "self_reported"
  | "imported"
  | "device"
  | "pending"
  | "unverified";

export interface SourceKindMeta {
  labelVi: string;
  labelEn: string;
  icon: IconName;
  tone: BadgeTone;
}

export const SOURCE_KIND_MAP: Record<string, SourceKindMeta> = {
  clinician: {
    labelVi: "Bác sĩ",
    labelEn: "Clinician",
    icon: "clinical-notes",
    tone: "ok",
  },
  doctor: {
    labelVi: "Bác sĩ",
    labelEn: "Doctor",
    icon: "clinical-notes",
    tone: "ok",
  },
  hospital: {
    labelVi: "Bệnh viện",
    labelEn: "Hospital",
    icon: "clinical-notes",
    tone: "ok",
  },
  clinic: {
    labelVi: "Phòng khám",
    labelEn: "Clinic",
    icon: "clinical-notes",
    tone: "ok",
  },
  device: {
    labelVi: "Thiết bị y tế",
    labelEn: "Medical device",
    icon: "scan",
    tone: "brand",
  },
  patient: {
    labelVi: "Bệnh nhân tự ghi",
    labelEn: "Self-reported",
    icon: "user-card",
    tone: "neutral",
  },
  self: {
    labelVi: "Tự ghi nhận",
    labelEn: "Self-reported",
    icon: "user-card",
    tone: "neutral",
  },
  imported: {
    labelVi: "Hồ sơ nhập",
    labelEn: "Imported record",
    icon: "folder",
    tone: "brand",
  },
  prescription: {
    labelVi: "Đơn thuốc",
    labelEn: "Prescription",
    icon: "medication",
    tone: "brand",
  },
  lab: {
    labelVi: "Kết quả xét nghiệm",
    labelEn: "Lab result",
    icon: "scan",
    tone: "brand",
  },
};

export interface VerificationMeta {
  labelVi: string;
  labelEn: string;
  tone: BadgeTone;
  icon: IconName;
}

export const VERIFICATION_STATE_MAP: Record<string, VerificationMeta> = {
  verified: {
    labelVi: "Đã kiểm chứng",
    labelEn: "Verified",
    tone: "ok",
    icon: "check",
  },
  "self-reported": {
    labelVi: "Tự ghi nhận",
    labelEn: "Self-reported",
    tone: "neutral",
    icon: "user-card",
  },
  self_reported: {
    labelVi: "Tự ghi nhận",
    labelEn: "Self-reported",
    tone: "neutral",
    icon: "user-card",
  },
  imported: {
    labelVi: "Nhập từ hồ sơ",
    labelEn: "Imported",
    tone: "brand",
    icon: "folder",
  },
  device: {
    labelVi: "Thiết bị y tế",
    labelEn: "Medical device",
    tone: "brand",
    icon: "scan",
  },
  pending: {
    labelVi: "Chờ đối chiếu",
    labelEn: "Pending verification",
    tone: "warn",
    icon: "progress",
  },
  unverified: {
    labelVi: "Chưa xác minh",
    labelEn: "Unverified",
    tone: "neutral",
    icon: "help",
  },
};

export interface SourceBadgeProps {
  sourceKind?: SourceKind | string;
  verificationState?: SourceVerificationState;
  label?: ReactNode;
  locale?: "vi" | "en";
  showIcon?: boolean;
  className?: string;
}

export function SourceBadge({
  sourceKind,
  verificationState,
  label,
  locale = "vi",
  showIcon = true,
  className = "",
}: SourceBadgeProps) {
  // If verificationState is provided and sourceKind is omitted, display verification state.
  if (verificationState && !sourceKind) {
    const meta = VERIFICATION_STATE_MAP[verificationState] ?? VERIFICATION_STATE_MAP.unverified;
    const text = label ?? (locale === "en" ? meta.labelEn : meta.labelVi);
    return (
      <Badge
        tone={meta.tone}
        icon={showIcon ? meta.icon : undefined}
        className={`source-badge ${className}`}
        data-testid={`source-badge-verification-${verificationState}`}
      >
        <span>{text}</span>
      </Badge>
    );
  }

  const kindKey = (sourceKind ?? "patient").toLowerCase();
  const meta = SOURCE_KIND_MAP[kindKey] ?? {
    labelVi: sourceKind || "Nguồn dữ liệu",
    labelEn: sourceKind || "Data source",
    icon: "clinical-notes",
    tone: "neutral" as BadgeTone,
  };

  const text = label ?? (locale === "en" ? meta.labelEn : meta.labelVi);

  return (
    <Badge
      tone={meta.tone}
      icon={showIcon ? meta.icon : undefined}
      className={`source-badge ${className}`}
      data-testid={`source-badge-${kindKey}`}
    >
      <span>{text}</span>
    </Badge>
  );
}

export interface SourceDetailProps {
  sourceKind?: SourceKind | string;
  sourceName?: string;
  recorder?: string;
  recordedAt?: string | Date;
  verificationState?: SourceVerificationState;
  notes?: string;
  referenceUrl?: string;
  locale?: "vi" | "en";
  compact?: boolean;
  className?: string;
}

function formatDate(date: string | Date | undefined, locale: "vi" | "en"): string {
  if (!date) return "";
  if (typeof date === "string") {
    // If it's already a formatted display string like DD/MM/YYYY or similar, return it
    if (/^\d{1,2}\/\d{1,2}\/\d{4}/.test(date)) return date;
    const parsed = new Date(date);
    if (isNaN(parsed.getTime())) return date;
    date = parsed;
  }
  return date.toLocaleDateString(locale === "en" ? "en-US" : "vi-VN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function SourceDetail({
  sourceKind,
  sourceName,
  recorder,
  recordedAt,
  verificationState,
  notes,
  referenceUrl,
  locale = "vi",
  compact = false,
  className = "",
}: SourceDetailProps) {
  const isEn = locale === "en";
  const formattedDate = formatDate(recordedAt, locale);

  const labels = {
    source: isEn ? "Source" : "Nguồn ghi",
    recorder: isEn ? "Recorded by" : "Người ghi nhận",
    date: isEn ? "Recorded date" : "Ngày ghi nhận",
    verification: isEn ? "Verification status" : "Trạng thái kiểm chứng",
    notes: isEn ? "Notes" : "Ghi chú",
    reference: isEn ? "Reference" : "Tài liệu đính kèm",
  };

  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-sm text-[var(--text-primary)] ${className}`}
      data-testid="source-detail-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/50 pb-2">
        <div className="flex items-center gap-2">
          {sourceKind ? (
            <SourceBadge sourceKind={sourceKind} locale={locale} />
          ) : null}
          {sourceName ? (
            <span className="font-semibold text-[var(--text-primary)]">{sourceName}</span>
          ) : null}
        </div>
        {verificationState ? (
          <SourceBadge verificationState={verificationState} locale={locale} />
        ) : null}
      </div>

      <div className={`grid gap-2 pt-2 ${compact ? "grid-cols-1 sm:grid-cols-2 text-xs" : "grid-cols-1 sm:grid-cols-2"}`}>
        {recorder ? (
          <div>
            <span className="text-[var(--text-muted)] block text-xs">{labels.recorder}:</span>
            <span className="font-medium text-[var(--text-primary)]">{recorder}</span>
          </div>
        ) : null}

        {formattedDate ? (
          <div>
            <span className="text-[var(--text-muted)] block text-xs">{labels.date}:</span>
            <span className="font-medium text-[var(--text-primary)]">{formattedDate}</span>
          </div>
        ) : null}

        {notes ? (
          <div className="sm:col-span-2">
            <span className="text-[var(--text-muted)] block text-xs">{labels.notes}:</span>
            <span className="text-[var(--text-secondary)]">{notes}</span>
          </div>
        ) : null}

        {referenceUrl ? (
          <div className="sm:col-span-2">
            <a
              href={referenceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-medium text-[var(--color-content-link)] hover:underline"
            >
              <Icon name="folder" size="0.9em" />
              <span>{labels.reference}</span>
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default SourceBadge;
