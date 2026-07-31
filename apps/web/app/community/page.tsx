"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Textarea, Select, Field } from "@/components/ui/field";
import { SurfaceCard, EmptyState, InlineError } from "@/components/ui/surface";
import { Modal } from "@/components/ui/modal";
import PostDetailDialog from "@/components/community/post-detail-dialog";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  SocialCommunity,
  SocialPost,
  getSocialConsent,
  grantSocialConsent,
  listCommunities,
  joinCommunity,
  getFeed,
  createPost,
  SocialUnavailableError,
  isSocialModerationBlock
} from "@/lib/social";

export default function CommunityPage() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consentGranted, setConsentGranted] = useState(false);
  const [communities, setCommunities] = useState<SocialCommunity[]>([]);
  const [feed, setFeed] = useState<SocialPost[]>([]);

  const [composeOpen, setComposeOpen] = useState(false);
  const [composeCommunity, setComposeCommunity] = useState<number | null>(null);
  const [composeTitle, setComposeTitle] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeError, setComposeError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activePost, setActivePost] = useState<SocialPost | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const [consent, comm, posts] = await Promise.all([
        getSocialConsent(),
        listCommunities(),
        getFeed()
      ]);
      setConsentGranted(consent.granted);
      setCommunities(comm);
      setFeed(posts);
    } catch (err) {
      if (err instanceof SocialUnavailableError) {
        setUnavailable(true);
      } else {
        setError(copy("community.loadError"));
      }
    } finally {
      setLoading(false);
    }
  }, [copy]);

  useEffect(() => {
    void load();
  }, [load]);

  const onGrantConsent = useCallback(async () => {
    try {
      await grantSocialConsent();
      setConsentGranted(true);
    } catch {
      setError(copy("community.consentError"));
    }
  }, [copy]);

  const onJoin = useCallback(async (id: number) => {
    try {
      await joinCommunity(id);
      setCommunities((prev) =>
        prev.map((c) => (c.id === id ? { ...c, joined: true, member_count: c.member_count + 1 } : c))
      );
    } catch {
      setError(copy("community.joinError"));
    }
  }, [copy]);

  const openCompose = useCallback(() => {
    setComposeError(null);
    setComposeTitle("");
    setComposeBody("");
    setComposeCommunity(communities[0]?.id ?? null);
    setComposeOpen(true);
  }, [communities]);

  const submitPost = useCallback(async () => {
    if (composeCommunity == null) {
      setComposeError(copy("community.compose.chooseCommunity"));
      return;
    }
    setSubmitting(true);
    setComposeError(null);
    try {
      await createPost({ communityId: composeCommunity, title: composeTitle, body: composeBody });
      setComposeOpen(false);
      await load();
    } catch (err) {
      if (isSocialModerationBlock(err)) {
        setComposeError(copy("community.compose.moderationBlocked"));
      } else {
        setComposeError(copy("community.compose.createError"));
      }
    } finally {
      setSubmitting(false);
    }
  }, [composeCommunity, composeTitle, composeBody, copy, load]);

  const canCompose = useMemo(
    () => consentGranted && communities.length > 0,
    [consentGranted, communities.length]
  );

  if (unavailable) {
    return (
      <PageShell title={copy("community.title")} description={copy("community.description")}>
        <EmptyState
          icon="groups"
          title={copy("community.unavailable.title")}
          description={copy("community.unavailable.description")}
        />
      </PageShell>
    );
  }

  return (
    <PageShell title={copy("community.title")} description={copy("community.description")}>
      <div className="space-y-5">
        <div className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-3 text-sm text-[var(--status-warn-text)]">
          {copy("community.disclaimer")}
        </div>

        {error ? <InlineError message={error} /> : null}

        {loading ? (
          <p className="text-sm text-[var(--text-secondary)]">{copy("community.loading")}</p>
        ) : (
          <>
            {!consentGranted ? (
              <SurfaceCard className="p-5">
                <p className="font-semibold text-[var(--text-primary)]">{copy("community.consent.title")}</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                  {copy("community.consent.description")}
                </p>
                <div className="mt-3">
                  <Button variant="primary" size="sm" onClick={onGrantConsent}>
                    {copy("community.consent.action")}
                  </Button>
                </div>
              </SurfaceCard>
            ) : (
              <div className="flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={openCompose}
                  disabled={!canCompose}
                >
                  {copy("community.compose.action")}
                </Button>
              </div>
            )}

            {communities.length > 0 ? (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">{copy("community.communities.heading")}</h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {communities.map((c) => (
                    <SurfaceCard key={c.id} className="p-4">
                      <p className="font-semibold text-[var(--text-primary)]">{c.name}</p>
                      <p className="mt-1 line-clamp-2 text-sm text-[var(--text-secondary)]">{c.description}</p>
                      <p className="mt-2 text-xs text-[var(--text-secondary)]">
                        {copy("community.members", { count: formatLocaleNumber(language, c.member_count) })}
                      </p>
                      <Button
                        variant="secondary"
                        size="sm"
                        block
                        onClick={() => onJoin(c.id)}
                        disabled={c.joined}
                        className="mt-3"
                      >
                        {c.joined ? copy("community.joined") : copy("community.join")}
                      </Button>
                    </SurfaceCard>
                  ))}
                </div>
              </section>
            ) : null}

            <section>
              <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">{copy("community.feed.heading")}</h2>
              {feed.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)]">
                  {copy("community.feed.empty")}
                </p>
              ) : (
                <div className="space-y-3">
                  {feed.map((post) => (
                    <SurfaceCard
                      key={post.id}
                      interactive
                      className="cursor-pointer p-4"
                    >
                      <article
                        role="button"
                        tabIndex={0}
                        onClick={() => setActivePost(post)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setActivePost(post);
                          }
                        }}
                        className="focus-ring rounded-[var(--radius-lg)]"
                      >
                        <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                          <span className="font-medium text-[var(--text-primary)]">@{post.author_handle}</span>
                          <span>·</span>
                          <span>{formatLocaleDate(language, post.created_at)}</span>
                        </div>
                        <h3 className="mt-2 font-semibold text-[var(--text-primary)]">{post.title}</h3>
                        <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-[var(--text-secondary)]">{post.body}</p>
                        <div className="mt-3 flex gap-4 text-xs text-[var(--text-secondary)]">
                          <span>{copy("community.comments.count", { count: formatLocaleNumber(language, post.comment_count) })}</span>
                          <span>{copy("community.reactions.count", { count: formatLocaleNumber(language, post.reaction_count) })}</span>
                        </div>
                      </article>
                    </SurfaceCard>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      <Modal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        title={copy("community.compose.title")}
        size="md"
        footer={
          <>
            <Button variant="ghost" size="sm" onClick={() => setComposeOpen(false)}>
              {copy("community.compose.cancel")}
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={submitPost}
              disabled={submitting || !composeTitle.trim() || !composeBody.trim()}
              loading={submitting}
              loadingLabel={copy("community.compose.submitting")}
            >
              {copy("community.compose.action")}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <Select
            label={copy("community.compose.communityLabel")}
            value={composeCommunity ?? ""}
            onChange={(e) => setComposeCommunity(Number(e.target.value))}
          >
            {communities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
          <Field
            label={copy("community.compose.titleLabel")}
            value={composeTitle}
            onChange={(e) => setComposeTitle(e.target.value)}
            maxLength={200}
          />
          <Textarea
            label={copy("community.compose.bodyLabel")}
            value={composeBody}
            onChange={(e) => setComposeBody(e.target.value)}
            rows={5}
            maxLength={5000}
          />
          {composeError ? (
            <p className="text-sm text-[var(--status-danger-text)]">{composeError}</p>
          ) : null}
        </div>
      </Modal>

      {activePost ? (
        <PostDetailDialog
          post={activePost}
          canParticipate={consentGranted}
          onClose={() => setActivePost(null)}
        />
      ) : null}
    </PageShell>
  );
}
