"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { SurfaceCard, EmptyState, InlineError } from "@/components/ui/surface";
import {
  SafetyBanner,
  TopicFilterBar,
  PostCard,
  ComposeModal,
  ReportModal,
  PrivacyModal,
  PostDetailDialog,
} from "@/components/community";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  SocialCommunity,
  SocialPost,
  ReactionKind,
  getSocialConsent,
  grantSocialConsent,
  listCommunities,
  joinCommunity,
  leaveCommunity,
  getFeed,
  createPost,
  addReaction,
  reportContent,
  SocialUnavailableError,
  isClaraOfficial,
} from "@/lib/social";

export default function CommunityPage() {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language]
  );

  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [consentGranted, setConsentGranted] = useState(false);
  const [communities, setCommunities] = useState<SocialCommunity[]>([]);
  const [feed, setFeed] = useState<SocialPost[]>([]);

  // Filtering & Search
  const [selectedCommunityId, setSelectedCommunityId] = useState<number | "all">("all");
  const [authorFilter, setAuthorFilter] = useState<"all" | "official" | "peers">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Compose Modal
  const [composeOpen, setComposeOpen] = useState(false);

  // Post Detail & Report Modal
  const [activePost, setActivePost] = useState<SocialPost | null>(null);
  const [reportTarget, setReportTarget] = useState<{
    type: "post" | "comment";
    id: number;
    titleOrSnippet: string;
  } | null>(null);
  const [privacyModalOpen, setPrivacyModalOpen] = useState(false);

  // Hidden post IDs for local mute
  const [hiddenPostIds, setHiddenPostIds] = useState<number[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const [consent, comm, posts] = await Promise.all([
        getSocialConsent(),
        listCommunities(),
        getFeed(),
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
      setNotice(isEn ? "Community guidelines accepted." : "Đã đồng ý tham gia cộng đồng.");
    } catch {
      setError(copy("community.consentError"));
    }
  }, [copy, isEn]);

  const onToggleJoinCommunity = useCallback(
    async (community: SocialCommunity) => {
      try {
        if (community.joined) {
          await leaveCommunity(community.id);
          setCommunities((prev) =>
            prev.map((c) =>
              c.id === community.id
                ? { ...c, joined: false, member_count: Math.max(0, c.member_count - 1) }
                : c
            )
          );
          setNotice(
            isEn
              ? `Left ${community.name}`
              : `Đã rời cộng đồng ${community.name}`
          );
        } else {
          await joinCommunity(community.id);
          setCommunities((prev) =>
            prev.map((c) =>
              c.id === community.id
                ? { ...c, joined: true, member_count: c.member_count + 1 }
                : c
            )
          );
          setNotice(
            isEn
              ? `Joined ${community.name}`
              : `Đã tham gia cộng đồng ${community.name}`
          );
        }
      } catch {
        setError(copy("community.joinError"));
      }
    },
    [copy, isEn]
  );

  const openCompose = useCallback(() => {
    setComposeOpen(true);
  }, []);

  const handleQuickReaction = useCallback(
    async (post: SocialPost, kind: ReactionKind = "helpful") => {
      if (!consentGranted) {
        setNotice(copy("community.reaction.joinToReact"));
        return;
      }
      try {
        await addReaction(post.id, kind);
        setFeed((prev) =>
          prev.map((p) => (p.id === post.id ? { ...p, reaction_count: p.reaction_count + 1 } : p))
        );
        setNotice(copy("community.reaction.sent"));
      } catch {
        setNotice(copy("community.reaction.error"));
      }
    },
    [consentGranted, copy]
  );

  const toggleHidePost = useCallback((postId: number) => {
    setHiddenPostIds((prev) =>
      prev.includes(postId) ? prev.filter((id) => id !== postId) : [...prev, postId]
    );
  }, []);

  const canCompose = useMemo(
    () => consentGranted && communities.length > 0,
    [consentGranted, communities.length]
  );

  // Active community metadata if filtered
  const activeCommunity = useMemo(() => {
    if (selectedCommunityId === "all") return null;
    return communities.find((c) => c.id === selectedCommunityId) ?? null;
  }, [communities, selectedCommunityId]);

  // Filtered feed list
  const filteredFeed = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return feed.filter((post) => {
      if (hiddenPostIds.includes(post.id)) return false;
      if (selectedCommunityId !== "all" && post.community_id !== selectedCommunityId) {
        return false;
      }
      if (authorFilter === "official" && !isClaraOfficial(post.author_handle)) {
        return false;
      }
      if (authorFilter === "peers" && isClaraOfficial(post.author_handle)) {
        return false;
      }
      if (q) {
        const text = `${post.title} ${post.body} ${post.author_handle}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });
  }, [feed, hiddenPostIds, selectedCommunityId, authorFilter, searchQuery]);

  if (unavailable) {
    return (
      <PageShell
        title={copy("community.title")}
        description={copy("community.description")}
        variant="plain"
      >
        <div className="max-w-4xl mx-auto py-8">
          <EmptyState
            icon="groups"
            title={copy("community.unavailable.title")}
            description={copy("community.unavailable.description")}
          />
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title={copy("community.title")}
      description={copy("community.description")}
      variant="plain"
    >
      <div className="max-w-4xl mx-auto space-y-6">
        {/* 1. Safety Distinction Banner */}
        <SafetyBanner onOpenPrivacyPolicy={() => setPrivacyModalOpen(true)} />

        {notice ? (
          <div className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-2.5 text-xs text-[var(--status-ok-text)]">
            <div className="flex items-center gap-2">
              <Icon name="check" size="1rem" />
              <span>{notice}</span>
            </div>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
            >
              <Icon name="close" size="0.9rem" />
            </button>
          </div>
        ) : null}

        {error ? <InlineError message={error} /> : null}

        {/* 2. Topic & Filter Controls */}
        <TopicFilterBar
          communities={communities}
          selectedCommunityId={selectedCommunityId}
          onSelectCommunity={setSelectedCommunityId}
          authorFilter={authorFilter}
          onSelectAuthorFilter={setAuthorFilter}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onToggleJoinCommunity={onToggleJoinCommunity}
          activeCommunity={activeCommunity}
        />

        {/* 3. Composer Action or Participation Consent Card */}
        {!consentGranted ? (
          <SurfaceCard className="p-5 sm:p-6 border-[color:var(--brand-500)]/40 bg-[var(--surface-panel)] space-y-3 shadow-xs">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] flex items-center justify-center shrink-0 border border-[color:var(--brand-500)]/30">
                <Icon name="contact" size="1.25rem" />
              </div>
              <div className="space-y-1.5 flex-1 min-w-0">
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {copy("community.consent.title")}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {copy("community.consent.description")}
                </p>
                <div className="pt-1.5">
                  <Button variant="primary" size="sm" onClick={onGrantConsent}>
                    {copy("community.consent.action")}
                  </Button>
                </div>
              </div>
            </div>
          </SurfaceCard>
        ) : (
          <SurfaceCard className="p-4 sm:p-5 flex items-center justify-between gap-4 border-[color:var(--shell-border)] bg-[var(--surface-panel)] shadow-xs">
            <div
              onClick={openCompose}
              className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition"
            >
              <div className="w-8 h-8 rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold text-xs flex items-center justify-center shrink-0 border border-[color:var(--brand-500)]/20">
                <Icon name="edit" size="0.95rem" />
              </div>
              <span className="truncate font-medium">
                {isEn
                  ? "Share a health experience, question or tip with the community..."
                  : "Chia sẻ câu chuyện, kinh nghiệm sức khỏe hoặc đặt câu hỏi cùng cộng đồng..."}
              </span>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={openCompose}
              disabled={!canCompose}
              className="shrink-0 font-bold"
            >
              <Icon name="plus" size="0.9rem" className="mr-1" />
              {copy("community.compose.action")}
            </Button>
          </SurfaceCard>
        )}

        {/* 4. Flowing Editorial Feed List */}
        <section aria-labelledby="community-feed-heading" className="space-y-4">
          <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-2">
            <h2
              id="community-feed-heading"
              className="text-base font-bold text-[var(--text-primary)] flex items-center gap-2"
            >
              <span>{copy("community.feed.heading")}</span>
              <span className="text-xs font-normal text-[var(--text-muted)]">
                ({filteredFeed.length} {isEn ? "posts" : "bài viết"})
              </span>
            </h2>
            {hiddenPostIds.length > 0 ? (
              <button
                type="button"
                onClick={() => setHiddenPostIds([])}
                className="text-xs text-[var(--text-brand)] hover:underline font-semibold cursor-pointer"
              >
                {isEn
                  ? `Unhide ${hiddenPostIds.length} hidden posts`
                  : `Hiện lại ${hiddenPostIds.length} bài đã ẩn`}
              </button>
            ) : null}
          </div>

          {loading ? (
            <div className="py-12 text-center text-sm text-[var(--text-secondary)] space-y-2">
              <Icon name="progress" size="1.5rem" className="mx-auto text-[var(--text-brand)] animate-spin" />
              <p>{copy("community.loading")}</p>
            </div>
          ) : filteredFeed.length === 0 ? (
            <EmptyState
              icon="groups"
              title={copy("community.feed.empty")}
              description={
                searchQuery || selectedCommunityId !== "all" || authorFilter !== "all"
                  ? isEn
                    ? "No posts matched your current filters. Try resetting search or selecting all topics."
                    : "Không tìm thấy bài viết nào phù hợp với bộ lọc. Hãy thử đặt lại tìm kiếm."
                  : isEn
                  ? "Be the first to share an experience or question with the community."
                  : "Hãy là người đầu tiên chia sẻ câu chuyện cùng cộng đồng."
              }
            >
              {canCompose ? (
                <Button variant="secondary" size="sm" onClick={openCompose}>
                  {copy("community.compose.action")}
                </Button>
              ) : null}
            </EmptyState>
          ) : (
            <div className="space-y-4">
              {filteredFeed.map((post) => {
                const comm = communities.find((c) => c.id === post.community_id);
                return (
                  <PostCard
                    key={post.id}
                    post={post}
                    community={comm}
                    canParticipate={consentGranted}
                    onOpenDetail={(p) => setActivePost(p)}
                    onReaction={(p) => handleQuickReaction(p, "helpful")}
                    onReport={(p) =>
                      setReportTarget({
                        type: "post",
                        id: p.id,
                        titleOrSnippet: p.title,
                      })
                    }
                    onToggleHide={toggleHidePost}
                  />
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Compose Dialog (Modal) */}
      <ComposeModal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        communities={communities}
        initialCommunityId={typeof selectedCommunityId === "number" ? selectedCommunityId : null}
        onPostCreated={load}
        createPostFn={createPost}
      />

      {/* Report Content Modal */}
      <ReportModal
        open={Boolean(reportTarget)}
        target={reportTarget}
        onClose={() => setReportTarget(null)}
        onSuccess={(msg) => setNotice(msg)}
        onError={(err) => setNotice(err)}
        reportFn={reportContent}
      />

      {/* Privacy & Zero-PII Policy Modal */}
      <PrivacyModal
        open={privacyModalOpen}
        onClose={() => setPrivacyModalOpen(false)}
      />

      {/* Post Detail Dialog (Comments & Interactions) */}
      {activePost ? (
        <PostDetailDialog
          post={activePost}
          canParticipate={consentGranted}
          onClose={() => setActivePost(null)}
          onReactionAdded={(postId) => {
            setFeed((prev) =>
              prev.map((p) => (p.id === postId ? { ...p, reaction_count: p.reaction_count + 1 } : p))
            );
          }}
          onCommentAdded={(postId) => {
            setFeed((prev) =>
              prev.map((p) => (p.id === postId ? { ...p, comment_count: p.comment_count + 1 } : p))
            );
          }}
        />
      ) : null}
    </PageShell>
  );
}
