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

export default function YouNotificationsPage() {
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());

  const [medications, setMedications] = useState(true);
  const [visits, setVisits] = useState(true);
  const [reviewItems, setReviewItems] = useState(true);
  const [safetyAlerts, setSafetyAlerts] = useState(true);

  const [pushChannel, setPushChannel] = useState(true);
  const [emailChannel, setEmailChannel] = useState(true);
  const [inAppChannel, setInAppChannel] = useState(true);

  const [quietHoursEnabled, setQuietHoursEnabled] = useState(true);
  const [startTime, setStartTime] = useState("22:00");
  const [endTime, setEndTime] = useState("07:00");

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

  return (
    <div className="space-y-6" data-testid="you-notifications-page">
      <HealthPageHeader
        title={isEn ? "Notification Preferences" : "Cài đặt Thông báo"}
        subtitle={
          isEn
            ? "Configure alerts by clinical category, select delivery channels, and set scheduled quiet hours."
            : "Tùy chỉnh nhận thông báo theo danh mục lâm sàng, kênh nhận tin và thiết lập giờ yên tĩnh."
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
          {/* Left Column: Categories & Quiet Hours */}
          <div className="space-y-6 lg:col-span-7">
            {/* Category Preferences */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="notification-categories-section"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="notifications" size="1.25rem" />
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    {isEn ? "Clinical Notification Categories" : "Danh mục Thông báo Y tế"}
                  </h3>
                </div>
                <Badge tone="brand">{isEn ? "Per-Category" : "Theo danh mục"}</Badge>
              </div>

              <div className="space-y-3">
                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Medications & Dose Schedules" : "Thuốc & Lịch uống thuốc"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn ? "Daily dose reminders and refill prompts" : "Nhắc nhở uống thuốc và hết hạn đơn thuốc"}
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

                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Visits & Appointments" : "Lịch khám & Chuẩn bị đi khám"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn ? "Prep prompts 2 days prior to visits" : "Nhắc chuẩn bị câu hỏi 2 ngày trước buổi khám"}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={visits}
                    onChange={(e) => setVisits(e.target.checked)}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-visits"
                  />
                </label>

                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Clinician Review Items" : "Hồ sơ Bác sĩ đã rà soát"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn ? "Doctor validated lab insights and edits" : "Thông báo khi bác sĩ xác nhận kết quả xét nghiệm"}
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={reviewItems}
                    onChange={(e) => setReviewItems(e.target.checked)}
                    className="rounded text-[var(--brand-600)] mt-1"
                    data-testid="toggle-notif-reviews"
                  />
                </label>

                <label className="flex items-start justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <div>
                    <p>{isEn ? "Critical Safety Alerts (Emergency overrides)" : "Cảnh báo An toàn Khẩn cấp"}</p>
                    <p className="text-[11px] text-[var(--text-secondary)] font-normal mt-0.5">
                      {isEn ? "Severe drug interaction warnings" : "Cảnh báo tương tác thuốc nghiêm trọng (luôn ưu tiên)"}
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

            {/* Quiet Hours Settings */}
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="quiet-hours-section"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="calendar" size="1.25rem" />
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

          {/* Right Column: Channels */}
          <div className="space-y-6 lg:col-span-5">
            <section
              className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="notification-channels-section"
            >
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                {isEn ? "Delivery Channels" : "Kênh nhận thông báo"}
              </h3>
              <p className="text-xs text-[var(--text-secondary)]">
                {isEn
                  ? "Choose where you want to receive alerts and summaries."
                  : "Chọn các kênh nhận tin nhắn và bản tóm tắt."}
              </p>

              <div className="space-y-3">
                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <span>{isEn ? "Push Notifications (Mobile/Browser)" : "Thông báo đẩy (Thiết bị di động)"}</span>
                  <input
                    type="checkbox"
                    checked={pushChannel}
                    onChange={(e) => setPushChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-push"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <span>{isEn ? "Email Digests & Summaries" : "Email tóm tắt định kỳ"}</span>
                  <input
                    type="checkbox"
                    checked={emailChannel}
                    onChange={(e) => setEmailChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-email"
                  />
                </label>

                <label className="flex items-center justify-between p-3 rounded-[var(--radius-lg)] bg-[var(--surface-muted)] cursor-pointer text-xs font-semibold text-[var(--text-primary)]">
                  <span>{isEn ? "In-App Topbar Badge" : "Hộp thư thông báo trong ứng dụng"}</span>
                  <input
                    type="checkbox"
                    checked={inAppChannel}
                    onChange={(e) => setInAppChannel(e.target.checked)}
                    className="rounded text-[var(--brand-600)]"
                    data-testid="toggle-channel-inapp"
                  />
                </label>
              </div>
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
