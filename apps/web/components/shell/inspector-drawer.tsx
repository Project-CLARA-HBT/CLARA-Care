"use client";

import React, {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import Icon, { type IconName } from "@/components/ui/icon";

export type InspectorDrawerWidth =
  | "sm"
  | "md"
  | "lg"
  | "300px"
  | "340px"
  | "360px"
  | "380px"
  | number
  | string;

export type InspectorDrawerDensity = "comfortable" | "compact" | "dense";
export type InspectorDrawerMode = "slide-over" | "inline";
export type InspectorDrawerSide = "right" | "left";

export interface InspectorDrawerProps {
  /** Controlled open state */
  open?: boolean;
  /** Close callback */
  onClose?: () => void;
  /** Primary entity title */
  title: ReactNode;
  /** Optional subtitle or description */
  subtitle?: ReactNode;
  description?: ReactNode;
  /** Single badge or multiple badges */
  badge?: ReactNode;
  badges?: ReactNode;
  /** Header action buttons or menu */
  actions?: ReactNode;
  /** Main body content */
  children?: ReactNode;
  /** Optional footer */
  footer?: ReactNode;
  /** Mode: slide-over drawer (default) or inline panel */
  mode?: InspectorDrawerMode;
  /** Drawer slide direction (default "right") */
  side?: InspectorDrawerSide;
  /** Width: 300px–380px (preset: sm=300px, md=340px, lg=380px, or custom) */
  width?: InspectorDrawerWidth;
  /** Density preset */
  density?: InspectorDrawerDensity;
  /** Close button aria-label */
  closeLabel?: string;
  /** Accessibility role (default "dialog") */
  role?: "dialog" | "alertdialog";
  /** Aria labels override */
  ariaLabel?: string;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  /** Whether drawer can be closed with Escape / backdrop click */
  dismissible?: boolean;
  /** Whether to show close button */
  showCloseButton?: boolean;
  /** Additional styling */
  className?: string;
  bodyClassName?: string;
  headerClassName?: string;
  footerClassName?: string;
  "data-testid"?: string;
  id?: string;
}

export interface InspectorDrawerSectionProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  className?: string;
}

export interface InspectorDrawerFieldProps {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  copyable?: boolean;
  vertical?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Specialized Source Inspection Data & View
// ---------------------------------------------------------------------------
export interface SourceInspectionItem {
  id?: string;
  title: string;
  source?: string;
  year?: string | number;
  authors?: string;
  url?: string;
  pmid?: string;
  doi?: string;
  trustTier?: "T1_OFFICIAL" | "T2_PEER_REVIEWED" | "T3_CLINICAL_GUIDELINE" | "T4_PREPRINT" | string;
  trustTierLabel?: string;
  excerpt?: string;
  relevanceScore?: number;
}

export interface SourceInspectorViewProps {
  sources: SourceInspectionItem[];
  title?: string;
  emptyMessage?: string;
  className?: string;
  onSelectSource?: (source: SourceInspectionItem) => void;
}

// ---------------------------------------------------------------------------
// Specialized Evidence Breakdown Data & View
// ---------------------------------------------------------------------------
export interface EvidenceClaimBreakdown {
  id?: string;
  claim: string;
  status: "VERIFIED" | "CAUTION" | "CRITICAL_BLOCKED" | "UNVERIFIED" | "PENDING";
  statusLabel?: string;
  fidesTier?: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  confidence?: number;
  rationale?: string;
  citations?: string[];
  conflicts?: string[];
  recommendation?: string;
}

export interface EvidenceBreakdownViewProps {
  claims: EvidenceClaimBreakdown[];
  title?: string;
  summary?: ReactNode;
  className?: string;
}

// ---------------------------------------------------------------------------
// Specialized Patient Details Data & View
// ---------------------------------------------------------------------------
export interface PatientDetailsData {
  id?: string;
  name: string;
  mrn?: string;
  age?: number | string;
  gender?: "Nam" | "Nữ" | "Khác" | string;
  dob?: string;
  bloodType?: string;
  allergies?: Array<{
    allergen: string;
    severity?: "Nặng" | "Vừa" | "Nhẹ" | string;
    reaction?: string;
  }>;
  vitals?: Array<{
    label: string;
    value: string;
    unit?: string;
    status?: "normal" | "warning" | "critical";
  }>;
  activeMedications?: Array<{
    name: string;
    dosage?: string;
    frequency?: string;
  }>;
  emergencyContact?: {
    name: string;
    phone: string;
    relationship?: string;
  };
  insuranceNumber?: string;
}

export interface PatientDetailsViewProps {
  patient: PatientDetailsData;
  className?: string;
}

// ---------------------------------------------------------------------------
// Specialized Telemetry Data & View
// ---------------------------------------------------------------------------
export interface TelemetryInspectionData {
  requestId?: string;
  model?: string;
  timestamp?: string;
  totalLatencyMs?: number;
  latencyBreakdown?: {
    guardrailMs?: number;
    retrievalMs?: number;
    synthesisMs?: number;
    fidesVerificationMs?: number;
  };
  tokenUsage?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
  };
  ragChunksRetrieved?: number;
  ragChunksUsed?: number;
  guardrailPassed?: boolean;
  guardrailInterventions?: string[];
  zeroPiiVerified?: boolean;
  cacheHit?: boolean;
}

export interface TelemetryViewProps {
  telemetry: TelemetryInspectionData;
  className?: string;
}

// ---------------------------------------------------------------------------
// Focus utilities
// ---------------------------------------------------------------------------
const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function getFocusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((el) => {
    if (el.hasAttribute("disabled")) return false;
    if (el.getAttribute("aria-hidden") === "true") return false;
    if (el.hasAttribute("hidden")) return false;
    if (el.style.display === "none" || el.style.visibility === "hidden") {
      return false;
    }
    return true;
  });
}

const WIDTH_CLASSES: Record<string, string> = {
  sm: "w-[300px] max-w-[300px]",
  md: "w-[340px] max-w-[340px]",
  lg: "w-[380px] max-w-[380px]",
  "300px": "w-[300px] max-w-[300px]",
  "340px": "w-[340px] max-w-[340px]",
  "360px": "w-[360px] max-w-[360px]",
  "380px": "w-[380px] max-w-[380px]",
};

const DENSITY_SPACING: Record<
  InspectorDrawerDensity,
  { body: string; header: string; footer: string }
> = {
  comfortable: {
    body: "p-5 space-y-5",
    header: "px-5 py-4",
    footer: "px-5 py-3.5",
  },
  compact: {
    body: "p-4 space-y-4",
    header: "px-4 py-3",
    footer: "px-4 py-3",
  },
  dense: {
    body: "p-3 space-y-2.5 text-xs",
    header: "px-3 py-2.5",
    footer: "px-3 py-2 text-xs",
  },
};

// ---------------------------------------------------------------------------
// 1. InspectorDrawerSection Component
// ---------------------------------------------------------------------------
export function InspectorDrawerSection({
  title,
  description,
  badge,
  actions,
  children,
  collapsible = false,
  defaultExpanded = true,
  className = "",
  ...rest
}: InspectorDrawerSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] overflow-hidden transition-all shadow-sm ${className}`}
      {...rest}
    >
      {(title || description || actions || badge) && (
        <div
          className={`flex items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/40 px-3.5 py-2.5 ${
            collapsible
              ? "cursor-pointer select-none hover:bg-[var(--surface-muted)]"
              : ""
          }`}
          onClick={collapsible ? () => setIsExpanded((prev) => !prev) : undefined}
          role={collapsible ? "button" : undefined}
          aria-expanded={collapsible ? isExpanded : undefined}
          tabIndex={collapsible ? 0 : undefined}
          onKeyDown={
            collapsible
              ? (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setIsExpanded((prev) => !prev);
                  }
                }
              : undefined
          }
        >
          <div className="min-w-0 flex-1">
            {title && (
              <h3 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                {collapsible && (
                  <Icon
                    name={isExpanded ? "chevron-down" : "arrow-right"}
                    size={14}
                    className="shrink-0 text-[var(--text-secondary)] transition-transform duration-150"
                  />
                )}
                <span className="truncate">{title}</span>
                {badge ? <span className="shrink-0">{badge}</span> : null}
              </h3>
            )}
            {description && (
              <p className="mt-0.5 text-[0.6875rem] text-[var(--text-secondary)] truncate">
                {description}
              </p>
            )}
          </div>

          {actions && (
            <div
              className="flex shrink-0 items-center gap-1"
              onClick={(e) => e.stopPropagation()}
            >
              {actions}
            </div>
          )}
        </div>
      )}

      {(!collapsible || isExpanded) && (
        <div className="p-3.5 text-xs sm:text-sm text-[var(--text-primary)]">
          {children}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. InspectorDrawerField Component
// ---------------------------------------------------------------------------
export function InspectorDrawerField({
  label,
  value,
  hint,
  copyable = false,
  vertical = false,
  className = "",
}: InspectorDrawerFieldProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (typeof value === "string" || typeof value === "number") {
      try {
        await navigator.clipboard.writeText(String(value));
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } catch {
        // Safe fallback
      }
    }
  };

  return (
    <div
      className={`flex gap-1.5 py-1.5 border-b border-[color:var(--shell-border)]/30 last:border-0 ${
        vertical
          ? "flex-col items-start"
          : "flex-col sm:flex-row sm:items-baseline sm:justify-between"
      } ${className}`}
    >
      <div className="min-w-0">
        <span className="text-[0.6875rem] sm:text-xs font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        {hint && (
          <p className="text-[0.625rem] text-[var(--text-secondary)] opacity-80">{hint}</p>
        )}
      </div>

      <div className="flex items-center gap-1.5 min-w-0">
        <div className="text-xs sm:text-sm font-medium text-[var(--text-primary)] break-all">
          {value}
        </div>
        {copyable && (
          <button
            type="button"
            onClick={handleCopy}
            title={copied ? "Đã sao chép" : "Sao chép"}
            aria-label={copied ? "Đã sao chép" : "Sao chép giá trị"}
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-[var(--radius-sm)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--focus-ring-color)] transition"
          >
            {copied ? (
              <Icon name="check" size={11} className="text-[var(--brand-500)]" />
            ) : (
              <Icon name="clinical-notes" size={11} />
            )}
          </button>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. SourceInspectorView Subcomponent
// ---------------------------------------------------------------------------
export function SourceInspectorView({
  sources,
  title = "Nguồn & Bằng chứng tham chiếu",
  emptyMessage = "Chưa có nguồn trích dẫn nào được ghi nhận.",
  className = "",
  onSelectSource,
}: SourceInspectorViewProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)]">
          {title}
        </h3>
        <span className="rounded-full bg-[var(--surface-muted)] px-2 py-0.5 text-[0.6875rem] font-bold text-[var(--text-secondary)]">
          {sources.length}
        </span>
      </div>

      {sources.length === 0 ? (
        <p className="text-xs text-[var(--text-secondary)] italic py-2">
          {emptyMessage}
        </p>
      ) : (
        <div className="space-y-2.5">
          {sources.map((src, index) => {
            const isOfficial =
              src.trustTier === "T1_OFFICIAL" ||
              src.trustTierLabel?.includes("Dược thư") ||
              src.trustTierLabel?.includes("BYT");

            return (
              <div
                key={src.id ?? `src-${index}`}
                onClick={onSelectSource ? () => onSelectSource(src) : undefined}
                className={`group rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/80 bg-[var(--surface-panel)] p-3 transition hover:border-[color:var(--shell-border-strong)] ${
                  onSelectSource ? "cursor-pointer" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-[var(--text-primary)] leading-snug">
                    {src.title}
                  </span>
                  {src.trustTier && (
                    <span
                      className={`shrink-0 rounded-full px-1.5 py-0.5 text-[0.625rem] font-bold ${
                        isOfficial
                          ? "bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/40 text-[var(--text-brand)]"
                          : "bg-[var(--status-neutral-bg)] border border-[color:var(--status-neutral-border)] text-[var(--status-neutral-text)]"
                      }`}
                    >
                      {src.trustTierLabel ?? src.trustTier}
                    </span>
                  )}
                </div>

                <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[0.6875rem] text-[var(--text-secondary)]">
                  {src.source && <span>{src.source}</span>}
                  {src.year && <span>• {src.year}</span>}
                  {src.authors && <span>• {src.authors}</span>}
                  {src.pmid && <span>• PMID: {src.pmid}</span>}
                </div>

                {src.excerpt && (
                  <p className="mt-2 rounded bg-[var(--surface-muted)]/50 p-2 text-[0.6875rem] text-[var(--text-secondary)] line-clamp-3">
                    &ldquo;{src.excerpt}&rdquo;
                  </p>
                )}

                {src.url && (
                  <div className="mt-2 flex items-center justify-end">
                    <a
                      href={src.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[0.6875rem] font-medium text-[var(--text-brand)] hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <span>Xem tài liệu gốc</span>
                      <Icon name="arrow-right" size={10} />
                    </a>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 4. EvidenceBreakdownView Subcomponent
// ---------------------------------------------------------------------------
export function EvidenceBreakdownView({
  claims,
  title = "Chi tiết kiểm chứng FIDES & Bằng chứng",
  summary,
  className = "",
}: EvidenceBreakdownViewProps) {
  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)]">
          {title}
        </h3>
        <span className="rounded-full bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30 px-2 py-0.5 text-[0.6875rem] font-bold text-[var(--text-brand)]">
          FIDES Verified
        </span>
      </div>

      {summary && (
        <div className="rounded-[var(--radius-md)] bg-[var(--surface-muted)]/50 p-2.5 text-xs text-[var(--text-secondary)]">
          {summary}
        </div>
      )}

      <div className="space-y-2.5">
        {claims.map((item, index) => {
          const isBlocked = item.status === "CRITICAL_BLOCKED";
          const isCaution = item.status === "CAUTION";
          const isVerified = item.status === "VERIFIED";

          let statusClass = "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border-[color:var(--brand-500)]/30";
          if (isBlocked) {
            statusClass = "bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border-[color:var(--status-danger-border)]";
          } else if (isCaution) {
            statusClass = "bg-[var(--status-warn-bg)] text-[var(--status-warn-text)] border-[color:var(--status-warn-border)]";
          }

          return (
            <div
              key={item.id ?? `claim-${index}`}
              className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/80 bg-[var(--surface-panel)] p-3 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold text-[var(--text-primary)] leading-snug">
                  {item.claim}
                </span>
                <span
                  className={`shrink-0 rounded-full border px-2 py-0.5 text-[0.625rem] font-bold uppercase ${statusClass}`}
                >
                  {item.statusLabel ?? item.status}
                </span>
              </div>

              {item.confidence !== undefined && (
                <div className="space-y-1">
                  <div className="flex justify-between text-[0.625rem] text-[var(--text-secondary)]">
                    <span>Độ tin cậy</span>
                    <span className="font-semibold">{Math.round(item.confidence * 100)}%</span>
                  </div>
                  <div className="h-1.5 w-full rounded-full bg-[var(--surface-muted)] overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        isBlocked
                          ? "bg-[var(--danger-500)]"
                          : isCaution
                            ? "bg-[var(--warn-500)]"
                            : "bg-[var(--brand-500)]"
                      }`}
                      style={{ width: `${Math.min(100, Math.max(0, item.confidence * 100))}%` }}
                    />
                  </div>
                </div>
              )}

              {item.rationale && (
                <p className="text-[0.6875rem] text-[var(--text-secondary)]">
                  {item.rationale}
                </p>
              )}

              {item.citations && item.citations.length > 0 && (
                <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-[color:var(--shell-border)]/30">
                  <span className="text-[0.625rem] font-medium text-[var(--text-secondary)]">Trích dẫn:</span>
                  {item.citations.map((c, cIdx) => (
                    <span
                      key={cIdx}
                      className="rounded bg-[var(--surface-muted)] px-1.5 py-0.25 text-[0.625rem] font-mono text-[var(--text-primary)]"
                    >
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5. PatientDetailsView Subcomponent
// ---------------------------------------------------------------------------
export function PatientDetailsView({
  patient,
  className = "",
}: PatientDetailsViewProps) {
  return (
    <div className={`space-y-4 ${className}`}>
      {/* Patient Header */}
      <div className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]/80 bg-[var(--surface-muted)]/40 p-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30 text-[var(--text-brand)]">
          <Icon name="user-card" size={20} />
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="text-sm font-bold text-[var(--text-primary)] truncate">
            {patient.name}
          </h4>
          <p className="text-xs text-[var(--text-secondary)]">
            MRN: {patient.mrn || "N/A"} • {patient.gender || "Chưa rõ"} • {patient.age ? `${patient.age} tuổi` : ""}
          </p>
        </div>
      </div>

      {/* Demographics */}
      <InspectorDrawerSection title="Thông tin hành chính" collapsible defaultExpanded>
        <InspectorDrawerField label="Họ và tên" value={patient.name} />
        {patient.mrn && <InspectorDrawerField label="Mã hồ sơ (MRN)" value={patient.mrn} copyable />}
        {patient.dob && <InspectorDrawerField label="Ngày sinh" value={patient.dob} />}
        {patient.bloodType && <InspectorDrawerField label="Nhóm máu" value={patient.bloodType} />}
        {patient.insuranceNumber && (
          <InspectorDrawerField label="Số thẻ BHYT" value={patient.insuranceNumber} copyable />
        )}
      </InspectorDrawerSection>

      {/* Vital signs */}
      {patient.vitals && patient.vitals.length > 0 && (
        <InspectorDrawerSection title="Chỉ số sinh tồn gần nhất" collapsible defaultExpanded>
          <div className="grid grid-cols-2 gap-2">
            {patient.vitals.map((v, vIdx) => {
              const isWarning = v.status === "warning" || v.status === "critical";
              return (
                <div
                  key={vIdx}
                  className={`rounded-[var(--radius-md)] border p-2.5 ${
                    isWarning
                      ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
                  }`}
                >
                  <span className="text-[0.625rem] font-medium text-[var(--text-secondary)] block">
                    {v.label}
                  </span>
                  <span className="text-sm font-bold block mt-0.5">
                    {v.value} <span className="text-xs font-normal text-[var(--text-secondary)]">{v.unit}</span>
                  </span>
                </div>
              );
            })}
          </div>
        </InspectorDrawerSection>
      )}

      {/* Allergies */}
      {patient.allergies && patient.allergies.length > 0 && (
        <InspectorDrawerSection
          title="Tiền sử dị ứng"
          badge={
            <span className="rounded-full bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-1.5 py-0.25 text-[0.625rem] font-bold text-[var(--status-danger-text)]">
              {patient.allergies.length}
            </span>
          }
          collapsible
          defaultExpanded
        >
          <div className="space-y-1.5">
            {patient.allergies.map((al, aIdx) => (
              <div
                key={aIdx}
                className="flex items-center justify-between rounded bg-[var(--surface-muted)]/50 px-2.5 py-1.5 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-medium text-[var(--text-primary)]">{al.allergen}</span>
                  {al.reaction && (
                    <span className="text-[0.6875rem] text-[var(--text-secondary)] ml-1.5">
                      {al.reaction}
                    </span>
                  )}
                </div>
                <span className="rounded bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] px-1.5 py-0.25 text-[0.625rem] font-bold shrink-0 ml-2">
                  {al.severity || "Cảnh báo"}
                </span>
              </div>
            ))}
          </div>
        </InspectorDrawerSection>
      )}

      {/* Active Medications */}
      {patient.activeMedications && patient.activeMedications.length > 0 && (
        <InspectorDrawerSection title="Thuốc đang sử dụng" collapsible defaultExpanded={false}>
          <div className="space-y-1.5">
            {patient.activeMedications.map((med, mIdx) => (
              <div
                key={mIdx}
                className="rounded bg-[var(--surface-muted)]/50 p-2 text-xs"
              >
                <span className="font-semibold text-[var(--text-primary)] block">{med.name}</span>
                <span className="text-[0.6875rem] text-[var(--text-secondary)] block">
                  {med.dosage} {med.frequency ? `• ${med.frequency}` : ""}
                </span>
              </div>
            ))}
          </div>
        </InspectorDrawerSection>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 6. TelemetryInspectorView Subcomponent
// ---------------------------------------------------------------------------
export function TelemetryInspectorView({
  telemetry,
  className = "",
}: TelemetryViewProps) {
  return (
    <div className={`space-y-3.5 ${className}`}>
      {/* Zero PII Guarantee Banner */}
      <div className="flex items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-2.5 text-xs text-[var(--status-ok-text)]">
        <Icon name="check" size={14} className="shrink-0 text-[var(--brand-500)]" />
        <span className="font-medium leading-tight">
          Bảo mật Zero-PII: Không lưu trữ danh tính người dùng hoặc thông tin cá nhân.
        </span>
      </div>

      {/* Overview stats */}
      <InspectorDrawerSection title="Hiệu năng & Mô hình" collapsible defaultExpanded>
        {telemetry.requestId && (
          <InspectorDrawerField label="Request ID" value={telemetry.requestId} copyable />
        )}
        {telemetry.model && (
          <InspectorDrawerField label="Mô hình tổng hợp" value={telemetry.model} />
        )}
        {telemetry.totalLatencyMs !== undefined && (
          <InspectorDrawerField
            label="Tổng độ trễ"
            value={`${telemetry.totalLatencyMs} ms`}
          />
        )}
        {telemetry.timestamp && (
          <InspectorDrawerField label="Thời gian thực thi" value={telemetry.timestamp} />
        )}
      </InspectorDrawerSection>

      {/* Latency Breakdown */}
      {telemetry.latencyBreakdown && (
        <InspectorDrawerSection title="Chi tiết độ trễ các pha (ms)" collapsible defaultExpanded>
          <div className="space-y-1.5">
            {Object.entries(telemetry.latencyBreakdown).map(([phase, ms]) => (
              <div
                key={phase}
                className="flex items-center justify-between text-xs py-1 border-b border-[color:var(--shell-border)]/20 last:border-0"
              >
                <span className="capitalize text-[var(--text-secondary)]">
                  {phase.replace("Ms", "")}
                </span>
                <span className="font-mono font-medium text-[var(--text-primary)]">
                  {ms} ms
                </span>
              </div>
            ))}
          </div>
        </InspectorDrawerSection>
      )}

      {/* Tokens & RAG */}
      {(telemetry.tokenUsage || telemetry.ragChunksRetrieved !== undefined) && (
        <InspectorDrawerSection title="Token & RAG Retrieval" collapsible defaultExpanded>
          {telemetry.tokenUsage?.promptTokens !== undefined && (
            <InspectorDrawerField
              label="Prompt Tokens"
              value={telemetry.tokenUsage.promptTokens}
            />
          )}
          {telemetry.tokenUsage?.completionTokens !== undefined && (
            <InspectorDrawerField
              label="Completion Tokens"
              value={telemetry.tokenUsage.completionTokens}
            />
          )}
          {telemetry.tokenUsage?.totalTokens !== undefined && (
            <InspectorDrawerField
              label="Total Tokens"
              value={telemetry.tokenUsage.totalTokens}
            />
          )}
          {telemetry.ragChunksRetrieved !== undefined && (
            <InspectorDrawerField
              label="RAG Chunks Đã truy hồi"
              value={`${telemetry.ragChunksUsed ?? 0} / ${telemetry.ragChunksRetrieved}`}
            />
          )}
        </InspectorDrawerSection>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main InspectorDrawer Component (Spec v8 Section 5.8)
// ---------------------------------------------------------------------------
export function InspectorDrawer({
  open = true,
  onClose,
  title,
  subtitle,
  description,
  badge,
  badges,
  actions,
  children,
  footer,
  mode = "slide-over",
  side = "right",
  width = "360px",
  density = "compact",
  closeLabel = "Đóng bộ kiểm tra",
  role = "dialog",
  ariaLabel,
  ariaLabelledBy,
  ariaDescribedBy,
  dismissible = true,
  showCloseButton = true,
  className = "",
  bodyClassName = "",
  headerClassName = "",
  footerClassName = "",
  "data-testid": dataTestId,
  id: customId,
}: InspectorDrawerProps) {
  const generatedId = useId();
  const drawerId = customId ?? `inspector-drawer-${generatedId}`;
  const titleId = ariaLabelledBy ?? `${drawerId}-title`;
  const descriptionId = ariaDescribedBy ?? `${drawerId}-desc`;

  const drawerPanelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  // Focus trap and Escape key dismissal
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (dismissible && event.key === "Escape") {
        event.preventDefault();
        onClose?.();
        return;
      }

      if (event.key !== "Tab") return;
      const panel = drawerPanelRef.current;
      if (!panel) return;

      const focusableNodes = getFocusableElements(panel);
      if (focusableNodes.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }

      const firstNode = focusableNodes[0];
      const lastNode = focusableNodes[focusableNodes.length - 1];
      const activeEl = document.activeElement;

      if (
        event.shiftKey &&
        (activeEl === firstNode || activeEl === panel || !panel.contains(activeEl))
      ) {
        event.preventDefault();
        lastNode.focus();
      } else if (
        !event.shiftKey &&
        (activeEl === lastNode || !panel.contains(activeEl))
      ) {
        event.preventDefault();
        firstNode.focus();
      }
    },
    [dismissible, onClose],
  );

  // Trap focus and lock scroll in slide-over mode
  useEffect(() => {
    if (mode !== "slide-over" || !open) return;
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);

    const timer = setTimeout(() => {
      const panel = drawerPanelRef.current;
      const firstFocusable = panel ? getFocusableElements(panel)[0] : null;
      (firstFocusable ?? panel)?.focus();
    }, 40);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [mode, open, handleKeyDown]);

  const densityStyles = DENSITY_SPACING[density] ?? DENSITY_SPACING.compact;

  // Resolve width classes (300px–380px)
  const resolvedWidthClass =
    typeof width === "string" && WIDTH_CLASSES[width]
      ? WIDTH_CLASSES[width]
      : "w-[360px] sm:w-[360px] md:w-[380px] max-w-[380px]";

  const customWidthStyle =
    typeof width === "number" ? { width: `${width}px`, maxWidth: `${width}px` } : undefined;

  const headerContent = (
    <div className="flex min-w-0 flex-1 flex-col gap-0.5">
      <div className="flex items-center gap-2 flex-wrap">
        <h2
          id={titleId}
          className="text-sm sm:text-base font-bold text-[var(--text-primary)] truncate"
        >
          {title}
        </h2>
        {badge ? <div>{badge}</div> : null}
        {badges ? (
          <div className="inline-flex items-center gap-1.5">{badges}</div>
        ) : null}
      </div>
      {(subtitle || description) && (
        <p
          id={descriptionId}
          className="text-xs text-[var(--text-secondary)] line-clamp-2"
        >
          {subtitle || description}
        </p>
      )}
    </div>
  );

  // Slide-over modal drawer mode
  if (mode === "slide-over") {
    if (!open) return null;

    return (
      <div
        className="fixed inset-0 z-50 flex justify-end"
        data-testid={dataTestId}
        id={drawerId}
      >
        {/* Backdrop overlay */}
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity animate-in fade-in duration-200"
          onClick={dismissible ? onClose : undefined}
          aria-hidden="true"
        />

        {/* Drawer slide-over surface */}
        <div
          ref={drawerPanelRef}
          role={role}
          aria-modal="true"
          aria-labelledby={title ? titleId : undefined}
          aria-describedby={subtitle || description ? descriptionId : undefined}
          aria-label={ariaLabel}
          tabIndex={-1}
          style={customWidthStyle}
          className={`relative z-10 flex h-full ${resolvedWidthClass} flex-col border-l border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-2xl transition-all duration-200 animate-in slide-in-from-right ${className}`}
        >
          {/* Header */}
          <div
            className={`flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)]/80 bg-[var(--surface-panel)] ${densityStyles.header} ${headerClassName}`}
          >
            {headerContent}
            <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
              {actions}
              {showCloseButton && onClose && (
                <button
                  type="button"
                  onClick={onClose}
                  aria-label={closeLabel}
                  title={closeLabel}
                  className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)] transition"
                >
                  <Icon name="close" size={15} />
                </button>
              )}
            </div>
          </div>

          {/* Body */}
          <div
            className={`flex-1 overflow-y-auto ${densityStyles.body} ${bodyClassName}`}
          >
            {children}
          </div>

          {/* Footer */}
          {footer ? (
            <div
              className={`border-t border-[color:var(--shell-border)]/80 bg-[var(--surface-panel)] ${densityStyles.footer} ${footerClassName}`}
            >
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  // Inline mode: renders as embedded aside landmark
  return (
    <aside
      id={drawerId}
      role="region"
      aria-label={typeof title === "string" ? title : ariaLabel || "Bộ kiểm tra"}
      data-testid={dataTestId}
      style={customWidthStyle}
      className={`flex flex-col rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm text-[var(--text-primary)] ${resolvedWidthClass} ${className}`}
    >
      {/* Header */}
      <div
        className={`flex items-start justify-between gap-3 border-b border-[color:var(--shell-border)]/80 ${densityStyles.header} ${headerClassName}`}
      >
        {headerContent}
        <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
          {actions}
          {showCloseButton && onClose && (
            <button
              type="button"
              onClick={onClose}
              aria-label={closeLabel}
              title={closeLabel}
              className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-md)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--focus-ring-color)] transition"
            >
              <Icon name="close" size={15} />
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div
        className={`flex-1 overflow-y-auto ${densityStyles.body} ${bodyClassName}`}
      >
        {children}
      </div>

      {/* Footer */}
      {footer ? (
        <div
          className={`border-t border-[color:var(--shell-border)]/80 ${densityStyles.footer} ${footerClassName}`}
        >
          {footer}
        </div>
      ) : null}
    </aside>
  );
}

export default InspectorDrawer;
