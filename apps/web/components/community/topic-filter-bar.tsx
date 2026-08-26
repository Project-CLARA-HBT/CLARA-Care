"use client";

import Button from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SocialCommunity } from "@/lib/social";
import { formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export interface TopicFilterBarProps {
  communities: SocialCommunity[];
  selectedCommunityId: number | "all";
  onSelectCommunity: (id: number | "all") => void;
  authorFilter: "all" | "official" | "peers" | "bookmarks";
  onSelectAuthorFilter: (filter: "all" | "official" | "peers" | "bookmarks") => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onToggleJoinCommunity: (community: SocialCommunity) => void;
  activeCommunity: SocialCommunity | null;
}

export function TopicFilterBar({
  communities,
  selectedCommunityId,
  onSelectCommunity,
  authorFilter,
  onSelectAuthorFilter,
  searchQuery,
  onSearchChange,
  onToggleJoinCommunity,
  activeCommunity,
}: TopicFilterBarProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  return (
    <section
      aria-labelledby="community-filter-heading"
      className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-4 shadow-sm"
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2
            id="community-filter-heading"
            className="text-sm font-bold uppercase tracking-wider text-[var(--text-muted)]"
          >
            {copy("community.communities.heading")}
          </h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            {isEn
              ? "Select a topic or filter by author verification."
              : "Chọn chủ đề thảo luận hoặc lọc theo nguồn chuyên gia."}
          </p>
        </div>

        {/* Author filter segmented toggle */}
        <div className="inline-flex flex-wrap rounded-lg bg-[var(--surface-muted)] p-1 border border-[color:var(--shell-border)] text-xs">
          <button
            type="button"
            onClick={() => onSelectAuthorFilter("all")}
            className={`px-3 py-1 rounded-md font-semibold transition ${
              authorFilter === "all"
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-xs border border-[color:var(--shell-border)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? "All Posts" : "Tất cả"}
          </button>
          <button
            type="button"
            onClick={() => onSelectAuthorFilter("official")}
            className={`px-3 py-1 rounded-md font-semibold transition ${
              authorFilter === "official"
                ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-xs border border-[color:var(--shell-border)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? "CLARA / Verified" : "CLARA & Chuyên gia"}
          </button>
          <button
            type="button"
            onClick={() => onSelectAuthorFilter("peers")}
            className={`px-3 py-1 rounded-md font-semibold transition ${
              authorFilter === "peers"
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-xs border border-[color:var(--shell-border)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {isEn ? "Peer Community" : "Thành viên"}
          </button>
          <button
            type="button"
            onClick={() => onSelectAuthorFilter("bookmarks")}
            className={`px-3 py-1 rounded-md font-semibold transition flex items-center gap-1 ${
              authorFilter === "bookmarks"
                ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-xs border border-[color:var(--shell-border)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Icon name="folder" size="0.8rem" />
            <span>{isEn ? "Bookmarks" : "Đã lưu"}</span>
          </button>
        </div>
      </div>

      {/* Communities horizontal pill selector */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button
          type="button"
          onClick={() => onSelectCommunity("all")}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition border ${
            selectedCommunityId === "all"
              ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] border-[color:var(--brand-500)] shadow-xs"
              : "bg-[var(--surface-muted)] text-[var(--text-secondary)] border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
          }`}
        >
          {isEn ? "All Topics" : "Tất cả chủ đề"}
        </button>
        {communities.map((c) => {
          const isSelected = selectedCommunityId === c.id;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelectCommunity(c.id)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition border flex items-center gap-1.5 ${
                isSelected
                  ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] border-[color:var(--brand-500)] shadow-xs"
                  : "bg-[var(--surface-muted)] text-[var(--text-secondary)] border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
              }`}
            >
              <span>{c.name}</span>
              {c.joined ? (
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full ${
                    isSelected ? "bg-white" : "bg-[var(--brand-500)]"
                  }`}
                  title={copy("community.joined")}
                />
              ) : null}
            </button>
          );
        })}
      </div>

      {/* Active community summary banner */}
      {activeCommunity ? (
        <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/70 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="space-y-1">
            <p className="font-bold text-sm text-[var(--text-primary)]">{activeCommunity.name}</p>
            <p className="text-[var(--text-secondary)] leading-relaxed">{activeCommunity.description}</p>
            <p className="text-[11px] text-[var(--text-muted)] font-medium">
              {copy("community.members", {
                count: formatLocaleNumber(language, activeCommunity.member_count),
              })}
            </p>
          </div>
          <Button
            variant={activeCommunity.joined ? "ghost" : "secondary"}
            size="sm"
            onClick={() => onToggleJoinCommunity(activeCommunity)}
            className="self-start sm:self-center shrink-0 font-semibold"
          >
            {activeCommunity.joined ? copy("community.joined") : copy("community.join")}
          </Button>
        </div>
      ) : null}

      {/* Search bar inside feed */}
      <div className="relative pt-1">
        <div className="absolute inset-y-0 left-0 pl-3 pt-1 flex items-center pointer-events-none text-[var(--text-muted)]">
          <Icon name="search" size="1rem" />
        </div>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={
            isEn
              ? "Search posts in community feed..."
              : "Tìm kiếm bài viết, tác giả hoặc từ khóa trong cộng đồng..."
          }
          className="block w-full pl-9 pr-8 py-2 bg-[var(--surface-muted)] border border-[color:var(--shell-border)] rounded-lg text-xs font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-1 focus:ring-[var(--brand-500)] outline-none transition"
          data-testid="community-search-input"
        />
        {searchQuery ? (
          <button
            type="button"
            onClick={() => onSearchChange("")}
            className="absolute inset-y-0 right-0 pr-3 pt-1 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            aria-label={isEn ? "Clear search" : "Xóa tìm kiếm"}
          >
            <Icon name="close" size="0.85rem" />
          </button>
        ) : null}
      </div>
    </section>
  );
}

export default TopicFilterBar;
