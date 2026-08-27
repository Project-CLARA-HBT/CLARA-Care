"use client";

import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { isClaraOfficial, SocialCommunity, SocialPost } from "@/lib/social";

export interface PostCardProps {
  post: SocialPost;
  community?: SocialCommunity;
  canParticipate: boolean;
  onOpenDetail: (post: SocialPost) => void;
  onReaction: (post: SocialPost, kind?: "helpful" | "relate" | "thanks") => void;
  onToggleBookmark?: (post: SocialPost) => void;
  onReport: (post: SocialPost) => void;
  onToggleHide: (postId: number) => void;
  onDelete?: (postId: number) => void;
  canDelete?: boolean;
}

export function PostCard({
  post,
  community,
  canParticipate,
  onOpenDetail,
  onReaction,
  onToggleBookmark,
  onReport,
  onToggleHide,
  onDelete,
  canDelete,
}: PostCardProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  const official =
    typeof isClaraOfficial === "function"
      ? isClaraOfficial(post.author_handle) || Boolean(post.is_verified_clinician)
      : Boolean(post.is_verified_clinician);

  return (
    <SurfaceCard
      interactive
      className="p-4 sm:p-5 space-y-3 transition border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-xs hover:border-[color:var(--brand-500)]/50"
    >
      {/* Post Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          {/* Avatar */}
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
              official
                ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-xs"
                : "bg-[var(--surface-muted)] text-[var(--text-primary)] border border-[color:var(--shell-border)]"
            }`}
          >
            {(post.author_display_name || post.author_handle).slice(0, 2).toUpperCase()}
          </div>

          <div className="flex flex-col">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-bold text-[var(--text-primary)]">
                {post.author_display_name ? post.author_display_name : `@${post.author_handle}`}
              </span>
              {post.author_display_name ? (
                <span className="text-[11px] text-[var(--text-muted)]">
                  @{post.author_handle}
                </span>
              ) : null}

              {/* Author verification badge */}
              {official ? (
                <Badge tone="brand" icon="check" className="text-[10px] py-0.5 font-bold">
                  {isEn ? "Verified Clinician" : "Bác sĩ Chuyên gia"}
                </Badge>
              ) : (
                <Badge tone="neutral" className="text-[10px] py-0.5">
                  {isEn ? "Peer Member" : "Thành viên"}
                </Badge>
              )}

              {/* Safety moderation badge */}
              <Badge tone="ok" className="text-[10px] py-0.5">
                {isEn ? "Moderated" : "Đã duyệt an toàn"}
              </Badge>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-[var(--text-muted)] text-[11px]">
          {community || post.community_name ? (
            <span className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)] border border-[color:var(--shell-border)]">
              {community?.name || post.community_name}
            </span>
          ) : null}
          <span>{formatLocaleDate(language, post.created_at)}</span>
        </div>
      </div>

      {/* Post Content Clickable Area */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onOpenDetail(post)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onOpenDetail(post);
          }
        }}
        className="cursor-pointer space-y-1.5 group focus:outline-none"
      >
        <h3 className="font-bold text-base sm:text-lg text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition">
          {post.title}
        </h3>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-secondary)] line-clamp-3">
          {post.body}
        </p>
      </div>

      {/* Action Bar */}
      <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/50 text-xs text-[var(--text-secondary)]">
        <div className="flex items-center gap-1.5 sm:gap-3 flex-wrap">
          {/* Comments count button */}
          <button
            type="button"
            onClick={() => onOpenDetail(post)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition cursor-pointer font-medium"
          >
            <Icon name="chat" size="0.95rem" />
            <span>
              {copy("community.comments.count", {
                count: formatLocaleNumber(language, post.comment_count),
              })}
            </span>
          </button>

          {/* 3 Supportive reactions */}
          <div className="inline-flex items-center gap-1">
            <button
              type="button"
              onClick={() => onReaction(post)}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg transition cursor-pointer font-medium text-xs ${
                post.user_reaction === "helpful"
                  ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold border border-[color:var(--brand-500)]/30"
                  : "hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              }`}
              title={
                canParticipate
                  ? isEn
                    ? "Helpful 👍"
                    : "Gửi phản hồi tích cực"
                  : copy("community.reaction.joinToReact")
              }
            >
              <span aria-hidden="true">👍</span>
              <span>
                {post.reactions_breakdown?.helpful ?? (
                  post.reaction_count > 0 ? formatLocaleNumber(language, post.reaction_count) : ""
                )}
              </span>
            </button>

            <button
              type="button"
              onClick={() => onReaction(post, "relate")}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg transition cursor-pointer font-medium text-xs ${
                post.user_reaction === "relate"
                  ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold border border-[color:var(--brand-500)]/30"
                  : "hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              }`}
              title={
                canParticipate
                  ? isEn
                    ? "Relate 🤝"
                    : "Đồng cảm 🤝"
                  : copy("community.reaction.joinToReact")
              }
            >
              <span aria-hidden="true">🤝</span>
              {post.reactions_breakdown?.relate ? (
                <span>{formatLocaleNumber(language, post.reactions_breakdown.relate)}</span>
              ) : null}
            </button>

            <button
              type="button"
              onClick={() => onReaction(post, "thanks")}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg transition cursor-pointer font-medium text-xs ${
                post.user_reaction === "thanks"
                  ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold border border-[color:var(--brand-500)]/30"
                  : "hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)]"
              }`}
              title={
                canParticipate
                  ? isEn
                    ? "Thanks 🙏"
                    : "Cảm ơn 🙏"
                  : copy("community.reaction.joinToReact")
              }
            >
              <span aria-hidden="true">🙏</span>
              {post.reactions_breakdown?.thanks ? (
                <span>{formatLocaleNumber(language, post.reactions_breakdown.thanks)}</span>
              ) : null}
            </button>
          </div>

          {/* Bookmark Toggle */}
          {onToggleBookmark ? (
            <button
              type="button"
              onClick={() => onToggleBookmark(post)}
              className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg transition cursor-pointer font-medium text-xs ${
                post.is_bookmarked
                  ? "text-[var(--text-brand)] font-bold bg-[var(--surface-brand-soft)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
              }`}
              title={
                post.is_bookmarked
                  ? isEn
                    ? "Remove Bookmark"
                    : "Bỏ lưu bài viết"
                  : isEn
                  ? "Bookmark Post"
                  : "Lưu bài viết"
              }
            >
              <Icon
                name={post.is_bookmarked ? "folder" : "folder"}
                size="0.85rem"
              />
              <span className="hidden sm:inline">
                {post.is_bookmarked
                  ? isEn
                    ? "Saved"
                    : "Đã lưu"
                  : isEn
                  ? "Save"
                  : "Lưu"}
              </span>
            </button>
          ) : null}
        </div>

        {/* Report / Hide / Delete Actions */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onReport(post)}
            className="px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition rounded cursor-pointer"
            title={copy("community.report.post")}
          >
            {copy("community.report.post")}
          </button>
          <button
            type="button"
            onClick={() => onToggleHide(post.id)}
            className="px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition rounded cursor-pointer"
            title={isEn ? "Hide post from feed" : "Ẩn bài viết khỏi bảng tin"}
          >
            {isEn ? "Hide" : "Ẩn bài"}
          </button>
          {canDelete && onDelete ? (
            <button
              type="button"
              onClick={() => onDelete(post.id)}
              className="px-2 py-1 text-[11px] text-[var(--status-danger-text)] hover:underline transition rounded cursor-pointer"
              title={isEn ? "Delete Post" : "Xóa bài viết"}
            >
              {isEn ? "Delete" : "Xóa"}
            </button>
          ) : null}
        </div>
      </div>
    </SurfaceCard>
  );
}

export default PostCard;
