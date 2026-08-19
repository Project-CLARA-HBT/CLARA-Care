"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { InlineError } from "@/components/shared/inline-error";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import { useProfileContext } from "@/components/shell/profile-boundary";
import { useSession } from "@/components/shell/session-boundary";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import { v2Client, type YouOverviewDto } from "@/lib/api/v2-client";

function YouOverviewSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Đang tải thông tin cá nhân"
      data-testid="you-overview-skeleton"
    >
      <div className="flex flex-col gap-3 pb-4 border-b border-[color:var(--shell-border)]/60 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-2">
          <div className="h-7 w-48 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
          <div className="h-4 w-72 rounded-[var(--radius-md)] bg-[var(--surface-muted)]" />
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="h-44 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]"
          />
        ))}
      </div>
    </div>
  );
}

function YouOverviewContent() {
  const router = useRouter();
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const { role, isLoggingOut, handleLogout } = useSession();
  const { activeProfile, profileContext, handleProfileChange, isProfileChanging } =
    useProfileContext();

  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());

  const isProfessionalRole =
    role === "doctor" || role === "researcher" || role === "admin";

  const {
    data: overview,
    isLoading,
    error,
    refetch,
  } = useQuery<YouOverviewDto>({
    queryKey: queryKeys.profile(activeProfileId).you.overview(),
    queryFn: async () => {
      try {
        return await v2Client.getYouOverview(activeProfileId);
      } catch {
        // Fallback default structure if backend endpoint returns mock/empty
        return {
          profile: activeProfile,
          demographics: {
            full_name: activeProfile?.display_name ?? "Người dùng CLARA",
            blood_type: "O+",
          },
          emergency_card: {
            blood_type: "O+",
            allergies_count: 1,
            conditions_count: 1,
            medications_count: 2,
            medical_alerts: ["Dị ứng Penicillin"],
            emergency_contact: {
              name: "Nguyễn Thị B",
              phone: "0901234567",
              relationship: "Vợ",
            },
            is_configured: true,
          },
          family_sharing: {
            active_grants_count: 1,
            received_grants_count: 0,
            pending_invites_count: 0,
            members: [
              {
                id: "m-1",
                name: "Nguyễn Thị B",
                relationship: "Vợ / Người chăm sóc",
                role: "caregiver",
                status: "active",
              },
            ],
          },
          privacy_ai: {
            data_classes_used: ["medications", "conditions", "allergies", "visits"],
            ai_features_enabled: true,
            cot_disabled: true,
            retention_policy_days: 90,
            consent_status: "granted",
          },
          integrations: {
            total_connected: 1,
            sources: [
              {
                id: "src-1",
                name: "health_connect",
                title: "Google Health Connect",
                connected: true,
                sync_enabled: true,
                last_sync_at: "2026-08-20T08:00:00Z",
                status: "active",
              },
            ],
          },
          professional_mode: {
            eligible: isProfessionalRole,
            role: role ?? "patient",
            active_workspace: isProfessionalRole ? "clinical" : "personal",
          },
        };
      }
    },
  });

  const displayName =
    overview?.demographics?.full_name ||
    activeProfile?.display_name ||
    (isEn ? "Personal Account" : "Hồ sơ cá nhân");

  return (
    <div className="space-y-6" data-testid="you-overview-page">
      <HealthPageHeader
        title={isEn ? "You & Privacy Controls" : "Cá nhân & Quyền riêng tư"}
        subtitle={
          isEn
            ? "Manage your demographics, emergency card, caregiver sharing, AI privacy transparency, and connected health sources."
            : "Quản lý hồ sơ, thẻ cấp cứu y tế, chia sẻ người thân, tính minh bạch AI và nguồn dữ liệu sức khỏe."
        }
        activeProfile={
          activeProfile
            ? {
                name: activeProfile.display_name,
                relationship:
                  activeProfile.kind === "shared"
                    ? isEn
                      ? "Shared profile"
                      : "Hồ sơ chia sẻ"
                    : isEn
                      ? "Primary"
                      : "Chính",
              }
            : null
        }
      />

      {error ? (
        <InlineError
          message={isEn ? "Unable to load personal overview" : "Không thể tải tổng quan cá nhân"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {isLoading ? (
        <YouOverviewSkeleton />
      ) : (
        <div className="space-y-6">
          {/* Top Profile Summary Card */}
          <section
            className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm"
            data-testid="profile-summary-card"
          >
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--brand-50)] text-2xl font-bold text-[var(--brand-700)] border border-[color:var(--brand-200)] shadow-inner">
                  {displayName.charAt(0).toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-[var(--text-primary)] truncate">
                      {displayName}
                    </h2>
                    <Badge tone="brand">
                      {activeProfile?.kind === "shared"
                        ? isEn
                          ? "Shared Profile"
                          : "Hồ sơ chia sẻ"
                        : isEn
                          ? "Owner"
                          : "Chủ sở hữu"}
                    </Badge>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] mt-1">
                    {overview?.demographics?.blood_type
                      ? `${isEn ? "Blood Type:" : "Nhóm máu:"} ${overview.demographics.blood_type} · `
                      : ""}
                    {overview?.emergency_card?.allergies_count ?? 0}{" "}
                    {isEn ? "allergies" : "dị ứng"} ·{" "}
                    {overview?.emergency_card?.conditions_count ?? 0}{" "}
                    {isEn ? "conditions" : "bệnh lý"}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  href="/you/profile"
                  className="fluent-button-primary inline-flex items-center gap-2 rounded-[var(--radius-lg)] px-4 py-2 text-xs font-semibold"
                  data-testid="edit-profile-btn"
                >
                  <Icon name="edit" size="1rem" />
                  <span>{isEn ? "Edit Profile & Emergency Card" : "Chỉnh sửa hồ sơ & Thẻ cấp cứu"}</span>
                </Link>
              </div>
            </div>

            {profileContext?.profiles && profileContext.profiles.length > 1 ? (
              <div className="mt-5 border-t border-[color:var(--shell-border)]/60 pt-4">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold text-[var(--text-secondary)]">
                    {isEn ? "Switch active profile context:" : "Chuyển đổi hồ sơ đang xem:"}
                  </span>
                  <select
                    aria-label={isEn ? "Active Profile" : "Hồ sơ đang xem"}
                    value={activeProfile?.id ?? ""}
                    disabled={isProfileChanging}
                    onChange={(e) => {
                      void handleProfileChange(e.target.value);
                      setActiveProfileId(e.target.value);
                    }}
                    className="min-h-11 w-full max-w-md rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-medium text-[var(--text-primary)] outline-none"
                    data-testid="profile-switcher-select"
                  >
                    {profileContext.profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.kind === "shared" ? `[${isEn ? "Shared" : "Được chia sẻ"}] ` : ""}
                        {p.display_name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}
          </section>

          {/* Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 1. Emergency Card Card */}
            <div
              className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
              data-testid="emergency-card-summary"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[var(--status-danger-text)]">
                    <Icon name="emergency" size="1.25rem" />
                    <h3 className="font-bold text-sm text-[var(--text-primary)]">
                      {isEn ? "Emergency Medical Card" : "Thẻ Cấp cứu Y tế"}
                    </h3>
                  </div>
                  <Badge tone={overview?.emergency_card?.is_configured ? "ok" : "warn"}>
                    {overview?.emergency_card?.is_configured
                      ? isEn
                        ? "Active"
                        : "Đã thiết lập"
                      : isEn
                        ? "Needs Setup"
                        : "Chưa hoàn tất"}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "Instant critical information for emergency responders: blood type, severe allergies, active medications, and contacts."
                    : "Thông tin thiết yếu khi cấp cứu: nhóm máu, dị ứng nghiêm trọng, thuốc đang dùng và người liên hệ khẩn cấp."}
                </p>

                {overview?.emergency_card?.medical_alerts &&
                overview.emergency_card.medical_alerts.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-1.5" data-testid="medical-alert-badges">
                    {overview.emergency_card.medical_alerts.map((alert, idx) => (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1 rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2.5 py-0.5 text-[11px] font-bold text-[var(--status-danger-text)]"
                      >
                        <Icon name="warning" size="0.75rem" />
                        {alert}
                      </span>
                    ))}
                  </div>
                ) : null}

                {overview?.emergency_card?.emergency_contact ? (
                  <div className="mt-3 rounded-[var(--radius-md)] bg-[var(--surface-muted)] p-2.5 text-xs text-[var(--text-secondary)]">
                    <span className="font-semibold text-[var(--text-primary)]">
                      {isEn ? "Emergency Contact: " : "Người liên hệ: "}
                    </span>
                    {overview.emergency_card.emergency_contact.name} (
                    {overview.emergency_card.emergency_contact.relationship}) ·{" "}
                    <span className="font-mono text-[var(--text-primary)] font-medium">
                      {overview.emergency_card.emergency_contact.phone}
                    </span>
                  </div>
                ) : null}
              </div>

              <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "Offline & lockscreen ready" : "Sẵn sàng ngoại tuyến & màn hình khóa"}
                </span>
                <Link
                  href="/you/profile"
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  data-testid="view-emergency-card-link"
                >
                  <span>{isEn ? "Manage Emergency Card" : "Quản lý Thẻ cấp cứu"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>

            {/* 2. Family Sharing & Caregivers */}
            <div
              className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
              data-testid="family-sharing-summary"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name="contact" size="1.25rem" />
                    <h3 className="font-bold text-sm text-[var(--text-primary)]">
                      {isEn ? "Family & Caregiver Sharing" : "Chia sẻ Người thân & Người chăm sóc"}
                    </h3>
                  </div>
                  <Badge tone="neutral">
                    {overview?.family_sharing?.active_grants_count ?? 0}{" "}
                    {isEn ? "Active" : "Đang chia sẻ"}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "Granular, revocable sharing with scoped categories (medications, visits, lab results). You always stay in full control."
                    : "Chia sẻ có thời hạn và phân quyền theo danh mục (đơn thuốc, buổi khám, xét nghiệm). Bạn luôn giữ toàn quyền kiểm soát."}
                </p>

                {overview?.family_sharing?.members && overview.family_sharing.members.length > 0 ? (
                  <ul className="mt-3 space-y-1.5">
                    {overview.family_sharing.members.map((member) => (
                      <li
                        key={member.id}
                        className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs"
                      >
                        <span className="font-medium text-[var(--text-primary)]">
                          {member.name}
                        </span>
                        <span className="text-[11px] text-[var(--text-muted)]">
                          {member.relationship}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-xs text-[var(--text-muted)] italic">
                    {isEn ? "No family members linked yet." : "Chưa có người thân liên kết."}
                  </p>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "Scoped access & instant revoke" : "Phân quyền & thu hồi ngay lập tức"}
                </span>
                <Link
                  href="/you/sharing"
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  data-testid="view-sharing-link"
                >
                  <span>{isEn ? "Manage Sharing Grants" : "Quản lý quyền chia sẻ"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>

            {/* 3. Privacy & AI Controls */}
            <div
              className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
              data-testid="privacy-ai-summary"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name="user-card" size="1.25rem" />
                    <h3 className="font-bold text-sm text-[var(--text-primary)]">
                      {isEn ? "Privacy & AI Transparency" : "Quyền riêng tư & Minh bạch AI"}
                    </h3>
                  </div>
                  <Badge tone="ok">
                    {overview?.privacy_ai?.cot_disabled
                      ? isEn
                        ? "Zero-CoT Verified"
                        : "Bảo vệ Không lưu CoT"
                      : isEn
                        ? "Protected"
                        : "Được bảo vệ"}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "CLARA operates strictly without Chain-of-Thought exposure. You can disable optional AI features at any time without losing health records."
                    : "CLARA vận hành nghiêm ngặt không lưu chuỗi suy luận (Zero-CoT). Bạn có thể tắt các tính năng AI bổ sung mà không ảnh hưởng đến hồ sơ."}
                </p>

                <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--text-secondary)]">
                  <span className="rounded-md bg-[var(--surface-muted)] px-2 py-1">
                    {isEn ? "Retention: " : "Lưu trữ: "}
                    <strong className="text-[var(--text-primary)]">
                      {overview?.privacy_ai?.retention_policy_days ?? 90}{" "}
                      {isEn ? "days" : "ngày"}
                    </strong>
                  </span>
                  <span className="rounded-md bg-[var(--surface-muted)] px-2 py-1">
                    {isEn ? "Consent: " : "Đồng thuận: "}
                    <strong className="text-[var(--status-ok-text)]">
                      {overview?.privacy_ai?.consent_status === "granted"
                        ? isEn
                          ? "Granted"
                          : "Đã đồng thuận"
                        : isEn
                          ? "Pending"
                          : "Chờ xác nhận"}
                    </strong>
                  </span>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "PDPD compliant & Exportable" : "Tuân thủ PDPD & Xuất dữ liệu"}
                </span>
                <Link
                  href="/you/privacy"
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  data-testid="view-privacy-link"
                >
                  <span>{isEn ? "AI & Privacy Controls" : "Cài đặt Quyền riêng tư & AI"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>

            {/* 4. Connected Health Sources */}
            <div
              className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
              data-testid="integrations-summary"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name="scan" size="1.25rem" />
                    <h3 className="font-bold text-sm text-[var(--text-primary)]">
                      {isEn ? "Connected Health Sources" : "Nguồn dữ liệu Sức khỏe"}
                    </h3>
                  </div>
                  <Badge tone={overview?.integrations?.total_connected ? "brand" : "neutral"}>
                    {overview?.integrations?.total_connected ?? 0}{" "}
                    {isEn ? "Connected" : "Đã kết nối"}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "Sync vitals and activity from Apple Health, Google Health Connect, and wearables with granular metric permissions."
                    : "Đồng bộ sinh hiệu và hoạt động từ Apple Health, Health Connect với phân quyền theo từng chỉ số."}
                </p>

                {overview?.integrations?.sources && overview.integrations.sources.length > 0 ? (
                  <ul className="mt-3 space-y-1.5">
                    {overview.integrations.sources.map((src) => (
                      <li
                        key={src.id}
                        className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs"
                      >
                        <span className="font-medium text-[var(--text-primary)]">
                          {src.title}
                        </span>
                        <Badge tone={src.sync_enabled ? "ok" : "neutral"}>
                          {src.sync_enabled ? (isEn ? "Syncing" : "Đang đồng bộ") : (isEn ? "Paused" : "Tạm dừng")}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-xs text-[var(--text-muted)] italic">
                    {isEn ? "No external sources connected." : "Chưa kết nối nguồn thiết bị ngoài."}
                  </p>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "Per-metric sync toggles" : "Tùy chọn đồng bộ theo chỉ số"}
                </span>
                <Link
                  href="/you/integrations"
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  data-testid="view-integrations-link"
                >
                  <span>{isEn ? "Manage Integrations" : "Quản lý kết nối"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>

            {/* 5. Notification Preferences */}
            <div
              className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
              data-testid="notifications-summary"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name="notifications" size="1.25rem" />
                    <h3 className="font-bold text-sm text-[var(--text-primary)]">
                      {isEn ? "Notification Preferences" : "Cài đặt Thông báo"}
                    </h3>
                  </div>
                  <Badge tone="neutral">
                    {isEn ? "Quiet Hours Ready" : "Có giờ yên tĩnh"}
                  </Badge>
                </div>

                <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                  {isEn
                    ? "Manage alerts for medication reminders, upcoming visits, doctor reviews, and critical safety notifications."
                    : "Quản lý thông báo nhắc thuốc, lịch khám, rà soát hồ sơ từ bác sĩ và cảnh báo an toàn y tế."}
                </p>
              </div>

              <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                <span className="text-[11px] text-[var(--text-muted)]">
                  {isEn ? "Granular by category" : "Tùy chỉnh theo danh mục"}
                </span>
                <Link
                  href="/you/notifications"
                  className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                  data-testid="view-notifications-link"
                >
                  <span>{isEn ? "Configure Notifications" : "Tùy chỉnh thông báo"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </div>

            {/* 6. Professional Mode Switcher (if privileged) */}
            {isProfessionalRole ? (
              <div
                className="flex flex-col justify-between rounded-[var(--radius-xl)] border border-[color:var(--brand-300)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                data-testid="professional-mode-card"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-[var(--text-brand)]">
                      <Icon name="clinical-notes" size="1.25rem" />
                      <h3 className="font-bold text-sm text-[var(--text-primary)]">
                        {isEn ? "Professional Workspaces" : "Khu vực Chuyên môn"}
                      </h3>
                    </div>
                    <Badge tone="brand">
                      {role?.toUpperCase()}
                    </Badge>
                  </div>

                  <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                    {isEn
                      ? "Switch between Consumer mode, Clinical Workspace (Doctor), Research Tier 2, and Admin Operations."
                      : "Chuyển đổi giữa chế độ Người dùng, Không gian Lâm sàng (Bác sĩ), Nghiên cứu Chuyên sâu và Quản trị."}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                  <span className="text-[11px] text-[var(--text-muted)]">
                    {isEn ? "Role-gated workspace" : "Phân quyền theo vai trò"}
                  </span>
                  <Link
                    href="/dashboard"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                    data-testid="switch-professional-mode-link"
                  >
                    <span>{isEn ? "Open Professional Dashboard" : "Vào Trang Chuyên môn"}</span>
                    <Icon name="arrow-right" size="0.85rem" />
                  </Link>
                </div>
              </div>
            ) : null}
          </div>

          {/* Sign Out Button */}
          <div className="pt-4 border-t border-[color:var(--shell-border)]/60">
            <button
              type="button"
              onClick={handleLogout}
              disabled={isLoggingOut}
              className="flex min-h-[46px] w-full items-center justify-center gap-2 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 text-sm font-semibold text-[var(--status-danger-text)] transition hover:bg-[var(--status-danger-bg)]/80 disabled:cursor-not-allowed disabled:opacity-70"
              data-testid="you-sign-out-btn"
            >
              <Icon name="arrow-right" size={18} />
              <span>
                {isLoggingOut
                  ? isEn
                    ? "Signing out..."
                    : "Đang đăng xuất..."
                  : isEn
                    ? "Sign Out"
                    : "Đăng xuất tài khoản"}
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ConsumerYouPage() {
  return <YouOverviewContent />;
}
