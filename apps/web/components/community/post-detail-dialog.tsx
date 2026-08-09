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
import Modal from "@/components/ui/modal";

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
    <Modal
      open
      onClose={onClose}
      title={post.title}
      description={`@${post.author_handle} · ${formatLocaleDate(language, post.created_at)}`}
      closeLabel={copy("community.dialog.close")}
      size="lg"
      footer={
        canParticipate ? (
          <div className="w-full">
            <textarea
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              rows={2}
              maxLength={5000}
              placeholder={copy("community.comment.placeholder")}
              className="w-full rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-primary)]"
            />
            {commentError ? (
              <p className="mt-1 text-xs text-[var(--status-danger-text)]">{commentError}</p>
            ) : null}
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={submitComment}
                disabled={submitting || !commentBody.trim()}
                className="rounded-[var(--radius-md)] bg-[var(--brand-600)] px-4 py-2 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[var(--brand-700)] disabled:opacity-50"
              >
                {submitting ? copy("community.comment.submitting") : copy("community.comment.submit")}
              </button>
            </div>
          </div>
        ) : (
          <p className="w-full text-center text-sm text-[var(--text-secondary)]">
            {copy("community.comment.joinToComment")}
          </p>
        )
      }
    >
        <div>
          <p className="whitespace-pre-wrap text-sm text-[var(--text-primary)]">{post.body}</p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {REACTIONS.map((r) => (
              <button
                key={r.kind}
                type="button"
                disabled={!canParticipate || reacted === r.kind}
                onClick={() => sendReaction(r.kind)}
                className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-sm text-[var(--text-primary)] disabled:opacity-50"
                title={canParticipate ? reactionLabel(r.kind) : copy("community.reaction.joinToReact")}
              >
                <span aria-hidden="true">{r.icon}</span> {reactionLabel(r.kind)}
              </button>
            ))}
            <button
              type="button"
              onClick={() => report("post", post.id)}
              className="ml-auto rounded-lg px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--status-danger-text)]"
            >
              {copy("community.report.post")}
            </button>
          </div>

          {notice ? (
            <p className="mt-3 rounded-[var(--radius-md)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-secondary)]">
              {notice}
            </p>
          ) : null}

          <hr className="my-5 border-[color:var(--shell-border)]" />

          <h4 className="mb-3 text-sm font-semibold text-[var(--text-primary)]">
            {comments.length > 0
              ? copy("community.comments.count", { count: formatLocaleNumber(language, comments.length) })
              : copy("community.comments.heading")}
          </h4>

          {loading ? (
            <p className="text-sm text-[var(--text-secondary)]">{copy("community.comment.loading")}</p>
          ) : error ? (
            <p className="text-sm text-[var(--status-danger-text)]">{error}</p>
          ) : comments.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{copy("community.comment.empty")}</p>
          ) : (
            <ul className="space-y-3">
              {comments.map((c) => (
                <li key={c.id} className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                  <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                    <span className="font-medium text-[var(--text-primary)]">@{c.author_handle}</span>
                    <span>·</span>
                    <span>{formatLocaleDate(language, c.created_at)}</span>
                    <button
                      type="button"
                      onClick={() => report("comment", c.id)}
                      className="ml-auto text-[var(--text-secondary)] hover:text-[var(--status-danger-text)]"
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

    </Modal>
  );
}
