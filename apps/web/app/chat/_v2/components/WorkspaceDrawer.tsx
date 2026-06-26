"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { UILanguage } from "@/lib/ui-language";
import type { ConversationItem } from "@/components/research/lib/research-page-types";
import type { UseWorkspace } from "@/app/chat/_v2/hooks/useWorkspace";
import { asConversationId, parseTagsInput } from "@/app/chat/_v2/lib/chat-format";
import { useFocusTrap } from "@/app/chat/_v2/lib/useFocusTrap";
import { Button, IconButton, Tabs } from "@/app/chat/_v2/components/primitives";

/**
 * Progressive-disclosure workspace drawer for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Surfaces notes + shares + export behind an on-demand drawer (Requirement 2.4,
 * 6.1, 6.2). Opened from the shell (sidebar "Folders & workspace" entry or the
 * header); manages focus on open/close (Requirement 5.4) and closes on Escape.
 *
 * Capabilities (Requirement 6.2):
 *  - Notes management: create / list / delete.
 *  - Shares: create with an expiry, rotate the token, revoke, and copy URL.
 *  - Export the active conversation to Markdown and DOCX.
 *
 * It reuses the existing workspace client unchanged via `useWorkspace`
 * (Requirement 8.3); when the workspace API is unavailable, share controls are
 * disabled but export still works through the local-markdown fallback baked
 * into the hook (Requirement 6.5).
 */

export type WorkspaceDrawerProps = {
  open: boolean;
  onClose: () => void;
  workspace: UseWorkspace;
  uiLanguage: UILanguage;
  onCopyShareUrl: (url: string) => void;
  /** Active conversation, enabling share/export for the open chat. */
  activeConversationId?: number | null;
  /** Title used for export filenames / headings. */
  activeTitle?: string;
  /** In-memory turns used as the local-export fallback. */
  activeTurns?: ConversationItem[];
  /** Whether the workspace API is unavailable (disables share creation). */
  apiUnavailable?: boolean;
  /** Best-effort, transient status callback surfaced by the shell. */
  onNotice?: (message: string) => void;
};

type DrawerTab = "notes" | "shares";

/** Expiry presets for share creation (hours; `null` ⇒ no expiry). */
const EXPIRY_OPTIONS: Array<{ value: number | null; vi: string; en: string }> = [
  { value: 24, vi: "24 giờ", en: "24 hours" },
  { value: 168, vi: "7 ngày", en: "7 days" },
  { value: 720, vi: "30 ngày", en: "30 days" },
  { value: null, vi: "Không hết hạn", en: "No expiry" },
];

export default function WorkspaceDrawer({
  open,
  onClose,
  workspace,
  uiLanguage,
  onCopyShareUrl,
  activeConversationId = null,
  activeTitle = "",
  activeTurns = [],
  apiUnavailable = false,
  onNotice,
}: WorkspaceDrawerProps) {
  const closeRef = useRef<HTMLButtonElement | null>(null);
  const dialogRef = useRef<HTMLElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const isEn = uiLanguage === "en";

  // Keep Tab focus inside the drawer dialog while open (Req 5.4).
  useFocusTrap(open, dialogRef);

  const [tab, setTab] = useState<DrawerTab>("notes");
  const [noteTitle, setNoteTitle] = useState("");
  const [noteBody, setNoteBody] = useState("");
  const [noteTags, setNoteTags] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);
  const [expiryHours, setExpiryHours] = useState<number | null>(168);
  const [busyShareId, setBusyShareId] = useState<number | null>(null);
  const [isCreatingShare, setIsCreatingShare] = useState(false);

  const conversationId = useMemo(
    () => asConversationId(activeConversationId),
    [activeConversationId],
  );

  useEffect(() => {
    if (!open) return;
    restoreFocusRef.current = (document.activeElement as HTMLElement) ?? null;
    const timer = window.setTimeout(() => closeRef.current?.focus(), 10);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("keydown", onKeyDown);
      restoreFocusRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  const notify = (message: string) => onNotice?.(message);

  const handleSaveNote = async () => {
    const title = noteTitle.trim();
    if (!title || isSavingNote) return;
    setIsSavingNote(true);
    try {
      await workspace.saveNote({
        title: title.slice(0, 200),
        contentMarkdown: noteBody.trim(),
        tags: parseTagsInput(noteTags),
        conversationId,
      });
      setNoteTitle("");
      setNoteBody("");
      setNoteTags("");
      notify(isEn ? "Note saved." : "Đã lưu ghi chú.");
    } catch {
      notify(isEn ? "Could not save the note." : "Không thể lưu ghi chú.");
    } finally {
      setIsSavingNote(false);
    }
  };

  const handleCreateShare = async (rotate: boolean) => {
    if (!conversationId || apiUnavailable || isCreatingShare) return;
    setIsCreatingShare(true);
    try {
      const rows = await workspace.share(conversationId, {
        expiresInHours: expiryHours ?? undefined,
        rotate,
      });
      const created = rows?.find((row) => row.conversation_id === conversationId);
      if (created) onCopyShareUrl(created.public_url);
      notify(
        rotate
          ? isEn
            ? "Share link rotated."
            : "Đã làm mới liên kết."
          : isEn
            ? "Share link created."
            : "Đã tạo liên kết chia sẻ.",
      );
    } catch {
      notify(isEn ? "Could not create the share." : "Không thể tạo liên kết.");
    } finally {
      setIsCreatingShare(false);
    }
  };

  const handleRotate = async (id: number) => {
    if (apiUnavailable || busyShareId !== null) return;
    setBusyShareId(id);
    try {
      const rows = await workspace.share(id, {
        expiresInHours: expiryHours ?? undefined,
        rotate: true,
      });
      const updated = rows?.find((row) => row.conversation_id === id);
      if (updated) onCopyShareUrl(updated.public_url);
      notify(isEn ? "Share link rotated." : "Đã làm mới liên kết.");
    } catch {
      notify(isEn ? "Could not rotate the link." : "Không thể làm mới liên kết.");
    } finally {
      setBusyShareId(null);
    }
  };

  const handleRevoke = async (id: number) => {
    if (apiUnavailable || busyShareId !== null) return;
    setBusyShareId(id);
    try {
      await workspace.revokeShare(id);
      notify(isEn ? "Share revoked." : "Đã thu hồi liên kết.");
    } catch {
      notify(isEn ? "Could not revoke the share." : "Không thể thu hồi liên kết.");
    } finally {
      setBusyShareId(null);
    }
  };

  const handleExport = async (format: "markdown" | "docx") => {
    if (!conversationId) return;
    try {
      await workspace.exportConversation(
        conversationId,
        format,
        activeTurns,
        activeTitle || `Conversation ${conversationId}`,
      );
      notify(
        isEn
          ? `Exported ${format === "markdown" ? "Markdown" : "DOCX"}.`
          : `Đã xuất ${format === "markdown" ? "Markdown" : "DOCX"}.`,
      );
    } catch {
      notify(isEn ? "Could not export." : "Không thể xuất tài liệu.");
    }
  };

  return (
    <div className="fixed inset-0 z-[65] flex justify-end">
      <button
        type="button"
        aria-label={isEn ? "Close workspace" : "Đóng workspace"}
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]"
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={isEn ? "Workspace" : "Không gian làm việc"}
        className="relative flex h-full w-[min(92vw,26rem)] flex-col border-l border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            {isEn ? "Workspace" : "Không gian làm việc"}
          </h2>
          <IconButton
            ref={closeRef}
            label={isEn ? "Close" : "Đóng"}
            icon="close"
            onClick={onClose}
          />
        </div>

        {/* Export the active conversation (Requirement 6.2). */}
        <section
          aria-label={isEn ? "Export conversation" : "Xuất cuộc trò chuyện"}
          className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
            {isEn ? "Export" : "Xuất tài liệu"}
          </p>
          {conversationId ? (
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void handleExport("markdown")}
              >
                {isEn ? "Markdown (.md)" : "Markdown (.md)"}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void handleExport("docx")}
              >
                {isEn ? "Word (.docx)" : "Word (.docx)"}
              </Button>
            </div>
          ) : (
            <p className="mt-1 text-[12px] text-[var(--text-muted)]">
              {isEn
                ? "Open a conversation to export it."
                : "Mở một cuộc trò chuyện để xuất."}
            </p>
          )}
        </section>

        <div className="mt-3">
          <Tabs
            label={isEn ? "Workspace sections" : "Mục workspace"}
            activeId={tab}
            onChange={(id) => setTab(id as DrawerTab)}
            items={[
              {
                id: "notes",
                label: `${isEn ? "Notes" : "Ghi chú"} (${workspace.notes.length})`,
              },
              {
                id: "shares",
                label: `${isEn ? "Shares" : "Chia sẻ"} (${workspace.shares.length})`,
              },
            ]}
          />
        </div>

        <div className="clara-scrollbar mt-3 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {tab === "notes" ? (
            <section
              role="tabpanel"
              id="tabpanel-notes"
              aria-labelledby="tab-notes"
              aria-label={isEn ? "Notes" : "Ghi chú"}
            >
              {/* Create note (Requirement 6.2). */}
              <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <input
                  type="text"
                  value={noteTitle}
                  onChange={(event) => setNoteTitle(event.target.value)}
                  placeholder={isEn ? "Note title" : "Tiêu đề ghi chú"}
                  aria-label={isEn ? "Note title" : "Tiêu đề ghi chú"}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <textarea
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  placeholder={isEn ? "Content (Markdown)" : "Nội dung (Markdown)"}
                  aria-label={isEn ? "Note content" : "Nội dung ghi chú"}
                  rows={3}
                  className="w-full resize-y rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <input
                  type="text"
                  value={noteTags}
                  onChange={(event) => setNoteTags(event.target.value)}
                  placeholder={isEn ? "Tags (comma-separated)" : "Thẻ (phân tách bằng dấu phẩy)"}
                  aria-label={isEn ? "Note tags" : "Thẻ ghi chú"}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <Button
                  size="sm"
                  variant="primary"
                  disabled={!noteTitle.trim() || isSavingNote}
                  onClick={() => void handleSaveNote()}
                >
                  {isSavingNote
                    ? isEn
                      ? "Saving..."
                      : "Đang lưu..."
                    : isEn
                      ? "Save note"
                      : "Lưu ghi chú"}
                </Button>
              </div>

              {workspace.notes.length ? (
                <ul className="mt-3 space-y-1.5">
                  {workspace.notes.slice(0, 30).map((note) => (
                    <li
                      key={note.id}
                      className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="line-clamp-1 text-[12px] font-semibold text-[var(--text-primary)]">
                          {note.title}
                        </p>
                        <button
                          type="button"
                          onClick={() => void workspace.removeNote(note.id)}
                          className="shrink-0 text-[10px] font-semibold text-[var(--status-danger-text)] hover:underline"
                        >
                          {isEn ? "Delete" : "Xóa"}
                        </button>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">
                        {note.summary || note.content_markdown || (isEn ? "(empty)" : "(trống)")}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-[12px] text-[var(--text-muted)]">
                  {isEn ? "No notes yet." : "Chưa có ghi chú."}
                </p>
              )}
            </section>
          ) : (
            <section
              role="tabpanel"
              id="tabpanel-shares"
              aria-labelledby="tab-shares"
              aria-label={isEn ? "Shares" : "Chia sẻ"}
            >
              {/* Create / rotate a share for the active conversation. */}
              <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <label
                  htmlFor="workspace-share-expiry"
                  className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]"
                >
                  {isEn ? "Link expiry" : "Thời hạn liên kết"}
                </label>
                <select
                  id="workspace-share-expiry"
                  value={expiryHours === null ? "none" : String(expiryHours)}
                  onChange={(event) =>
                    setExpiryHours(
                      event.target.value === "none"
                        ? null
                        : Number(event.target.value),
                    )
                  }
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                >
                  {EXPIRY_OPTIONS.map((option) => (
                    <option
                      key={option.value === null ? "none" : option.value}
                      value={option.value === null ? "none" : String(option.value)}
                    >
                      {isEn ? option.en : option.vi}
                    </option>
                  ))}
                </select>
                {conversationId && !apiUnavailable ? (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={isCreatingShare}
                      onClick={() => void handleCreateShare(false)}
                    >
                      {isEn ? "Create link" : "Tạo liên kết"}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isCreatingShare}
                      onClick={() => void handleCreateShare(true)}
                    >
                      {isEn ? "Rotate token" : "Làm mới token"}
                    </Button>
                  </div>
                ) : (
                  <p className="text-[12px] text-[var(--text-muted)]">
                    {apiUnavailable
                      ? isEn
                        ? "Sharing is unavailable offline."
                        : "Chia sẻ không khả dụng khi offline."
                      : isEn
                        ? "Open a conversation to share it."
                        : "Mở một cuộc trò chuyện để chia sẻ."}
                  </p>
                )}
              </div>

              {workspace.shares.length ? (
                <ul className="mt-3 space-y-1.5">
                  {workspace.shares.slice(0, 30).map((item) => {
                    const isBusy = busyShareId === item.conversation_id;
                    return (
                      <li
                        key={`${item.conversation_id}-${item.share_token}`}
                        className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                      >
                        <p className="line-clamp-1 text-[12px] font-semibold text-[var(--text-primary)]">
                          #{item.conversation_id} · {item.conversation_title}
                        </p>
                        <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                          {item.is_active
                            ? isEn
                              ? "Active"
                              : "Đang hoạt động"
                            : isEn
                              ? "Revoked"
                              : "Đã thu hồi"}
                          {item.expires_at
                            ? ` · ${isEn ? "expires" : "hết hạn"} ${new Date(item.expires_at).toLocaleDateString()}`
                            : ""}
                        </p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          <button
                            type="button"
                            onClick={() => onCopyShareUrl(item.public_url)}
                            className="rounded-lg border border-[color:var(--shell-border)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)]"
                          >
                            {isEn ? "Copy" : "Sao chép"}
                          </button>
                          {item.is_active && !apiUnavailable ? (
                            <>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void handleRotate(item.conversation_id)}
                                className="rounded-lg border border-[color:var(--shell-border)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] disabled:opacity-60"
                              >
                                {isEn ? "Rotate" : "Làm mới"}
                              </button>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void handleRevoke(item.conversation_id)}
                                className="rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--status-danger-text)] disabled:opacity-60"
                              >
                                {isEn ? "Revoke" : "Thu hồi"}
                              </button>
                            </>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="mt-3 text-[12px] text-[var(--text-muted)]">
                  {isEn ? "No shares yet." : "Chưa có chia sẻ."}
                </p>
              )}
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
