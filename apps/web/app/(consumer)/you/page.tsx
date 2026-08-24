"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SettingsLayout } from "@/components/page/settings-layout";
import { EmergencyQrModal } from "@/components/consumer/emergency-qr-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { ListRow } from "@/components/ui/list-row";
import { InlineError } from "@/components/shared/inline-error";
import { EmptyState } from "@/components/shared/empty-state";
import { useUILanguage } from "@/lib/use-ui-language";
import { getActiveProfileId } from "@/lib/profile-context";
import { useProfileContext } from "@/components/shell/profile-boundary";
import { useSession } from "@/components/shell/session-boundary";
import { useQuery } from "@/lib/query/use-query";
import { queryKeys } from "@/lib/query/query-keys";
import { v2Client, type YouOverviewDto } from "@/lib/api/v2-client";

/**
 * YouOverviewSkeleton
 * Accessible loading state while personal profile and overview data hydrate.
 */
function YouOverviewSkeleton() {
  return (
    <div
      className="space-y-6 animate-pulse"
      aria-busy="true"
      aria-label="Đang tải thông tin cá nhân"
      data-testid="you-overview-skeleton"
    >
      <div className="h-44 rounded-[var(--radius-2xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]" />
      <div className="space-y-3 rounded-[var(--radius-2xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-6">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <div
            key={i}
            className="h-16 rounded-[var(--radius-lg)] bg-[var(--surface-muted)]"
          />
        ))}
      </div>
    </div>
  );
}

/**
 * YouOverviewContent
 * Spec v5 Section 6.74:
 * - Shell: EXPLORE
 * - Archetype: Account & Preferences Hub
 * - Layout:
 *   1. Identity & Profile card (Demographics, Emergency Medical Alert, Quick QR, Profile Switcher)
 *   2. Categorized vertical list rows:
 *      - Health Record (PHR)
 *      - Family & Care Sharing
 *      - Connected Health Devices
 *      - Privacy & Medical Consent
 *      - Data Rights (Decree 13 / GDPR)
 *      - Notifications
 *      - Security & Preferences
 *      - Help & Guides
 */
function YouOverviewContent() {
  const router = useRouter();
  const uiLanguage = useUILanguage();
  const isEn = uiLanguage === "en";
  const { role, isLoggingOut, handleLogout } = useSession();
  const { activeProfile, profileContext, handleProfileChange, isProfileChanging } =
    useProfileContext();

  const [activeProfileId, setActiveProfileId] = useState<string | null>(getActiveProfileId());
  const [qrModalOpen, setQrModalOpen] = useState(false);

  const isProfessionalRole =
    role === "doctor" || role === "researcher" || role === "admin";

  const {
    data: overview,
    isLoading,
    error,
    refetch,
  } = useQuery<YouOverviewDto>({
    queryKey: queryKeys.profile(activeProfileId).you.overview(),
    queryFn: () => v2Client.getYouOverview(activeProfileId),
  });

  const displayName =
    overview?.demographics?.full_name ||
    activeProfile?.display_name ||
    (isEn ? "Personal Account" : "Tài khoản cá nhân");

  // Get initials for avatar
  const initials =
    displayName
      .split(" ")
      .filter(Boolean)
      .slice(-2)
      .map((w) => w[0].toUpperCase())
      .join("") || (isEn ? "PA" : "CN");

  const bloodType =
    overview?.demographics?.blood_type ||
    overview?.emergency_card?.blood_type ||
    (isEn ? "Unknown" : "Chưa rõ");
  const medicalAlerts = overview?.emergency_card?.medical_alerts || [];

  return (
    <SettingsLayout
      workspace="personal"
      title={isEn ? "Account & Preferences" : "Cá nhân & Quyền riêng tư"}
      subtitle={
        isEn
          ? "Unified personal health hub, privacy controls, caregiver sharing, connected devices, and data rights."
          : "Trung tâm quản lý hồ sơ cá nhân, bảo mật quyền riêng tư, chia sẻ người thân và nguồn dữ liệu sức khỏe."
      }
      badges={
        activeProfile ? (
          <Badge tone="brand">
            {activeProfile.kind === "shared"
              ? isEn
                ? "Shared profile"
                : "Hồ sơ chia sẻ"
              : isEn
                ? "Primary"
                : "Chính"}
          </Badge>
        ) : undefined
      }
      maxWidth="prose"
      data-testid="you-overview-page"
    >
      {error && overview ? (
        <InlineError
          message={isEn ? "Unable to load personal overview" : "Không thể tải tổng quan cá nhân"}
          onRetry={() => void refetch()}
        />
      ) : null}

      {isLoading ? (
        <YouOverviewSkeleton />
      ) : error ? (
        <EmptyState
          title={isEn ? "Unable to load overview" : "Không thể tải tổng quan cá nhân"}
          description={
            isEn
              ? "We could not load your personal account data. Please check your network connection and retry."
              : "Không thể tải dữ liệu hồ sơ cá nhân. Vui lòng kiểm tra kết nối mạng và thử lại."
          }
          actionLabel={isEn ? "Retry" : "Thử lại"}
          onAction={() => void refetch()}
        />
      ) : (
        <div className="space-y-6">
          {/* 1. Identity & Profile card (Spec v5 Section 6.74 Layout Item 1) */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm relative overflow-hidden space-y-5"
            data-testid="profile-summary-card"
          >
            {/* Ambient Top Glow */}
            <div className="absolute top-0 right-0 w-80 h-80 bg-[var(--brand-500)]/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-16" />

            <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
              {/* Left: Avatar & Identity details */}
              <div className="flex items-center gap-5">
                <div className="relative flex-shrink-0">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-[var(--brand-600)] flex items-center justify-center text-white text-xl sm:text-2xl font-bold shadow-lg shadow-[var(--brand-600)]/20 border border-[color:var(--brand-400)]/30">
                    {initials}
                  </div>
                  <Link
                    href="/you/profile"
                    className="absolute -bottom-1.5 -right-1.5 w-7 h-7 bg-[var(--surface-panel)] rounded-full flex items-center justify-center border border-[color:var(--shell-border)] shadow-sm hover:scale-110 transition"
                    title={isEn ? "Edit profile details" : "Chỉnh sửa hồ sơ"}
                  >
                    <div className="w-5 h-5 bg-[var(--brand-500)] rounded-full flex items-center justify-center text-white">
                      <Icon name="edit" size="0.75rem" />
                    </div>
                  </Link>
                </div>

                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h2 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">
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

                  {/* Demographics and Emergency overview summary */}
                  <div
                    className="flex flex-wrap items-center gap-2.5 text-xs text-[var(--text-secondary)]"
                    data-testid="emergency-card-summary"
                  >
                    <span className="inline-flex items-center gap-1 bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] border border-[color:var(--status-danger-border)] px-2.5 py-0.5 rounded-md font-bold text-xs">
                      <Icon name="emergency" size="0.85rem" />
                      <span>{bloodType}</span>
                    </span>
                    <span className="w-1 h-1 rounded-full bg-[color:var(--shell-border)]" />
                    <span>
                      {overview?.emergency_card?.allergies_count ?? 0}{" "}
                      {isEn ? "critical allergy" : "dị ứng quan trọng"}
                    </span>
                    <span className="w-1 h-1 rounded-full bg-[color:var(--shell-border)]" />
                    <span>
                      {overview?.emergency_card?.conditions_count ?? 0}{" "}
                      {isEn ? "active conditions" : "bệnh lý đang theo dõi"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Right: Quick Emergency Actions */}
              <div className="flex flex-wrap items-center gap-2.5">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setQrModalOpen(true)}
                  className="rounded-full px-4 py-2 text-xs font-semibold text-[var(--status-danger-text)] border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] hover:opacity-90"
                  data-testid="open-emergency-qr-btn"
                >
                  <Icon name="emergency" size="1rem" />
                  <span>{isEn ? "Quick Emergency QR" : "Mã QR Cấp Cứu"}</span>
                </Button>

                <Link
                  href="/you/profile"
                  className="fluent-button-primary inline-flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold"
                  data-testid="edit-profile-btn"
                >
                  <Icon name="edit" size="1rem" />
                  <span>{isEn ? "Edit Profile & Emergency Card" : "Chỉnh sửa hồ sơ & Thẻ cấp cứu"}</span>
                </Link>
              </div>
            </div>

            {/* Medical Alert Badges Banner if present */}
            {medicalAlerts.length > 0 ? (
              <div className="relative z-10 rounded-xl bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)]/60 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2.5 text-[var(--status-danger-text)]">
                  <Icon name="warning" size="1.1rem" className="shrink-0" />
                  <span className="font-semibold">
                    {isEn ? "Critical Alert: " : "Cảnh báo khẩn cấp: "}
                    <strong>{medicalAlerts[0]}</strong>
                  </span>
                </div>
                {overview?.emergency_card?.emergency_contact ? (
                  <div className="text-[var(--text-secondary)] text-[11px] flex items-center gap-2 shrink-0">
                    <span>
                      {isEn ? "Emergency Contact: " : "Liên hệ: "}
                      <strong className="text-[var(--text-primary)]">
                        {overview.emergency_card.emergency_contact.name} (
                        {overview.emergency_card.emergency_contact.relationship})
                      </strong>
                    </span>
                    <a
                      href={`tel:${overview.emergency_card.emergency_contact.phone}`}
                      className="text-[var(--text-brand)] font-mono font-semibold hover:underline"
                    >
                      {overview.emergency_card.emergency_contact.phone}
                    </a>
                  </div>
                ) : null}
              </div>
            ) : null}

            {/* Multi-Profile Switcher if available */}
            {profileContext?.profiles && profileContext.profiles.length > 1 ? (
              <div className="border-t border-[color:var(--shell-border)]/60 pt-4">
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

          {/* 2. Categorized vertical list rows (Spec v5 Section 6.74 Layout Item 2) */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-6 shadow-sm space-y-1"
            data-testid="categorized-account-rows"
          >
            <div className="pb-3 mb-2 border-b border-[color:var(--shell-border)]/60 flex items-center justify-between">
              <h3 className="font-bold text-sm text-[var(--text-primary)] uppercase tracking-wider">
                {isEn ? "Account & Health Capabilities" : "Danh mục Quản lý & Cài đặt"}
              </h3>
              <span className="text-xs text-[var(--text-muted)]">
                {isEn ? "8 core hubs" : "8 danh mục chính"}
              </span>
            </div>

            {/* Row 1: Health Record (PHR) */}
            <div data-testid="phr-summary">
              <ListRow
                density="comfortable"
                href="/phr"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)] border border-[color:var(--shell-border)]">
                    <Icon name="clinical-notes" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Health Record (PHR)" : "Hồ sơ Sức khỏe Cá nhân (PHR)"}
                subtitle={
                  isEn
                    ? "Clinical documents, lab results, vitals, active medications, and chronic conditions"
                    : "Tài liệu lâm sàng, kết quả xét nghiệm, sinh hiệu, đơn thuốc và bệnh lý nền"
                }
                badges={
                  <Badge tone="brand">
                    {isEn ? "Health Hub" : "Hồ sơ y tế"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {overview?.emergency_card?.conditions_count ?? 0}{" "}
                    {isEn ? "conditions" : "bệnh lý"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 2: Family & Care Sharing */}
            <div data-testid="family-sharing-summary">
              <ListRow
                density="comfortable"
                href="/you/sharing"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-teal-600 dark:text-teal-400 border border-[color:var(--shell-border)]">
                    <Icon name="contact" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Family & Care Sharing" : "Chia sẻ Người thân & Người chăm sóc"}
                subtitle={
                  isEn
                    ? "Manage granular, time-bound access grants with instant one-click revocation"
                    : "Ủy quyền truy cập theo danh mục có thời hạn, phân quyền cho người chăm sóc và thu hồi tức thì"
                }
                badges={
                  <Badge tone={overview?.family_sharing?.active_grants_count ? "ok" : "neutral"}>
                    {overview?.family_sharing?.active_grants_count ?? 0}{" "}
                    {isEn ? "Active" : "Đang chia sẻ"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "Care circle" : "Vòng chăm sóc"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 3: Connected Health Devices */}
            <div data-testid="integrations-summary">
              <ListRow
                density="comfortable"
                href="/you/integrations"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-blue-600 dark:text-blue-400 border border-[color:var(--shell-border)]">
                    <Icon name="scan" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Connected Health Devices" : "Thiết bị & Nguồn kết nối (Integrations)"}
                subtitle={
                  isEn
                    ? "Apple Health, Google Health Connect, Garmin, Fitbit with per-metric sync controls"
                    : "Đồng bộ Apple Health, Google Health Connect, thiết bị đeo với quyền kiểm soát từng chỉ số"
                }
                badges={
                  <Badge tone={overview?.integrations?.total_connected ? "brand" : "neutral"}>
                    {overview?.integrations?.total_connected ?? 0}{" "}
                    {isEn ? "Connected" : "Đã kết nối"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "Continuous sync" : "Đồng bộ liên tục"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 4: Privacy & Medical Consent */}
            <div data-testid="privacy-ai-summary">
              <ListRow
                density="comfortable"
                href="/you/privacy"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-emerald-600 dark:text-emerald-400 border border-[color:var(--shell-border)]">
                    <Icon name="user-card" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Privacy & Medical Consent" : "Quyền riêng tư & Đồng thuận Y tế"}
                subtitle={
                  isEn
                    ? "Zero-CoT reasoning guarantee, purpose-specific consent ledger, and AI feature switches"
                    : "Bảo đảm Zero-CoT, sổ cái đồng thuận 6 mục đích y khoa và tắt/bật tính năng AI chủ động"
                }
                badges={
                  <Badge tone="ok">
                    {overview?.privacy_ai?.cot_disabled
                      ? isEn
                        ? "Zero-CoT"
                        : "Zero-CoT"
                      : isEn
                        ? "Protected"
                        : "Bảo vệ"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--status-ok-text)] font-medium">
                    {overview?.privacy_ai?.consent_status === "granted"
                      ? isEn
                        ? "Granted"
                        : "Đã đồng thuận"
                      : isEn
                        ? "Pending"
                        : "Chờ xác nhận"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 5: Data Rights (Decree 13 / GDPR) */}
            <div data-testid="data-rights-summary">
              <ListRow
                density="comfortable"
                href="/account/data"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-indigo-600 dark:text-indigo-400 border border-[color:var(--shell-border)]">
                    <Icon name="check" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Data Rights (Decree 13 / GDPR)" : "Quyền Dữ liệu (Nghị định 13 / GDPR)"}
                subtitle={
                  isEn
                    ? "Statutory PDPD rights: access, export your complete health data, and permanent erasure"
                    : "Thực hiện quyền theo Nghị định 13/2023/NĐ-CP: tra cứu, xuất dữ liệu PHR và yêu cầu xóa vĩnh viễn"
                }
                badges={
                  <Badge tone="brand">
                    {isEn ? "Decree 13 / GDPR" : "Nghị định 13 / GDPR"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "DSAR Portal" : "Cổng DSAR"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 6: Notifications */}
            <div data-testid="notifications-summary">
              <ListRow
                density="comfortable"
                href="/you/notifications"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-amber-600 dark:text-amber-400 border border-[color:var(--shell-border)]">
                    <Icon name="notifications" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Notifications" : "Cài đặt Thông báo & Nhắc nhở"}
                subtitle={
                  isEn
                    ? "Medication reminders, appointment alerts, critical safety warnings, and quiet hours"
                    : "Nhắc uống thuốc, lịch hẹn khám bác sĩ, cảnh báo an toàn y tế và khung giờ yên tĩnh"
                }
                badges={
                  <Badge tone="neutral">
                    {isEn ? "Quiet Hours Ready" : "Có giờ yên tĩnh"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "Granular alerts" : "Tùy chỉnh"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 7: Security & Preferences */}
            <div data-testid="security-preferences-summary">
              <ListRow
                density="comfortable"
                href="/you/settings"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-purple-600 dark:text-purple-400 border border-[color:var(--shell-border)]">
                    <Icon name="settings" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Security & Preferences" : "Bảo mật & Tùy chọn Tài khoản"}
                subtitle={
                  isEn
                    ? "Theme mode (Light/Dark/System), Language (Vietnamese default), MFA management, Session security, and active logins"
                    : "Giao diện (Sáng/Tối/Hệ thống), Ngôn ngữ, Xác thực 2 yếu tố (MFA), Quản lý phiên và Thiết bị đăng nhập"
                }
                badges={
                  <Badge tone="brand">
                    {isEn ? "MFA & Sessions" : "MFA & Phiên"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "Protected" : "Đã bảo vệ"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>

            {/* Row 8: Help & Guides */}
            <div data-testid="help-guide-summary">
              <ListRow
                density="comfortable"
                href="/huong-dan"
                leading={
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-cyan-600 dark:text-cyan-400 border border-[color:var(--shell-border)]">
                    <Icon name="search" size="1.25rem" />
                  </div>
                }
                title={isEn ? "Help & Guides" : "Hướng dẫn & Trợ giúp"}
                subtitle={
                  isEn
                    ? "Quick 5-minute guides, clinical safety principles, FAQ knowledge base, and support"
                    : "Hướng dẫn sử dụng nhanh, nguyên tắc an toàn tham vấn y khoa và câu hỏi thường gặp"
                }
                badges={
                  <Badge tone="neutral">
                    {isEn ? "Help Center" : "Trợ giúp"}
                  </Badge>
                }
                meta={
                  <span className="text-xs text-[var(--text-secondary)]">
                    {isEn ? "Guides & FAQ" : "Cẩm nang & FAQ"}
                  </span>
                }
                trailing={
                  <Icon
                    name="arrow-right"
                    size="1.1rem"
                    className="text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition"
                  />
                }
              />
            </div>
          </section>

          {/* 3. Professional Mode Launcher (if privileged role) */}
          {isProfessionalRole ? (
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-300)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3"
              data-testid="professional-mode-card"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)] border border-[color:var(--shell-border)] shrink-0">
                    <Icon name="clinical-notes" size="1.25rem" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-sm text-[var(--text-primary)]">
                        {isEn ? "Professional Workspaces" : "Khu vực Chuyên môn"}
                      </h4>
                      <Badge tone="brand">{role?.toUpperCase()}</Badge>
                    </div>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      {isEn
                        ? "Switch between Consumer mode, Clinical Workspace (Doctor), Research Tier 2, and Admin Operations."
                        : "Chuyển đổi giữa chế độ Người dùng, Không gian Lâm sàng (Bác sĩ), Nghiên cứu Chuyên sâu và Quản trị."}
                    </p>
                  </div>
                </div>
                <Link
                  href="/dashboard"
                  className="fluent-button-primary inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold shrink-0 self-start sm:self-auto"
                  data-testid="switch-professional-mode-link"
                >
                  <span>{isEn ? "Open Professional Dashboard" : "Vào Trang Chuyên môn"}</span>
                  <Icon name="arrow-right" size="0.85rem" />
                </Link>
              </div>
            </section>
          ) : null}

          {/* 4. Sign Out Button */}
          <div className="pt-2">
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

      {/* Quick Emergency QR Modal */}
      <EmergencyQrModal
        open={qrModalOpen}
        onClose={() => setQrModalOpen(false)}
        patientName={displayName}
        bloodType={bloodType}
        emergencyContact={overview?.emergency_card?.emergency_contact}
        medicalAlerts={medicalAlerts}
        isEn={isEn}
      />
    </SettingsLayout>
  );
}

export default function ConsumerYouPage() {
  return <YouOverviewContent />;
}
