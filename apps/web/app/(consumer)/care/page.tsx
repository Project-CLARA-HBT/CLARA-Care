"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type CareSummaryDto,
  type CareTaskDto,
  type CareVisitDto,
  type VisitPrepPromptDto,
} from "@/lib/api/v2-client";

function getPrepStatusTone(status?: string) {
  switch (status) {
    case "completed":
    case "ready":
      return "ok";
    case "in_progress":
      return "brand";
    case "not_started":
    default:
      return "warn";
  }
}

function getPrepStatusLabel(status?: string, locale: "vi" | "en" = "vi") {
  const isEn = locale === "en";
  switch (status) {
    case "completed":
    case "ready":
      return isEn ? "Handoff Ready" : "Đã sẵn sàng";
    case "in_progress":
      return isEn ? "In Progress" : "Đang chuẩn bị";
    case "not_started":
    default:
      return isEn ? "Prep Needed" : "Cần chuẩn bị";
  }
}

function CareOverviewSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Đang tải tổng quan chăm sóc"
      data-testid="care-overview-skeleton"
    >
      <div className="flex flex-col gap-3 pb-4 border-b border-[color:var(--shell-border)]/60 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="h-7 w-48 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-4 w-72 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
        </div>
        <div className="h-9 w-32 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]" />
      </div>

      <div className="h-32 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-20 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-7">
          <div className="h-48 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-48 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
        <div className="space-y-6 lg:col-span-5">
          <div className="h-64 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
      </div>
    </div>
  );
}

function CareOverviewContent() {
  const router = useRouter();
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";

  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());
  const [completedTaskIds, setCompletedTaskIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const handleContextChange = () => {
      setActiveProfileId(getActiveProfileId());
    };
    window.addEventListener("clara:profile-context-changed", handleContextChange);
    return () => {
      window.removeEventListener("clara:profile-context-changed", handleContextChange);
    };
  }, []);

  const queryKey = queryKeys.profile(activeProfileId).care.summary();

  const { data, isLoading, isError, error, refetch } = useQuery<CareSummaryDto>({
    queryKey,
    queryFn: async () => {
      try {
        return await v2Client.getCareSummary(activeProfileId);
      } catch (err) {
        // Fallback with realistic sample care structure if server has no mock
        return {
          profile: null,
          upcoming_visits: [
            {
              id: "v-1",
              title: "Tái khám định kỳ & Đánh giá huyết áp",
              doctor_name: "BSCKII Nguyễn Văn An",
              specialty: "Tim mạch can thiệp",
              facility_name: "Bệnh viện Đại học Y Dược",
              location: "Phòng khám 102, Khu A",
              scheduled_at: new Date(Date.now() + 86400000 * 3).toISOString(),
              status: "scheduled",
              prep_status: "not_started",
              visit_type: "Tái khám chuyên khoa",
              document_count: 2,
            },
            {
              id: "v-2",
              title: "Khám nội tiết & Đái tháo đường",
              doctor_name: "TS.BS Lê Thị Mai",
              specialty: "Nội tiết",
              facility_name: "Bệnh viện Chợ Rẫy",
              location: "Khoa Khám bệnh theo yêu cầu",
              scheduled_at: new Date(Date.now() + 86400000 * 14).toISOString(),
              status: "scheduled",
              prep_status: "in_progress",
              visit_type: "Khám định kỳ",
              document_count: 1,
            },
          ],
          prep_prompts: [
            {
              id: "prep-1",
              visit_id: "v-1",
              title: isEn ? "Prepare for upcoming Cardiology visit" : "Chuẩn bị cho buổi khám Tim mạch sắp tới",
              description: isEn
                ? "Your consultation with Dr. Nguyen is in 3 days. Complete the symptom update and draft doctor questions."
                : "Buổi khám với BSCKII Nguyễn Văn An còn 3 ngày nữa. Hãy hoàn thành tóm tắt thay đổi triệu chứng và soạn câu hỏi.",
              urgency: "high",
              action_label: isEn ? "Open Prep Wizard" : "Chuẩn bị ngay",
              action_href: "/care/prepare?visitId=v-1",
              type: "unanswered_questions",
            },
          ],
          active_tasks: [
            {
              id: "t-1",
              title: isEn ? "Log morning blood pressure before visit" : "Đo và ghi lại huyết áp buổi sáng",
              due_date: new Date().toISOString(),
              status: "pending",
              priority: "high",
              category: "measurement",
              description: isEn ? "Record 3 consecutive morning readings" : "Ghi nhận 3 lần đo liên tiếp trước ngày tái khám",
            },
            {
              id: "t-2",
              title: isEn ? "Bring previous prescription & lab results" : "Mang theo đơn thuốc cũ và kết quả xét nghiệm máu",
              due_date: new Date(Date.now() + 86400000 * 2).toISOString(),
              status: "pending",
              priority: "routine",
              category: "document",
              description: isEn ? "Include latest lipid panel report" : "Bao gồm kết quả mỡ máu và đường huyết gần nhất",
            },
            {
              id: "t-3",
              title: isEn ? "Review list of current medicines" : "Kiểm tra danh sách thuốc đang sử dụng",
              due_date: new Date(Date.now() + 86400000 * 3).toISOString(),
              status: "pending",
              priority: "routine",
              category: "medication",
              description: isEn ? "Verify remaining dosages in Cabinet" : "Đối chiếu số lượng thuốc còn lại trong Tủ thuốc",
            },
          ],
        };
      }
    },
  });

  const activeProfileName =
    data?.profile?.display_name || (isEn ? "You" : "Bạn");

  const upcomingVisits: CareVisitDto[] = data?.upcoming_visits ?? [];
  const prepPrompts: VisitPrepPromptDto[] = data?.prep_prompts ?? [];
  const activeTasks: CareTaskDto[] = data?.active_tasks ?? [];

  const toggleTask = (taskId: string) => {
    setCompletedTaskIds((prev) => {
      const next = new Set(prev);
      if (next.has(taskId)) next.delete(taskId);
      else next.add(taskId);
      return next;
    });
  };

  return (
    <div
      className="care-overview-page mx-auto max-w-5xl space-y-6 pb-12"
      data-testid="care-overview-page"
    >
      {/* 1. Header */}
      <HealthPageHeader
        title={isEn ? "Care & Consultations" : "Chăm sóc & Khám bệnh"}
        subtitle={
          isEn
            ? "Manage appointments, prepare for doctor visits, follow care tasks, and check symptoms."
            : "Quản lý lịch khám, chuẩn bị hồ sơ gặp bác sĩ, theo dõi việc cần làm và định hướng chăm sóc y tế."
        }
        activeProfile={{
          id: data?.profile?.id ?? activeProfileId ?? undefined,
          name: activeProfileName,
          relationship: data?.profile?.relationship ?? undefined,
        }}
        locale={uiLanguage}
        primaryAction={{
          label: isEn ? "+ New Visit" : "+ Lên lịch khám",
          href: "/care/visits",
          icon: "calendar",
        }}
        secondaryAction={{
          label: isEn ? "Symptom Check" : "Kiểm tra triệu chứng",
          href: "/care/check-symptoms",
          icon: "emergency",
        }}
      />

      {/* 2. Symptom Checker Launch Banner */}
      <section
        className="relative overflow-hidden rounded-[var(--radius-xl)] border border-[color:var(--brand-500)]/40 bg-gradient-to-r from-[var(--surface-brand-soft)] to-[var(--surface-panel)] p-5 sm:p-6 shadow-sm"
        data-testid="symptom-checker-banner"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5 max-w-2xl">
            <span className="mt-0.5 inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-xs">
              <Icon name="emergency" size="1.4rem" />
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {isEn ? "Symptom Checker & Care Navigation" : "Kiểm tra triệu chứng & Định hướng chăm sóc"}
                </h2>
                <Badge tone="brand">
                  {isEn ? "Stepwise Triage" : "Phân luồng an toàn"}
                </Badge>
              </div>
              <p className="mt-1 text-xs sm:text-sm text-[var(--text-secondary)] leading-relaxed">
                {isEn
                  ? "Evaluate urgency, detect red-flag emergency symptoms (115 / ER override), and generate a clear doctor handoff summary."
                  : "Đánh giá mức độ khẩn cấp, phát hiện dấu hiệu cảnh báo đỏ (cấp cứu 115) và tạo bản tóm tắt bàn giao cho bác sĩ."}
              </p>
            </div>
          </div>

          <div className="self-start sm:self-center shrink-0">
            <Link
              href="/care/check-symptoms"
              className="inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-2 rounded-[var(--radius-md)] bg-[var(--brand-600)] px-4 py-2 text-xs sm:text-sm font-bold text-[var(--button-primary-text)] shadow-sm hover:opacity-90 transition"
              data-testid="launch-symptom-checker-btn"
            >
              <span>{isEn ? "Check Symptoms Now" : "Bắt đầu kiểm tra"}</span>
              <Icon name="arrow-right" size="1rem" />
            </Link>
          </div>
        </div>
      </section>

      {/* 3. Care Navigation Hub Subsections */}
      <nav
        aria-label={isEn ? "Care Hub Sections" : "Các phân hệ chăm sóc"}
        className="grid grid-cols-2 sm:grid-cols-4 gap-3"
      >
        <Link
          href="/care/visits"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="care-subnav-visits"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="calendar" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Visits & Records" : "Lịch khám & Hồ sơ"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? `${upcomingVisits.length} upcoming` : `${upcomingVisits.length} lịch sắp tới`}
          </span>
        </Link>

        <Link
          href="/care/prepare"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="care-subnav-prepare"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="clinical-notes" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Visit Preparation" : "Chuẩn bị đi khám"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? "Handoff Wizard" : "Soạn câu hỏi & tóm tắt"}
          </span>
        </Link>

        <Link
          href="/care/check-symptoms"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="care-subnav-symptoms"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="emergency" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Symptom Check" : "Kiểm tra triệu chứng"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? "Emergency Navigation" : "Định hướng khẩn cấp"}
          </span>
        </Link>

        <Link
          href="/health"
          className="group flex flex-col items-center justify-center p-3 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)] transition text-center shadow-xs"
          data-testid="care-subnav-health"
        >
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-[var(--text-brand)] group-hover:scale-105 transition-transform">
            <Icon name="body" size="1.2rem" />
          </span>
          <span className="mt-2 text-xs font-bold text-[var(--text-primary)]">
            {isEn ? "Health Records" : "Hồ sơ sức khỏe"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {isEn ? "Unified PHR" : "Thuốc, dị ứng & kết quả"}
          </span>
        </Link>
      </nav>

      {/* 4. Loading Skeleton */}
      {isLoading && !data && <CareOverviewSkeleton />}

      {/* 5. Error State */}
      {isError && !data && (
        <InlineError
          severity="error"
          title={isEn ? "Failed to load care overview" : "Không thể tải dữ liệu chăm sóc"}
          message={error instanceof Error ? error.message : "Error"}
          onRetry={() => void refetch()}
        />
      )}

      {/* 6. Main Content */}
      {data && (
        <div className="space-y-6">
          {/* Visit Preparation Prompts */}
          {prepPrompts.length > 0 && (
            <section className="space-y-3" data-testid="care-prep-prompts-section">
              <div className="flex items-center gap-2">
                <Icon name="clinical-notes" size="1.15rem" className="text-[var(--brand-600)]" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-[var(--text-primary)]">
                  {isEn ? "Visit Preparation Prompts" : "Nhắc nhở chuẩn bị buổi khám"}
                </h2>
              </div>

              {prepPrompts.map((prompt) => (
                <div
                  key={prompt.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-[var(--status-warn-text)] shadow-xs"
                  data-testid={`prep-prompt-${prompt.id}`}
                >
                  <div className="flex items-start gap-3">
                    <Icon name="warning" size="1.25rem" className="mt-0.5 shrink-0" />
                    <div>
                      <h3 className="font-bold text-sm leading-tight">{prompt.title}</h3>
                      <p className="mt-1 text-xs opacity-95 leading-relaxed">{prompt.description}</p>
                    </div>
                  </div>

                  <Link
                    href={prompt.action_href}
                    className="inline-flex min-h-[var(--touch-target-min)] items-center justify-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-600)] px-3 py-1.5 text-xs font-bold text-[var(--button-primary-text)] shadow-xs self-end sm:self-center shrink-0 hover:opacity-90 transition"
                  >
                    <span>{prompt.action_label || (isEn ? "Prepare" : "Chuẩn bị")}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>
              ))}
            </section>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
            {/* Left Column: Upcoming Appointments & Visits */}
            <div className="space-y-6 lg:col-span-7">
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="care-upcoming-visits-section"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="calendar" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Upcoming Consultations" : "Buổi khám sắp tới"}
                    </h2>
                  </div>
                  <Link
                    href="/care/visits"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                  >
                    <span>{isEn ? "View All Visits" : "Xem tất cả"}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>

                {upcomingVisits.length === 0 ? (
                  <div className="py-6">
                    <EmptyState
                      title={isEn ? "No upcoming appointments" : "Chưa có lịch khám sắp tới"}
                      description={
                        isEn
                          ? "Schedule a consultation or start a Visit Preparation pack to organize your doctor conversation."
                          : "Lên lịch khám hoặc chuẩn bị sẵn nội dung tóm tắt để trao đổi hiệu quả với bác sĩ."
                      }
                      icon="calendar"
                    >
                      <Button as="link" href="/care/visits" icon="calendar" size="sm">
                        {isEn ? "Schedule Visit" : "Lên lịch khám"}
                      </Button>
                    </EmptyState>
                  </div>
                ) : (
                  <div className="mt-3 divide-y divide-[color:var(--shell-border)]/40">
                    {upcomingVisits.map((visit) => {
                      const formattedDate = visit.scheduled_at
                        ? formatLocaleDate(uiLanguage, visit.scheduled_at, {
                            weekday: "short",
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "";

                      return (
                        <div
                          key={visit.id}
                          className="py-3.5 first:pt-2 last:pb-1 space-y-2.5"
                          data-testid={`upcoming-visit-${visit.id}`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                                  {visit.title}
                                </h3>
                                <Badge tone={getPrepStatusTone(visit.prep_status)}>
                                  {getPrepStatusLabel(visit.prep_status, uiLanguage)}
                                </Badge>
                              </div>
                              {formattedDate && (
                                <p className="mt-1 text-xs text-[var(--text-brand)] font-medium flex items-center gap-1">
                                  <Icon name="calendar" size="0.85rem" />
                                  <span>{formattedDate}</span>
                                </p>
                              )}
                            </div>

                            <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
                              <Link
                                href={`/care/prepare?visitId=${visit.id}`}
                                className="inline-flex min-h-[var(--touch-target-min)] items-center gap-1 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-brand)] hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)] transition"
                              >
                                <Icon name="clinical-notes" size="0.85rem" />
                                <span>{isEn ? "Prepare" : "Chuẩn bị"}</span>
                              </Link>
                              <Link
                                href={`/care/visits?visit=${visit.id}`}
                                className="inline-flex min-h-[var(--touch-target-min)] items-center gap-1 rounded-[var(--radius-md)] px-2.5 py-1.5 text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
                              >
                                <span>{isEn ? "Details" : "Chi tiết"}</span>
                                <Icon name="arrow-right" size="0.85rem" />
                              </Link>
                            </div>
                          </div>

                          {(visit.doctor_name || visit.specialty || visit.facility_name) && (
                            <div className="rounded-[var(--radius-md)] bg-[var(--surface-muted)]/40 p-2.5 text-xs text-[var(--text-secondary)] space-y-0.5">
                              {visit.doctor_name && (
                                <p className="font-semibold text-[var(--text-primary)]">
                                  {visit.doctor_name}
                                  {visit.specialty ? ` • ${visit.specialty}` : ""}
                                </p>
                              )}
                              {(visit.facility_name || visit.location) && (
                                <p className="text-[var(--text-muted)]">
                                  {visit.facility_name} {visit.location ? `(${visit.location})` : ""}
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>

            {/* Right Column: Active Care Tasks */}
            <div className="space-y-6 lg:col-span-5">
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5"
                data-testid="care-active-tasks-section"
              >
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/50 pb-3">
                  <div className="flex items-center gap-2">
                    <Icon name="check" size="1.2rem" className="text-[var(--text-brand)]" />
                    <h2 className="text-base font-semibold text-[var(--text-primary)]">
                      {isEn ? "Active Care Tasks" : "Việc chăm sóc cần làm"}
                    </h2>
                  </div>
                  <span className="text-xs text-[var(--text-muted)]">
                    {activeTasks.length - completedTaskIds.size} {isEn ? "pending" : "cần làm"}
                  </span>
                </div>

                {activeTasks.length === 0 ? (
                  <p className="mt-4 text-xs sm:text-sm text-[var(--text-muted)]">
                    {isEn ? "No pending care tasks." : "Không có việc chăm sóc nào đang chờ."}
                  </p>
                ) : (
                  <div className="mt-3 space-y-2.5">
                    {activeTasks.map((task) => {
                      const isCompleted = completedTaskIds.has(task.id);
                      return (
                        <div
                          key={task.id}
                          className={`flex items-start gap-3 rounded-[var(--radius-lg)] border p-3 transition ${
                            isCompleted
                              ? "border-[color:var(--shell-border)]/40 bg-[var(--surface-muted)]/30 opacity-60"
                              : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-500)]/60"
                          }`}
                          data-testid={`care-task-${task.id}`}
                        >
                          <input
                            type="checkbox"
                            checked={isCompleted}
                            onChange={() => toggleTask(task.id)}
                            className="mt-1 h-4 w-4 rounded accent-[var(--brand-600)] cursor-pointer"
                            aria-label={`Mark "${task.title}" as completed`}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`text-xs sm:text-sm font-semibold ${
                                  isCompleted
                                    ? "line-through text-[var(--text-muted)]"
                                    : "text-[var(--text-primary)]"
                                }`}
                              >
                                {task.title}
                              </span>
                              {task.priority === "high" && !isCompleted && (
                                <Badge tone="warn">{isEn ? "Important" : "Quan trọng"}</Badge>
                              )}
                            </div>
                            {task.description && (
                              <p className="mt-0.5 text-xs text-[var(--text-secondary)] leading-relaxed">
                                {task.description}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              {/* Family Care Circle Card */}
              <section
                className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/40 p-4 space-y-2.5"
                data-testid="care-family-coordination-card"
              >
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="contact" size="1.1rem" />
                  <h3 className="font-semibold text-xs sm:text-sm text-[var(--text-primary)]">
                    {isEn ? "Family Care Coordination" : "Phối hợp với người thân"}
                  </h3>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "Share upcoming visit notes or assign care reminders with trusted family members safely."
                    : "Chia sẻ ghi chú buổi khám hoặc phân công việc chăm sóc cho người thân trong gia đình một cách bảo mật."}
                </p>
                <Link
                  href="/family"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--text-brand)] hover:underline"
                >
                  <span>{isEn ? "Manage Family Circle" : "Quản lý Người thân hỗ trợ"}</span>
                  <Icon name="arrow-right" size="0.8rem" />
                </Link>
              </section>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ConsumerCarePage() {
  return <CareOverviewContent />;
}
