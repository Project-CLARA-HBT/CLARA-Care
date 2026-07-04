"use client";

import { useCallback, useEffect, useState } from "react";
import {
  SocialComment,
  SocialPost,
  ReactionKind,
  addComment,
  addReaction,
  getComments,
  isSocialModerationBlock,
  reportContent
} from "@/lib/social";

// Interactive post-detail dialog for the CLARA community surface.
//
// Lets a member read a post in full, browse + add comments (server-moderated,
// fail-closed), send a supportive reaction, and report content. Every write
// path surfaces the moderation-block message verbatim so the not-a-doctor /
// no-prescribing guardrail is visible, never silently swallowed.

const REACTIONS: { kind: ReactionKind; label: string; icon: string }[] = [
  { kind: "helpful", label: "Hữu ích", icon: "👍" },
  { kind: "relate", label: "Đồng cảm", icon: "🤝" },
  { kind: "thanks", label: "Cảm ơn", icon: "🙏" }
];

export default function PostDetailDialog({
  post,
  canParticipate,
  onClose
}: {
  post: SocialPost;
  canParticipate: boolean;
  onClose: () => void;
}) {
  const [comments, setComments] = useState<SocialComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [commentBody, setCommentBody] = useState("");
  const [commentError, setCommentError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [reacted, setReacted] = useState<ReactionKind | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setComments(await getComments(post.id));
    } catch {
      setError("Không thể tải bình luận. Vui lòng thử lại.");
    } finally {
      setLoading(false);
    }
  }, [post.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Close on Escape for keyboard users.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submitComment = useCallback(async () => {
    if (!commentBody.trim()) return;
    setSubmitting(true);
    setCommentError(null);
    try {
      await addComment(post.id, commentBody.trim());
      setCommentBody("");
      await load();
    } catch (err) {
      if (isSocialModerationBlock(err)) {
        setCommentError(
          "Bình luận không phù hợp quy tắc cộng đồng (không kê đơn/chẩn đoán/liều dùng) hoặc có dấu hiệu khẩn cấp."
        );
      } else {
        setCommentError("Không thể gửi bình luận. Vui lòng thử lại.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [commentBody, post.id, load]);

  const sendReaction = useCallback(
    async (kind: ReactionKind) => {
      try {
        await addReaction(post.id, kind);
        setReacted(kind);
        setNotice("Đã gửi phản hồi tích cực.");
      } catch {
        setNotice("Không thể gửi phản hồi. Vui lòng thử lại.");
      }
    },
    [post.id]
  );

  const report = useCallback(
    async (targetType: "post" | "comment", targetId: number) => {
      try {
        await reportContent({ targetType, targetId, reason: "user_report" });
        setNotice("Đã gửi báo cáo. Đội ngũ kiểm duyệt sẽ xem xét.");
      } catch {
        setNotice("Không thể gửi báo cáo. Vui lòng thử lại.");
      }
    },
    []
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={post.title}
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-[var(--surface)] shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border-subtle)] p-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <span className="font-medium text-[var(--text-primary)]">@{post.author_handle}</span>
              <span>·</span>
              <span>{new Date(post.created_at).toLocaleDateString("vi-VN")}</span>
            </div>
            <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{post.title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="rounded-lg px-2 py-1 text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          <p className="whitespace-pre-wrap text-sm text-[var(--text-primary)]">{post.body}</p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {REACTIONS.map((r) => (
              <button
                key={r.kind}
                type="button"
                disabled={!canParticipate || reacted === r.kind}
                onClick={() => sendReaction(r.kind)}
                className="rounded-full border border-[var(--border-subtle)] px-3 py-1.5 text-sm disabled:opacity-50"
                title={canParticipate ? r.label : "Tham gia cộng đồng để phản hồi"}
              >
                <span aria-hidden="true">{r.icon}</span> {r.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => report("post", post.id)}
              className="ml-auto rounded-lg px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-red-600"
            >
              Báo cáo bài viết
            </button>
          </div>

          {notice ? (
            <p className="mt-3 rounded-lg bg-[var(--surface-hover)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              {notice}
            </p>
          ) : null}

          <hr className="my-5 border-[var(--border-subtle)]" />

          <h4 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
            Bình luận {comments.length > 0 ? `(${comments.length})` : ""}
          </h4>

          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">Đang tải bình luận…</p>
          ) : error ? (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : comments.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">Chưa có bình luận. Hãy là người đầu tiên.</p>
          ) : (
            <ul className="space-y-3">
              {comments.map((c) => (
                <li key={c.id} className="rounded-xl border border-[var(--border-subtle)] p-3">
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">@{c.author_handle}</span>
                    <span>·</span>
                    <span>{new Date(c.created_at).toLocaleDateString("vi-VN")}</span>
                    <button
                      type="button"
                      onClick={() => report("comment", c.id)}
                      className="ml-auto text-[var(--text-secondary)] hover:text-red-600"
                    >
                      Báo cáo
                    </button>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-[var(--text-primary)]">{c.body}</p>
                </li>
              ))}
            </ul>
          )}
        </div>

        {canParticipate ? (
          <div className="border-t border-[var(--border-subtle)] p-4">
            <textarea
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              rows={2}
              maxLength={5000}
              placeholder="Chia sẻ suy nghĩ của bạn (không kê đơn/chẩn đoán/liều dùng)…"
              className="w-full rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2 text-sm"
            />
            {commentError ? (
              <p className="mt-1 text-xs text-red-600 dark:text-red-400">{commentError}</p>
            ) : null}
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={submitComment}
                disabled={submitting || !commentBody.trim()}
                className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {submitting ? "Đang gửi…" : "Gửi bình luận"}
              </button>
            </div>
          </div>
        ) : (
          <div className="border-t border-[var(--border-subtle)] p-4 text-center text-sm text-[var(--text-secondary)]">
            Tham gia cộng đồng để bình luận.
          </div>
        )}
      </div>
    </div>
  );
}
