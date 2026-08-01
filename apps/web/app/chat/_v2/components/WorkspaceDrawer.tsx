"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import {
  formatLocaleDate,
  t,
  type UITranslationKey,
} from "@/lib/i18n/catalog";
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
const EXPIRY_OPTIONS: Array<{
  value: number | null;
  label: UITranslationKey;
}> = [
  { value: 24, label: "chat.workspace.expiry.oneDay" },
  { value: 168, label: "chat.workspace.expiry.sevenDays" },
  { value: 720, label: "chat.workspace.expiry.thirtyDays" },
  { value: null, label: "chat.workspace.expiry.none" },
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
  const copy = (
    key: UITranslationKey,
    values: Record<string, string | number> = {},
  ) => t(uiLanguage, key, values);

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
      notify(copy("chat.workspace.notice.noteSaved"));
    } catch {
      notify(copy("chat.workspace.notice.noteSaveFailed"));
    } finally {
      setIsSavingNote(false);
    }
  };

  const handleCreateShare = async (rotate: boolean) => {
    if (!conversationId || apiUnavailable || isCreatingShare) return;
    setIsCreatingShare(true);
    try {
      const alreadyShared = workspace.shares.some(
        (item) => item.conversation_id === conversationId && item.is_active,
      );
      const effectiveRotate = rotate || alreadyShared;
      const created = await workspace.share(conversationId, {
        expiresInHours: expiryHours ?? undefined,
        rotate: effectiveRotate,
      });
      if (created?.public_url) onCopyShareUrl(created.public_url);
      notify(
        copy(
          effectiveRotate
            ? "chat.workspace.notice.shareRotated"
            : "chat.workspace.notice.shareCreated",
        ),
      );
    } catch {
      notify(copy("chat.workspace.notice.shareCreateFailed"));
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
      if (updated?.public_url) onCopyShareUrl(updated.public_url);
      notify(copy("chat.workspace.notice.shareRotated"));
    } catch {
      notify(copy("chat.workspace.notice.shareRotateFailed"));
    } finally {
      setBusyShareId(null);
    }
  };

  const handleRevoke = async (id: number) => {
    if (apiUnavailable || busyShareId !== null) return;
    setBusyShareId(id);
    try {
      await workspace.revokeShare(id);
      notify(copy("chat.workspace.notice.shareRevoked"));
    } catch {
      notify(copy("chat.workspace.notice.shareRevokeFailed"));
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
        activeTitle ||
          copy("chat.workspace.untitledConversation", { id: conversationId }),
      );
      notify(
        copy("chat.workspace.notice.exported", {
          format: copy(
            format === "markdown"
              ? "chat.workspace.format.markdown"
              : "chat.workspace.format.docx",
          ),
        }),
      );
    } catch {
      notify(copy("chat.workspace.notice.exportFailed"));
    }
  };

  return (
    <div className="fixed inset-0 z-[65] flex justify-end">
      <button
        type="button"
        aria-label={copy("chat.workspace.closeAria")}
        onClick={onClose}
        className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]"
      />
      <aside
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={copy("chat.workspace.title")}
        className="relative flex h-full w-[min(92vw,26rem)] flex-col border-l border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-2xl"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-[var(--text-primary)]">
            {copy("chat.workspace.title")}
          </h2>
          <IconButton
            ref={closeRef}
            label={copy("chat.workspace.close")}
            icon="close"
            onClick={onClose}
          />
        </div>

        {/* Export the active conversation (Requirement 6.2). */}
        <section
          aria-label={copy("chat.workspace.exportAria")}
          className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2.5"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
            {copy("chat.workspace.export")}
          </p>
          {conversationId ? (
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void handleExport("markdown")}
              >
                {copy("chat.workspace.markdownFile")}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => void handleExport("docx")}
              >
                {copy("chat.workspace.docxFile")}
              </Button>
            </div>
          ) : (
            <p className="mt-1 text-[12px] text-[var(--text-muted)]">
              {copy("chat.workspace.openConversationToExport")}
            </p>
          )}
        </section>

        <div className="mt-3">
          <Tabs
            label={copy("chat.workspace.sections")}
            activeId={tab}
            onChange={(id) => setTab(id as DrawerTab)}
            items={[
              {
                id: "notes",
                label: copy("chat.workspace.notesTab", {
                  count: workspace.notes.length,
                }),
              },
              {
                id: "shares",
                label: copy("chat.workspace.sharesTab", {
                  count: workspace.shares.length,
                }),
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
              aria-label={copy("chat.workspace.notes")}
            >
              {/* Create note (Requirement 6.2). */}
              <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <input
                  type="text"
                  value={noteTitle}
                  onChange={(event) => setNoteTitle(event.target.value)}
                  placeholder={copy("chat.workspace.noteTitle")}
                  aria-label={copy("chat.workspace.noteTitle")}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <textarea
                  value={noteBody}
                  onChange={(event) => setNoteBody(event.target.value)}
                  placeholder={copy("chat.workspace.noteBody")}
                  aria-label={copy("chat.workspace.noteBodyAria")}
                  rows={3}
                  className="w-full resize-y rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <input
                  type="text"
                  value={noteTags}
                  onChange={(event) => setNoteTags(event.target.value)}
                  placeholder={copy("chat.workspace.noteTags")}
                  aria-label={copy("chat.workspace.noteTagsAria")}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-[12px] text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
                />
                <Button
                  size="sm"
                  variant="primary"
                  disabled={!noteTitle.trim() || isSavingNote}
                  onClick={() => void handleSaveNote()}
                >
                  {isSavingNote
                    ? copy("chat.workspace.savingNote")
                    : copy("chat.workspace.saveNote")}
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
                          {copy("chat.workspace.deleteNote")}
                        </button>
                      </div>
                      <p className="mt-1 line-clamp-2 text-[11px] text-[var(--text-secondary)]">
                        {note.summary ||
                          note.content_markdown ||
                          copy("chat.workspace.emptyNote")}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-[12px] text-[var(--text-muted)]">
                  {copy("chat.workspace.noNotes")}
                </p>
              )}
            </section>
          ) : (
            <section
              role="tabpanel"
              id="tabpanel-shares"
              aria-labelledby="tab-shares"
              aria-label={copy("chat.workspace.shares")}
            >
              {/* Create / rotate a share for the active conversation. */}
              <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                <label
                  htmlFor="workspace-share-expiry"
                  className="block text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]"
                >
                  {copy("chat.workspace.linkExpiry")}
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
                      {copy(option.label)}
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
                      {copy("chat.workspace.createLink")}
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={isCreatingShare}
                      onClick={() => void handleCreateShare(true)}
                    >
                      {copy("chat.workspace.rotateToken")}
                    </Button>
                  </div>
                ) : (
                  <p className="text-[12px] text-[var(--text-muted)]">
                    {copy(
                      apiUnavailable
                        ? "chat.workspace.sharingUnavailable"
                        : "chat.workspace.openConversationToShare",
                    )}
                  </p>
                )}
              </div>

              {workspace.shares.length ? (
                <ul className="mt-3 space-y-1.5">
                  {workspace.shares.slice(0, 30).map((item) => {
                    const isBusy = busyShareId === item.conversation_id;
                    return (
                      <li
                        key={item.share_id}
                        className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2"
                      >
                        <p className="line-clamp-1 text-[12px] font-semibold text-[var(--text-primary)]">
                          #{item.conversation_id} · {item.conversation_title}
                        </p>
                        <p className="mt-0.5 text-[10px] text-[var(--text-muted)]">
                          {copy(
                            item.is_active
                              ? "chat.workspace.status.active"
                              : "chat.workspace.status.revoked",
                          )}
                          {item.expires_at
                            ? ` · ${copy("chat.workspace.expiresAt", {
                                date: formatLocaleDate(
                                  uiLanguage,
                                  item.expires_at,
                                ),
                              })}`
                            : ""}
                        </p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {item.is_active && !apiUnavailable ? (
                            <>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void handleRotate(item.conversation_id)}
                                className="rounded-lg border border-[color:var(--shell-border)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)] hover:border-[color:var(--shell-border-strong)] disabled:opacity-60"
                              >
                                {copy("chat.workspace.rotate")}
                              </button>
                              <button
                                type="button"
                                disabled={isBusy}
                                onClick={() => void handleRevoke(item.conversation_id)}
                                className="rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--status-danger-text)] disabled:opacity-60"
                              >
                                {copy("chat.workspace.revoke")}
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
                  {copy("chat.workspace.noShares")}
                </p>
              )}
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
