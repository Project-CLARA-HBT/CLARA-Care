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
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

// Interactive post-detail dialog for the CLARA community surface.
//
// Lets a member read a post in full, browse + add comments (server-moderated,
// fail-closed), send a supportive reaction, and report content. Every write
// path surfaces the moderation-block message verbatim so the not-a-doctor /
// no-prescribing guardrail is visible, never silently swallowed.

const REACTIONS: { kind: ReactionKind; icon: string }[] = [
  { kind: "helpful", icon: "👍" },
  { kind: "relate", icon: "🤝" },
  { kind: "thanks", icon: "🙏" }
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
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );
  const reactionLabel = (kind: ReactionKind) =>
    copy(`community.reaction.${kind}` as UITranslationKey);
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
      setError(copy("community.comment.loadError"));
    } finally {
      setLoading(false);
    }
  }, [copy, post.id]);

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
        setCommentError(copy("community.comment.moderationBlocked"));
      } else {
        setCommentError(copy("community.comment.submitError"));
      }
    } finally {
      setSubmitting(false);
    }
  }, [commentBody, copy, post.id, load]);

  const sendReaction = useCallback(
    async (kind: ReactionKind) => {
      try {
        await addReaction(post.id, kind);
        setReacted(kind);
        setNotice(copy("community.reaction.sent"));
      } catch {
        setNotice(copy("community.reaction.error"));
      }
    },
    [copy, post.id]
  );

  const report = useCallback(
    async (targetType: "post" | "comment", targetId: number) => {
      try {
        await reportContent({ targetType, targetId, reason: "user_report" });
        setNotice(copy("community.report.sent"));
      } catch {
        setNotice(copy("community.report.error"));
      }
    },
    [copy]
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
              <span>{formatLocaleDate(language, post.created_at)}</span>
            </div>
            <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{post.title}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={copy("community.dialog.close")}
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
                title={canParticipate ? reactionLabel(r.kind) : copy("community.reaction.joinToReact")}
              >
                <span aria-hidden="true">{r.icon}</span> {reactionLabel(r.kind)}
              </button>
            ))}
            <button
              type="button"
              onClick={() => report("post", post.id)}
              className="ml-auto rounded-lg px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-red-600"
            >
              {copy("community.report.post")}
            </button>
          </div>

          {notice ? (
            <p className="mt-3 rounded-lg bg-[var(--surface-hover)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              {notice}
            </p>
          ) : null}

          <hr className="my-5 border-[var(--border-subtle)]" />

          <h4 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
            {comments.length > 0
              ? copy("community.comments.count", { count: formatLocaleNumber(language, comments.length) })
              : copy("community.comments.heading")}
          </h4>

          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">{copy("community.comment.loading")}</p>
          ) : error ? (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          ) : comments.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{copy("community.comment.empty")}</p>
          ) : (
            <ul className="space-y-3">
              {comments.map((c) => (
                <li key={c.id} className="rounded-xl border border-[var(--border-subtle)] p-3">
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">@{c.author_handle}</span>
                    <span>·</span>
                    <span>{formatLocaleDate(language, c.created_at)}</span>
                    <button
                      type="button"
                      onClick={() => report("comment", c.id)}
                      className="ml-auto text-[var(--text-secondary)] hover:text-red-600"
                    >
                      {copy("community.report.comment")}
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
              placeholder={copy("community.comment.placeholder")}
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
                className="rounded-[var(--radius-md)] bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-[var(--on-secondary-container)] disabled:opacity-50"
              >
                {submitting ? copy("community.comment.submitting") : copy("community.comment.submit")}
              </button>
            </div>
          </div>
        ) : (
          <div className="border-t border-[var(--border-subtle)] p-4 text-center text-sm text-[var(--text-secondary)]">
            {copy("community.comment.joinToComment")}
          </div>
        )}
      </div>
    </div>
  );
}
