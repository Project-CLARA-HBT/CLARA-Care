"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { HealthStateBadge, type HealthState } from "@/components/health/health-state-badge";
import { SourceBadge } from "@/components/health/source-badge";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import { EmptyState } from "@/components/shared/empty-state";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type HealthTimelineEventDto,
  type HealthTimelineResponseDto,
  type HealthTimelineRevisionDto,
} from "@/lib/api/v2-client";

export type PeriodFilter = "recent" | "month" | "year" | "all";
export type TypeFilter = "medication" | "symptom" | "visit" | "result" | "measurement" | "document";

export interface TimelineViewProps {
  initialProfileId?: string | null;
  initialData?: HealthTimelineResponseDto;
  className?: string;
}

const PERIOD_OPTIONS: Array<{ key: PeriodFilter; labelVi: string; labelEn: string }> = [
  { key: "recent", labelVi: "Gần đây", labelEn: "Recent" },
  { key: "month", labelVi: "Tháng này", labelEn: "This Month" },
  { key: "year", labelVi: "Năm nay", labelEn: "This Year" },
  { key: "all", labelVi: "Tất cả", labelEn: "All History" },
];

const TYPE_OPTIONS: Array<{ key: TypeFilter; labelVi: string; labelEn: string; icon: IconName }> = [
  { key: "medication", labelVi: "Thuốc", labelEn: "Medications", icon: "medication" },
  { key: "symptom", labelVi: "Triệu chứng & Bệnh lý", labelEn: "Symptoms & Conditions", icon: "body" },
  { key: "visit", labelVi: "Lịch khám", labelEn: "Visits", icon: "calendar" },
  { key: "result", labelVi: "Kết quả", labelEn: "Results", icon: "scan" },
  { key: "measurement", labelVi: "Chỉ số", labelEn: "Measurements", icon: "progress" },
  { key: "document", labelVi: "Tài liệu", labelEn: "Documents", icon: "folder" },
];

function getEventIcon(kind: string): IconName {
  switch (kind?.toLowerCase()) {
    case "medication":
    case "medication_change":
      return "medication";
    case "symptom":
    case "condition":
      return "body";
    case "visit":
      return "calendar";
    case "result":
      return "scan";
    case "measurement":
      return "scan";
    case "document":
      return "folder";
    default:
      return "clinical-notes";
  }
}

export function TimelineView({
  initialProfileId,
  initialData,
  className = "",
}: TimelineViewProps) {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const [activeProfileId, setActiveProfileId] = useState<string | null>(
    initialProfileId ?? getActiveProfileId(),
  );

  // Filters
  const [period, setPeriod] = useState<PeriodFilter>("recent");
  const [selectedTypes, setSelectedTypes] = useState<Set<TypeFilter>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  // Pagination cursor
  const [cursor, setCursor] = useState<string | null>(null);
  const [accumulatedItems, setAccumulatedItems] = useState<HealthTimelineEventDto[]>([]);

  // Revision History Inspector modal state (HEALTH-004)
  const [inspectingEvent, setInspectingEvent] = useState<HealthTimelineEventDto | null>(null);

  const queryKey = queryKeys.profile(activeProfileId).health.timeline({
    period,
    types: Array.from(selectedTypes),
    cursor: cursor ?? undefined,
  });

  const { data, isLoading, isError, error, refetch } = useQuery<HealthTimelineResponseDto>({
    queryKey,
    queryFn: () =>
      v2Client.getHealthTimeline(
        {
          period,
          types: selectedTypes.size > 0 ? Array.from(selectedTypes) : undefined,
          cursor,
          search: searchQuery.trim() || undefined,
        },
        activeProfileId,
      ),
    initialData,
  });

  const items = useMemo(() => {
    const fetched = data?.items ?? [];
    if (!cursor) return fetched;
    // Combine without duplicates
    const ids = new Set(accumulatedItems.map((i) => i.id));
    const newItems = fetched.filter((i) => !ids.has(i.id));
    return [...accumulatedItems, ...newItems];
  }, [data?.items, cursor, accumulatedItems]);

  const filteredItems = useMemo(() => {
    if (!searchQuery.trim()) return items;
    const q = searchQuery.toLowerCase().trim();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        (item.summary && item.summary.toLowerCase().includes(q)),
    );
  }, [items, searchQuery]);

  const handleTypeToggle = (typeKey: TypeFilter) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(typeKey)) next.delete(typeKey);
      else next.add(typeKey);
      return next;
    });
    setCursor(null);
    setAccumulatedItems([]);
  };

  const handlePeriodChange = (newPeriod: PeriodFilter) => {
    setPeriod(newPeriod);
    setCursor(null);
    setAccumulatedItems([]);
  };

  const handleLoadMore = () => {
    if (data?.next_cursor) {
      setAccumulatedItems(items);
      setCursor(data.next_cursor);
    }
  };

  return (
    <div
      className={`timeline-view-container mx-auto max-w-5xl space-y-6 pb-12 ${className}`}
      data-testid="timeline-view"
    >
      {/* 1. Header */}
      <HealthPageHeader
        title={isEn ? "Health Timeline" : "Dòng thời gian sức khỏe"}
        subtitle={
          isEn
            ? "Longitudinal health records, medication changes, test results, visits, and clinical revisions."
            : "Lịch sử sự kiện y tế theo thời gian: thay đổi thuốc, kết quả xét nghiệm, lịch khám và lịch sử điều chỉnh."
        }
        backHref="/health"
        backLabel={isEn ? "Back to Health Overview" : "Quay lại Tổng quan"}
        locale={uiLanguage}
      />

      {/* 2. Filter Controls (HEALTH-005, HEALTH-006) */}
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-4 shadow-xs"
        data-testid="timeline-filters-section"
      >
        {/* Search Bar */}
        <div className="relative">
          <Field
            type="search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={isEn ? "Search timeline events..." : "Tìm kiếm sự kiện trong dòng thời gian..."}
            data-testid="timeline-search-input"
          />
        </div>

        {/* Period Filters */}
        <div className="space-y-1.5">
          <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
            {isEn ? "Time Period:" : "Khoảng thời gian:"}
          </span>
          <div
            role="radiogroup"
            aria-label={isEn ? "Time period filters" : "Bộ lọc thời gian"}
            className="flex flex-wrap gap-2"
          >
            {PERIOD_OPTIONS.map((opt) => {
              const active = period === opt.key;
              return (
                <button
                  key={opt.key}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => handlePeriodChange(opt.key)}
                  className={`inline-flex items-center rounded-[var(--radius-pill)] border px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "border-[color:var(--brand-600)] bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-xs"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid={`filter-period-${opt.key}`}
                >
                  {isEn ? opt.labelEn : opt.labelVi}
                </button>
              );
            })}
          </div>
        </div>

        {/* Type Filter Chips */}
        <div className="space-y-1.5">
          <span className="text-xs font-bold text-[var(--text-secondary)] uppercase tracking-wider">
            {isEn ? "Event Types:" : "Loại sự kiện:"}
          </span>
          <div
            role="group"
            aria-label={isEn ? "Event type filters" : "Bộ lọc loại sự kiện"}
            className="flex flex-wrap gap-2"
          >
            {TYPE_OPTIONS.map((opt) => {
              const active = selectedTypes.has(opt.key);
              return (
                <button
                  key={opt.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => handleTypeToggle(opt.key)}
                  className={`inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] border px-3 py-1.5 text-xs font-medium transition ${
                    active
                      ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-semibold"
                      : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid={`filter-type-${opt.key}`}
                >
                  <Icon name={opt.icon} size="0.9rem" />
                  <span>{isEn ? opt.labelEn : opt.labelVi}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* 3. Error state */}
      {isError && !data && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load timeline" : "Không thể tải dòng thời gian"}
          message={
            error instanceof Error ? error.message : isEn ? "Error loading timeline events." : "Lỗi khi tải các sự kiện."
          }
          onRetry={() => void refetch()}
        />
      )}

      {/* 4. Loading state */}
      {isLoading && !data && (
        <div className="space-y-4 animate-pulse" aria-busy="true" data-testid="timeline-skeleton">
          {[1, 2, 3, 4].map((n) => (
            <div
              key={n}
              className="h-28 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
            />
          ))}
        </div>
      )}

      {/* 5. Event List */}
      {!isLoading && filteredItems.length === 0 && (
        <EmptyState
          title={isEn ? "No events found" : "Không có sự kiện nào"}
          description={
            isEn
              ? "No timeline records match the selected filters or search query."
              : "Không có bản ghi nào phù hợp với bộ lọc hoặc từ khóa tìm kiếm đã chọn."
          }
          icon="progress"
        />
      )}

      {filteredItems.length > 0 && (
        <section
          aria-label={isEn ? "Timeline Events" : "Danh sách sự kiện"}
          className="space-y-4"
          data-testid="timeline-event-list"
        >
          <div className="relative border-l-2 border-[color:var(--shell-border)] pl-4 sm:pl-6 ml-3 sm:ml-4 space-y-6">
            {filteredItems.map((event) => {
              const iconName = getEventIcon(event.kind);
              const formattedDate = event.effective_at
                ? formatLocaleDate(uiLanguage, event.effective_at, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "";

              const hasRevisions = Boolean(event.revisions && event.revisions.length > 0);

              return (
                <article
                  key={event.id}
                  className="relative rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 transition hover:border-[color:var(--shell-border-strong)] shadow-xs"
                  data-testid={`timeline-event-${event.id}`}
                >
                  {/* Timeline dot */}
                  <span
                    className="absolute -left-[calc(1.1rem+1px)] sm:-left-[calc(1.6rem+1px)] top-5 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--surface-panel)] border-2 border-[color:var(--brand-600)] text-[var(--text-brand)]"
                    aria-hidden="true"
                  >
                    <Icon name={iconName} size="0.75rem" />
                  </span>

                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-bold text-sm sm:text-base text-[var(--text-primary)]">
                          {event.title}
                        </h3>
                        {event.state && (
                          <HealthStateBadge state={event.state as HealthState} locale={uiLanguage} />
                        )}
                        {event.source?.kind && (
                          <SourceBadge
                            sourceKind={event.source.kind}
                            verificationState={event.source.verification_state as any}
                            locale={uiLanguage}
                          />
                        )}
                      </div>

                      {event.summary && (
                        <p className="text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                          {event.summary}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-muted)] pt-1">
                        {formattedDate && (
                          <span className="inline-flex items-center gap-1">
                            <Icon name="calendar" size="0.8rem" />
                            <time dateTime={event.effective_at}>{formattedDate}</time>
                          </span>
                        )}
                        {event.source?.name && (
                          <span>• {event.source.name}</span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 self-end sm:self-start shrink-0">
                      {hasRevisions && (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon="progress"
                          onClick={() => setInspectingEvent(event)}
                          data-testid={`btn-inspect-revision-${event.id}`}
                        >
                          {isEn ? "History" : "Lịch sử sửa"}
                        </Button>
                      )}
                      {event.detail_href && (
                        <Link
                          href={event.detail_href}
                          className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                        >
                          <span>{isEn ? "Details" : "Chi tiết"}</span>
                          <Icon name="arrow-right" size="0.85rem" />
                        </Link>
                      )}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          {/* 6. Pagination Load More */}
          {data?.next_cursor && (
            <div className="flex justify-center pt-4" data-testid="timeline-pagination">
              <Button
                variant="secondary"
                size="md"
                onClick={handleLoadMore}
                loading={isLoading}
                icon="progress"
              >
                {isEn ? "Load More Events" : "Tải thêm sự kiện"}
              </Button>
            </div>
          )}
        </section>
      )}

      {/* 7. Revision History Inspector Modal (HEALTH-004) */}
      {inspectingEvent && (
        <Modal
          open={Boolean(inspectingEvent)}
          onClose={() => setInspectingEvent(null)}
          title={isEn ? "Revision & Audit History" : "Lịch sử sửa đổi & Kiểm toán"}
          description={
            isEn
              ? `Audit trail for: "${inspectingEvent.title}". Corrected facts retain full provenance.`
              : `Nhật ký chỉnh sửa của sự kiện: "${inspectingEvent.title}". Dữ liệu được bảo toàn lịch sử đầy đủ.`
          }
          size="md"
          closeLabel={isEn ? "Close" : "Đóng"}
          footer={
            <Button variant="secondary" onClick={() => setInspectingEvent(null)}>
              {isEn ? "Close" : "Đóng"}
            </Button>
          }
        >
          <div className="space-y-4" data-testid="revision-history-content">
            {(!inspectingEvent.revisions || inspectingEvent.revisions.length === 0) ? (
              <p className="text-sm text-[var(--text-muted)]">
                {isEn ? "No revisions recorded for this event." : "Chưa có bản sửa đổi nào cho sự kiện này."}
              </p>
            ) : (
              <div className="divide-y divide-[color:var(--shell-border)]/50">
                {inspectingEvent.revisions.map((rev: HealthTimelineRevisionDto, idx: number) => (
                  <div key={rev.id || idx} className="py-3 first:pt-0 last:pb-0 space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-[var(--text-primary)]">
                        {rev.modified_by || (isEn ? "User / Clinician" : "Người dùng / Bác sĩ")}
                      </span>
                      <time className="text-[var(--text-muted)]">{rev.modified_at}</time>
                    </div>
                    <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
                      {rev.summary}
                    </p>
                    {(rev.previous_value || rev.new_value) && (
                      <div className="mt-2 rounded-[var(--radius-md)] bg-[var(--surface-muted)]/40 p-2 text-xs font-mono space-y-1">
                        {rev.previous_value && (
                          <div className="text-[var(--status-danger-text)]">
                            - {rev.previous_value}
                          </div>
                        )}
                        {rev.new_value && (
                          <div className="text-[var(--status-ok-text)]">
                            + {rev.new_value}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}

export default TimelineView;
