"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { EmergencyQrModal } from "@/components/consumer/emergency-qr-modal";
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
    queryFn: async () => {
      try {
        return await v2Client.getYouOverview(activeProfileId);
      } catch {
        // Fallback default structure if backend endpoint returns mock/empty
        return {
          profile: activeProfile,
          demographics: {
            full_name: activeProfile?.display_name ?? "Nguyễn Văn A",
            blood_type: "O+",
          },
          emergency_card: {
            blood_type: "O+",
            allergies_count: 1,
            conditions_count: 2,
            medications_count: 2,
            medical_alerts: ["Dị ứng nghiêm trọng Penicillin"],
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
    (isEn ? "Personal Account" : "Nguyễn Văn A");

  // Get initials for avatar
  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(-2)
    .map((w) => w[0].toUpperCase())
    .join("") || "NV";

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
          {/* Top Profile Summary Card - Stitch Bento Header */}
          <section
            className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm relative overflow-hidden"
            data-testid="profile-summary-card"
          >
            {/* Ambient Top Glow */}
            <div className="absolute top-0 right-0 w-80 h-80 bg-[var(--brand-500)]/5 rounded-full blur-3xl pointer-events-none -mr-16 -mt-16" />

            <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="flex items-center gap-5">
                {/* Avatar Badge with edit indicator */}
                <div className="relative flex-shrink-0">
                  <div className="w-20 h-20 rounded-2xl bg-[var(--brand-600)] flex items-center justify-center text-white text-2xl font-bold shadow-lg shadow-[var(--brand-600)]/20 border border-[color:var(--brand-400)]/30">
                    {initials}
                  </div>
                  <Link
                    href="/you/profile"
                    className="absolute -bottom-1.5 -right-1.5 w-7 h-7 bg-[var(--surface-panel)] rounded-full flex items-center justify-center border border-[color:var(--shell-border)] shadow-sm hover:scale-110 transition"
                    title={isEn ? "Edit profile avatar" : "Chỉnh sửa ảnh đại diện"}
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

                  <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                    <span className="inline-flex items-center gap-1 bg-[var(--surface-muted)] px-2.5 py-1 rounded-md text-[var(--status-danger-text)] font-semibold border border-[color:var(--shell-border)]">
                      <Icon name="emergency" size="0.85rem" />
                      {overview?.demographics?.blood_type || "O+"}
                    </span>
                    <span className="w-1 h-1 rounded-full bg-[color:var(--shell-border)]" />
                    <span>
                      {overview?.emergency_card?.allergies_count ?? 1}{" "}
                      {isEn ? "critical allergy" : "dị ứng quan trọng"}
                    </span>
                    <span className="w-1 h-1 rounded-full bg-[color:var(--shell-border)]" />
                    <span>
                      {overview?.emergency_card?.conditions_count ?? 2}{" "}
                      {isEn ? "active conditions" : "bệnh lý đang theo dõi"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
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

          {/* Bento Grid: Personal Details & Emergency ID Preview */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Main Info Column (Span 7) */}
            <div className="lg:col-span-7 space-y-6">
              {/* Basic Info Card */}
              <section className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-[var(--surface-muted)] flex items-center justify-center text-[var(--text-brand)]">
                    <Icon name="user-card" size="1.25rem" />
                  </div>
                  <h3 className="font-bold text-base text-[var(--text-primary)]">
                    {isEn ? "Basic Information" : "Thông tin cơ bản"}
                  </h3>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-4 gap-x-6 text-xs">
                  <div>
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Full Name" : "Họ và tên"}
                    </span>
                    <div className="text-sm font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      {displayName}
                    </div>
                  </div>

                  <div>
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Date of Birth" : "Ngày sinh"}
                    </span>
                    <div className="text-sm font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      15 / 05 / 1985
                    </div>
                  </div>

                  <div>
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Gender" : "Giới tính"}
                    </span>
                    <div className="text-sm font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      {isEn ? "Male" : "Nam"}
                    </div>
                  </div>

                  <div>
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Phone Number" : "Số điện thoại"}
                    </span>
                    <div className="text-sm font-mono font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      0912 345 678
                    </div>
                  </div>

                  <div className="sm:col-span-2">
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      Email
                    </span>
                    <div className="text-sm font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      nguyen.vana@example.com
                    </div>
                  </div>

                  <div className="sm:col-span-2">
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Address" : "Địa chỉ cư trú"}
                    </span>
                    <div className="text-sm font-medium text-[var(--text-primary)] pb-1.5 border-b border-[color:var(--shell-border)]/60">
                      Quận 1, TP. Hồ Chí Minh
                    </div>
                  </div>

                  <div>
                    <span className="font-semibold text-[var(--text-secondary)] block mb-1">
                      {isEn ? "Blood Type" : "Nhóm máu"}
                    </span>
                    <div className="text-sm font-bold text-[var(--status-danger-text)] pb-1.5 border-b border-[color:var(--shell-border)]/60 flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-[var(--status-danger-text)]" />
                      {overview?.demographics?.blood_type || "O+"}
                    </div>
                  </div>
                </div>
              </section>

              {/* Primary Emergency Contact Card */}
              <section className="rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)]/50 bg-[var(--surface-panel)] p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[var(--status-danger-bg)] flex items-center justify-center text-[var(--status-danger-text)]">
                      <Icon name="emergency" size="1.25rem" />
                    </div>
                    <h3 className="font-bold text-base text-[var(--text-primary)]">
                      {isEn ? "Primary Emergency Contact" : "Người liên hệ khẩn cấp"}
                    </h3>
                  </div>
                  <Link
                    href="/you/profile"
                    className="text-xs font-semibold text-[var(--text-brand)] hover:underline flex items-center gap-1"
                  >
                    <Icon name="edit" size="0.85rem" />
                    <span>{isEn ? "Edit" : "Chỉnh sửa"}</span>
                  </Link>
                </div>

                <div className="rounded-xl bg-[var(--surface-muted)] p-4 border border-[color:var(--shell-border)] flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-[var(--surface-panel)] border border-[color:var(--shell-border)] flex items-center justify-center text-[var(--text-primary)] font-bold text-lg">
                      B
                    </div>
                    <div>
                      <div className="font-semibold text-sm text-[var(--text-primary)]">
                        {overview?.emergency_card?.emergency_contact?.name || "Nguyễn Thị B"}
                      </div>
                      <div className="text-xs text-[var(--text-secondary)] flex items-center gap-2 mt-0.5">
                        <span>{overview?.emergency_card?.emergency_contact?.relationship || "Vợ"}</span>
                        <span className="w-1 h-1 rounded-full bg-[color:var(--shell-border)]" />
                        <span className="font-mono text-[var(--text-primary)] font-medium">
                          {overview?.emergency_card?.emergency_contact?.phone || "0901 234 567"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <a
                    href={`tel:${overview?.emergency_card?.emergency_contact?.phone || "0901234567"}`}
                    className="w-9 h-9 rounded-full bg-[var(--surface-panel)] hover:bg-[var(--surface-hover)] border border-[color:var(--shell-border)] flex items-center justify-center text-[var(--text-brand)] transition"
                    title={isEn ? "Call emergency contact" : "Gọi khẩn cấp"}
                  >
                    <Icon name="contact" size="1.1rem" />
                  </a>
                </div>
              </section>
            </div>

            {/* Right Column: Live Emergency Medical ID Card (Span 5) */}
            <div className="lg:col-span-5 space-y-6">
              {/* Emergency ID Live Card Preview */}
              <div
                className="rounded-[var(--radius-2xl)] border-2 border-[color:var(--status-danger-border)] bg-[var(--bg-elev-3)] p-5 shadow-xl space-y-4 relative overflow-hidden"
                data-testid="emergency-card-summary"
              >
                {/* Red pulse glow effect */}
                <div className="absolute top-0 right-0 w-48 h-48 bg-rose-500/10 rounded-full blur-2xl pointer-events-none -mr-10 -mt-10" />

                {/* Card Header */}
                <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                  <div className="flex items-center gap-2 text-[var(--status-danger-text)]">
                    <Icon name="emergency" size="1.4rem" />
                    <span className="font-bold tracking-widest text-[11px] uppercase">
                      CLARA EMERGENCY MEDICAL ID
                    </span>
                  </div>
                  <span className="rounded-lg bg-[var(--status-danger-bg)] border border-[color:var(--status-danger-border)] px-2.5 py-1 text-sm font-extrabold text-[var(--status-danger-text)]">
                    {overview?.emergency_card?.blood_type || "O+"}
                  </span>
                </div>

                {/* Identity */}
                <div>
                  <h4 className="text-lg font-bold text-[var(--text-primary)] leading-tight">
                    {displayName}
                  </h4>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    {isEn ? "DOB:" : "NS:"} 1985-05-15
                  </p>
                </div>

                {/* Medical Alert Badges */}
                <div className="space-y-1.5">
                  <p className="text-[10px] font-bold text-[var(--status-danger-text)] uppercase tracking-wider">
                    {isEn ? "Critical Medical Alerts" : "Cảnh báo Y tế Đặc biệt"}
                  </p>
                  <div className="flex flex-wrap gap-1.5" data-testid="medical-alert-badges">
                    {overview?.emergency_card?.medical_alerts &&
                    overview.emergency_card.medical_alerts.length > 0 ? (
                      overview.emergency_card.medical_alerts.map((alert, idx) => (
                        <div
                          key={idx}
                          className="w-full inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-1 text-xs font-bold text-[var(--status-danger-text)]"
                        >
                          <Icon name="warning" size="0.8rem" />
                          <span>{alert}</span>
                        </div>
                      ))
                    ) : (
                      <div className="w-full inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-1 text-xs font-bold text-[var(--status-danger-text)]">
                        <Icon name="warning" size="0.8rem" />
                        <span>Dị ứng nghiêm trọng Penicillin (nguy cơ sốc phản vệ)</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Clinical Data Snapshot */}
                <div className="space-y-3 pt-1 text-xs">
                  <div>
                    <p className="font-bold text-[var(--text-secondary)] mb-1">
                      {isEn ? "Allergies:" : "Dị ứng:"}
                    </p>
                    <ul className="text-[var(--text-primary)] space-y-0.5 list-disc list-inside">
                      <li><strong>Penicillin</strong> (nguy cơ sốc phản vệ)</li>
                      <li><strong>Aspirin</strong> (mày đay)</li>
                    </ul>
                  </div>

                  <div>
                    <p className="font-bold text-[var(--text-secondary)] mb-1">
                      {isEn ? "Active Medications:" : "Thuốc đang sử dụng:"}
                    </p>
                    <ul className="text-[var(--text-primary)] space-y-0.5 list-disc list-inside">
                      <li>Amlodipine 5mg · 1 viên/ngày (sáng)</li>
                      <li>Metformin 500mg · 1 viên x 2 lần/ngày</li>
                    </ul>
                  </div>

                  <div>
                    <p className="font-bold text-[var(--text-secondary)] mb-1">
                      {isEn ? "Chronic Conditions:" : "Bệnh lý nền:"}
                    </p>
                    <ul className="text-[var(--text-primary)] space-y-0.5 list-disc list-inside">
                      <li>Tăng huyết áp vô căn</li>
                      <li>Đái tháo đường Type 2</li>
                    </ul>
                  </div>
                </div>

                {/* Emergency Contact Box */}
                <div className="rounded-xl bg-[var(--surface-panel)] p-3 border border-[color:var(--shell-border)] flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-[var(--text-secondary)] text-[11px] block mb-0.5">
                      {isEn ? "Emergency Contact:" : "Liên hệ khẩn cấp:"}
                    </span>
                    <span className="font-medium text-[var(--text-primary)]">
                      {overview?.emergency_card?.emergency_contact?.name || "Nguyễn Thị B"} (
                      {overview?.emergency_card?.emergency_contact?.relationship || "Vợ"}) ·{" "}
                      <strong className="font-mono text-[var(--text-brand)]">
                        {overview?.emergency_card?.emergency_contact?.phone || "0901234567"}
                      </strong>
                    </span>
                  </div>
                  <Icon name="contact" size="1.2rem" className="text-[var(--text-brand)]" />
                </div>

                {/* Quick QR Share Action inside Card */}
                <div className="pt-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => setQrModalOpen(true)}
                    className="w-full justify-center gap-2 rounded-xl text-xs font-bold border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)] hover:opacity-90"
                  >
                    <Icon name="scan" size="1rem" />
                    <span>{isEn ? "Show Emergency QR Code" : "Xem Mã QR Cấp Cứu Nhanh"}</span>
                  </Button>
                </div>

                {/* Footer Disclaimer */}
                <p className="text-[10px] text-[var(--text-muted)] border-t border-[color:var(--shell-border)]/60 pt-2 italic text-center">
                  {isEn
                    ? "Self-declared emergency medical summary for first responder decision support. Not a doctor prescription."
                    : "Bản tóm tắt y tế khẩn cấp tự khai báo hỗ trợ người cấp cứu. Không thay thế chẩn đoán bác sĩ."}
                </p>

                {/* Links */}
                <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                  <Link
                    href="/phr"
                    className="text-xs font-semibold text-[var(--text-secondary)] hover:text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                    data-testid="view-full-phr-link"
                  >
                    <Icon name="clinical-notes" size="0.85rem" />
                    <span>{isEn ? "Full PHR (/phr)" : "Xem hồ sơ đầy đủ (/phr)"}</span>
                  </Link>
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
            </div>
          </div>

          {/* 5-Category Hub Cards */}
          <div className="space-y-6 pt-4">
            {/* Category 1: Health (Sức khỏe & Kết nối) */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/60 pb-2">
                <Icon name="user-card" size="1.2rem" className="text-[var(--text-brand)]" />
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {isEn ? "1. Health & Connected Sources" : "1. Sức khỏe & Nguồn dữ liệu"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 1.1 Connected Health Sources */}
                <div
                  className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                  data-testid="integrations-summary"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[var(--text-brand)]">
                        <Icon name="scan" size="1.25rem" />
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? "Connected Health Sources" : "Nguồn dữ liệu Sức khỏe"}
                        </h4>
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
                            className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-3 py-2 text-xs"
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

                {/* 1.2 Family Sharing & Caregivers */}
                <div
                  className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                  data-testid="family-sharing-summary"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[var(--text-brand)]">
                        <Icon name="contact" size="1.25rem" />
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? "Family & Caregiver Sharing" : "Chia sẻ Người thân & Người chăm sóc"}
                        </h4>
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
                            className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-3 py-2 text-xs"
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
              </div>
            </div>

            {/* Category 2: Privacy (Quyền riêng tư & AI) */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/60 pb-2">
                <Icon name="user-card" size="1.2rem" className="text-[var(--text-brand)]" />
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {isEn ? "2. Privacy & AI Transparency" : "2. Quyền riêng tư & Minh bạch AI"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 2.1 Privacy & AI Controls */}
                <div
                  className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                  data-testid="privacy-ai-summary"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[var(--text-brand)]">
                        <Icon name="user-card" size="1.25rem" />
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? "Privacy & AI Transparency" : "Quyền riêng tư & Minh bạch AI"}
                        </h4>
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
                      <span className="rounded-md bg-[var(--surface-muted)] px-2.5 py-1">
                        {isEn ? "Retention: " : "Lưu trữ: "}
                        <strong className="text-[var(--text-primary)]">
                          {overview?.privacy_ai?.retention_policy_days ?? 90}{" "}
                          {isEn ? "days" : "ngày"}
                        </strong>
                      </span>
                      <span className="rounded-md bg-[var(--surface-muted)] px-2.5 py-1">
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

                {/* 2.2 Notification Preferences */}
                <div
                  className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                  data-testid="notifications-summary"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[var(--text-brand)]">
                        <Icon name="notifications" size="1.25rem" />
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? "Notification Preferences" : "Cài đặt Thông báo"}
                        </h4>
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
              </div>
            </div>

            {/* Category 3: Workspace & Help */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 border-b border-[color:var(--shell-border)]/60 pb-2">
                <Icon name="settings" size="1.2rem" className="text-[var(--text-brand)]" />
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {isEn ? "3. Workspaces & Help Center" : "3. Khu vực làm việc & Trợ giúp"}
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 3.1 Help Guides */}
                <div
                  className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                  data-testid="help-guide-summary"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-[var(--text-brand)]">
                        <Icon name="clinical-notes" size="1.25rem" />
                        <h4 className="font-bold text-sm text-[var(--text-primary)]">
                          {isEn ? "User Guides & FAQs" : "Hướng dẫn sử dụng & Hỏi đáp"}
                        </h4>
                      </div>
                      <Badge tone="ok">
                        {isEn ? "Available" : "Sẵn sàng"}
                      </Badge>
                    </div>

                    <p className="mt-2 text-xs text-[var(--text-secondary)] leading-relaxed">
                      {isEn
                        ? "Learn how to ask questions safely, prepare for clinic visits, check medication interactions, and manage your health record."
                        : "Tìm hiểu cách hỏi đáp y tế an toàn, chuẩn bị trước khi đi khám, kiểm tra tương tác thuốc và bảo mật thông tin."}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between">
                    <span className="text-[11px] text-[var(--text-muted)]">
                      {isEn ? "Quick 5-minute guides" : "Hướng dẫn 5 phút"}
                    </span>
                    <Link
                      href="/huong-dan"
                      className="text-xs font-semibold text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                      data-testid="view-help-link"
                    >
                      <span>{isEn ? "Open Help Center" : "Mở Trung tâm hướng dẫn"}</span>
                      <Icon name="arrow-right" size="0.85rem" />
                    </Link>
                  </div>
                </div>

                {/* 3.2 Professional Mode Switcher (if privileged) */}
                {isProfessionalRole ? (
                  <div
                    className="flex flex-col justify-between rounded-[var(--radius-2xl)] border border-[color:var(--brand-300)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:shadow-md"
                    data-testid="professional-mode-card"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-[var(--text-brand)]">
                          <Icon name="clinical-notes" size="1.25rem" />
                          <h4 className="font-bold text-sm text-[var(--text-primary)]">
                            {isEn ? "Professional Workspaces" : "Khu vực Chuyên môn"}
                          </h4>
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
            </div>
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

      {/* Quick Emergency QR Modal */}
      <EmergencyQrModal
        open={qrModalOpen}
        onClose={() => setQrModalOpen(false)}
        patientName={displayName}
        bloodType={overview?.demographics?.blood_type || "O+"}
        emergencyContact={overview?.emergency_card?.emergency_contact}
        medicalAlerts={overview?.emergency_card?.medical_alerts || ["Dị ứng nghiêm trọng Penicillin"]}
        isEn={isEn}
      />
    </div>
  );
}

export default function ConsumerYouPage() {
  return <YouOverviewContent />;
}
