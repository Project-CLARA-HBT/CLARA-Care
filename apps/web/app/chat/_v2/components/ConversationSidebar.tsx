"use client";

import { memo, useMemo, useState, useRef } from "react";
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
import { Icon } from "@/components/ui/icon";

/**
 * Modernized Conversation Sidebar with Search and Category Tags for CLARA Chat.
 * Aligned with Stitch template h_i_clara_active_conversation_refined.
 *
 * Renders a categorized, day-bucketed conversation list with an inline search field
 * (Requirement 2.4, 6.4) and a progressive-disclosure entry point into the
 * folders/workspace surface (Requirement 2.4, 6.4). The list is virtualized so
 * long histories stay fast (Requirement 7.1).
 */

type SidebarRow =
  | { kind: "header"; key: string; label: ConversationDayBucket }
  | { kind: "item"; key: string; item: WorkspaceConversationItem; tag: string; tagTone: string };

type CategoryFilter = "all" | "medicines" | "labs" | "protocols" | "saved";

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

function inferCategoryTag(item: WorkspaceConversationItem, language: UILanguage): {
  filter: CategoryFilter;
  label: string;
  tone: string;
} {
  const text = `${item.title || ""} ${item.preview || ""}`.toLowerCase();
  if (
    /thuốc|warfarin|metformin|amiodarone|aspirin|tương tác|liều|kháng sinh|paracetamol|statin|medication|drug|dose|capsule/i.test(
      text,
    )
  ) {
    return {
      filter: "medicines",
      label: language === "vi" ? "Thuốc" : "Medicines",
      tone: "text-emerald-400 bg-emerald-950/40 border-emerald-800/40",
    };
  }
  if (
    /xét nghiệm|kết quả|chỉ số|huyết học|sinh hóa|men gan|creatinine|inr|crp|ast|alt|blood|lab|test/i.test(
      text,
    )
  ) {
    return {
      filter: "labs",
      label: language === "vi" ? "Xét nghiệm" : "Labs",
      tone: "text-cyan-400 bg-cyan-950/40 border-cyan-800/40",
    };
  }
  if (
    /phác đồ|chẩn đoán|phân biệt|hướng dẫn|protocol|guideline|điều trị|ca bệnh|tiêu chuẩn|tóm tắt/i.test(
      text,
    )
  ) {
    return {
      filter: "protocols",
      label: language === "vi" ? "Phác đồ" : "Protocols",
      tone: "text-amber-400 bg-amber-950/40 border-amber-800/40",
    };
  }
  return {
    filter: "all",
    label: language === "vi" ? "Tổng quát" : "General",
    tone: "text-[var(--text-brand)] bg-[var(--surface-muted)] border-[color:var(--shell-border)]/50",
  };
}

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
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>("all");

  const categoryFilters: Array<{ id: CategoryFilter; label: string; icon: string }> = useMemo(
    () => [
      { id: "all", label: t(uiLanguage, "chat.sidebar.filter.all"), icon: "chat" },
      { id: "medicines", label: t(uiLanguage, "chat.sidebar.filter.medicines"), icon: "medication" },
      { id: "labs", label: t(uiLanguage, "chat.sidebar.filter.labs"), icon: "scan" },
      { id: "protocols", label: t(uiLanguage, "chat.sidebar.filter.protocols"), icon: "clinical-notes" },
      { id: "saved", label: t(uiLanguage, "chat.sidebar.filter.saved"), icon: "folder" },
    ],
    [uiLanguage],
  );

  const filteredConversations = useMemo(() => {
    if (activeCategory === "all") return conversations;
    if (activeCategory === "saved") {
      return conversations.filter((item) => item.is_favorite || Boolean(item.folder_id));
    }
    return conversations.filter((item) => {
      const tagInfo = inferCategoryTag(item, uiLanguage);
      return tagInfo.filter === activeCategory;
    });
  }, [conversations, activeCategory, uiLanguage]);

  const rows = useMemo<SidebarRow[]>(() => {
    const out: SidebarRow[] = [];
    let previousBucket: ConversationDayBucket | null = null;
    for (const item of filteredConversations) {
      const bucket = toDayKey(toConversationTimestamp(item));
      if (bucket !== previousBucket) {
        out.push({
          kind: "header",
          key: `h-${bucket}-${item.conversation_id}`,
          label: bucket,
        });
        previousBucket = bucket;
      }
      const tagInfo = inferCategoryTag(item, uiLanguage);
      out.push({
        kind: "item",
        key: `c-${item.conversation_id}`,
        item,
        tag: tagInfo.label,
        tagTone: tagInfo.tone,
      });
    }
    return out;
  }, [filteredConversations, uiLanguage]);

  // Virtualize rows
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => (rows[index]?.kind === "header" ? 24 : 58),
    overscan: 8,
  });

  return (
    <nav
      aria-label={t(uiLanguage, "chat.sidebar.aria")}
      className="flex h-full min-h-0 flex-col gap-2.5 bg-[var(--surface-sidebar)] p-3.5 border-r border-[color:var(--shell-border)]/60"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2 pb-1 border-b border-[color:var(--shell-border)]/40">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-xs">
            <Icon name="chat" size={17} />
          </span>
          <div>
            <p className="text-sm font-bold tracking-tight text-[var(--text-primary)] leading-none">
              CLARA
            </p>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
              {t(uiLanguage, "chat.shell.mode.fast")} · AI
            </p>
          </div>
        </div>
        <Button size="sm" variant="primary" onClick={onNewChat} className="rounded-full shadow-xs">
          + {t(uiLanguage, "chat.sidebar.new")}
        </Button>
      </div>

      {/* Search Field */}
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
          className="min-h-[38px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] dark:bg-[#181c1f] px-3 pr-9 text-xs sm:text-[13px] text-[var(--text-primary)] outline-none transition focus-visible:border-[color:var(--brand-500)] focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]/20 placeholder:text-[var(--text-muted)]"
        />
        <Icon
          name="search"
          size={16}
          className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
        />
      </div>

      {/* Category Tags Bar */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 no-scrollbar text-xs">
        {categoryFilters.map((cat) => {
          const active = cat.id === activeCategory;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => setActiveCategory(cat.id)}
              className={[
                "inline-flex shrink-0 items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-semibold transition active:scale-95",
                active
                  ? "bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-xs"
                  : "bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)]/60",
              ].join(" ")}
            >
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {/* Folders / workspace entry point */}
      {onOpenFolders ? (
        <button
          type="button"
          onClick={onOpenFolders}
          className="flex w-full items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] dark:bg-[#181c1f] px-3 py-2 text-left text-xs font-semibold text-[var(--text-secondary)] transition hover:border-[color:var(--shell-border-strong)] hover:text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
        >
          <Icon name="folder" size={16} className="text-[var(--text-brand)]" />
          <span>{t(uiLanguage, "chat.sidebar.saved")}</span>
        </button>
      ) : null}

      {/* Virtualized Conversation List */}
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
                    <p className="px-1.5 pt-2 pb-1 text-[9px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
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
                        "mb-1 w-full rounded-xl border p-2.5 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)]",
                        row.item.conversation_id === activeId
                          ? "border-[color:var(--brand-500)] bg-[var(--surface-brand-soft)] shadow-xs"
                          : "border-transparent bg-transparent hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)]",
                      ].join(" ")}
                    >
                      <div className="flex items-center justify-between gap-1.5 mb-1">
                        <p className="truncate text-xs font-semibold text-[var(--text-primary)]">
                          {buildConversationPreview(row.item)}
                        </p>
                        {row.tag ? (
                          <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold border ${row.tagTone}`}>
                            #{row.tag}
                          </span>
                        ) : null}
                      </div>
                      <p className="truncate text-[10px] text-[var(--text-muted)]">
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
 * Memoized virtualized conversation list with category tags.
 */
export default memo(ConversationSidebar);
