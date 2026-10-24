"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import {
  Timeline,
  TimelineContent,
  TimelineItem,
  TimelineNode,
} from "@/components/ui/timeline";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import type { MultiSourceContradiction } from "@/lib/lifemap-conflict-provenance";
import { MultiSourceContradictionBanner } from "./multi-source-contradiction-banner";

export type LongitudinalTimelineItemType =
  | "encounter"
  | "medication"
  | "lab"
  | "report"
  | "milestone"
  | "journal";

export type LongitudinalTruthState =
  | "confirmed"
  | "user_reported"
  | "draft"
  | "disputed"
  | "superseded";

export interface LongitudinalTimelineEventItem {
  id: string;
  type: LongitudinalTimelineItemType;
  title: string;
  description: string;
  occurred_at: string;
  recorded_at: string;
  revision: number;
  truth_state: LongitudinalTruthState;
  provenance: {
    source_kind: string;
    attribution: string;
    policy_version?: string;
    source_id?: string;
    content_hash?: string;
  };
  metrics?: Record<string, string | number>;
  status?: string;
  associated_journey?: string;
  contradictions?: MultiSourceContradiction[];
}

export interface LongitudinalConflictTimelineProps {
  events: LongitudinalTimelineEventItem[];
  perspective: "valid_time" | "transaction_time";
  onInspectAudit?: (event: LongitudinalTimelineEventItem) => void;
  onInspectContradiction?: (
    contradiction: MultiSourceContradiction,
    event: LongitudinalTimelineEventItem,
  ) => void;
  onDisputeEvent?: (event: LongitudinalTimelineEventItem) => void;
  filterConflictOnly?: boolean;
  onToggleFilterConflictOnly?: (active: boolean) => void;
  className?: string;
}

export function LongitudinalConflictTimeline({
  events,
  perspective,
  onInspectAudit,
  onInspectContradiction,
  onDisputeEvent,
  filterConflictOnly = false,
  onToggleFilterConflictOnly,
  className = "",
}: LongitudinalConflictTimelineProps) {
  const language = useUILanguage();
  const isEn = language === "en";

  const [localConflictOnly, setLocalConflictOnly] = useState(filterConflictOnly);
  const activeConflictFilter =
    onToggleFilterConflictOnly !== undefined
      ? filterConflictOnly
      : localConflictOnly;

  const handleConflictFilterToggle = () => {
    const next = !activeConflictFilter;
    if (onToggleFilterConflictOnly) {
      onToggleFilterConflictOnly(next);
    } else {
      setLocalConflictOnly(next);
    }
  };

  const displayedEvents = useMemo(() => {
    let list = [...events];
    if (activeConflictFilter) {
      list = list.filter(
        (e) =>
          (e.contradictions && e.contradictions.length > 0) ||
          e.truth_state === "disputed",
      );
    }
    return list.sort((a, b) => {
      const timeA =
        perspective === "valid_time"
          ? new Date(a.occurred_at).getTime()
          : new Date(a.recorded_at).getTime();
      const timeB =
        perspective === "valid_time"
          ? new Date(b.occurred_at).getTime()
          : new Date(b.recorded_at).getTime();
      return timeB - timeA;
    });
  }, [events, activeConflictFilter, perspective]);

  const conflictCount = useMemo(() => {
    return events.reduce((acc, e) => {
      const cCount = e.contradictions?.length || 0;
      return acc + (cCount > 0 || e.truth_state === "disputed" ? 1 : 0);
    }, 0);
  }, [events]);

  const typeConfig: Record<
    LongitudinalTimelineItemType,
    { labelVi: string; labelEn: string; icon: string; tone: "brand" | "ok" | "warn" | "neutral" }
  > = {
    encounter: {
      labelVi: "Khám lâm sàng",
      labelEn: "Clinical Encounter",
      icon: "stethoscope",
      tone: "brand",
    },
    medication: {
      labelVi: "Đơn thuốc",
      labelEn: "Medication",
      icon: "medication",
      tone: "warn",
    },
    lab: {
      labelVi: "Xét nghiệm",
      labelEn: "Lab Test",
      icon: "biotech",
      tone: "brand",
    },
    report: {
      labelVi: "Báo cáo theo dõi",
      labelEn: "Report",
      icon: "monitoring",
      tone: "ok",
    },
    milestone: {
      labelVi: "Mốc hành trình",
      labelEn: "Milestone",
      icon: "flag",
      tone: "ok",
    },
    journal: {
      labelVi: "Nhật ký người bệnh",
      labelEn: "Journal",
      icon: "notes",
      tone: "neutral",
    },
  };

  return (
    <div
      className={`longitudinal-conflict-timeline space-y-4 ${className}`}
      data-testid="longitudinal-conflict-timeline"
    >
      {/* Longitudinal Conflict Ribbon & Counter */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl bg-[var(--surface-muted)] border border-[var(--shell-border)]">
        <div className="flex items-center gap-2">
          <Badge tone={conflictCount > 0 ? "warn" : "ok"}>
            {conflictCount > 0
              ? isEn
                ? `${conflictCount} Discrepancies`
                : `${conflictCount} Điểm mâu thuẫn`
              : isEn
                ? "No Conflicts"
                : "Không có mâu thuẫn"}
          </Badge>
          <span className="text-xs text-[var(--text-secondary)] font-medium">
            {isEn
              ? `Timeline perspective: ${
                  perspective === "valid_time"
                    ? "Valid Time (Occurrence)"
                    : "System Time (Recorded)"
                }`
              : `Trục thời gian: ${
                  perspective === "valid_time"
                    ? "Thời gian diễn ra (Valid Time)"
                    : "Thời gian ghi nhận (System Time)"
                }`}
          </span>
        </div>

        {conflictCount > 0 && (
          <Button
            size="sm"
            variant={activeConflictFilter ? "primary" : "secondary"}
            icon="warning"
            onClick={handleConflictFilterToggle}
            data-testid="toggle-conflict-filter-btn"
          >
            {activeConflictFilter
              ? isEn
                ? "Show All Events"
                : "Xem tất cả sự kiện"
              : isEn
                ? `Filter Conflicts (${conflictCount})`
                : `Chỉ xem mâu thuẫn (${conflictCount})`}
          </Button>
        )}
      </div>

      {/* Events Vertical Stream */}
      {displayedEvents.length === 0 ? (
        <SurfaceCard className="p-8 text-center rounded-xl border border-[var(--shell-border)]">
          <p className="text-sm text-[var(--text-secondary)]">
            {activeConflictFilter
              ? isEn
                ? "No conflicting timeline events match the filter."
                : "Không có sự kiện mâu thuẫn nào khớp với bộ lọc."
              : isEn
                ? "No timeline events available."
                : "Chưa có sự kiện nào trong dòng thời gian."}
          </p>
        </SurfaceCard>
      ) : (
        <Timeline orientation="vertical" className="space-y-4">
          {displayedEvents.map((item) => {
            const typeInfo = typeConfig[item.type] || typeConfig.journal;
            const hasContradiction =
              (item.contradictions && item.contradictions.length > 0) ||
              item.truth_state === "disputed";
            const displayDate =
              perspective === "valid_time" ? item.occurred_at : item.recorded_at;

            return (
              <TimelineItem key={item.id} className="relative group">
                <TimelineNode
                  state={hasContradiction ? "disputed" : "completed"}
                  icon={typeInfo.icon}
                  size="md"
                />

                <TimelineContent className="w-full">
                  <SurfaceCard
                    className={`p-5 rounded-xl border transition-all ${
                      hasContradiction
                        ? "border-[var(--status-warn-border,#facc15)] bg-[var(--status-warn-bg,rgba(250,204,21,0.05))]"
                        : "border-[var(--shell-border)] bg-[var(--surface-panel)] hover:shadow-xs"
                    }`}
                    data-testid={`timeline-card-${item.id}`}
                  >
                    {/* Header line */}
                    <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={typeInfo.tone}>
                          {isEn ? typeInfo.labelEn : typeInfo.labelVi}
                        </Badge>
                        <Badge
                          tone={
                            item.truth_state === "confirmed"
                              ? "ok"
                              : item.truth_state === "disputed"
                                ? "danger"
                                : "neutral"
                          }
                        >
                          {item.truth_state}
                        </Badge>
                        {item.associated_journey && (
                          <span className="text-xs font-medium text-[var(--brand-600)] bg-[var(--brand-500)]/10 px-2 py-0.5 rounded-md">
                            {item.associated_journey}
                          </span>
                        )}
                      </div>

                      <span className="text-xs text-[var(--text-secondary)] font-mono">
                        {formatLocaleDate(language, displayDate, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </span>
                    </div>

                    {/* Title & Description */}
                    <h3 className="text-base font-semibold text-[var(--text-primary)] mb-1">
                      {item.title}
                    </h3>
                    <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">
                      {item.description}
                    </p>

                    {/* Metrics stream */}
                    {item.metrics && Object.keys(item.metrics).length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-3">
                        {Object.entries(item.metrics).map(([k, v]) => (
                          <span
                            key={k}
                            className="text-xs px-2.5 py-1 rounded-md bg-[var(--surface-muted)] text-[var(--text-primary)] font-mono border border-[var(--shell-border)]"
                          >
                            <strong className="text-[var(--text-secondary)] mr-1">
                              {k}:
                            </strong>
                            {v}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Multi-Source Contradiction Ribbon if present */}
                    {item.contradictions && item.contradictions.length > 0 && (
                      <div className="my-3 space-y-2">
                        {item.contradictions.map((contra) => (
                          <MultiSourceContradictionBanner
                            key={contra.id}
                            contradiction={contra}
                            onInspect={(c) =>
                              onInspectContradiction?.(c, item)
                            }
                          />
                        ))}
                      </div>
                    )}

                    {/* Bitemporal Coordinates Strip */}
                    <div className="pt-3 border-t border-[var(--shell-border)] flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--text-muted)]">
                      <div className="flex flex-wrap items-center gap-3">
                        <span>
                          <strong className="text-[var(--text-secondary)] mr-1">
                            {isEn ? "Occurred:" : "Diễn ra:"}
                          </strong>
                          {formatLocaleDate(language, item.occurred_at, {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-[var(--text-secondary)] mr-1">
                            {isEn ? "Recorded:" : "Ghi nhận:"}
                          </strong>
                          {formatLocaleDate(language, item.recorded_at, {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-[var(--text-secondary)] mr-1">
                            {isEn ? "Source:" : "Nguồn:"}
                          </strong>
                          {item.provenance.attribution}
                        </span>
                      </div>

                      <div className="flex items-center gap-3">
                        {onInspectAudit && (
                          <button
                            type="button"
                            onClick={() => onInspectAudit(item)}
                            className="text-[var(--brand-600)] hover:underline font-medium"
                          >
                            {isEn ? "Inspect Provenance" : "Xem nhật ký kiểm toán & nguồn"}
                          </button>
                        )}
                        {onDisputeEvent && item.truth_state !== "disputed" && (
                          <button
                            type="button"
                            onClick={() => onDisputeEvent(item)}
                            className="text-[var(--warn-600,#d97706)] hover:underline font-medium"
                          >
                            {isEn ? "Dispute Event" : "Khiếu nại / Báo sai"}
                          </button>
                        )}
                      </div>
                    </div>
                  </SurfaceCard>
                </TimelineContent>
              </TimelineItem>
            );
          })}
        </Timeline>
      )}
    </div>
  );
}
