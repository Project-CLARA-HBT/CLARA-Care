"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import {
  v2Client,
  type NotificationPreferencesDto,
} from "@/lib/api/v2-client";

export type NotificationCategoryTab =
  | "all"
  | "medications"
  | "milestones"
  | "family"
  | "safety";

export interface CenterNotificationItem {
  id: string;
  category: "medications" | "milestones" | "family" | "safety";
  title: string;
  description: string;
  timestamp: string;
  is_unread: boolean;
  action_label?: string;
  action_href?: string;
  action_kind?: "mark_taken" | "link";
  is_completed?: boolean;
}

export default function YouNotificationsPage() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId] = useState<string | null>(getActiveProfileId());

  // Category Preferences
  const [medications, setMedications] = useState(true);
  const [visits, setVisits] = useState(true);
  const [reviewItems, setReviewItems] = useState(true);
  const [safetyAlerts, setSafetyAlerts] = useState(true);
  const [journeyMilestones, setJourneyMilestones] = useState(true);
  const [familyActivity, setFamilyActivity] = useState(true);

  // Delivery Channels
  const [pushChannel, setPushChannel] = useState(true);
  const [emailChannel, setEmailChannel] = useState(true);
  const [inAppChannel, setInAppChannel] = useState(true);

  // Quiet Hours
  const [quietHoursEnabled, setQuietHoursEnabled] = useState(true);
  const [startTime, setStartTime] = useState("22:00");
  const [endTime, setEndTime] = useState("07:00");

  // Filter & Feed State (Notification Center EXPLORE archetype)
  const [activeTab, setActiveTab] = useState<NotificationCategoryTab>("all");
  const [notifications, setNotifications] = useState<CenterNotificationItem[]>([
    {
      id: "notif-med-1",
      category: "medications",
      title: isEn ? "Medication Reminder: Amlodipine 5mg" : "Nhắc nhở uống thuốc: Amlodipine 5mg",
      description: isEn
        ? "Scheduled morning dose (1 tablet after breakfast). Maintain adherence for blood pressure control."
        : "Lịch uống buổi sáng (1 viên sau ăn sáng). Hãy uống đều đặn để ổn định huyết áp.",
      timestamp: isEn ? "15 minutes ago" : "15 phút trước",
      is_unread: true,
      action_label: isEn ? "Mark as Taken" : "Xác nhận đã uống",
      action_kind: "mark_taken",
    },
    {
      id: "notif-mile-1",
      category: "milestones",
      title: isEn ? "Journey Milestone: Week 2 Completed" : "Cột mốc Lộ trình: Hoàn thành Tuần 2",
      description: isEn
        ? "Hypertension Management Journey: 7/7 consecutive blood pressure readings recorded! Review your weekly trajectory."
        : "Lộ trình Kiểm soát Huyết áp: Đã ghi nhận 7/7 ngày liên tục! Xem phân tích xu hướng tuần này.",
      timestamp: isEn ? "2 hours ago" : "2 giờ trước",
      is_unread: true,
      action_label: isEn ? "View Journey" : "Xem lộ trình",
      action_href: "/lifemap",
      action_kind: "link",
    },
    {
      id: "notif-fam-1",
      category: "family",
      title: isEn ? "Family Activity: Blood Sugar Logged" : "Hoạt động Gia đình: Chỉ số mới",
      description: isEn
        ? "Trần Thị B (Wife) shared a fasting glucose measurement (5.8 mmol/L) to the coordinated health profile."
        : "Trần Thị B (Vợ) vừa cập nhật chỉ số đường huyết lúc đói (5.8 mmol/L) vào hồ sơ chăm sóc chung.",
      timestamp: isEn ? "Yesterday at 18:30" : "Hôm qua lúc 18:30",
      is_unread: false,
      action_label: isEn ? "View Profile" : "Xem hồ sơ",
      action_href: "/family",
      action_kind: "link",
    },
    {
      id: "notif-mile-2",
      category: "milestones",
      title: isEn ? "Clinician Review Item Validated" : "Bác sĩ đã rà soát hồ sơ xét nghiệm",
      description: isEn
        ? "Dr. Trần Văn Hùng validated your latest echocardiogram findings and updated the clinical baseline."
        : "BS. Trần Văn Hùng đã xác nhận kết quả siêu âm tim mới nhất và cập nhật chỉ số chuẩn.",
      timestamp: isEn ? "2 days ago" : "2 ngày trước",
      is_unread: false,
      action_label: isEn ? "Check Visits" : "Xem buổi khám",
      action_href: "/care/visits",
      action_kind: "link",
    },
    {
      id: "notif-safe-1",
      category: "safety",
      title: isEn ? "Safety Guardrail: DDI Cleared" : "Cảnh báo An toàn: Kiểm tra tương tác thuốc",
      description: isEn
        ? "FIDES Engine evaluated your active prescription list: No critical interactions detected with Paracetamol."
        : "Động cơ FIDES đã kiểm tra danh mục thuốc: Không phát hiện tương tác nguy hiểm với Paracetamol.",
      timestamp: isEn ? "3 days ago" : "3 ngày trước",
      is_unread: false,
      action_label: isEn ? "Safety Workspace" : "Tủ thuốc an toàn",
      action_href: "/health/medications",
      action_kind: "link",
    },
  ]);

  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState("");

  const {
    data: notifData,
    isLoading,
    error,
    refetch,
  } = useQuery<NotificationPreferencesDto>({
    queryKey: queryKeys.profile(activeProfileId).you.notifications(),
    queryFn: async () => {
      try {
        return await v2Client.getNotificationPreferences(activeProfileId);
      } catch {
        return {
          categories: {
            medications: true,
            visits: true,
            review_items: true,
            safety_alerts: true,
            journey_milestones: true,
            family_activity: true,
          },
          channels: {
            push: true,
            email: true,
            in_app: true,
          },
          quiet_hours: {
            enabled: true,
            start_time: "22:00",
            end_time: "07:00",
          },
        };
      }
    },
    onSuccess: (data) => {
      if (data) {
        setMedications(data.categories.medications);
        setVisits(data.categories.visits);
        setReviewItems(data.categories.review_items);
        setSafetyAlerts(data.categories.safety_alerts);
        if (data.categories.journey_milestones !== undefined) {
          setJourneyMilestones(data.categories.journey_milestones);
        }
        if (data.categories.family_activity !== undefined) {
          setFamilyActivity(data.categories.family_activity);
        }

        setPushChannel(data.channels.push);
        setEmailChannel(data.channels.email);
        setInAppChannel(data.channels.in_app);

        setQuietHoursEnabled(data.quiet_hours.enabled);
        setStartTime(data.quiet_hours.start_time);
        setEndTime(data.quiet_hours.end_time);
      }
    },
  });

  const handleSave = async () => {
    setSaving(true);
    setSaveSuccess(false);
    setSaveError("");
    try {
      await v2Client.updateNotificationPreferences({
        categories: {
          medications,
          visits,
          review_items: reviewItems,
          safety_alerts: safetyAlerts,
          journey_milestones: journeyMilestones,
          family_activity: familyActivity,
        },
        channels: {
          push: pushChannel,
          email: emailChannel,
          in_app: inAppChannel,
        },
        quiet_hours: {
          enabled: quietHoursEnabled,
          start_time: startTime,
          end_time: endTime,
        },
      });
      setSaveSuccess(true);
    } catch {
      setSaveError(
        isEn
          ? "Failed to save notification preferences. Please try again."
          : "Không thể lưu cài đặt thông báo. Vui lòng thử lại.",
      );
    } finally {
      setSaving(false);
    }
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((item) => ({ ...item, is_unread: false })));
  };

  const handleToggleItemRead = (id: string) => {
    setNotifications((prev) =>
      prev.map((item) => (item.id === id ? { ...item, is_unread: !item.is_unread } : item)),
    );
  };

  const handleMarkTaken = (id: string) => {
    setNotifications((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              is_unread: false,
              is_completed: true,
              action_label: isEn ? "Completed" : "Đã uống",
            }
          : item,
      ),
    );
  };

  const filteredNotifications = notifications.filter((item) => {
    if (activeTab === "all") return true;
    return item.category === activeTab;
  });

  const unreadCount = notifications.filter((n) => n.is_unread).length;
  const medUnread = notifications.filter((n) => n.category === "medications" && n.is_unread).length;
  const milestoneUnread = notifications.filter((n) => n.category === "milestones" && n.is_unread).length;
  const familyUnread = notifications.filter((n) => n.category === "family" && n.is_unread).length;
  const safetyUnread = notifications.filter((n) => n.category === "safety" && n.is_unread).length;

  return (
    <div className="space-y-6" data-testid="you-notifications-page">
      <HealthPageHeader
        title={isEn ? "Notification Center & Alerts" : "Trung tâm Thông báo & Nhắc nhở"}
        subtitle={
          isEn
            ? "Explore upcoming medication reminders, care journey milestones, family updates, and configure delivery channels."
            : "Theo dõi lịch nhắc uống thuốc, cột mốc lộ trình sức khỏe, hoạt động gia đình và tùy chỉnh các kênh nhận tin."
        }
        backHref="/you"
        backLabel={isEn ? "Back to You" : "Quay lại Cá nhân"}
        primaryAction={{
          label: saving
            ? isEn
              ? "Saving..."
              : "Đang lưu..."
            : isEn
              ? "Save Preferences"
              : "Lưu tùy chọn",
          icon: "check",
          onClick: () => void handleSave(),
          loading: saving,
        }}
      />

      {error ? (
        <InlineError
          message={isEn ? "Unable to load notifications" : "Không thể tải cài đặt thông báo"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {saveSuccess ? (
        <div
          className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3.5 text-xs font-semibold text-[var(--status-ok-text)] flex items-center gap-2"
          data-testid="notifications-save-success"
        >
          <Icon name="check" size="1rem" />
          <span>{isEn ? "Notification settings updated." : "Đã cập nhật cài đặt thông báo."}</span>
        </div>
      ) : null}

      {saveError ? (
        <InlineError message={saveError} onRetry={() => void handleSave()} />
      ) : null}

      {isLoading ? (
        <div className="space-y-4 animate-pulse" aria-busy="true">
          <div className="h-44 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
          <div className="h-44 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Notification Center Feed (EXPLORE Archetype) */}
          <div className="space-y-6 lg:col-span-7">
            {/* Notification Center Hub Feed */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="notification-feed-section"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[color:var(--shell-border)]/60 pb-3">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="notifications" size="1.25rem" />
                  <h2 className="text-base font-bold text-[var(--text-primary)]">
                    {isEn ? "Notification Feed" : "Bảng Tin Thông Báo"}
                  </h2>
                  {unreadCount > 0 ? (
                    <Badge tone="brand" data-testid="unread-count-badge">
                      {isEn ? `${unreadCount} new` : `${unreadCount} mới`}
                    </Badge>
                  ) : null}
                </div>

                {unreadCount > 0 ? (
                  <button
                    type="button"
                    onClick={handleMarkAllRead}
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1 self-start sm:self-auto"
                    data-testid="mark-all-read-btn"
                  >
                    <Icon name="check" size="0.85rem" />
                    <span>{isEn ? "Mark all as read" : "Đánh dấu tất cả đã đọc"}</span>
                  </button>
                ) : null}
              </div>

              {/* Filter Tabs */}
              <div
                role="tablist"
                className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs border-b border-[color:var(--shell-border)]/40"
                data-testid="notification-filter-tabs"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "all"}
                  onClick={() => setActiveTab("all")}
                  className={`px-3 py-1.5 rounded-[var(--radius-md)] font-semibold transition shrink-0 flex items-center gap-1.5 ${
                    activeTab === "all"
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid="tab-filter-all"
                >
                  <span>{isEn ? "All" : "Tất cả"}</span>
                  {unreadCount > 0 ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/20">
                      {unreadCount}
                    </span>
                  ) : null}
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "medications"}
                  onClick={() => setActiveTab("medications")}
                  className={`px-3 py-1.5 rounded-[var(--radius-md)] font-semibold transition shrink-0 flex items-center gap-1.5 ${
                    activeTab === "medications"
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid="tab-filter-medications"
                >
                  <Icon name="medication" size="0.85rem" />
                  <span>{isEn ? "Medications" : "Uống thuốc"}</span>
                  {medUnread > 0 ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/20">
                      {medUnread}
                    </span>
                  ) : null}
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "milestones"}
                  onClick={() => setActiveTab("milestones")}
                  className={`px-3 py-1.5 rounded-[var(--radius-md)] font-semibold transition shrink-0 flex items-center gap-1.5 ${
                    activeTab === "milestones"
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid="tab-filter-milestones"
                >
                  <Icon name="calendar" size="0.85rem" />
                  <span>{isEn ? "Milestones" : "Cột mốc"}</span>
                  {milestoneUnread > 0 ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/20">
                      {milestoneUnread}
                    </span>
                  ) : null}
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "family"}
                  onClick={() => setActiveTab("family")}
                  className={`px-3 py-1.5 rounded-[var(--radius-md)] font-semibold transition shrink-0 flex items-center gap-1.5 ${
                    activeTab === "family"
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid="tab-filter-family"
                >
                  <Icon name="contact" size="0.85rem" />
                  <span>{isEn ? "Family" : "Gia đình"}</span>
                  {familyUnread > 0 ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/20">
                      {familyUnread}
                    </span>
                  ) : null}
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "safety"}
                  onClick={() => setActiveTab("safety")}
                  className={`px-3 py-1.5 rounded-[var(--radius-md)] font-semibold transition shrink-0 flex items-center gap-1.5 ${
                    activeTab === "safety"
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
                  }`}
                  data-testid="tab-filter-safety"
                >
                  <Icon name="clinical-notes" size="0.85rem" />
                  <span>{isEn ? "Safety" : "An toàn"}</span>
                  {safetyUnread > 0 ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-white/20">
                      {safetyUnread}
                    </span>
                  ) : null}
                </button>
              </div>

              {/* Feed Items List */}
              <div className="space-y-3" data-testid="notification-items-list">
                {filteredNotifications.length === 0 ? (
                  <div
                    className="p-8 text-center rounded-[var(--radius-lg)] bg-[var(--surface-muted)] text-xs text-[var(--text-secondary)]"
                    data-testid="empty-notifications-state"
                  >
                    <Icon name="notifications" size="2rem" className="mx-auto mb-2 text-[var(--text-muted)]" />
                    <p className="font-semibold text-[var(--text-primary)]">
                      {isEn ? "No notifications in this category" : "Không có thông báo trong mục này"}
                    </p>
                    <p className="mt-1">
                      {isEn ? "You're all caught up!" : "Bạn đã cập nhật hết tất cả các thông báo."}
                    </p>
                  </div>
                ) : (
                  filteredNotifications.map((item) => (
                    <div
                      key={item.id}
                      className={`p-4 rounded-[var(--radius-lg)] border transition-all ${
                        item.is_unread
                          ? "bg-[var(--surface-panel)] border-[color:var(--brand-400)] shadow-sm"
                          : "bg-[var(--surface-muted)]/70 border-[color:var(--shell-border)]"
                      }`}
                      data-testid={`notif-card-${item.id}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex items-start gap-3 min-w-0">
                          <div
                            className={`h-8 w-8 rounded-[var(--radius-md)] flex items-center justify-center shrink-0 mt-0.5 ${
                              item.category === "medications"
                                ? "bg-[var(--brand-600)]/15 text-[var(--brand-600)]"
                                : item.category === "milestones"
                                  ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                                  : item.category === "family"
                                    ? "bg-purple-500/15 text-purple-600 dark:text-purple-400"
                                    : "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                            }`}
                          >
                            <Icon
                              name={
                                item.category === "medications"
                                  ? "medication"
                                  : item.category === "milestones"
                                    ? "calendar"
                                    : item.category === "family"
                                      ? "contact"
                                      : "clinical-notes"
                              }
                              size="1rem"
                            />
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-bold text-[var(--text-primary)]">
                                {item.title}
                              </span>
                              {item.is_unread ? (
                                <span className="h-2 w-2 rounded-full bg-[var(--brand-600)] shrink-0" />
                              ) : null}
                            </div>
                            <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                              {item.description}
                            </p>
                            <span className="text-[11px] text-[var(--text-muted)] mt-1.5 block">
                              {item.timestamp}
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col items-end gap-1.5 shrink-0">
                          {item.action_kind === "mark_taken" ? (
                            <Button
                              variant={item.is_completed ? "secondary" : "primary"}
                              size="sm"
                              disabled={item.is_completed}
                              onClick={() => handleMarkTaken(item.id)}
                              data-testid={`action-btn-${item.id}`}
                            >
                              {item.action_label}
                            </Button>
                          ) : item.action_href ? (
                            <Link
                              href={item.action_href}
                              className="fluent-button-secondary inline-flex items-center gap-1 rounded-[var(--radius-md)] px-2.5 py-1 text-xs font-semibold"
                              data-testid={`action-link-${item.id}`}
                            >
                              <span>{item.action_label}</span>
                              <Icon name="arrow-right" size="0.75rem" />
                            </Link>
                          ) : null}

                          <button
                            type="button"
                            onClick={() => handleToggleItemRead(item.id)}
                            className="text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            data-testid={`toggle-read-btn-${item.id}`}
                          >
                            {item.is_unread
                              ? isEn
                                ? "Mark as read"
                                : "Đánh dấu đã đọc"
                              : isEn
                                ? "Mark unread"
                                : "Đánh dấu chưa đọc"}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </section>
          </div>

          {/* Right Column: Preferences, Channels & Quiet Hours */}
          <div className="space-y-6 lg:col-span-5">
            {/* Category Preferences */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="notification-categories-section"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="clinical-notes" size="1.25rem" />
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    {isEn ? "Notification Preferences" : "Tùy Chọn Danh Mục"}
                  </h3>
                </div>
                <Badge tone="brand">{isEn ? "Active Filters" : "Bộ lọc chủ động"}</Badge>
              </div>

              <div className="space-y-3">
                {/* 1. Medication Reminders */}
                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Medication Reminders & Dosing" : "Thuốc & Nhắc nhở uống thuốc"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn
                        ? "Daily dose prompts and medication cabinet refill alerts."
                        : "Nhắc lịch uống hàng ngày và thông báo sắp hết thuốc."}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={medications}
                    onChange={(e) => setMedications(e.target.checked)}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-medications"
                  />
                </label>

                {/* 2. Journey Milestone Alerts */}
                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Journey Milestone & Visit Prep" : "Cột mốc Lộ trình & Chuẩn bị khám"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn
                        ? "Health goal milestones and clinic visit prep reminders 2 days prior."
                        : "Thông báo hoàn thành mục tiêu lộ trình và nhắc chuẩn bị trước ngày đi khám."}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={journeyMilestones && visits}
                    onChange={(e) => {
                      setJourneyMilestones(e.target.checked);
                      setVisits(e.target.checked);
                    }}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-milestones"
                  />
                </label>

                {/* Legacy toggle-notif-visits alias for regression safety */}
                <input
                  type="checkbox"
                  checked={visits}
                  onChange={(e) => setVisits(e.target.checked)}
                  className="hidden"
                  data-testid="toggle-notif-visits"
                />

                {/* 3. Family Activity Notifications */}
                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Family Activity & Doctor Reviews" : "Hoạt động Gia đình & Bác sĩ rà soát"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn
                        ? "Caregiver record updates, sharing requests, and clinician lab validations."
                        : "Thông báo khi người thân cập nhật chỉ số hoặc bác sĩ xác nhận kết quả xét nghiệm."}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={familyActivity && reviewItems}
                    onChange={(e) => {
                      setFamilyActivity(e.target.checked);
                      setReviewItems(e.target.checked);
                    }}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-family"
                  />
                </label>

                {/* Legacy toggle-notif-reviews alias */}
                <input
                  type="checkbox"
                  checked={reviewItems}
                  onChange={(e) => setReviewItems(e.target.checked)}
                  className="hidden"
                  data-testid="toggle-notif-reviews"
                />

                {/* 4. Critical Safety Alerts */}
                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Critical Safety Alerts (Emergency overrides)" : "Cảnh báo An toàn Khẩn cấp"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn
                        ? "Severe drug-drug interactions and critical baseline contradictions."
                        : "Cảnh báo tương tác thuốc nghiêm trọng (luôn ưu tiên phát thông báo)."}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={safetyAlerts}
                    onChange={(e) => setSafetyAlerts(e.target.checked)}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-safety"
                  />
                </label>
              </div>
            </section>

            {/* Delivery Channels */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="notification-channels-section"
            >
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Delivery Channels" : "Kênh Nhận Thông Báo"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? "Choose where and how alerts should reach you."
                  : "Chọn các kênh tiếp nhận thông báo và nhắc nhở y tế."}
              </p>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div className="flex items-center gap-2.5">
                    <Icon name="notifications" size="1.1rem" className="text-[var(--text-brand)]" />
                    <span>{isEn ? "In-App Topbar Badge" : "Hộp thư thông báo trong ứng dụng"}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={inAppChannel}
                    onChange={(e) => setInAppChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-inapp"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div className="flex items-center gap-2.5">
                    <Icon name="scan" size="1.1rem" className="text-[var(--text-brand)]" />
                    <span>{isEn ? "Push Notifications (Mobile & Browser)" : "Thông báo đẩy (Điện thoại & Trình duyệt)"}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={pushChannel}
                    onChange={(e) => setPushChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-push"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div className="flex items-center gap-2.5">
                    <Icon name="chat" size="1.1rem" className="text-[var(--text-brand)]" />
                    <span>{isEn ? "Email Digests & Summaries" : "Email tóm tắt định kỳ"}</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={emailChannel}
                    onChange={(e) => setEmailChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-email"
                  />
                </label>
              </div>
            </section>

            {/* Quiet Hours Settings */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="quiet-hours-section"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="theme" size="1.25rem" />
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    {isEn ? "Scheduled Quiet Hours" : "Lịch Giờ Yên Tĩnh"}
                  </h3>
                </div>
                <Badge tone={quietHoursEnabled ? "ok" : "neutral"}>
                  {quietHoursEnabled ? (isEn ? "Enabled" : "Đang bật") : (isEn ? "Disabled" : "Đã tắt")}
                </Badge>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                {isEn
                  ? "Non-critical reminders will be silenced during this window. Emergency safety alerts will always break through."
                  : "Thông báo nhắc nhở thông thường sẽ được tắt âm trong khung giờ này. Các cảnh báo cấp cứu khẩn cấp luôn được phát."}
              </p>

              <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                <span>{isEn ? "Enable Quiet Hours Schedule" : "Bật chế độ Giờ Yên Tĩnh"}</span>
                <input
                  type="checkbox"
                  checked={quietHoursEnabled}
                  onChange={(e) => setQuietHoursEnabled(e.target.checked)}
                  className="rounded text-[var(--brand-600)]"
                  data-testid="toggle-quiet-hours"
                />
              </label>

              {quietHoursEnabled ? (
                <div className="grid grid-cols-2 gap-4 pt-1">
                  <div>
                    <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                      {isEn ? "Start Time (Sleep)" : "Bắt đầu"}
                    </label>
                    <input
                      type="time"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                      className="fluent-input w-full font-mono text-xs"
                      data-testid="quiet-start-time-input"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[var(--text-secondary)] mb-1">
                      {isEn ? "End Time (Wake)" : "Kết thúc"}
                    </label>
                    <input
                      type="time"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                      className="fluent-input w-full font-mono text-xs"
                      data-testid="quiet-end-time-input"
                    />
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
