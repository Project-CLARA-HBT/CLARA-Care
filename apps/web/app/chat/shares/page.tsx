"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PageShell from "@/components/ui/page-shell";
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
          <Link
            href="/chat"
            className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
          >
            ← Back to Chat
          </Link>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex min-h-[36px] items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-xs font-semibold text-[var(--text-secondary)]"
          >
            Reload
          </button>
        </div>

        {loading ? <p className="text-sm text-[var(--text-muted)]">Đang tải...</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        {!error && notice ? <p className="text-sm text-emerald-700">{notice}</p> : null}

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
                          <span className="rounded-full border border-emerald-300/70 bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-700">Active</span>
                        ) : (
                          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-xs text-[var(--text-secondary)]">Revoked</span>
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
                          <button
                            type="button"
                            onClick={() => void onCopy(item.public_url)}
                            className="rounded border border-[color:var(--shell-border)] px-2 py-1 text-xs text-[var(--text-secondary)]"
                          >
                            Copy
                          </button>
                          <a
                            href={item.public_url}
                            target="_blank"
                            rel="noreferrer"
                            className="rounded border border-cyan-300/70 bg-cyan-500/10 px-2 py-1 text-xs font-semibold text-cyan-700"
                          >
                            Open
                          </a>
                          {item.is_active ? (
                            <button
                              type="button"
                              onClick={() => void onRevoke(item.conversation_id)}
                              className="rounded border border-rose-300/70 bg-rose-500/10 px-2 py-1 text-xs font-semibold text-rose-700"
                            >
                              Revoke
                            </button>
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
