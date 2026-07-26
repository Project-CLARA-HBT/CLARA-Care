"use client";

import { useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InlineError } from "@/components/ui/surface";
import {
  WorkspaceConversationShareListItem,
  listWorkspaceShares,
  revokeWorkspaceConversationShare,
} from "@/lib/workspace";

export default function ChatShareManagementPage() {
  const [items, setItems] = useState<WorkspaceConversationShareListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await listWorkspaceShares({ limit: 120, activeOnly: false });
      setItems(rows);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải danh sách share.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const onRevoke = async (conversationId: number) => {
    try {
      await revokeWorkspaceConversationShare(conversationId);
      setNotice(`Đã thu hồi share cho conversation #${conversationId}.`);
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể thu hồi share.");
    }
  };

  const onCopy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setNotice("Đã copy public URL.");
    } catch {
      window.prompt("Copy public URL", url);
    }
  };

  return (
    <PageShell
      variant="plain"
      title="Share Management"
      description="Quản lý toàn bộ public links của Chat Workspace."
    >
      <div className="chrome-panel rounded-2xl p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <Button as="link" href="/chat" variant="secondary" size="sm" icon="arrow_back">
            Back to Chat
          </Button>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={() => void load()}
          >
            Reload
          </Button>
        </div>

        {loading ? <p className="text-sm text-[var(--text-muted)]">Đang tải...</p> : null}
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
                    <th className="px-2 py-2">Conversation</th>
                    <th className="px-2 py-2">Messages</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Expires</th>
                    <th className="px-2 py-2">Public URL</th>
                    <th className="px-2 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={`${item.conversation_id}-${item.share_token}`} className="border-b border-[color:var(--shell-border)]">
                      <td className="px-2 py-2">
                        <div className="font-semibold text-[var(--text-primary)]">#{item.conversation_id}</div>
                        <div className="line-clamp-2 text-xs text-[var(--text-secondary)]">{item.conversation_title}</div>
                      </td>
                      <td className="px-2 py-2 text-[var(--text-secondary)]">{item.message_count}</td>
                      <td className="px-2 py-2">
                        {item.is_active ? (
                          <Badge tone="ok">Active</Badge>
                        ) : (
                          <Badge tone="neutral">Revoked</Badge>
                        )}
                      </td>
                      <td className="px-2 py-2 text-xs text-[var(--text-secondary)]">
                        {item.expires_at ? new Date(item.expires_at).toLocaleString("vi-VN") : "—"}
                      </td>
                      <td className="max-w-[28rem] px-2 py-2">
                        <div className="truncate text-xs text-[var(--text-secondary)]">{item.public_url}</div>
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1.5">
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            icon="content_copy"
                            onClick={() => void onCopy(item.public_url)}
                          >
                            Copy
                          </Button>
                          <a
                            href={item.public_url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex min-h-9 items-center gap-2 rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-[0.8125rem] font-semibold text-[var(--text-secondary)] shadow-[var(--shadow-sm)] transition hover:border-[color:var(--shell-border-strong)] hover:bg-[var(--surface-muted)] focus-ring"
                          >
                            <span className="material-symbols-outlined text-[1.15em]" aria-hidden="true">
                              open_in_new
                            </span>
                            Open
                          </a>
                          {item.is_active ? (
                            <Button
                              type="button"
                              variant="danger"
                              size="sm"
                              icon="link_off"
                              onClick={() => void onRevoke(item.conversation_id)}
                            >
                              Revoke
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">Chưa có share link nào.</p>
          )
        ) : null}
      </div>
    </PageShell>
  );
}
