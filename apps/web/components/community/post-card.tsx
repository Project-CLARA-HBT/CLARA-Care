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
  onReaction: (post: SocialPost) => void;
  onReport: (post: SocialPost) => void;
  onToggleHide: (postId: number) => void;
}

export function PostCard({
  post,
  community,
  canParticipate,
  onOpenDetail,
  onReaction,
  onReport,
  onToggleHide,
}: PostCardProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = (key: UITranslationKey, values?: Record<string, string | number>) =>
    t(language, key, values ?? {});

  const official =
    typeof isClaraOfficial === "function"
      ? isClaraOfficial(post.author_handle)
      : false;

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
            className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
              official
                ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] shadow-xs"
                : "bg-[var(--surface-muted)] text-[var(--text-primary)] border border-[color:var(--shell-border)]"
            }`}
          >
            {post.author_handle.slice(0, 2).toUpperCase()}
          </div>

          <span className="font-bold text-[var(--text-primary)]">
            @{post.author_handle}
          </span>

          {/* Author verification badge */}
          {official ? (
            <Badge tone="brand" icon="check" className="text-[10px] py-0.5 font-bold">
              {isEn ? "CLARA Official" : "CLARA Chuyên gia"}
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

          {community ? (
            <span className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)] border border-[color:var(--shell-border)]">
              {community.name}
            </span>
          ) : null}
        </div>

        <div className="flex items-center gap-2 text-[var(--text-muted)] text-[11px]">
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
        <div className="flex items-center gap-2 sm:gap-4">
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

          {/* Quick supportive reaction button */}
          <button
            type="button"
            onClick={() => onReaction(post)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition cursor-pointer font-medium"
            title={
              canParticipate
                ? isEn
                  ? "Send supportive reaction"
                  : "Gửi phản hồi tích cực"
                : copy("community.reaction.joinToReact")
            }
          >
            <span aria-hidden="true">👍</span>
            <span>
              {copy("community.reactions.count", {
                count: formatLocaleNumber(language, post.reaction_count),
              })}
            </span>
          </button>
        </div>

        {/* Report / Mute Actions */}
        <div className="flex items-center gap-2">
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
        </div>
      </div>
    </SurfaceCard>
  );
}

export default PostCard;
