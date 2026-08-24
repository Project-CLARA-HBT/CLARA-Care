"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { HealthPageHeader } from "@/components/consumer/health-page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { EmptyState } from "@/components/shared/empty-state";
import { InlineError } from "@/components/shared/inline-error";
import { LoadingCards } from "@/components/ui/surface";
import { TabPanel, Tabs, type TabItem } from "@/components/ui/tabs";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import type { UILanguage } from "@/lib/ui-language";
import {
  acknowledgeFamilyNotification,
  listFamilyAccessLog,
  listFamilyGrants,
  listFamilyNotifications,
  listFamilyRelationships,
  renewFamilyGrant,
  revokeFamilyGrant,
  type FamilyAccessLog,
  type FamilyGrant,
  type FamilyNotification,
} from "@/lib/visit-family";

export type FamilyTab = "shared" | "received" | "log";

function isFamilyTab(value: string | null): value is FamilyTab {
  return value === "shared" || value === "received" || value === "log";
}

function getDaysRemaining(expiresAt: string): { days: number; isExpired: boolean } {
  const exp = new Date(expiresAt).getTime();
  const now = Date.now();
  const diffDays = Math.ceil((exp - now) / (1000 * 60 * 60 * 24));
  return {
    days: diffDays > 0 ? diffDays : 0,
    isExpired: diffDays <= 0,
  };
}

function getGrantStatus(grant: FamilyGrant): "active" | "expired" | "revoked" {
  if (grant.status === "revoked" || Boolean(grant.revoked_at)) return "revoked";
  if (grant.status === "expired" || getDaysRemaining(grant.expires_at).isExpired) return "expired";
  return "active";
}

function FamilyWorkspace() {
  const language = useUILanguage();
  const isEn = language === "en";
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const [selectedTab, setSelectedTab] = useState<FamilyTab>(
    isFamilyTab(requestedTab) ? requestedTab : "shared",
  );
  const activeTab: FamilyTab = selectedTab;

  useEffect(() => {
    if (isFamilyTab(requestedTab) && requestedTab !== selectedTab) {
      setSelectedTab(requestedTab);
    }
  }, [requestedTab, selectedTab]);

  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );

  const objectLabel = useCallback(
    (objectType: string) => {
      if (objectType === "episode") return copy("familyCircle.object.episode");
      if (objectType === "visit") return copy("familyCircle.object.visit");
      if (objectType === "care_task") return copy("familyCircle.object.careTask");
      if (objectType === "medications") return isEn ? "Medications & Cabinet" : "Đơn thuốc & Tủ thuốc";
      if (objectType === "allergies") return isEn ? "Allergies & Alerts" : "Dị ứng & Cảnh báo an toàn";
      if (objectType === "lab_results") return isEn ? "Lab Results" : "Kết quả xét nghiệm";
      return copy("familyCircle.label.sharedScope");
    },
    [copy, isEn],
  );

  const objectIcon = (objectType: string): IconName => {
    if (objectType === "episode") return "progress";
    if (objectType === "visit") return "calendar";
    if (objectType === "care_task") return "check";
    if (objectType === "medications") return "medication";
    if (objectType === "allergies") return "warning";
    if (objectType === "lab_results") return "scan";
    return "share";
  };

  const actionLabel = useCallback(
    (action: string) => {
      if (action === "view") return copy("familyCircle.permission.view");
      if (action === "add_observation") return copy("familyCircle.permission.addObservation");
      if (action === "complete_task") return copy("familyCircle.permission.completeTask");
      return copy("familyCircle.permission.other");
    },
    [copy],
  );

  const purposeLabel = useCallback(
    (purpose: string) => {
      if (purpose === "care_coordination") return copy("familyCircle.purpose.careCoordination");
      if (purpose === "visit_support") return copy("familyCircle.purpose.visitSupport");
      if (purpose === "emergency_only") return isEn ? "Emergency Backup" : "Dự phòng khẩn cấp";
      if (purpose === "full_access") return isEn ? "Full Guardian Access" : "Ủy quyền giám hộ toàn phần";
      return purpose;
    },
    [copy, isEn],
  );

  const accessLogActorLabel = useCallback(
    (code: string | undefined, fallback: string) => {
      if (code === "owner") return copy("familyCircle.accessLog.actor.owner");
      if (code === "supporter") return copy("familyCircle.accessLog.actor.supporter");
      if (code === "system") return copy("familyCircle.accessLog.actor.system");
      return fallback || copy("familyCircle.accessLog.actor.other");
    },
    [copy],
  );

  const accessLogActionLabel = useCallback(
    (code: string | undefined) => {
      if (code === "view") return copy("familyCircle.accessLog.action.view");
      if (code === "add_observation") return copy("familyCircle.accessLog.action.addObservation");
      if (code === "complete_task") return copy("familyCircle.accessLog.action.completeTask");
      if (code === "invitation_accept" || code === "invitation.accept") return copy("familyCircle.accessLog.action.invitationAccept");
      if (code === "grant_revoke" || code === "grant.revoke") return copy("familyCircle.accessLog.action.grantRevoke");
      if (code === "grant_renewal_invited" || code === "grant.renewal_invited") return copy("familyCircle.accessLog.action.grantRenewalInvited");
      if (code === "notification_acknowledged" || code === "notification.acknowledged") return copy("familyCircle.accessLog.action.notificationAcknowledged");
      return copy("familyCircle.accessLog.action.other");
    },
    [copy],
  );

  const accessLogOutcomeCode = (code: string | undefined, legacy: string) => {
    if (code === "allowed" || code === "denied" || code === "failed" || code === "unknown") {
      return code;
    }
    if (legacy === "success") return "allowed";
    if (legacy === "denied") return "denied";
    if (legacy === "failure" || legacy === "failed") return "failed";
    return "unknown";
  };

  const accessLogOutcomeLabel = useCallback(
    (code: string) => {
      if (code === "allowed") return copy("familyCircle.accessLog.outcome.allowed");
      if (code === "denied") return copy("familyCircle.accessLog.outcome.denied");
      if (code === "failed") return copy("familyCircle.accessLog.outcome.failed");
      return copy("familyCircle.accessLog.outcome.unknown");
    },
    [copy],
  );

  const [grants, setGrants] = useState<FamilyGrant[]>([]);
  const [relationships, setRelationships] = useState<FamilyGrant[]>([]);
  const [notifications, setNotifications] = useState<FamilyNotification[]>([]);
  const [logs, setLogs] = useState<FamilyAccessLog[]>([]);
  const [createdToken, setCreatedToken] = useState("");
  const [copiedToken, setCopiedToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [grantToRevoke, setGrantToRevoke] = useState<FamilyGrant | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "expired" | "revoked">("all");

  const changeTab = (key: string) => {
    if (!isFamilyTab(key)) return;
    setSelectedTab(key);
    const next = new URLSearchParams(searchParams.toString());
    if (key === "shared") next.delete("tab");
    else next.set("tab", key);
    const query = next.toString();
    router.replace(query ? `/family?${query}` : "/family", { scroll: false });
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [owned, received, notifs, history] = await Promise.all([
        listFamilyGrants(),
        listFamilyRelationships(),
        listFamilyNotifications().catch(() => []),
        listFamilyAccessLog(),
      ]);
      setGrants(owned);
      setRelationships(received);
      setNotifications(notifs);
      setLogs(history);
    } catch {
      setError(copy("familyCircle.loadError"));
    } finally {
      setLoading(false);
    }
  }, [copy]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!createdToken) return;
    const timer = window.setTimeout(() => setCreatedToken(""), 60_000);
    return () => window.clearTimeout(timer);
  }, [createdToken]);

  const revoke = async (grantId: string) => {
    setSaving(true);
    setError("");
    try {
      await revokeFamilyGrant(grantId);
      setGrantToRevoke(null);
      await load();
    } catch {
      setError(copy("familyCircle.revokeError"));
    } finally {
      setSaving(false);
    }
  };

  const renew = async (grantId: string) => {
    setSaving(true);
    setError("");
    setCreatedToken("");
    try {
      const result = await renewFamilyGrant(
        grantId,
        new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
      );
      setCreatedToken(result.token);
      await load();
    } catch {
      setError(copy("familyCircle.renewError"));
    } finally {
      setSaving(false);
    }
  };

  const handleAcknowledgeNotification = async (notification: FamilyNotification) => {
    setAcknowledgingId(notification.id);
    setError("");
    try {
      await acknowledgeFamilyNotification(
        notification.id,
        notification.task_id,
        notification.purpose,
      );
      await load();
    } catch {
      setError(isEn ? "Failed to acknowledge delegated care task." : "Chưa thể ghi nhận nhiệm vụ chăm sóc.");
    } finally {
      setAcknowledgingId(null);
    }
  };

  const handleCopyToken = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard && createdToken) {
      navigator.clipboard.writeText(createdToken);
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    }
  };

  const activeGrants = useMemo(
    () => grants.filter((g) => getGrantStatus(g) === "active"),
    [grants],
  );
  const expiredGrants = useMemo(
    () => grants.filter((g) => getGrantStatus(g) === "expired"),
    [grants],
  );
  const revokedGrants = useMemo(
    () => grants.filter((g) => getGrantStatus(g) === "revoked"),
    [grants],
  );

  const displayedGrants = useMemo(() => {
    if (statusFilter === "active") return activeGrants;
    if (statusFilter === "expired") return expiredGrants;
    if (statusFilter === "revoked") return revokedGrants;
    return grants;
  }, [statusFilter, grants, activeGrants, expiredGrants, revokedGrants]);

  const tabItems: TabItem[] = [
    {
      key: "shared",
      label: `${copy("familyCircle.tabs.shared")}${activeGrants.length > 0 ? ` (${activeGrants.length})` : ""}`,
      icon: "share",
    },
    {
      key: "received",
      label: `${copy("familyCircle.tabs.received")}${notifications.length + relationships.length > 0 ? ` (${notifications.length + relationships.length})` : ""}`,
      icon: "diversity_1",
    },
    {
      key: "log",
      label: copy("familyCircle.tabs.log"),
      icon: "history",
    },
  ];

  return (
    <div className="space-y-6" data-testid="family-sharing-hub">
      {/* 1. Header + CTA */}
      <HealthPageHeader
        title={copy("familyCircle.title")}
        subtitle={copy("familyCircle.description")}
        backHref="/you"
        backLabel={isEn ? "Back to You" : "Quay lại Cá nhân"}
        primaryAction={{
          label: isEn ? "Invite Caregiver / Doctor" : "Mời người chăm sóc / Bác sĩ",
          icon: "person_add",
          href: "/family/invite",
        }}
        secondaryAction={{
          label: copy("familyCircle.accept.start"),
          icon: "verified_user",
          href: "/family/accept",
        }}
      />

      {error ? <InlineError message={error} onRetry={() => void load()} /> : null}

      {/* 2. Explicit Scope Disclosure Banner */}
      <section
        className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-300)]/60 bg-[var(--brand-50)]/20 p-5 shadow-sm space-y-3"
        data-testid="scope-disclosure-banner"
      >
        <div className="flex items-center gap-2.5 text-[var(--text-brand)]">
          <Icon name="check" size="1.25rem" />
          <h2 className="text-sm font-bold text-[var(--text-primary)]">
            {isEn ? "Patient Privacy Protections & Sharing Scope" : "Bảo vệ quyền riêng tư & Minh bạch phạm vi chia sẻ"}
          </h2>
        </div>
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          {isEn
            ? "All shared medical access is strictly scoped, time-bounded, and under your absolute control. Zero internal AI reasoning is ever disclosed."
            : "Mọi quyền truy cập dữ liệu y tế đều được phân quyền chính xác theo danh mục, có thời hạn hiệu lực và có thể thu hồi bất cứ lúc nào. Chuỗi suy luận nội bộ của AI hoàn toàn được bảo mật."}
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-2">
          <div className="rounded-[var(--radius-lg)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/70 p-3 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <Icon name="check" size="0.95rem" className="text-[var(--status-ok-text)]" />
              <span>{isEn ? "Explicit Scope" : "Phân quyền tường minh"}</span>
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              {isEn ? "Only chosen categories (meds, visits, care tasks) are visible." : "Chỉ chia sẻ đúng danh mục được phê duyệt."}
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/70 p-3 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <Icon name="check" size="0.95rem" className="text-[var(--status-ok-text)]" />
              <span>{isEn ? "Zero CoT Exposure" : "Bảo mật suy luận AI"}</span>
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              {isEn ? "Internal AI thought chains are never shared with anyone." : "Không bao giờ để lộ chuỗi tư duy suy luận của AI."}
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/70 p-3 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <Icon name="check" size="0.95rem" className="text-[var(--status-ok-text)]" />
              <span>{isEn ? "Instant Revocation" : "Thu hồi tức thì 1 chạm"}</span>
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              {isEn ? "Revoke any access link instantly with immediate invalidation." : "Vô hiệu hóa ngay lập tức mọi quyền truy cập."}
            </p>
          </div>
          <div className="rounded-[var(--radius-lg)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/70 p-3 space-y-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--text-primary)]">
              <Icon name="check" size="0.95rem" className="text-[var(--status-ok-text)]" />
              <span>{isEn ? "Immutable Audit Log" : "Nhật ký kiểm toán"}</span>
            </div>
            <p className="text-[11px] text-[var(--text-muted)]">
              {isEn ? "Every access event is permanently recorded in your audit trail." : "Ghi nhận minh bạch mọi lượt xem và thao tác."}
            </p>
          </div>
        </div>
      </section>

      {/* Generated Token Notice */}
      {createdToken ? (
        <div
          className="rounded-[var(--radius-2xl)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4 text-xs text-[var(--status-ok-text)] space-y-2 shadow-sm"
          data-testid="grant-created-notice"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon name="check" size="1.1rem" className="text-[var(--status-ok-text)]" />
              <span className="font-bold">
                {isEn ? "Renewal invitation token created" : "Đã tạo mã mời gia hạn quyền truy cập"}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setCreatedToken("")}
              className="text-[var(--status-ok-text)] font-bold hover:underline"
            >
              {isEn ? "Dismiss" : "Đóng"}
            </button>
          </div>
          <p className="text-[11px]">
            {isEn
              ? "Share this secure authorization token with your family member or caregiver:"
              : "Gửi mã ủy quyền bảo mật này cho người thân hoặc người chăm sóc của bạn:"}
          </p>
          <div className="flex items-center gap-2">
            <code className="block flex-1 bg-[var(--surface-panel)] border border-[color:var(--shell-border)] p-2.5 rounded-[var(--radius-lg)] text-[11px] font-mono break-all text-[var(--text-primary)]">
              {createdToken}
            </code>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleCopyToken}
              icon={copiedToken ? "check" : "share"}
            >
              {copiedToken ? (isEn ? "Copied" : "Đã chép") : isEn ? "Copy" : "Sao chép"}
            </Button>
          </div>
        </div>
      ) : null}

      {/* Main Tabs Navigation */}
      <Tabs
        idBase="family-support"
        ariaLabel={copy("familyCircle.tabs.label")}
        active={activeTab}
        onChange={changeTab}
        items={tabItems}
      />

      {loading ? (
        <LoadingCards count={2} />
      ) : (
        <>
          {/* 3. Tab: I Share (Active Sharing Grants List Rows) */}
          <TabPanel idBase="family-support" tabKey="shared" active={activeTab}>
            <div className="space-y-4" data-testid="shared-tab-panel">
              {/* Filter Pills Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[color:var(--shell-border)]/60 pb-3">
                <div>
                  <h2 className="font-bold text-base text-[var(--text-primary)]">
                    {copy("familyCircle.grants.title")}
                  </h2>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("familyCircle.grants.description")}
                  </p>
                </div>

                <div className="flex items-center gap-1.5 bg-[var(--surface-muted)] p-1 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)]">
                  {(
                    [
                      { key: "all", label: isEn ? "All" : "Tất cả", count: grants.length },
                      { key: "active", label: isEn ? "Active" : "Đang hoạt động", count: activeGrants.length },
                      { key: "expired", label: isEn ? "Expired" : "Đã hết hạn", count: expiredGrants.length },
                      { key: "revoked", label: isEn ? "Revoked" : "Đã thu hồi", count: revokedGrants.length },
                    ] as const
                  ).map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => setStatusFilter(item.key)}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-[var(--radius-md)] transition ${
                        statusFilter === item.key
                          ? "bg-[var(--surface-panel)] text-[var(--brand-600)] shadow-sm"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                      }`}
                      data-testid={`filter-${item.key}`}
                    >
                      {item.label} ({item.count})
                    </button>
                  ))}
                </div>
              </div>

              {/* Grants List Rows */}
              {displayedGrants.length > 0 ? (
                <div className="space-y-3" data-testid="grants-list">
                  {displayedGrants.map((grant) => {
                    const status = getGrantStatus(grant);
                    const { days: daysLeft, isExpired } = getDaysRemaining(grant.expires_at);
                    const isRevoked = status === "revoked";
                    const displayName = grant.supporter_label || copy("familyCircle.label.supporter");

                    return (
                      <div
                        key={grant.id}
                        className={`rounded-[var(--radius-2xl)] border p-5 shadow-sm transition space-y-4 ${
                          isRevoked
                            ? "border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)]/50 opacity-80"
                            : isExpired
                              ? "border-[color:var(--status-warn-border)]/60 bg-[var(--surface-panel)]"
                              : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] hover:border-[color:var(--brand-400)]/60"
                        }`}
                        data-testid={`grant-card-${grant.id}`}
                      >
                        {/* Top: Who & Status & Actions */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                          <div className="flex items-center gap-3.5">
                            <div className="w-11 h-11 rounded-full bg-[var(--brand-50)] text-[var(--brand-700)] border border-[color:var(--brand-200)] flex items-center justify-center font-bold text-base shrink-0">
                              {displayName.charAt(0).toUpperCase()}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                                  {displayName}
                                </h3>
                                <Badge
                                  tone={
                                    status === "active"
                                      ? "ok"
                                      : status === "expired"
                                        ? "warn"
                                        : "danger"
                                  }
                                >
                                  {status === "active" ? (
                                    <span className="flex items-center gap-1">
                                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                      {isEn ? "Active" : "Đang hoạt động"}
                                    </span>
                                  ) : status === "expired" ? (
                                    isEn ? "Expired" : "Đã hết hạn"
                                  ) : (
                                    copy("familyCircle.action.revoked")
                                  )}
                                </Badge>
                              </div>
                              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                                {copy("familyCircle.label.supporter")} · {purposeLabel(grant.purpose)}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 self-end sm:self-center">
                            {!isRevoked ? (
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                disabled={saving}
                                onClick={() => void renew(grant.id)}
                                icon="autorenew"
                                data-testid={`renew-grant-btn-${grant.id}`}
                              >
                                {copy("familyCircle.action.renew")}
                              </Button>
                            ) : null}

                            <Button
                              type="button"
                              variant="danger"
                              size="sm"
                              disabled={saving || isRevoked}
                              onClick={() => setGrantToRevoke(grant)}
                              icon="delete"
                              data-testid={`revoke-grant-btn-${grant.id}`}
                            >
                              {isRevoked
                                ? copy("familyCircle.action.revoked")
                                : copy("familyCircle.action.revoke")}
                            </Button>
                          </div>
                        </div>

                        {/* Middle: Scoped Category & Allowed Permissions */}
                        <div className="pt-3 border-t border-[color:var(--shell-border)]/60 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                          {/* What categories */}
                          <div className="space-y-1">
                            <span className="text-[11px] font-semibold text-[var(--text-secondary)] block">
                              {isEn ? "Shared Scope:" : "Phạm vi chia sẻ:"}
                            </span>
                            <div className="inline-flex items-center gap-1.5 rounded-[var(--radius-md)] bg-[var(--brand-50)]/50 border border-[color:var(--brand-200)] px-2.5 py-1 text-[var(--brand-700)] font-medium">
                              <Icon name={objectIcon(grant.object_type)} size="0.9rem" />
                              <span>{objectLabel(grant.object_type)}</span>
                            </div>
                          </div>

                          {/* Permission */}
                          <div className="space-y-1">
                            <span className="text-[11px] font-semibold text-[var(--text-secondary)] block">
                              {isEn ? "Permissions:" : "Quyền hạn:"}
                            </span>
                            <div className="flex flex-wrap items-center gap-1">
                              {grant.allowed_actions.map((act) => (
                                <span
                                  key={act}
                                  className="rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-primary)] font-medium border border-[color:var(--shell-border)]/60"
                                >
                                  {actionLabel(act)}
                                </span>
                              ))}
                            </div>
                          </div>

                          {/* Expiry countdown */}
                          <div className="space-y-1">
                            <span className="text-[11px] font-semibold text-[var(--text-secondary)] block">
                              {isEn ? "Validity Window:" : "Thời hạn hiệu lực:"}
                            </span>
                            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--text-secondary)] bg-[var(--surface-muted)] px-2.5 py-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60">
                              <Icon name="progress" size="0.85rem" className="text-[var(--text-brand)]" />
                              <span>
                                {isRevoked
                                  ? copy("familyCircle.action.revoked")
                                  : isExpired
                                    ? isEn ? "Expired" : "Đã hết hạn"
                                    : isEn
                                      ? `${daysLeft} days remaining (${formatLocaleDate(language, grant.expires_at, { dateStyle: "medium" })})`
                                      : `Còn ${daysLeft} ngày (${formatLocaleDate(language, grant.expires_at, { dateStyle: "medium" })})`}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <EmptyState
                  icon="family_restroom"
                  title={copy("familyCircle.grants.emptyTitle")}
                  description={copy("familyCircle.grants.emptyDescription")}
                >
                  <Button as="link" href="/family/invite" icon="person_add">
                    {copy("familyCircle.invite.start")}
                  </Button>
                </EmptyState>
              )}

              {/* Dashed Add Action Button */}
              <Link
                href="/family/invite"
                className="w-full py-4 rounded-[var(--radius-2xl)] border-2 border-dashed border-[color:var(--shell-border)] hover:border-[color:var(--brand-500)] hover:bg-[var(--brand-50)]/10 text-[var(--text-secondary)] hover:text-[var(--text-brand)] transition flex items-center justify-center gap-2 text-xs font-bold shadow-sm"
              >
                <Icon name="contact" size="1.1rem" />
                <span>{isEn ? "Invite Another Caregiver or Doctor" : "Mời thêm người chăm sóc hoặc Bác sĩ"}</span>
              </Link>
            </div>
          </TabPanel>

          {/* 4. Tab: Shared With Me (Delegated tasks from family members) */}
          <TabPanel idBase="family-support" tabKey="received" active={activeTab}>
            <div className="space-y-6" data-testid="received-tab-panel">
              {/* Section 4.1: Delegated Tasks from Family Members */}
              <section className="space-y-3" data-testid="delegated-tasks-section">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[var(--text-brand)]">
                    <Icon name="check" size="1.25rem" />
                    <h2 className="text-base font-bold text-[var(--text-primary)]">
                      {isEn ? "Delegated Care Tasks from Family" : "Nhiệm vụ & Việc chăm sóc được ủy quyền"}
                    </h2>
                  </div>
                  {notifications.length > 0 ? (
                    <Badge tone="brand">
                      {notifications.length} {isEn ? "pending" : "đang chờ"}
                    </Badge>
                  ) : null}
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  {isEn
                    ? "Care tasks and adherence checks assigned to you by family members who granted you access."
                    : "Các nhiệm vụ chăm sóc và kiểm tra tuân thủ được người thân ủy thác cho bạn."}
                </p>

                {notifications.length > 0 ? (
                  <div className="space-y-3">
                    {notifications.map((notif) => {
                      const { days: daysLeft, isExpired } = getDaysRemaining(notif.expires_at);
                      const isAcknowledging = acknowledgingId === notif.id;

                      return (
                        <div
                          key={notif.id}
                          className="rounded-[var(--radius-2xl)] border border-[color:var(--brand-300)]/60 bg-[var(--surface-panel)] p-5 shadow-sm space-y-3"
                          data-testid={`delegated-task-${notif.id}`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div className="flex items-start gap-3">
                              <div className="w-10 h-10 rounded-full bg-[var(--brand-50)] text-[var(--brand-600)] flex items-center justify-center font-bold text-sm shrink-0 border border-[color:var(--brand-200)]">
                                <Icon name="check" size="1.2rem" />
                              </div>
                              <div>
                                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                                  {notif.message || (isEn ? "Delegated Care Task" : "Nhiệm vụ chăm sóc người thân")}
                                </h3>
                                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                                  {purposeLabel(notif.purpose)} · {isEn ? "Action: " : "Hành động: "}{actionLabel(notif.action)}
                                </p>
                              </div>
                            </div>

                            <Button
                              type="button"
                              variant="primary"
                              size="sm"
                              loading={isAcknowledging}
                              disabled={isAcknowledging}
                              onClick={() => void handleAcknowledgeNotification(notif)}
                              icon="check"
                              data-testid={`acknowledge-task-btn-${notif.id}`}
                            >
                              {isEn ? "Confirm Completed" : "Xác nhận đã nhận"}
                            </Button>
                          </div>

                          <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                            <span>{isEn ? "Task ID:" : "Mã nhiệm vụ:"} {notif.task_id}</span>
                            <span>
                              {isExpired
                                ? isEn ? "Expired" : "Đã hết hạn"
                                : isEn
                                  ? `${daysLeft} days to complete`
                                  : `Hạn hoàn thành: Còn ${daysLeft} ngày`}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-[var(--radius-xl)] bg-[var(--surface-muted)] p-4 text-xs text-[var(--text-secondary)] text-center border border-[color:var(--shell-border)]">
                    {isEn ? "No pending delegated care tasks." : "Hiện không có nhiệm vụ chăm sóc nào đang chờ bạn xử lý."}
                  </div>
                )}
              </section>

              {/* Section 4.2: Shared Records / Relationships */}
              <section className="space-y-3" data-testid="received-relationships-section">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 border-b border-[color:var(--shell-border)]/60 pb-3">
                  <div>
                    <h2 className="font-bold text-base text-[var(--text-primary)]">
                      {copy("familyCircle.relationships.title")}
                    </h2>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {copy("familyCircle.relationships.description")}
                    </p>
                  </div>
                  <Button as="link" href="/family/accept" size="sm" variant="secondary" icon="verified_user">
                    {copy("familyCircle.accept.start")}
                  </Button>
                </div>

                {relationships.length > 0 ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    {relationships.map((rel) => (
                      <div
                        key={rel.id}
                        className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm space-y-3"
                        data-testid={`relationship-card-${rel.id}`}
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-[var(--brand-50)] text-[var(--brand-700)] flex items-center justify-center font-bold text-sm">
                            {(rel.supporter_label || copy("familyCircle.label.sharedScope")).charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <h3 className="text-sm font-bold text-[var(--text-primary)]">
                              {rel.supporter_label || copy("familyCircle.label.sharedScope")}
                            </h3>
                            <p className="text-xs text-[var(--text-secondary)]">
                              {objectLabel(rel.object_type)} · {purposeLabel(rel.purpose)}
                            </p>
                          </div>
                        </div>

                        <div className="pt-2 border-t border-[color:var(--shell-border)]/60 flex flex-wrap items-center justify-between gap-2 text-xs">
                          <div className="flex flex-wrap gap-1">
                            {rel.allowed_actions.map((act) => (
                              <span
                                key={act}
                                className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-primary)] border border-[color:var(--shell-border)]/60"
                              >
                                {actionLabel(act)}
                              </span>
                            ))}
                          </div>
                          <span className="text-[11px] text-[var(--text-muted)]">
                            {formatLocaleDate(language, rel.expires_at, { dateStyle: "short" })}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : notifications.length === 0 ? (
                  <EmptyState
                    icon="diversity_1"
                    title={copy("familyCircle.relationships.emptyTitle")}
                    description={copy("familyCircle.relationships.emptyDescription")}
                  >
                    <Button as="link" href="/family/accept" variant="secondary" icon="check">
                      {copy("familyCircle.accept.start")}
                    </Button>
                  </EmptyState>
                ) : null}
              </section>
            </div>
          </TabPanel>

          {/* 5. Tab: Access Audit Log History */}
          <TabPanel idBase="family-support" tabKey="log" active={activeTab}>
            <section
              className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm space-y-4"
              data-testid="access-history-section"
            >
              <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
                <div className="flex items-center gap-2 text-[var(--text-brand)]">
                  <Icon name="progress" size="1.25rem" />
                  <div>
                    <h2 className="text-base font-bold text-[var(--text-primary)]">
                      {copy("familyCircle.accessLog.title")}
                    </h2>
                    <p className="text-xs text-[var(--text-secondary)]">
                      {isEn ? "Immutable audit trail of all access events." : "Nhật ký kiểm toán truy cập bảo mật bất biến."}
                    </p>
                  </div>
                </div>
                <span className="text-[11px] font-mono text-[var(--text-muted)] bg-[var(--surface-muted)] px-2.5 py-1 rounded-[var(--radius-md)] border border-[color:var(--shell-border)]/60">
                  {isEn ? "Append-only ledger" : "Sổ nhật ký bảo mật"}
                </span>
              </div>

              {logs.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs" data-testid="access-logs-table">
                    <thead className="border-b border-[color:var(--shell-border)]/60 text-[var(--text-secondary)] font-semibold">
                      <tr>
                        <th className="pb-2.5">{isEn ? "Timestamp" : "Thời gian"}</th>
                        <th className="pb-2.5">{isEn ? "Actor" : "Người truy cập"}</th>
                        <th className="pb-2.5">{isEn ? "Data Category" : "Dữ liệu truy cập"}</th>
                        <th className="pb-2.5">{isEn ? "Action" : "Hành động"}</th>
                        <th className="pb-2.5 text-right">{isEn ? "Outcome" : "Kết quả"}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[color:var(--shell-border)]/40">
                      {logs.slice(0, 50).map((log) => {
                        const outcomeCode = accessLogOutcomeCode(log.outcome_code, log.outcome);
                        const outcomeLabel = accessLogOutcomeLabel(outcomeCode);
                        const actorLabel = accessLogActorLabel(log.actor_code, log.actor_label);
                        const actLabel = accessLogActionLabel(log.action_code || log.action);
                        const objLabel = objectLabel(log.object_type);

                        return (
                          <tr key={log.id} className="text-[var(--text-primary)] hover:bg-[var(--surface-muted)]/40 transition">
                            <td className="py-3 font-mono text-[11px] text-[var(--text-muted)] whitespace-nowrap">
                              {formatLocaleDate(language, log.created_at, {
                                dateStyle: "short",
                                timeStyle: "short",
                              })}
                            </td>
                            <td className="py-3 font-semibold">
                              {actorLabel}
                            </td>
                            <td className="py-3">
                              <span className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-medium border border-[color:var(--shell-border)]/60">
                                <Icon name={objectIcon(log.object_type)} size="0.8rem" />
                                <span>{objLabel}</span>
                              </span>
                            </td>
                            <td className="py-3 capitalize text-[var(--text-secondary)]">
                              {actLabel}
                            </td>
                            <td className="py-3 text-right">
                              <Badge
                                tone={
                                  outcomeCode === "allowed"
                                    ? "ok"
                                    : outcomeCode === "denied"
                                      ? "danger"
                                      : "warn"
                                }
                              >
                                {outcomeLabel}
                              </Badge>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-[var(--text-muted)] italic py-3 text-center">
                  {copy("familyCircle.accessLog.empty")}
                </p>
              )}
            </section>
          </TabPanel>
        </>
      )}

      {/* Revoke Confirmation Dialog */}
      {grantToRevoke ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          data-testid="revoke-confirm-dialog"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-[var(--radius-2xl)] border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-[var(--status-danger-text)]">
              <Icon name="warning" size="1.5rem" />
              <h3 className="text-base font-bold text-[var(--text-primary)]">
                {isEn ? "Revoke Sharing Grant?" : "Thu hồi quyền chia sẻ?"}
              </h3>
            </div>

            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {isEn
                ? `Are you sure you want to revoke access for ${grantToRevoke.supporter_label || "this supporter"}? They will immediately lose access to your medical records and shared links will be disabled.`
                : `Bạn có chắc chắn muốn thu hồi quyền của ${grantToRevoke.supporter_label || "người nhận"}? Người này sẽ lập tức mất quyền truy cập hồ sơ sức khỏe và liên kết chia sẻ sẽ bị vô hiệu hóa.`}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-[color:var(--shell-border)]/60">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setGrantToRevoke(null)}
                disabled={saving}
                data-testid="cancel-revoke-btn"
              >
                {isEn ? "Cancel" : "Hủy"}
              </Button>
              <Button
                type="button"
                variant="danger"
                size="sm"
                loading={saving}
                onClick={() => void revoke(grantToRevoke.id)}
                data-testid="confirm-revoke-btn"
              >
                {isEn ? "Revoke Immediately" : "Thu hồi ngay lập tức"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default function FamilyPage() {
  return (
    <Suspense fallback={null}>
      <FamilyWorkspace />
    </Suspense>
  );
}
