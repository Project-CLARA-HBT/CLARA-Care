"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import EmptyState from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  WorkspaceConversationShareListItem,
  createWorkspaceConversationShare,
  listWorkspaceShares,
  revokeWorkspaceConversationShare,
} from "@/lib/workspace";

function isShareExpired(expiresAt?: string | null): boolean {
  if (!expiresAt) return false;
  const expiryTime = new Date(expiresAt).getTime();
  if (Number.isNaN(expiryTime)) return false;
  return expiryTime <= Date.now();
}

function getExpiryCountdown(
  expiresAt?: string | null,
  isActive?: boolean,
  language: "vi" | "en" = "vi",
): {
  label: string;
  tone: "ok" | "warn" | "danger" | "neutral";
  isExpired: boolean;
} {
  if (!isActive) {
    return {
      label: t(language, "chatShares.status.revoked"),
      tone: "neutral",
      isExpired: true,
    };
  }
  if (!expiresAt) {
    return {
      label: t(language, "chatShares.noExpiry"),
      tone: "neutral",
      isExpired: false,
    };
  }
  const expiryTime = new Date(expiresAt).getTime();
  if (Number.isNaN(expiryTime)) {
    return {
      label: t(language, "chatShares.noExpiry"),
      tone: "neutral",
      isExpired: false,
    };
  }

  const now = Date.now();
  const diffMs = expiryTime - now;

  if (diffMs <= 0) {
    return {
      label: t(language, "chatShares.status.expired"),
      tone: "danger",
      isExpired: true,
    };
  }

  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffHours < 24) {
    const hours = Math.max(1, diffHours);
    return {
      label: language === "vi" ? `Hết hạn sau ${hours} giờ` : `Expires in ${hours}h`,
      tone: "danger",
      isExpired: false,
    };
  }
  if (diffDays <= 3) {
    return {
      label: language === "vi" ? `Còn ${diffDays} ngày` : `${diffDays} days left`,
      tone: "warn",
      isExpired: false,
    };
  }
  return {
    label: language === "vi" ? `Còn ${diffDays} ngày` : `${diffDays} days left`,
    tone: "ok",
    isExpired: false,
  };
}

export default function ChatShareManagementPage() {
  const language = useUILanguage();
  const [items, setItems] = useState<WorkspaceConversationShareListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "active" | "archive">("all");
  const [revokingItem, setRevokingItem] = useState<WorkspaceConversationShareListItem | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await listWorkspaceShares({ limit: 120, activeOnly: false });
      setItems(rows);
    } catch {
      setError(t(language, "chatShares.loadError"));
    } finally {
      setLoading(false);
    }
  }, [language]);

  useEffect(() => {
    void load();
  }, [load]);

  const onRevoke = async (conversationId: number) => {
    setActionLoading(conversationId);
    setError("");
    try {
      await revokeWorkspaceConversationShare(conversationId);
      setNotice(t(language, "chatShares.revokeSuccess", { id: conversationId }));
      setRevokingItem(null);
      await load();
    } catch {
      setError(t(language, "chatShares.revokeError"));
    } finally {
      setActionLoading(null);
    }
  };

  const onReissue = async (conversationId: number) => {
    setActionLoading(conversationId);
    setError("");
    try {
      const issued = await createWorkspaceConversationShare(conversationId, {
        rotate: true,
      });
      if (!issued.public_url) throw new Error("share_url_not_issued");
      try {
        await navigator.clipboard.writeText(issued.public_url);
      } catch {
        // The capability exists only in this issuance response. Preserve a
        // manual-copy path rather than dropping it when Clipboard is blocked.
        window.prompt(t(language, "chatShares.copyPrompt"), issued.public_url);
      }
      setNotice(t(language, "chatShares.reissueSuccess"));
      await load();
    } catch {
      setError(t(language, "chatShares.reissueError"));
    } finally {
      setActionLoading(null);
    }
  };

  const { activeItems, archivedItems } = useMemo(() => {
    const active: WorkspaceConversationShareListItem[] = [];
    const archived: WorkspaceConversationShareListItem[] = [];

    const query = searchQuery.trim().toLowerCase();
    const filtered = query
      ? items.filter(
          (item) =>
            item.conversation_title.toLowerCase().includes(query) ||
            String(item.conversation_id).includes(query) ||
            (item.recipient && item.recipient.toLowerCase().includes(query)),
        )
      : items;

    for (const item of filtered) {
      if (item.is_active && !isShareExpired(item.expires_at)) {
        active.push(item);
      } else {
        archived.push(item);
      }
    }

    return { activeItems: active, archivedItems: archived };
  }, [items, searchQuery]);

  const totalActiveCount = useMemo(
    () => items.filter((item) => item.is_active && !isShareExpired(item.expires_at)).length,
    [items],
  );
  const totalArchivedCount = useMemo(
    () => items.filter((item) => !item.is_active || isShareExpired(item.expires_at)).length,
    [items],
  );

  const renderShareRow = (item: WorkspaceConversationShareListItem, isActive: boolean) => {
    const countdown = getExpiryCountdown(item.expires_at, item.is_active, language);

    return (
      <div
        key={item.share_id}
        data-testid={`share-row-${item.conversation_id}`}
        className="flex flex-col gap-3.5 p-4 sm:p-5 transition hover:bg-[var(--surface-muted)]/50"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          {/* Left info */}
          <div className="flex min-w-0 flex-1 items-start gap-3.5">
            <div
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-xl)] ${
                isActive
                  ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  : "bg-[var(--surface-muted)] text-[var(--text-muted)]"
              }`}
            >
              <Icon name="share" size="1.2rem" />
            </div>

            <div className="min-w-0 flex-1 space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-bold text-[var(--text-brand)]">
                  #{item.conversation_id}
                </span>
                <h3 className="truncate text-sm font-semibold text-[var(--text-primary)] sm:text-base">
                  {item.conversation_title || `Conversation #${item.conversation_id}`}
                </h3>
                {isActive ? (
                  <Badge tone="ok">{t(language, "chatShares.status.active")}</Badge>
                ) : !item.is_active ? (
                  <Badge tone="neutral">{t(language, "chatShares.status.revoked")}</Badge>
                ) : (
                  <Badge tone="danger">{t(language, "chatShares.status.expired")}</Badge>
                )}
              </div>

              {/* Scope & Metadata Row: Recipient, Shared At, Expiry Countdown, Access Count */}
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--text-secondary)]">
                {/* Recipient */}
                <div className="flex items-center gap-1">
                  <Icon name="contact" size="0.9rem" className="text-[var(--text-muted)]" />
                  <span className="font-medium text-[var(--text-primary)]">
                    {item.recipient || t(language, "chatShares.label.publicRecipient")}
                  </span>
                </div>

                {/* Shared at */}
                <div className="flex items-center gap-1">
                  <Icon name="calendar" size="0.9rem" className="text-[var(--text-muted)]" />
                  <span>
                    {t(language, "chatShares.label.sharedAt")}:{" "}
                    {formatLocaleDate(language, item.created_at, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    })}
                  </span>
                </div>

                {/* Expiry countdown */}
                <div className="flex items-center gap-1.5">
                  <Icon name="progress" size="0.9rem" className="text-[var(--text-muted)]" />
                  <span>{t(language, "chatShares.label.expires")}:</span>
                  <Badge tone={countdown.tone} className="!px-2 !py-0.5 text-[11px]">
                    {countdown.label}
                  </Badge>
                </div>

                {/* Access count */}
                <div className="flex items-center gap-1">
                  <Icon name="eye" size="0.9rem" className="text-[var(--text-muted)]" />
                  <span>
                    {t(language, "chatShares.label.accessCount")}:{" "}
                    <strong className="font-semibold text-[var(--text-primary)]">
                      {item.access_count ?? item.message_count}
                    </strong>
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Action buttons */}
          <div className="flex shrink-0 items-center gap-2 self-start pl-13 sm:self-center sm:pl-0">
            {isActive ? (
              <>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  icon="refresh"
                  disabled={actionLoading === item.conversation_id}
                  onClick={() => void onReissue(item.conversation_id)}
                  data-testid={`rotate-token-btn-${item.conversation_id}`}
                >
                  {t(language, "chatShares.reissue")}
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  icon="link_off"
                  disabled={actionLoading === item.conversation_id}
                  onClick={() => setRevokingItem(item)}
                  data-testid={`revoke-btn-${item.conversation_id}`}
                >
                  {t(language, "chatShares.revoke")}
                </Button>
              </>
            ) : (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon="refresh"
                disabled={actionLoading === item.conversation_id}
                onClick={() => void onReissue(item.conversation_id)}
                data-testid={`reissue-btn-${item.conversation_id}`}
              >
                {t(language, "chatShares.reissue")}
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <PageShell
      variant="plain"
      title={t(language, "chatShares.title")}
      description={t(language, "chatShares.description")}
    >
      <div className="space-y-6">
        {/* 1. Header toolbar: Back to chat, Reload, Filter tabs & Search */}
        <div className="flex flex-col gap-4 rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button as="link" href="/chat" variant="secondary" size="sm" icon="arrow_back">
              {t(language, "chatShares.backToChat")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon="refresh"
              onClick={() => void load()}
            >
              {t(language, "chatShares.reload")}
            </Button>
          </div>

          {/* Filter tabs & Search input */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="inline-flex rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1">
              <button
                type="button"
                data-testid="filter-all"
                onClick={() => setActiveTab("all")}
                className={`flex items-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "all"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                <span>{t(language, "chatShares.tabs.all")}</span>
                <span className="rounded-full bg-[var(--surface-panel)] px-1.5 py-0.2 text-[10px] text-[var(--text-secondary)]">
                  {items.length}
                </span>
              </button>
              <button
                type="button"
                data-testid="filter-active"
                onClick={() => setActiveTab("active")}
                className={`flex items-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "active"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                <span>{t(language, "chatShares.tabs.active")}</span>
                <span className="rounded-full bg-[var(--surface-panel)] px-1.5 py-0.2 text-[10px] text-[var(--status-ok-text)]">
                  {totalActiveCount}
                </span>
              </button>
              <button
                type="button"
                data-testid="filter-archive"
                onClick={() => setActiveTab("archive")}
                className={`flex items-center gap-1.5 rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-semibold transition ${
                  activeTab === "archive"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                <span>{t(language, "chatShares.tabs.archive")}</span>
                <span className="rounded-full bg-[var(--surface-panel)] px-1.5 py-0.2 text-[10px] text-[var(--text-secondary)]">
                  {totalArchivedCount}
                </span>
              </button>
            </div>

            {/* Search Input */}
            <div className="relative min-w-[240px]">
              <Icon
                name="search"
                size="1rem"
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                type="text"
                data-testid="shares-search-input"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t(language, "chatShares.filter.placeholder")}
                className="w-full rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-1.5 pl-9 pr-3 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] transition focus:border-[color:var(--brand-500)] focus:outline-none focus:ring-1 focus:ring-[var(--brand-500)]"
              />
            </div>
          </div>
        </div>

        {/* Notices & Errors */}
        {error ? <InlineError message={error} /> : null}
        {!error && notice ? (
          <div className="flex items-center gap-2 rounded-[var(--radius-xl)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-sm text-[var(--status-ok-text)]">
            <Icon name="check" size="1.1rem" />
            <span>{notice}</span>
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-8 text-center">
            <p className="text-sm text-[var(--text-muted)]">{t(language, "chatShares.loading")}</p>
          </div>
        ) : null}

        {/* Empty state when no items exist at all */}
        {!loading && items.length === 0 ? (
          <div data-testid="shares-empty-state">
            <EmptyState
              icon={<Icon name="share" size="1.75rem" />}
              title={t(language, "chatShares.empty")}
              description={t(language, "chatShares.description")}
              primaryAction={{
                label: t(language, "chatShares.backToChat"),
                href: "/chat",
              }}
            />
          </div>
        ) : null}

        {/* Filter empty states */}
        {!loading && items.length > 0 && activeTab === "active" && activeItems.length === 0 ? (
          <div data-testid="shares-empty-active">
            <EmptyState
              icon={<Icon name="share" size="1.75rem" />}
              title={t(language, "chatShares.empty.active")}
              description={t(language, "chatShares.description")}
              primaryAction={{
                label: t(language, "chatShares.backToChat"),
                href: "/chat",
              }}
            />
          </div>
        ) : null}

        {!loading && items.length > 0 && activeTab === "archive" && archivedItems.length === 0 ? (
          <div data-testid="shares-empty-archive">
            <EmptyState
              icon={<Icon name="progress" size="1.75rem" />}
              title={t(language, "chatShares.empty.archive")}
              description={t(language, "chatShares.archiveSection.description")}
            />
          </div>
        ) : null}

        {/* 2. Active shares list rows */}
        {!loading && (activeTab === "all" || activeTab === "active") && activeItems.length > 0 ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <div>
                <h2 className="text-sm font-bold text-[var(--text-primary)] sm:text-base">
                  {t(language, "chatShares.activeSection.title")}
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t(language, "chatShares.activeSection.description")}
                </p>
              </div>
              <Badge tone="ok">{activeItems.length}</Badge>
            </div>

            <div
              data-testid="active-shares-list"
              className="divide-y divide-[color:var(--shell-border)] rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm"
            >
              {activeItems.map((item) => renderShareRow(item, true))}
            </div>
          </section>
        ) : null}

        {/* 3. Expired / Revoked shares archive */}
        {!loading &&
        (activeTab === "all" || activeTab === "archive") &&
        archivedItems.length > 0 ? (
          <section className="space-y-3">
            <div className="flex items-center justify-between px-1">
              <div>
                <h2 className="text-sm font-bold text-[var(--text-primary)] sm:text-base">
                  {t(language, "chatShares.archiveSection.title")}
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t(language, "chatShares.archiveSection.description")}
                </p>
              </div>
              <Badge tone="neutral">{archivedItems.length}</Badge>
            </div>

            <div
              data-testid="archive-shares-list"
              className="divide-y divide-[color:var(--shell-border)] rounded-[var(--radius-2xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-sm"
            >
              {archivedItems.map((item) => renderShareRow(item, false))}
            </div>
          </section>
        ) : null}
      </div>

      {/* Revocation Confirmation Modal */}
      {revokingItem ? (
        <Modal
          open={Boolean(revokingItem)}
          onClose={() => setRevokingItem(null)}
          title={t(language, "chatShares.confirmRevoke.title")}
        >
          <div data-testid="revoke-confirm-modal" className="space-y-4">
            <p className="text-sm text-[var(--text-secondary)]">
              {t(language, "chatShares.confirmRevoke.description")}
            </p>
            <div className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-primary)]">
              <span className="font-semibold text-[var(--text-brand)]">
                #{revokingItem.conversation_id}
              </span>{" "}
              · {revokingItem.conversation_title}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => setRevokingItem(null)}
                data-testid="cancel-revoke-btn"
              >
                {t(language, "chatShares.confirmRevoke.cancel")}
              </Button>
              <Button
                type="button"
                variant="danger"
                icon="link_off"
                disabled={actionLoading === revokingItem.conversation_id}
                onClick={() => void onRevoke(revokingItem.conversation_id)}
                data-testid="confirm-revoke-btn"
              >
                {t(language, "chatShares.confirmRevoke.confirm")}
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </PageShell>
  );
}
