"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import {
  PrimaryActionCard,
  type ActionCardSeverity,
} from "@/components/consumer/primary-action-card";
import { AskBar } from "@/components/ask/ask-bar";
import { SourceBadge } from "@/components/health/source-badge";
import { InlineError } from "@/components/shared/inline-error";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";
import { UniversalCaptureModal } from "@/components/capture/universal-capture-modal";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type HomeAlertDto,
  type HomeOverviewDto,
  type HomeRecentChangeDto,
  type HomeTodayItemDto,
  type HomeTopActionDto,
} from "@/lib/api/v2-client";
import {
  trackHomeActionClicked,
  trackHomeAlertClicked,
  trackHomeRecentChangeClicked,
  trackHomeScheduleItemClicked,
  trackHomeViewed,
} from "@/lib/analytics/events";

export interface HomeViewProps {
  initialProfileId?: string | null;
  initialData?: HomeOverviewDto;
  className?: string;
}

function mapSeverity(severity?: string | null): ActionCardSeverity {
  switch (severity?.toLowerCase()) {
    case "critical":
      return "critical";
    case "urgent":
      return "urgent";
    case "high":
      return "high";
    case "warning":
    case "attention":
      return "warning";
    case "moderate":
      return "moderate";
    case "routine":
      return "routine";
    case "info":
      return "info";
    case "normal":
    default:
      return "normal";
  }
}

function formatItemTime(timeString?: string | null, locale: "vi" | "en" = "vi"): string {
  if (!timeString) return "";
  if (/^\d{1,2}:\d{2}$/.test(timeString)) return timeString;
  const parsed = new Date(timeString);
  if (isNaN(parsed.getTime())) return timeString;
  return formatLocaleDate(locale, parsed, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Loading skeleton component for Home.
 */
export function HomeSkeleton() {
  return (
    <div
      className="home-view-skeleton space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Đang tải dữ liệu tổng quan"
      data-testid="home-skeleton-loading"
    >
      <div className="flex flex-col gap-3 pb-4 border-b border-[color:var(--shell-border)]/60 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="h-7 w-40 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-4 w-64 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
        </div>
        <div className="h-9 w-32 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
      </div>

      <div className="h-14 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />

      <div className="h-40 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-7">
          <div className="h-6 w-48 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-24 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-24 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
        <div className="space-y-4 lg:col-span-5">
          <div className="h-6 w-36 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-20 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-20 w-full rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
      </div>
    </div>
  );
}

/**
 * Safety Alerts banner section.
 * Per HOME-005, critical safety alerts outrank engagement.
 */
export function AlertsBanner({
  alerts,
  locale = "vi",
  onDismiss,
}: {
  alerts: HomeAlertDto[];
  locale?: "vi" | "en";
  onDismiss?: (id: string) => void;
}) {
  const sorted = useMemo(() => {
    const priority = (s: string) =>
      s === "critical" || s === "error" ? 3 : s === "warning" ? 2 : 1;
    return [...alerts].sort((a, b) => priority(b.severity) - priority(a.severity));
  }, [alerts]);

  if (!sorted.length) return null;

  return (
    <section
      className="space-y-3"
      data-testid="home-alerts-banner"
      aria-label={t(locale, "home.alerts.title")}
    >
      {sorted.map((alert) => {
        const isCritical = alert.severity === "critical" || alert.severity === "error";
        const isWarn = alert.severity === "warning";
        const borderClass = isCritical
          ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
          : isWarn
            ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
            : "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]";

        return (
          <div
            key={alert.id}
            role="alert"
            className={`flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-[var(--radius-lg)] border p-3.5 sm:p-4 text-sm shadow-sm transition-all ${borderClass}`}
            data-testid={`home-alert-${alert.id}`}
          >
            <div className="flex items-start gap-3 min-w-0 flex-1">
              <span className="mt-0.5 inline-flex shrink-0">
                <Icon
                  name={isCritical ? "warning" : isWarn ? "warning" : "clinical-notes"}
                  size="1.25rem"
                />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-bold leading-tight">{alert.title}</h3>
                  {isCritical && (
                    <Badge tone="danger" icon="warning">
                      {t(locale, "home.alerts.criticalBadge")}
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-xs sm:text-sm leading-relaxed opacity-95">
                  {alert.message}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
              {alert.href && (
                <Link
                  href={alert.href}
                  onClick={() =>
                    trackHomeAlertClicked({
                      severity: alert.severity,
                      alertKind: alert.kind,
                    })
                  }
                  className="fluent-button-primary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold shadow-xs"
                >
                  <span>
                    {alert.action_label || (locale === "en" ? "View details" : "Xem chi tiết")}
                  </span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              )}
              {alert.dismissible && onDismiss && (
                <button
                  type="button"
                  onClick={() => onDismiss(alert.id)}
                  aria-label={locale === "en" ? "Dismiss alert" : "Đóng cảnh báo"}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius-md)] opacity-70 hover:opacity-100 transition-opacity"
                >
                  <Icon name="close" size="1rem" />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </section>
  );
}

/**
 * Today's schedule section for due medications, visits, and care tasks.
 */
export function TodayScheduleSection({
  items,
  locale = "vi",
}: {
  items: HomeTodayItemDto[];
  locale?: "vi" | "en";
}) {
  const isEn = locale === "en";

  if (!items.length) {
    return (
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
        data-testid="home-today-schedule"
      >
        <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
          <Icon name="calendar" size="1.2rem" className="text-[var(--text-brand)]" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {t(locale, "home.schedule.title")}
          </h2>
        </div>
        <p className="mt-4 text-xs sm:text-sm text-[var(--text-secondary)]">
          {t(locale, "home.schedule.empty")}
        </p>
      </section>
    );
  }

  const pendingCount = items.filter(
    (i) => i.status === "pending" || i.status === "overdue" || !i.status,
  ).length;

  return (
    <section
      className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
      data-testid="home-today-schedule"
    >
      <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
        <div className="flex items-center gap-2">
          <Icon name="calendar" size="1.2rem" className="text-[var(--text-brand)]" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {t(locale, "home.schedule.title")}
          </h2>
        </div>
        {pendingCount > 0 ? (
          <Badge tone="brand">
            {isEn ? `${pendingCount} due` : `${pendingCount} việc cần làm`}
          </Badge>
        ) : (
          <Badge tone="ok" icon="check">
            {t(locale, "home.schedule.allCompleted")}
          </Badge>
        )}
      </div>

      <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
        {items.map((item) => {
          const isMed = item.kind === "medication";
          const isVisit = item.kind === "visit";
          const itemIcon: IconName = isMed ? "medication" : isVisit ? "calendar" : "check";
          const targetHref =
            item.href ||
            (isMed ? "/health/medications" : isVisit ? "/care/visits" : "/care");
          const formattedTime = formatItemTime(item.time || item.due_time, locale);
          const isOverdue = item.status === "overdue";
          const isCompleted = item.status === "completed";

          return (
            <div
              key={item.id}
              className="group flex flex-col sm:flex-row sm:items-center justify-between gap-3 py-3 transition-colors hover:bg-[var(--surface-muted)]/50 rounded-[var(--radius-md)] px-2 -mx-2"
              data-testid={`today-schedule-item-${item.id}`}
            >
              <div className="flex items-start gap-3 min-w-0 flex-1">
                <span className="mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:bg-[var(--surface-panel)]">
                  <Icon name={itemIcon} size="1.1rem" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-sm text-[var(--text-primary)]">
                      {item.title}
                    </span>
                    {formattedTime && (
                      <span className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-secondary)]">
                        <Icon name="calendar" size="0.75rem" />
                        <span>{formattedTime}</span>
                      </span>
                    )}
                    {isOverdue && (
                      <Badge tone="danger" icon="warning">
                        {isEn ? "Overdue" : "Quá hạn"}
                      </Badge>
                    )}
                    {isCompleted && (
                      <Badge tone="ok" icon="check">
                        {isEn ? "Completed" : "Đã xong"}
                      </Badge>
                    )}
                  </div>

                  {(item.dosage || item.instructions || item.subtitle || item.description) && (
                    <p className="mt-1 text-xs text-[var(--text-secondary)] leading-relaxed">
                      {item.dosage ? `${item.dosage} • ` : ""}
                      {item.instructions || item.subtitle || item.description}
                    </p>
                  )}

                  {(item.doctor_name || item.location) && (
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                      {item.doctor_name && <span>{item.doctor_name}</span>}
                      {item.location && <span>• {item.location}</span>}
                    </div>
                  )}
                </div>
              </div>

              <div className="self-end sm:self-center shrink-0">
                <Link
                  href={targetHref}
                  onClick={() => trackHomeScheduleItemClicked({ itemKind: item.kind })}
                  className="fluent-button-secondary inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                >
                  <span>{isEn ? "Open" : "Chi tiết"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/**
 * Recent Changes section rendering new results, documents, and confirmed updates.
 */
export function RecentChangesSection({
  changes,
  locale = "vi",
}: {
  changes: HomeRecentChangeDto[];
  locale?: "vi" | "en";
}) {
  const isEn = locale === "en";

  if (!changes.length) {
    return (
      <section
        className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
        data-testid="home-recent-changes"
      >
        <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/50 pb-3">
          <Icon name="progress" size="1.2rem" className="text-[var(--text-brand)]" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {t(locale, "home.recentChanges.title")}
          </h2>
        </div>
        <p className="mt-4 text-xs sm:text-sm text-[var(--text-secondary)]">
          {t(locale, "home.recentChanges.empty")}
        </p>
      </section>
    );
  }

  return (
    <section
      className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
      data-testid="home-recent-changes"
    >
      <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
        <div className="flex items-center gap-2">
          <Icon name="progress" size="1.2rem" className="text-[var(--text-brand)]" />
          <h2 className="text-base font-semibold text-[var(--text-primary)]">
            {t(locale, "home.recentChanges.title")}
          </h2>
        </div>
        <span className="text-xs text-[var(--text-muted)]">
          {isEn ? `${changes.length} updates` : `${changes.length} cập nhật`}
        </span>
      </div>

      <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
        {changes.map((change) => {
          const targetHref =
            change.href ||
            (change.kind === "medication"
              ? "/health/medications"
              : change.kind === "document"
                ? "/health"
                : "/health/timeline");
          const formattedDate = formatItemTime(change.timestamp, locale);

          return (
            <div
              key={change.id}
              className="py-3 first:pt-2 last:pb-1"
              data-testid={`recent-change-item-${change.id}`}
            >
              <div className="flex flex-col gap-1.5">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={targetHref}
                    onClick={() => trackHomeRecentChangeClicked({ changeKind: change.kind })}
                    className="font-semibold text-sm text-[var(--text-primary)] hover:text-[var(--text-brand)] hover:underline leading-snug"
                  >
                    {change.title}
                  </Link>
                  {formattedDate && (
                    <span className="text-[11px] text-[var(--text-muted)] shrink-0">
                      {formattedDate}
                    </span>
                  )}
                </div>

                {change.description && (
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                    {change.description}
                  </p>
                )}

                <div className="mt-1 flex flex-wrap items-center gap-2">
                  {change.source_kind && (
                    <SourceBadge
                      sourceKind={change.source_kind}
                      verificationState={change.verification_state as any}
                      locale={locale}
                    />
                  )}
                  {change.source_name && !change.source_kind && (
                    <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                      {change.source_name}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/**
 * Actionable empty state ("Caught Up") when no tasks are due.
 * Per HOME-006 / HOME-008: Explains what user can do next without implying false health reassurance from absence of data.
 */
export function CaughtUpState({ locale = "vi" }: { locale?: "vi" | "en" }) {
  const isEn = locale === "en";

  return (
    <section className="space-y-4" data-testid="caught-up-state">
      <EmptyState
        title={t(locale, "home.caughtUp.title")}
        description={t(locale, "home.caughtUp.description")}
        icon="check"
        compact={false}
      >
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left">
          <Link
            href="/ask"
            onClick={() =>
              trackHomeActionClicked({ actionKind: "caught_up_ask", targetHref: "/ask" })
            }
            className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 hover:border-[color:var(--brand-500)] transition-colors"
            data-testid="caught-up-action-ask"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
              <Icon name="search" size="1.1rem" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-[var(--text-primary)]">
                {t(locale, "home.caughtUp.askAction")}
              </div>
              <div className="text-[11px] text-[var(--text-secondary)] truncate">
                {isEn ? "Ask health questions" : "Hỏi đáp triệu chứng & thuốc"}
              </div>
            </div>
          </Link>

          <Link
            href="/health/medications"
            onClick={() =>
              trackHomeActionClicked({
                actionKind: "caught_up_meds",
                targetHref: "/health/medications",
              })
            }
            className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 hover:border-[color:var(--brand-500)] transition-colors"
            data-testid="caught-up-action-meds"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
              <Icon name="medication" size="1.1rem" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-[var(--text-primary)]">
                {t(locale, "home.caughtUp.medsAction")}
              </div>
              <div className="text-[11px] text-[var(--text-secondary)] truncate">
                {isEn ? "Review prescriptions" : "Xem đơn thuốc & tương tác"}
              </div>
            </div>
          </Link>

          <Link
            href="/health"
            onClick={() =>
              trackHomeActionClicked({ actionKind: "caught_up_health", targetHref: "/health" })
            }
            className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 hover:border-[color:var(--brand-500)] transition-colors"
            data-testid="caught-up-action-health"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
              <Icon name="user-card" size="1.1rem" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-[var(--text-primary)]">
                {t(locale, "home.caughtUp.healthAction")}
              </div>
              <div className="text-[11px] text-[var(--text-secondary)] truncate">
                {isEn ? "Timeline & allergies" : "Dị ứng & chỉ số sức khỏe"}
              </div>
            </div>
          </Link>

          <Link
            href="/care/visits"
            onClick={() =>
              trackHomeActionClicked({ actionKind: "caught_up_care", targetHref: "/care/visits" })
            }
            className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 hover:border-[color:var(--brand-500)] transition-colors"
            data-testid="caught-up-action-care"
          >
            <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-md)] bg-[var(--surface-muted)] text-[var(--text-brand)]">
              <Icon name="calendar" size="1.1rem" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="text-xs font-semibold text-[var(--text-primary)]">
                {t(locale, "home.caughtUp.careAction")}
              </div>
              <div className="text-[11px] text-[var(--text-secondary)] truncate">
                {isEn ? "Upcoming consultations" : "Chuẩn bị đi khám"}
              </div>
            </div>
          </Link>
        </div>
      </EmptyState>
    </section>
  );
}

/**
 * Canonical Consumer Home View component.
 */
export function HomeView({
  initialProfileId,
  initialData,
  className = "",
}: HomeViewProps) {
  const router = useRouter();
  const uiLanguage = useUILanguage();
  const [activeProfileId, setActiveProfileId] = useState<string | null>(
    initialProfileId ?? getActiveProfileId(),
  );
  const [showCaptureModal, setShowCaptureModal] = useState(false);
  const [dismissedAlertIds, setDismissedAlertIds] = useState<Set<string>>(new Set());

  // Track home view once mounted
  useEffect(() => {
    trackHomeViewed();
  }, []);

  // Update profile ID when local context changes
  useEffect(() => {
    const handleContextChange = () => {
      setActiveProfileId(getActiveProfileId());
    };
    window.addEventListener("clara:profile-context-changed", handleContextChange);
    return () => {
      window.removeEventListener("clara:profile-context-changed", handleContextChange);
    };
  }, []);

  const queryKey = queryKeys.home.overview(activeProfileId);

  const { data, isLoading, isError, error, refetch } = useQuery<HomeOverviewDto>({
    queryKey,
    queryFn: () => v2Client.getHome(activeProfileId),
    initialData,
  });

  const activeProfileName =
    data?.profile?.display_name ||
    (uiLanguage === "en" ? "You" : "Bạn");

  const visibleAlerts = useMemo(() => {
    return (data?.alerts ?? []).filter((a) => !dismissedAlertIds.has(a.id));
  }, [data?.alerts, dismissedAlertIds]);

  const handleDismissAlert = (id: string) => {
    setDismissedAlertIds((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  };

  const topAction: HomeTopActionDto | null = data?.top_action ?? null;
  const todayItems: HomeTodayItemDto[] = data?.today ?? [];
  const recentChanges: HomeRecentChangeDto[] = data?.recent_changes ?? [];

  const isCaughtUp =
    !topAction &&
    todayItems.length === 0 &&
    visibleAlerts.length === 0 &&
    !isLoading &&
    !isError;

  return (
    <div
      className={`canonical-home-view mx-auto max-w-5xl space-y-6 pb-12 ${className}`}
      data-testid="consumer-home-view"
    >
      {/* 1. Header with active profile name */}
      <HealthPageHeader
        title={t(uiLanguage, "home.title")}
        subtitle={t(uiLanguage, "home.subtitle")}
        activeProfile={{
          id: data?.profile?.id ?? activeProfileId ?? undefined,
          name: activeProfileName,
          relationship: data?.profile?.relationship ?? undefined,
        }}
        primaryAction={{
          label: uiLanguage === "en" ? "Add health info" : "Thêm thông tin sức khỏe",
          icon: "camera",
          onClick: () => setShowCaptureModal(true),
        }}
        locale={uiLanguage}
      />

      <UniversalCaptureModal
        open={showCaptureModal}
        onClose={() => setShowCaptureModal(false)}
        locale={uiLanguage}
        onCommitSuccess={() => void refetch()}
      />

      {/* 2. Prominent AskBar */}
      <section className="relative" data-testid="home-ask-section">
        <AskBar
          variant="hero"
          locale={uiLanguage}
          targetHref="/ask"
          placeholder={t(uiLanguage, "home.askPlaceholder")}
          onSubmit={(query, actionType) => {
            trackHomeActionClicked({
              actionKind: `ask_${actionType ?? "text"}`,
              targetHref: "/ask",
            });
            const url = query.trim()
              ? `/ask?q=${encodeURIComponent(query.trim())}`
              : "/ask";
            router.push(url);
          }}
          onCameraClick={() => {
            trackHomeActionClicked({
              actionKind: "ask_camera",
              targetHref: "/ask?action=camera",
            });
            router.push("/ask?action=camera");
          }}
          onFileClick={() => {
            trackHomeActionClicked({
              actionKind: "ask_file",
              targetHref: "/ask?action=file",
            });
            router.push("/ask?action=file");
          }}
          onVoiceClick={() => {
            trackHomeActionClicked({
              actionKind: "ask_voice",
              targetHref: "/ask?action=voice",
            });
            router.push("/ask?action=voice");
          }}
        />
      </section>

      {/* 3. Skeleton Loading State */}
      {isLoading && !data && <HomeSkeleton />}

      {/* 4. InlineError when request fails */}
      {isError && !data && (
        <section data-testid="home-error-section">
          <InlineError
            severity="error"
            title={t(uiLanguage, "home.error.title")}
            message={t(uiLanguage, "home.error.description")}
            onRetry={() => void refetch()}
            retryLabel={t(uiLanguage, "home.error.retry")}
            className="mt-2"
          />
        </section>
      )}

      {/* 5. Main Content when data is present */}
      {data && (
        <div className="space-y-6">
          {/* Alerts Banner */}
          {visibleAlerts.length > 0 && (
            <AlertsBanner
              alerts={visibleAlerts}
              locale={uiLanguage}
              onDismiss={handleDismissAlert}
            />
          )}

          {/* Primary Action Card rendering top_action */}
          {topAction && (
            <section data-testid="home-top-action-section">
              <PrimaryActionCard
                title={
                  topAction.title ||
                  (topAction.title_key
                    ? t(uiLanguage, topAction.title_key as any)
                    : t(uiLanguage, "home.topAction.title"))
                }
                description={topAction.description ?? undefined}
                severity={mapSeverity(topAction.severity)}
                actionLabel={
                  topAction.action_label ||
                  (uiLanguage === "en" ? "Take action" : "Thực hiện ngay")
                }
                actionHref={topAction.href}
                onAction={() => {
                  trackHomeActionClicked({
                    actionKind: topAction.kind,
                    severity: String(topAction.severity),
                    targetHref: topAction.href,
                  });
                }}
                secondaryActionLabel={topAction.secondary_action_label ?? undefined}
                secondaryActionHref={topAction.secondary_href ?? undefined}
                onSecondaryAction={() => {
                  if (topAction.secondary_href) {
                    trackHomeActionClicked({
                      actionKind: `${topAction.kind}_secondary`,
                      targetHref: topAction.secondary_href,
                    });
                  }
                }}
                icon={
                  topAction.icon ||
                  (topAction.kind === "medication"
                    ? "medication"
                    : topAction.kind === "visit"
                      ? "calendar"
                      : topAction.kind === "result"
                        ? "scan"
                        : "clinical-notes")
                }
                locale={uiLanguage}
              />
            </section>
          )}

          {/* Actionable Caught Up state if no tasks/actions/alerts */}
          {isCaughtUp ? (
            <CaughtUpState locale={uiLanguage} />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Today Schedule Section */}
              <div className="space-y-4 lg:col-span-7">
                <TodayScheduleSection items={todayItems} locale={uiLanguage} />
              </div>

              {/* Recent Changes Section */}
              <div className="space-y-4 lg:col-span-5">
                <RecentChangesSection changes={recentChanges} locale={uiLanguage} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default HomeView;
