"use client";

import { memo, useMemo, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import type { WorkspaceConversationItem } from "@/lib/workspace";
import {
  buildConversationPreview,
  formatConversationDayLabel,
  toConversationTimestamp,
  toDayKey,
  type ConversationDayBucket,
} from "@/app/chat/_v2/lib/chat-format";
import { Button, IconButton } from "@/app/chat/_v2/components/primitives";

/**
 * Conversation list / search / folders entry for the rebuilt CLARA Chat.
 *
 * Renders a day-bucketed conversation list with an inline search field
 * (Requirement 2.4, 6.4) and a progressive-disclosure entry point into the
 * folders/workspace surface (Requirement 2.4, 6.4). The list is virtualized so
 * long histories stay fast (Requirement 7.1); the parent owns search +
 * selection + workspace-open state.
 */

type SidebarRow =
  | { kind: "header"; key: string; label: ConversationDayBucket }
  | { kind: "item"; key: string; item: WorkspaceConversationItem };

export type ConversationSidebarProps = {
  conversations: WorkspaceConversationItem[];
  activeId: number | null;
  isLoading: boolean;
  searchText: string;
  onSearchChange: (value: string) => void;
  onSelect: (item: WorkspaceConversationItem) => void;
  onNewChat: () => void;
  /**
   * Opens the folders / workspace surface (progressive disclosure). Optional so
   * the sidebar degrades gracefully when no workspace surface is wired up.
   */
  onOpenFolders?: () => void;
  uiLanguage: UILanguage;
};

function ConversationSidebar(props: ConversationSidebarProps) {
  const {
    conversations,
    activeId,
    isLoading,
    searchText,
    onSearchChange,
    onSelect,
    onNewChat,
    onOpenFolders,
    uiLanguage,
  } = props;
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const rows = useMemo<SidebarRow[]>(() => {
    const out: SidebarRow[] = [];
    let previousBucket: ConversationDayBucket | null = null;
    for (const item of conversations) {
      const bucket = toDayKey(toConversationTimestamp(item));
      if (bucket !== previousBucket) {
        out.push({
          kind: "header",
          key: `h-${bucket}-${item.conversation_id}`,
          label: bucket,
        });
        previousBucket = bucket;
      }
      out.push({ kind: "item", key: `c-${item.conversation_id}`, item });
    }
    return out;
  }, [conversations]);

  // Virtualize the (header + item) rows so long histories render only what's on
  // screen (Requirement 7.1). Headers are shorter than items, so we estimate by
  // row kind and let the virtualizer measure actual heights.
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (rows[index]?.kind === "header" ? 24 : 52),
    overscan: 8,
  });

  return (
    <nav
      aria-label={t(uiLanguage, "chat.sidebar.aria")}
      className="flex h-full min-h-0 flex-col gap-2.5 bg-[var(--surface-sidebar)] p-3"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--brand-600)] text-white">
            <span
              className="material-symbols-outlined text-[17px]"
              aria-hidden="true"
            >
              forum
            </span>
          </span>
          <p className="text-sm font-semibold tracking-[-0.02em] text-[var(--text-primary)]">
            CLARA
          </p>
        </div>
        <Button size="sm" variant="primary" onClick={onNewChat}>
          + {t(uiLanguage, "chat.sidebar.new")}
        </Button>
      </div>

      <div className="relative">
        <label className="sr-only" htmlFor="chat-v2-search">
          {t(uiLanguage, "chat.sidebar.searchLabel")}
        </label>
        <input
          id="chat-v2-search"
          type="search"
          value={searchText}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={t(uiLanguage, "chat.sidebar.searchPlaceholder")}
          className="min-h-[38px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 pr-9 text-[13px] text-[var(--text-primary)] outline-none focus-visible:border-[color:var(--brand-500)] focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]/20"
        />
        <span
          aria-hidden="true"
          className="material-symbols-outlined pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[18px] text-[var(--text-muted)]"
        >
          search
        </span>
      </div>

      {/* Folders / workspace entry point (progressive disclosure — Req 2.4, 6.4). */}
      {onOpenFolders ? (
        <button
          type="button"
          onClick={onOpenFolders}
          className="flex w-full items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-2 text-left text-[12px] font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
        >
          <span
            aria-hidden="true"
            className="material-symbols-outlined text-[18px]"
          >
            folder
          </span>
          {t(uiLanguage, "chat.sidebar.saved")}
        </button>
      ) : null}

      <div
        ref={scrollRef}
        className="clara-scrollbar min-h-0 flex-1 overflow-y-auto pr-1"
      >
        {isLoading ? (
          <p className="px-1 py-2 text-xs text-[var(--text-muted)]">
            {t(uiLanguage, "chat.sidebar.loading")}
          </p>
        ) : rows.length ? (
          <ul
            className="relative w-full"
            style={{ height: `${virtualizer.getTotalSize()}px` }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = rows[virtualRow.index];
              if (!row) return null;
              return (
                <li
                  key={row.key}
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {row.kind === "header" ? (
                    <p className="px-1.5 pt-2 pb-1 text-[9px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                      {formatConversationDayLabel(row.label, uiLanguage)}
                    </p>
                  ) : (
                    <button
                      type="button"
                      aria-current={
                        row.item.conversation_id === activeId
                          ? "true"
                          : undefined
                      }
                      onClick={() => onSelect(row.item)}
                      className={[
                        "mb-1 w-full rounded-xl border px-3 py-2.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]",
                        row.item.conversation_id === activeId
                          ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)]"
                          : "border-transparent bg-transparent hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)]",
                      ].join(" ")}
                    >
                      <p className="truncate text-[12px] font-semibold text-[var(--text-primary)]">
                        {buildConversationPreview(row.item)}
                      </p>
                      <p className="mt-0.5 truncate text-[10px] text-[var(--text-muted)]">
                        #{row.item.conversation_id} · {row.item.message_count}{" "}
                        {t(uiLanguage, "chat.sidebar.messageCount")}
                        {row.item.is_favorite ? " · ★" : ""}
                      </p>
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <div className="flex flex-col items-center gap-2 px-2 py-8 text-center">
            <p className="text-xs text-[var(--text-secondary)]">
              {t(uiLanguage, "chat.sidebar.empty")}
            </p>
            <IconButton
              label={t(uiLanguage, "chat.sidebar.newChat")}
              icon="add"
              onClick={onNewChat}
            />
          </div>
        )}
      </div>
    </nav>
  );
}

/**
 * Memoized: the virtualized conversation list rebuilds day-bucket rows on each
 * render, so it should only re-render when its inputs (conversations, active
 * id, search text, loading, stable callbacks) change — not on every parent
 * re-render (Requirement 7.2, Property P9).
 */
export default memo(ConversationSidebar);
