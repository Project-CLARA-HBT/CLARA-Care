"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Icon, type IconName } from "@/components/ui/icon";
import { Textarea, Select, Field } from "@/components/ui/field";
import { SurfaceCard, EmptyState, InlineError } from "@/components/ui/surface";
import { Modal } from "@/components/ui/modal";
import PostDetailDialog from "@/components/community/post-detail-dialog";
import { formatLocaleDate, formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
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
  isSocialModerationBlock
} from "@/lib/social";

/**
 * Checks if an author handle or title represents a CLARA official or verified clinician.
 */
function isClaraOfficial(handle: string): boolean {
  const lower = handle.toLowerCase();
  return (
    lower.startsWith("clara") ||
    lower.startsWith("dr_") ||
    lower.startsWith("bs_") ||
    lower.startsWith("bacsi_") ||
    lower.startsWith("duocsi_") ||
    lower.startsWith("expert_") ||
    lower.startsWith("mod_") ||
    lower.includes("official")
  );
}

export default function CommunityPage() {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
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
  const [composeCommunity, setComposeCommunity] = useState<number | null>(null);
  const [composeTitle, setComposeTitle] = useState("");
  const [composeBody, setComposeBody] = useState("");
  const [composeError, setComposeError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Post Detail & Report Modal
  const [activePost, setActivePost] = useState<SocialPost | null>(null);
  const [reportTarget, setReportTarget] = useState<{ id: number; title: string } | null>(null);
  const [reportReason, setReportReason] = useState("misinformation");
  const [reporting, setReporting] = useState(false);
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
    setComposeError(null);
    setComposeTitle("");
    setComposeBody("");
    setComposeCommunity(
      typeof selectedCommunityId === "number"
        ? selectedCommunityId
        : communities[0]?.id ?? null
    );
    setComposeOpen(true);
  }, [communities, selectedCommunityId]);

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
      setNotice(isEn ? "Post published after safety review." : "Bài viết đã được đăng sau khi rà soát an toàn.");
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
  }, [composeCommunity, composeTitle, composeBody, copy, isEn, load]);

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

  const submitReport = useCallback(async () => {
    if (!reportTarget) return;
    setReporting(true);
    try {
      await reportContent({
        targetType: "post",
        targetId: reportTarget.id,
        reason: reportReason
      });
      setNotice(copy("community.report.sent"));
      setReportTarget(null);
    } catch {
      setNotice(copy("community.report.error"));
    } finally {
      setReporting(false);
    }
  }, [copy, reportReason, reportTarget]);

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
        {/* 1. Safety Distinction Banner (Requirement 6.72 Layout Item 1) */}
        <section
          aria-labelledby="community-safety-banner-heading"
          className="rounded-[var(--radius-xl)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]/60 p-4 sm:p-5 space-y-2"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-[var(--status-warn-bg)] p-2 text-[var(--status-warn-text)] shrink-0 border border-[color:var(--status-warn-border)]">
              <Icon name="warning" size="1.2rem" />
            </div>
            <div className="space-y-1 flex-1 min-w-0">
              <h2
                id="community-safety-banner-heading"
                className="text-sm font-bold text-[var(--text-primary)] flex flex-wrap items-center gap-2"
              >
                <span>{isEn ? "Medical Safety & Peer Sharing Notice" : "Lưu ý an toàn y tế & Chia sẻ đồng cấp"}</span>
                <Badge tone="ok" icon="check" className="text-[10px] py-0.5">
                  {isEn ? "Pre-publish AI Screening Active" : "Đã kích hoạt kiểm duyệt AI"}
                </Badge>
              </h2>
              <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                {copy("community.disclaimer")}
              </p>
              <div className="pt-1 flex flex-wrap items-center gap-3 text-xs">
                <button
                  type="button"
                  onClick={() => setPrivacyModalOpen(true)}
                  className="font-medium text-[var(--text-brand)] hover:underline inline-flex items-center gap-1"
                >
                  <Icon name="help" size="0.85rem" />
                  <span>{isEn ? "Zero-PII & Moderation Policy" : "Chính sách bảo mật Zero-PII & Kiểm duyệt"}</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        {notice ? (
          <div className="flex items-center justify-between rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-2.5 text-xs text-[var(--status-ok-text)]">
            <div className="flex items-center gap-2">
              <Icon name="check" size="1rem" />
              <span>{notice}</span>
            </div>
            <button
              type="button"
              onClick={() => setNotice(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              <Icon name="close" size="0.9rem" />
            </button>
          </div>
        ) : null}

        {error ? <InlineError message={error} /> : null}

        {/* 2. Topic & Filter Controls (Requirement 6.72 Layout Item 2) */}
        <section
          aria-labelledby="community-filter-heading"
          className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 sm:p-5 space-y-4"
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

            {/* Author verification filter toggle */}
            <div className="inline-flex rounded-lg bg-[var(--surface-muted)] p-1 border border-[color:var(--shell-border)] text-xs">
              <button
                type="button"
                onClick={() => setAuthorFilter("all")}
                className={`px-3 py-1 rounded-md font-semibold transition ${
                  authorFilter === "all"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? "All Posts" : "Tất cả"}
              </button>
              <button
                type="button"
                onClick={() => setAuthorFilter("official")}
                className={`px-3 py-1 rounded-md font-semibold transition ${
                  authorFilter === "official"
                    ? "bg-[var(--surface-panel)] text-[var(--text-brand)] shadow-sm border border-[color:var(--shell-border)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? "CLARA / Verified" : "CLARA & Chuyên gia"}
              </button>
              <button
                type="button"
                onClick={() => setAuthorFilter("peers")}
                className={`px-3 py-1 rounded-md font-semibold transition ${
                  authorFilter === "peers"
                    ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-sm border border-[color:var(--shell-border)]"
                    : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                }`}
              >
                {isEn ? "Peer Community" : "Thành viên"}
              </button>
            </div>
          </div>

          {/* Communities horizontal pill selector */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              onClick={() => setSelectedCommunityId("all")}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition border ${
                selectedCommunityId === "all"
                  ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] border-[color:var(--brand-500)] shadow-sm"
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
                  onClick={() => setSelectedCommunityId(c.id)}
                  className={`rounded-full px-3 py-1.5 text-xs font-semibold transition border flex items-center gap-1.5 ${
                    isSelected
                      ? "bg-[var(--brand-600)] text-[var(--button-primary-text)] border-[color:var(--brand-500)] shadow-sm"
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

          {/* Active community information banner */}
          {activeCommunity ? (
            <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
              <div className="space-y-0.5">
                <p className="font-bold text-[var(--text-primary)]">{activeCommunity.name}</p>
                <p className="text-[var(--text-secondary)]">{activeCommunity.description}</p>
                <p className="text-[11px] text-[var(--text-muted)]">
                  {copy("community.members", {
                    count: formatLocaleNumber(language, activeCommunity.member_count)
                  })}
                </p>
              </div>
              <Button
                variant={activeCommunity.joined ? "ghost" : "secondary"}
                size="sm"
                onClick={() => onToggleJoinCommunity(activeCommunity)}
                className="self-start sm:self-center shrink-0"
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
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={
                isEn
                  ? "Search posts in community feed..."
                  : "Tìm kiếm bài viết, tác giả hoặc từ khóa trong cộng đồng..."
              }
              className="block w-full pl-9 pr-8 py-2 bg-[var(--surface-muted)] border border-[color:var(--shell-border)] rounded-lg text-xs font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-1 focus:ring-[var(--brand-500)] outline-none"
              data-testid="community-search-input"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute inset-y-0 right-0 pr-3 pt-1 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <Icon name="close" size="0.85rem" />
              </button>
            ) : null}
          </div>
        </section>

        {/* 3. One Composer Action (Requirement 6.72 Layout Item 3) */}
        {!consentGranted ? (
          <SurfaceCard className="p-5 sm:p-6 border-[color:var(--brand-500)]/40 bg-[var(--surface-panel)] space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)] flex items-center justify-center shrink-0 border border-[color:var(--brand-500)]/30">
                <Icon name="contact" size="1.25rem" />
              </div>
              <div className="space-y-1 flex-1 min-w-0">
                <h3 className="font-bold text-sm text-[var(--text-primary)]">
                  {copy("community.consent.title")}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {copy("community.consent.description")}
                </p>
                <div className="pt-2">
                  <Button variant="primary" size="sm" onClick={onGrantConsent}>
                    {copy("community.consent.action")}
                  </Button>
                </div>
              </div>
            </div>
          </SurfaceCard>
        ) : (
          <SurfaceCard className="p-4 sm:p-5 flex items-center justify-between gap-4 border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
            <div
              onClick={openCompose}
              className="flex items-center gap-3 flex-1 min-w-0 cursor-pointer text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)]"
            >
              <div className="w-8 h-8 rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold text-xs flex items-center justify-center shrink-0 border border-[color:var(--brand-500)]/20">
                <Icon name="edit" size="0.95rem" />
              </div>
              <span className="truncate">
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

        {/* 4. Flowing Editorial Feed List (Requirement 6.72 Layout Item 4, 5, 6) */}
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
                className="text-xs text-[var(--text-brand)] hover:underline"
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
                const official = isClaraOfficial(post.author_handle);
                const community = communities.find((c) => c.id === post.community_id);

                return (
                  <SurfaceCard
                    key={post.id}
                    interactive
                    className="p-5 space-y-3 transition border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
                  >
                    {/* Post Item Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        {/* Avatar */}
                        <div
                          className={`w-7 h-7 rounded-full flex items-center justify-center font-bold text-xs ${
                            official
                              ? "bg-[var(--brand-600)] text-[var(--button-primary-text)]"
                              : "bg-[var(--surface-muted)] text-[var(--text-primary)] border border-[color:var(--shell-border)]"
                          }`}
                        >
                          {post.author_handle.slice(0, 2).toUpperCase()}
                        </div>

                        <span className="font-bold text-[var(--text-primary)]">
                          @{post.author_handle}
                        </span>

                        {/* 5. Peer vs CLARA official distinction badge */}
                        {official ? (
                          <Badge tone="brand" icon="check" className="text-[10px] py-0.5 font-bold">
                            {isEn ? "CLARA Official" : "CLARA Chuyên gia"}
                          </Badge>
                        ) : (
                          <Badge tone="neutral" className="text-[10px] py-0.5">
                            {isEn ? "Peer Member" : "Thành viên"}
                          </Badge>
                        )}

                        {/* Moderation status badge */}
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

                    {/* Post Content */}
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => setActivePost(post)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setActivePost(post);
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

                    {/* 6. Action Bar & Footer */}
                    <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)]/50 text-xs text-[var(--text-secondary)]">
                      <div className="flex items-center gap-2 sm:gap-4">
                        {/* Open comments */}
                        <button
                          type="button"
                          onClick={() => setActivePost(post)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
                        >
                          <Icon name="chat" size="0.95rem" />
                          <span>
                            {copy("community.comments.count", {
                              count: formatLocaleNumber(language, post.comment_count)
                            })}
                          </span>
                        </button>

                        {/* Quick reaction */}
                        <button
                          type="button"
                          onClick={() => handleQuickReaction(post, "helpful")}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] transition"
                          title={
                            consentGranted
                              ? isEn
                                ? "Send supportive reaction"
                                : "Gửi phản hồi tích cực"
                              : copy("community.reaction.joinToReact")
                          }
                        >
                          <span aria-hidden="true">👍</span>
                          <span>
                            {copy("community.reactions.count", {
                              count: formatLocaleNumber(language, post.reaction_count)
                            })}
                          </span>
                        </button>
                      </div>

                      {/* Report / Mute Actions */}
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setReportTarget({ id: post.id, title: post.title })}
                          className="px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--status-danger-text)] transition rounded"
                          title={copy("community.report.post")}
                        >
                          {copy("community.report.post")}
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleHidePost(post.id)}
                          className="px-2 py-1 text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition rounded"
                          title={isEn ? "Hide post from feed" : "Ẩn bài viết khỏi bảng tin"}
                        >
                          {isEn ? "Hide" : "Ẩn bài"}
                        </button>
                      </div>
                    </div>
                  </SurfaceCard>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Compose Dialog (Modal) */}
      <Modal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        title={copy("community.compose.title")}
        description={
          isEn
            ? "Your post will be screened by AI to ensure patient safety and no illegal prescribing."
            : "Bài viết sẽ được AI rà soát tự động để đảm bảo an toàn y tế và không chứa đơn thuốc chỉ định."
        }
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
        <div className="space-y-4">
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
            placeholder={
              isEn
                ? "Enter a clear title for your experience or inquiry"
                : "Nhập tiêu đề rõ ràng cho chia sẻ hoặc câu hỏi của bạn"
            }
          />

          <Textarea
            label={copy("community.compose.bodyLabel")}
            value={composeBody}
            onChange={(e) => setComposeBody(e.target.value)}
            rows={5}
            maxLength={5000}
            placeholder={
              isEn
                ? "Describe your context, questions or insights. Please do not provide medical prescriptions or disclose personal identification details."
                : "Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm của bạn. Vui lòng không tự ý kê đơn thuốc hoặc tiết lộ thông tin định danh cá nhân."
            }
          />

          <div className="rounded-lg bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-secondary)] space-y-1">
            <p className="font-semibold text-[var(--text-primary)]">
              {isEn ? "Safety Guidelines:" : "Quy tắc an toàn:"}
            </p>
            <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
              <li>
                {isEn
                  ? "Do not post personal identification details (phone, email, full names)."
                  : "Không đăng tải thông tin định danh cá nhân (số điện thoại, email, họ tên đầy đủ)."}
              </li>
              <li>
                {isEn
                  ? "Do not offer clinical diagnosis or instruct others on medication dosages."
                  : "Không chẩn đoán thay bác sĩ hoặc hướng dẫn liều dùng thuốc cho người khác."}
              </li>
            </ul>
          </div>

          {composeError ? (
            <p className="text-xs font-semibold text-[var(--status-danger-text)] rounded bg-[var(--status-danger-bg)] p-2.5 border border-[color:var(--status-danger-border)]">
              {composeError}
            </p>
          ) : null}
        </div>
      </Modal>

      {/* Report Content Modal */}
      {reportTarget ? (
        <Modal
          open
          onClose={() => setReportTarget(null)}
          title={copy("community.report.post")}
          description={`"${reportTarget.title}"`}
          size="sm"
          footer={
            <>
              <Button variant="ghost" size="sm" onClick={() => setReportTarget(null)}>
                {copy("community.compose.cancel")}
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={submitReport}
                disabled={reporting}
                loading={reporting}
              >
                {isEn ? "Submit Report" : "Gửi báo cáo"}
              </Button>
            </>
          }
        >
          <div className="space-y-3">
            <p className="text-xs text-[var(--text-secondary)]">
              {isEn
                ? "Please select the primary reason for reporting this post to the clinical moderation team:"
                : "Vui lòng chọn lý do báo cáo bài viết này tới đội ngũ kiểm duyệt:"}
            </p>
            <Select
              label={isEn ? "Report Reason" : "Lý do báo cáo"}
              value={reportReason}
              onChange={(e) => setReportReason(e.target.value)}
            >
              <option value="misinformation">
                {isEn ? "Medical Misinformation" : "Thông tin sai lệch y tế"}
              </option>
              <option value="unauthorized_prescribing">
                {isEn ? "Unauthorized Drug Prescribing" : "Kê đơn thuốc trái phép"}
              </option>
              <option value="pii_disclosure">
                {isEn ? "Personal Identification (PII) Disclosure" : "Tiết lộ thông tin cá nhân"}
              </option>
              <option value="harassment_spam">
                {isEn ? "Harassment or Spam" : "Nội dung quấy rối hoặc spam"}
              </option>
            </Select>
          </div>
        </Modal>
      ) : null}

      {/* Privacy & Zero-PII Policy Modal */}
      {privacyModalOpen ? (
        <Modal
          open
          onClose={() => setPrivacyModalOpen(false)}
          title={isEn ? "Community Privacy & Moderation Policy" : "Chính sách kiểm duyệt & Quyền riêng tư"}
          size="md"
          footer={
            <Button variant="primary" size="sm" onClick={() => setPrivacyModalOpen(false)}>
              {copy("community.dialog.close")}
            </Button>
          }
        >
          <div className="space-y-3 text-xs leading-relaxed text-[var(--text-secondary)]">
            <p className="font-semibold text-sm text-[var(--text-primary)]">
              {isEn ? "Zero-PII Isolation Standard" : "Tiêu chuẩn cách ly Zero-PII"}
            </p>
            <p>
              {isEn
                ? "Your personal health records (PHR), prescriptions, and clinical chat consultations are completely isolated from your community handle. Community posts and comments contain zero health records unless explicitly shared by you in text."
                : "Hồ sơ sức khỏe cá nhân (PHR), đơn thuốc và các cuộc trò chuyện tư vấn của bạn được cách ly hoàn toàn khỏi tài khoản cộng đồng. Dữ liệu y tế riêng tư không bao giờ bị liên kết tự động."}
            </p>
            <p className="font-semibold text-sm text-[var(--text-primary)] pt-1">
              {isEn ? "Automated Safety Gate" : "Kiểm duyệt an toàn tự động"}
            </p>
            <p>
              {isEn
                ? "Every post and comment is screened by the CLARA Safety Engine before publishing. Content containing prohibited medical prescriptions, harmful advice, or private personal data fails closed and cannot be published."
                : "Toàn bộ bài viết và bình luận đều được rà soát qua cổng kiểm duyệt an toàn của CLARA trước khi xuất bản. Nội dung vi phạm quy định kê đơn hoặc chứa thông tin cá nhân nhạy cảm sẽ bị chặn xuất bản."}
            </p>
          </div>
        </Modal>
      ) : null}

      {/* Post Detail Dialog (Comments & Interactions) */}
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
