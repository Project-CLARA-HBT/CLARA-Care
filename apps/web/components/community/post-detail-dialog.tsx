"use client";

import { useCallback, useEffect, useState } from "react";
import {
  SocialComment,
  SocialPost,
  ReactionKind,
  addComment,
  addReaction,
  getComments,
  deleteComment,
  toggleBookmark,
  isSocialModerationBlock,
  isClaraOfficial,
  reportContent,
} from "@/lib/social";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import Modal from "@/components/ui/modal";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@/components/ui/icon";
import ReportModal from "./report-modal";

const REACTIONS: { kind: ReactionKind; icon: string; labelVi: string; labelEn: string }[] = [
  { kind: "helpful", icon: "👍", labelVi: "Hữu ích", labelEn: "Helpful" },
  { kind: "relate", icon: "🤝", labelVi: "Đồng cảm", labelEn: "Relate" },
  { kind: "thanks", icon: "🙏", labelVi: "Cảm ơn", labelEn: "Thanks" },
];

export interface PostDetailDialogProps {
  post: SocialPost;
  canParticipate: boolean;
  onClose: () => void;
  onReactionAdded?: (postId: number, kind: ReactionKind) => void;
  onCommentAdded?: (postId: number) => void;
  onBookmarkToggled?: (postId: number, bookmarked: boolean) => void;
}

export function PostDetailDialog({
  post,
  canParticipate,
  onClose,
  onReactionAdded,
  onCommentAdded,
  onBookmarkToggled,
}: PostDetailDialogProps) {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language]
  );

  const reactionLabel = (kind: ReactionKind) => {
    const item = REACTIONS.find((r) => r.kind === kind);
    return isEn ? item?.labelEn ?? kind : item?.labelVi ?? kind;
  };

  const [comments, setComments] = useState<SocialComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [commentBody, setCommentBody] = useState("");
  const [replyingTo, setReplyingTo] = useState<{ id: number; author: string } | null>(null);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [reacted, setReacted] = useState<ReactionKind | null>(
    (post.user_reaction as ReactionKind) || null
  );
  const [reactionCount, setReactionCount] = useState(post.reaction_count);
  const [isBookmarked, setIsBookmarked] = useState(Boolean(post.is_bookmarked));
  const [notice, setNotice] = useState<string | null>(null);

  // Internal reporting modal state
  const [reportTarget, setReportTarget] = useState<{
    type: "post" | "comment";
    id: number;
    titleOrSnippet: string;
  } | null>(null);

  const official =
    typeof isClaraOfficial === "function"
      ? isClaraOfficial(post.author_handle) || Boolean(post.is_verified_clinician)
      : Boolean(post.is_verified_clinician);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await getComments(post.id);
      setComments(items);
    } catch {
      setError(copy("community.comment.loadError"));
    } finally {
      setLoading(false);
    }
  }, [copy, post.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const submitComment = useCallback(async () => {
    if (!commentBody.trim()) return;
    setSubmitting(true);
    setCommentError(null);
    try {
      if (replyingTo?.id) {
        await addComment(post.id, commentBody.trim(), replyingTo.id);
      } else {
        await addComment(post.id, commentBody.trim());
      }
      setCommentBody("");
      setReplyingTo(null);
      onCommentAdded?.(post.id);
      await load();
    } catch (err: unknown) {
      const serverDetail = (err as { response?: { data?: { detail?: string } } })?.response
        ?.data?.detail;
      if (typeof serverDetail === "string" && serverDetail.trim()) {
        setCommentError(serverDetail);
      } else if (isSocialModerationBlock(err)) {
        setCommentError(copy("community.comment.moderationBlocked"));
      } else {
        setCommentError(copy("community.comment.submitError"));
      }
    } finally {
      setSubmitting(false);
    }
  }, [commentBody, copy, post.id, replyingTo, load, onCommentAdded]);

  const sendReaction = useCallback(
    async (kind: ReactionKind) => {
      try {
        await addReaction(post.id, kind);
        setReacted(kind);
        setReactionCount((prev) => prev + 1);
        setNotice(copy("community.reaction.sent"));
        onReactionAdded?.(post.id, kind);
      } catch {
        setNotice(copy("community.reaction.error"));
      }
    },
    [copy, post.id, onReactionAdded]
  );

  const handleBookmarkToggle = async () => {
    try {
      const res = await toggleBookmark(post.id);
      setIsBookmarked(res.bookmarked);
      onBookmarkToggled?.(post.id, res.bookmarked);
      setNotice(
        res.bookmarked
          ? isEn
            ? "Post saved to bookmarks."
            : "Đã lưu bài viết vào mục đã lưu."
          : isEn
          ? "Post removed from bookmarks."
          : "Đã bỏ lưu bài viết."
      );
    } catch {
      setNotice(isEn ? "Failed to update bookmark." : "Không thể cập nhật đã lưu.");
    }
  };

  const handleDeleteComment = async (commentId: number) => {
    try {
      await deleteComment(commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
      setNotice(isEn ? "Comment deleted." : "Đã xóa bình luận.");
    } catch {
      setNotice(isEn ? "Failed to delete comment." : "Không thể xóa bình luận.");
    }
  };

  return (
    <>
      <Modal
        open
        onClose={onClose}
        title={post.title}
        description={`@${post.author_handle} · ${formatLocaleDate(language, post.created_at)}`}
        closeLabel={copy("community.dialog.close")}
        size="lg"
        footer={
          canParticipate ? (
            <div className="w-full space-y-2">
              {replyingTo ? (
                <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[var(--surface-brand-soft)] border border-[color:var(--brand-500)]/30 text-xs">
                  <div className="flex items-center gap-1.5 text-[var(--text-brand)] font-medium">
                    <Icon name="chat" size="0.85rem" />
                    <span>
                      {isEn ? `Replying to @${replyingTo.author}` : `Đang trả lời @${replyingTo.author}`}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setReplyingTo(null)}
                    className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  >
                    <Icon name="close" size="0.75rem" />
                  </button>
                </div>
              ) : null}

              <div className="space-y-1">
                <textarea
                  value={commentBody}
                  onChange={(e) => setCommentBody(e.target.value)}
                  rows={3}
                  maxLength={5000}
                  placeholder={copy("community.comment.placeholder")}
                  className="w-full rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-2.5 text-xs sm:text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-1 focus:ring-[var(--brand-500)] outline-none transition"
                />
                <div className="flex justify-between items-center text-[11px] text-[var(--text-muted)]">
                  <span>
                    {isEn
                      ? "Comments are screened for safety & no prescribing."
                      : "Bình luận được rà soát an toàn & không kê đơn."}
                  </span>
                  <span>{commentBody.length}/5000</span>
                </div>
              </div>

              {commentError ? (
                <p className="text-xs font-semibold text-[var(--status-danger-text)] rounded-lg bg-[var(--status-danger-bg)] p-2.5 border border-[color:var(--status-danger-border)]">
                  {commentError}
                </p>
              ) : null}

              <div className="flex justify-end gap-2 pt-1">
                <Button variant="ghost" size="sm" onClick={onClose}>
                  {copy("community.dialog.close")}
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={submitComment}
                  disabled={submitting || !commentBody.trim()}
                  loading={submitting}
                  loadingLabel={copy("community.comment.submitting")}
                >
                  {copy("community.comment.submit")}
                </Button>
              </div>
            </div>
          ) : (
            <div className="w-full text-center py-2">
              <p className="text-xs text-[var(--text-secondary)]">
                {copy("community.comment.joinToComment")}
              </p>
            </div>
          )
        }
      >
        <div className="space-y-4">
          {/* Post Header Meta with Badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-[color:var(--shell-border)]/50 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                  official
                    ? "bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                    : "bg-[var(--surface-muted)] text-[var(--text-primary)] border border-[color:var(--shell-border)]"
                }`}
              >
                {(post.author_display_name || post.author_handle).slice(0, 2).toUpperCase()}
              </div>
              <div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="font-bold text-[var(--text-primary)]">
                    {post.author_display_name ? post.author_display_name : `@${post.author_handle}`}
                  </span>
                  {official ? (
                    <Badge tone="brand" icon="check" className="text-[10px] py-0.5 font-bold">
                      {isEn ? "Verified Clinician" : "Bác sĩ Chuyên gia"}
                    </Badge>
                  ) : (
                    <Badge tone="neutral" className="text-[10px] py-0.5">
                      {isEn ? "Peer Member" : "Thành viên"}
                    </Badge>
                  )}
                  <Badge tone="ok" className="text-[10px] py-0.5">
                    {isEn ? "Moderated" : "Đã duyệt an toàn"}
                  </Badge>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)]">
              {post.community_name ? (
                <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 font-medium border border-[color:var(--shell-border)]">
                  {post.community_name}
                </span>
              ) : null}
              <span>{formatLocaleDate(language, post.created_at)}</span>
            </div>
          </div>

          {/* Post Full Body */}
          <div className="space-y-3">
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
              {post.body}
            </p>

            {/* Medical safety peer reminder card */}
            <div className="rounded-lg bg-[var(--surface-muted)]/70 p-3 text-xs text-[var(--text-secondary)] border border-[color:var(--shell-border)] space-y-1">
              <p className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5 text-[11px]">
                <Icon name="warning" size="0.85rem" className="text-[var(--status-warn-text)]" />
                <span>{isEn ? "Peer Sharing Reminder" : "Lưu ý an toàn chia sẻ"}</span>
              </p>
              <p className="text-[11px] leading-relaxed">
                {isEn
                  ? "This post represents personal peer experience, not a clinical prescription. In an emergency, call 115."
                  : "Bài viết chia sẻ trải nghiệm cá nhân từ cộng đồng, không thay thế chẩn đoán hay đơn thuốc bác sĩ. Trường hợp khẩn cấp hãy gọi 115."}
              </p>
            </div>
          </div>

          {/* Reactions bar and actions */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[color:var(--shell-border)]/50">
            <div className="flex flex-wrap items-center gap-2">
              {REACTIONS.map((r) => {
                const isActive = reacted === r.kind;
                return (
                  <button
                    key={r.kind}
                    type="button"
                    disabled={!canParticipate}
                    onClick={() => sendReaction(r.kind)}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold transition border flex items-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                      isActive
                        ? "bg-[var(--surface-brand-soft)] text-[var(--text-brand)] border-[color:var(--brand-500)]/40 shadow-xs"
                        : "bg-[var(--surface-muted)] text-[var(--text-primary)] border-[color:var(--shell-border)] hover:bg-[var(--surface-panel)]"
                    }`}
                    title={
                      canParticipate
                        ? reactionLabel(r.kind)
                        : copy("community.reaction.joinToReact")
                    }
                  >
                    <span aria-hidden="true">{r.icon}</span>
                    <span>{reactionLabel(r.kind)}</span>
                  </button>
                );
              })}
              <span className="text-xs text-[var(--text-muted)] font-medium pl-1">
                ({formatLocaleNumber(language, reactionCount)})
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleBookmarkToggle}
                className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition cursor-pointer ${
                  isBookmarked
                    ? "text-[var(--text-brand)] bg-[var(--surface-brand-soft)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
                title={isBookmarked ? (isEn ? "Remove Bookmark" : "Bỏ lưu") : isEn ? "Bookmark" : "Lưu"}
              >
                <Icon name="folder" size="0.85rem" />
                <span>{isBookmarked ? (isEn ? "Saved" : "Đã lưu") : isEn ? "Save" : "Lưu"}</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  setReportTarget({
                    type: "post",
                    id: post.id,
                    titleOrSnippet: post.title,
                  })
                }
                className="rounded-lg px-2.5 py-1 text-xs text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition cursor-pointer font-medium"
              >
                {copy("community.report.post")}
              </button>
            </div>
          </div>

          {notice ? (
            <div className="flex items-center justify-between rounded-lg bg-[var(--status-ok-bg)] px-3 py-2 text-xs text-[var(--status-ok-text)] border border-[color:var(--status-ok-border)]">
              <span>{notice}</span>
              <button
                type="button"
                onClick={() => setNotice(null)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] ml-2"
              >
                <Icon name="close" size="0.8rem" />
              </button>
            </div>
          ) : null}

          <hr className="my-2 border-[color:var(--shell-border)]" />

          {/* Comments Section with nested replies */}
          <div className="space-y-3">
            <h4 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span>
                {comments.length > 0
                  ? copy("community.comments.count", {
                      count: formatLocaleNumber(language, comments.length),
                    })
                  : copy("community.comments.heading")}
              </span>
            </h4>

            {loading ? (
              <div className="py-6 text-center text-xs text-[var(--text-secondary)] space-y-2">
                <Icon
                  name="progress"
                  size="1.2rem"
                  className="mx-auto text-[var(--text-brand)] animate-spin"
                />
                <p>{copy("community.comment.loading")}</p>
              </div>
            ) : error ? (
              <div className="rounded-lg bg-[var(--status-danger-bg)] p-3 text-xs text-[var(--status-danger-text)] border border-[color:var(--status-danger-border)] flex items-center justify-between">
                <span>{error}</span>
                <Button variant="ghost" size="sm" onClick={load}>
                  {isEn ? "Retry" : "Thử lại"}
                </Button>
              </div>
            ) : comments.length === 0 ? (
              <div className="rounded-xl bg-[var(--surface-muted)]/50 p-6 text-center space-y-1.5 border border-dashed border-[color:var(--shell-border)]">
                <p className="text-xs font-semibold text-[var(--text-primary)]">
                  {copy("community.comment.empty")}
                </p>
                <p className="text-[11px] text-[var(--text-muted)]">
                  {isEn
                    ? "Share an empathetic word or supportive experience."
                    : "Hãy gửi lời động viên hoặc chia sẻ góc nhìn đồng cảm đầu tiên."}
                </p>
              </div>
            ) : (
              <ul className="space-y-2.5">
                {comments.map((c) => {
                  const commentOfficial =
                    isClaraOfficial(c.author_handle) || Boolean(c.is_verified_clinician);
                  const isReply = Boolean(c.parent_id);

                  return (
                    <li
                      key={c.id}
                      className={`rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-3.5 space-y-1.5 ${
                        isReply ? "ml-6 border-l-2 border-l-[var(--brand-500)]" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <div className="flex items-center gap-2 flex-wrap">
                          <div
                            className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-[10px] ${
                              commentOfficial
                                ? "bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                                : "bg-[var(--surface-muted)] text-[var(--text-primary)] border border-[color:var(--shell-border)]"
                            }`}
                          >
                            {(c.author_display_name || c.author_handle).slice(0, 2).toUpperCase()}
                          </div>
                          <span className="font-bold text-[var(--text-primary)]">
                            {c.author_display_name ? c.author_display_name : `@${c.author_handle}`}
                          </span>
                          {commentOfficial ? (
                            <Badge tone="brand" className="text-[9px] py-0 px-1 font-semibold">
                              {isEn ? "Verified Clinician" : "Bác sĩ Chuyên gia"}
                            </Badge>
                          ) : null}
                          {isReply ? (
                            <span className="text-[10px] text-[var(--text-brand)] font-medium">
                              {isEn ? "Reply" : "Phản hồi"}
                            </span>
                          ) : null}
                          <span className="text-[var(--text-muted)] text-[11px]">·</span>
                          <span className="text-[var(--text-muted)] text-[11px]">
                            {formatLocaleDate(language, c.created_at)}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          {canParticipate ? (
                            <button
                              type="button"
                              onClick={() => setReplyingTo({ id: c.id, author: c.author_handle })}
                              className="text-[11px] text-[var(--text-brand)] hover:underline font-medium cursor-pointer"
                            >
                              {isEn ? "Reply" : "Trả lời"}
                            </button>
                          ) : null}
                          <button
                            type="button"
                            onClick={() =>
                              setReportTarget({
                                type: "comment",
                                id: c.id,
                                titleOrSnippet: c.body.slice(0, 60),
                              })
                            }
                            className="text-[11px] text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition cursor-pointer"
                          >
                            {copy("community.report.comment")}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteComment(c.id)}
                            className="text-[11px] text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition cursor-pointer"
                            title={isEn ? "Delete Comment" : "Xóa bình luận"}
                          >
                            <Icon name="trash" size="0.75rem" />
                          </button>
                        </div>
                      </div>
                      <p className="whitespace-pre-wrap text-xs sm:text-sm text-[var(--text-primary)] leading-relaxed pl-7">
                        {c.body}
                      </p>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </Modal>

      {/* Report Modal */}
      <ReportModal
        open={Boolean(reportTarget)}
        target={reportTarget}
        onClose={() => setReportTarget(null)}
        onSuccess={(msg) => setNotice(msg)}
        onError={(err) => setNotice(err)}
        reportFn={reportContent}
      />
    </>
  );
}

export default PostDetailDialog;
