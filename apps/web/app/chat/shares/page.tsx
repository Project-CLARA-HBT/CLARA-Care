"use client";

import { useCallback, useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InlineError } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  WorkspaceConversationShareListItem,
  createWorkspaceConversationShare,
  listWorkspaceShares,
  revokeWorkspaceConversationShare,
} from "@/lib/workspace";

export default function ChatShareManagementPage() {
  const language = useUILanguage();
  const [items, setItems] = useState<WorkspaceConversationShareListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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
    try {
      await revokeWorkspaceConversationShare(conversationId);
      setNotice(t(language, "chatShares.revokeSuccess", { id: conversationId }));
      await load();
    } catch {
      setError(t(language, "chatShares.revokeError"));
    }
  };

  const onReissue = async (conversationId: number) => {
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
    }
  };

  return (
    <PageShell
      variant="plain"
      title={t(language, "chatShares.title")}
      description={t(language, "chatShares.description")}
    >
      <div className="chrome-panel rounded-2xl p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
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

        {loading ? (
          <p className="text-sm text-[var(--text-muted)]">
            {t(language, "chatShares.loading")}
          </p>
        ) : null}
        {error ? <InlineError message={error} /> : null}
        {!error && notice ? (
          <p className="text-sm text-[var(--status-ok-text)]">{notice}</p>
        ) : null}

        {!loading ? (
          items.length ? (
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] text-left text-xs uppercase tracking-[0.1em] text-[var(--text-muted)]">
                    <th className="px-2 py-2">{t(language, "chatShares.table.conversation")}</th>
                    <th className="px-2 py-2">{t(language, "chatShares.table.messages")}</th>
                    <th className="px-2 py-2">{t(language, "chatShares.table.status")}</th>
                    <th className="px-2 py-2">{t(language, "chatShares.table.expires")}</th>
                    <th className="px-2 py-2">{t(language, "chatShares.table.publicUrl")}</th>
                    <th className="px-2 py-2">{t(language, "chatShares.table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.share_id} className="border-b border-[color:var(--shell-border)]">
                      <td className="px-2 py-2">
                        <div className="font-semibold text-[var(--text-primary)]">#{item.conversation_id}</div>
                        <div className="line-clamp-2 text-xs text-[var(--text-secondary)]">{item.conversation_title}</div>
                      </td>
                      <td className="px-2 py-2 text-[var(--text-secondary)]">{item.message_count}</td>
                      <td className="px-2 py-2">
                        {item.is_active ? (
                          <Badge tone="ok">{t(language, "chatShares.status.active")}</Badge>
                        ) : (
                          <Badge tone="neutral">{t(language, "chatShares.status.revoked")}</Badge>
                        )}
                      </td>
                      <td className="px-2 py-2 text-xs text-[var(--text-secondary)]">
                        {item.expires_at
                          ? formatLocaleDate(language, item.expires_at, {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })
                          : t(language, "chatShares.noExpiry")}
                      </td>
                      <td className="max-w-[28rem] px-2 py-2 text-xs text-[var(--text-secondary)]">
                        {t(language, "chatShares.linkReissueRequired")}
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1.5">
                          {item.is_active ? (
                            <>
                              <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                icon="refresh"
                                onClick={() => void onReissue(item.conversation_id)}
                              >
                                {t(language, "chatShares.reissue")}
                              </Button>
                              <Button
                                type="button"
                                variant="danger"
                                size="sm"
                                icon="link_off"
                                onClick={() => void onRevoke(item.conversation_id)}
                              >
                                {t(language, "chatShares.revoke")}
                              </Button>
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">
              {t(language, "chatShares.empty")}
            </p>
          )
        ) : null}
      </div>
    </PageShell>
  );
}
