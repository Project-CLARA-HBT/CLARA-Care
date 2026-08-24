"use client";

import type { HTMLAttributes, ReactNode } from "react";
import React, { useId, useState } from "react";
import { Icon, resolveIconName, type IconName } from "@/components/ui/icon";
import { Badge, type BadgeTone } from "@/components/ui/badge";

export interface SourceItem {
  id?: string;
  title: string;
  kind?: string;
  authors?: string;
  publication?: string;
  year?: number | string;
  snippet?: string;
  confidenceScore?: number;
  trustTier?: string;
  verificationState?: "verified" | "unverified" | "disputed" | string;
  url?: string;
  pmid?: string;
  doi?: string;
  tags?: string[];
}

export interface SourceCategoryBreakdown {
  category: string;
  count: number;
  label?: string;
}

export interface SourceDisclosureBadgeProps
  extends Omit<HTMLAttributes<HTMLButtonElement>, "onToggle"> {
  count?: number;
  confidenceScore?: number;
  verificationLabel?: string;
  label?: string;
  tone?: BadgeTone;
  expanded?: boolean;
  onToggle?: () => void;
  className?: string;
}

export function SourceDisclosureBadge({
  count = 0,
  confidenceScore,
  verificationLabel,
  label,
  tone = "brand",
  expanded = false,
  onToggle,
  className = "",
  ...rest
}: SourceDisclosureBadgeProps) {
  const displayLabel =
    label ?? (count > 0 ? `${count} nguồn trích dẫn` : "Nguồn bằng chứng");

  return (
    <button
      type="button"
      aria-expanded={expanded}
      onClick={onToggle}
      className={`inline-flex items-center gap-2 rounded-[var(--radius-pill)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/80 hover:bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] transition-colors focus-ring ${className}`}
      {...rest}
    >
      <span className="flex items-center gap-1.5 text-[var(--text-primary)]">
        <Icon name="clinical-notes" size="0.95rem" className="text-[var(--brand-500)]" aria-hidden="true" />
        <span className="font-semibold">{displayLabel}</span>
      </span>

      {typeof confidenceScore === "number" && (
        <Badge tone={confidenceScore >= 0.8 || confidenceScore >= 80 ? "ok" : "warn"} className="py-0.5 px-2 text-[10px]">
          {confidenceScore > 1 ? `${confidenceScore}%` : `${Math.round(confidenceScore * 100)}%`}
        </Badge>
      )}

      {verificationLabel && (
        <Badge tone="ok" className="py-0.5 px-2 text-[10px]">
          {verificationLabel}
        </Badge>
      )}

      <Icon
        name="chevron-down"
        size="0.85rem"
        className={`text-[var(--text-muted)] transition-transform duration-200 ${
          expanded ? "rotate-180" : ""
        }`}
        aria-hidden="true"
      />
    </button>
  );
}

export function SourceItemCard({
  source,
  className = "",
}: {
  source: SourceItem;
  className?: string;
}) {
  const verificationTone: BadgeTone =
    source.verificationState === "verified"
      ? "ok"
      : source.verificationState === "disputed"
      ? "danger"
      : "neutral";

  return (
    <div
      className={`rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3.5 space-y-2 transition-colors hover:border-[color:var(--shell-border-strong)] ${className}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-xs sm:text-sm font-semibold text-[var(--text-primary)] leading-snug">
          {source.title}
        </h4>
        <div className="flex shrink-0 items-center gap-1.5">
          {source.trustTier && <Badge tone="brand">{source.trustTier}</Badge>}
          {source.verificationState && (
            <Badge tone={verificationTone}>
              {source.verificationState === "verified"
                ? "Đã xác minh"
                : source.verificationState === "disputed"
                ? "Tranh chấp"
                : source.verificationState}
            </Badge>
          )}
          {typeof source.confidenceScore === "number" && (
            <Badge tone={source.confidenceScore >= 0.8 || source.confidenceScore >= 80 ? "ok" : "warn"}>
              {source.confidenceScore > 1
                ? `${source.confidenceScore}%`
                : `${Math.round(source.confidenceScore * 100)}%`}
            </Badge>
          )}
        </div>
      </div>

      {(source.authors || source.publication || source.year) && (
        <div className="text-xs text-[var(--text-secondary)]">
          {source.authors && <span>{source.authors}. </span>}
          {source.publication && <span className="italic">{source.publication} </span>}
          {source.year && <span>({source.year}).</span>}
        </div>
      )}

      {source.snippet && (
        <p className="text-xs text-[var(--text-secondary)] bg-[var(--surface-muted)]/60 rounded-[var(--radius-md)] p-2.5 border border-[color:var(--shell-border)]/50 italic leading-relaxed">
          &ldquo;{source.snippet}&rdquo;
        </p>
      )}

      {source.tags && source.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-1">
          {source.tags.map((tag, idx) => (
            <span
              key={idx}
              className="text-[10px] bg-[var(--surface-muted)] text-[var(--text-muted)] px-2 py-0.5 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)]/40"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between pt-1 text-[11px]">
        <div className="text-[var(--text-muted)] space-x-2">
          {source.pmid && <span>PMID: {source.pmid}</span>}
          {source.doi && <span>DOI: {source.doi}</span>}
        </div>
        {source.url && (
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-semibold text-[var(--text-brand)] hover:underline ml-auto"
          >
            <span>Xem tài liệu gốc</span>
            <Icon name="arrow-right" size="0.75rem" aria-hidden="true" />
          </a>
        )}
      </div>
    </div>
  );
}

export interface SourceDisclosurePanelProps extends HTMLAttributes<HTMLDivElement> {
  sources?: SourceItem[];
  breakdown?: SourceCategoryBreakdown[];
  children?: ReactNode;
  className?: string;
}

export function SourceDisclosurePanel({
  sources = [],
  breakdown,
  children,
  className = "",
  ...rest
}: SourceDisclosurePanelProps) {
  return (
    <div
      role="region"
      className={`mt-3 space-y-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/30 p-4 transition-all duration-200 ${className}`}
      {...rest}
    >
      {breakdown && breakdown.length > 0 && (
        <div className="flex flex-wrap gap-2 pb-2 border-b border-[color:var(--shell-border)]/60">
          {breakdown.map((item, idx) => (
            <span
              key={idx}
              className="text-xs bg-[var(--surface-panel)] border border-[color:var(--shell-border)] px-2.5 py-1 rounded-[var(--radius-pill)] font-medium text-[var(--text-secondary)]"
            >
              {item.label ?? item.category}: <strong className="text-[var(--text-primary)]">{item.count}</strong>
            </span>
          ))}
        </div>
      )}

      {sources.length > 0 ? (
        <div className="space-y-2.5">
          {sources.map((source, index) => (
            <SourceItemCard key={source.id ?? index} source={source} />
          ))}
        </div>
      ) : children ? (
        children
      ) : (
        <p className="text-xs text-[var(--text-muted)] text-center py-4">
          Chưa có nguồn trích dẫn chi tiết.
        </p>
      )}
    </div>
  );
}

export interface SourceDisclosureProps
  extends Omit<HTMLAttributes<HTMLDivElement>, "title" | "onToggle"> {
  sources?: SourceItem[];
  confidenceScore?: number;
  verificationLabel?: string;
  summaryLabel?: string;
  badgeTone?: BadgeTone;
  expanded?: boolean;
  defaultExpanded?: boolean;
  onToggle?: (expanded: boolean) => void;
  breakdown?: SourceCategoryBreakdown[];
  children?: ReactNode;
  className?: string;
}

export function SourceDisclosure({
  sources = [],
  confidenceScore,
  verificationLabel,
  summaryLabel,
  badgeTone = "brand",
  expanded: controlledExpanded,
  defaultExpanded = false,
  onToggle,
  breakdown,
  children,
  className = "",
  ...rest
}: SourceDisclosureProps) {
  const [internalExpanded, setInternalExpanded] = useState(defaultExpanded);
  const isControlled = typeof controlledExpanded === "boolean";
  const isExpanded = isControlled ? controlledExpanded : internalExpanded;

  const panelId = useId();

  const handleToggle = () => {
    const nextState = !isExpanded;
    if (!isControlled) {
      setInternalExpanded(nextState);
    }
    onToggle?.(nextState);
  };

  return (
    <div className={`source-disclosure-container ${className}`} {...rest}>
      <SourceDisclosureBadge
        count={sources.length}
        confidenceScore={confidenceScore}
        verificationLabel={verificationLabel}
        label={summaryLabel}
        tone={badgeTone}
        expanded={isExpanded}
        onToggle={handleToggle}
        aria-controls={panelId}
      />

      {isExpanded && (
        <SourceDisclosurePanel
          id={panelId}
          sources={sources}
          breakdown={breakdown}
        >
          {children}
        </SourceDisclosurePanel>
      )}
    </div>
  );
}

export default SourceDisclosure;
