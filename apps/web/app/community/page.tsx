"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import Button from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
  ProfileDrawer,
  ConsentGateModal,
} from "@/components/community";
import { formatLocaleNumber, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { useShellMode } from "@/components/shell/shell-mode-provider";
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
  getMyBookmarks,
  createPost,
  deletePost,
  addReaction,
  toggleBookmark,
  reportContent,
  SocialUnavailableError,
  isClaraOfficial,
} from "@/lib/social";

// Curated fallback topics for Vietnamese health community if API returns empty
const CURATED_DEFAULT_TOPICS: SocialCommunity[] = [
  {
    id: 1,
    slug: "tim-mach-huyet-ap",
    name: "Tim mạch & Huyết áp",
    description: "Kinh nghiệm theo dõi chỉ số huyết áp, lối sống bảo vệ tim mạch và chế độ ăn giảm muối.",
    member_count: 1240,
    joined: false,
  },
  {
    id: 2,
    slug: "tieu-duong-noi-tiet",
    name: "Tiểu đường & Nội tiết",
    description: "Chia sẻ thực đơn chỉ số đường huyết thấp, quản lý đường huyết tại nhà và vận động hợp lý.",
    member_count: 980,
    joined: false,
  },
  {
    id: 3,
    slug: "suc-khoe-tam-tri",
    name: "Sức khỏe Tâm trí",
    description: "Giải tỏa căng thẳng, giấc ngủ ngon, thiền định chánh niệm và hỗ trợ sức khỏe tinh thần.",
    member_count: 1120,
    joined: false,
  },
  {
    id: 4,
    slug: "dinh-duong-van-dong",
    name: "Dinh dưỡng & Vận động",
    description: "Thói quen rèn luyện thể chất, bài tập dưỡng sinh, yoga phục hồi và chế độ ăn cân bằng.",
    member_count: 1560,
    joined: false,
  },
  {
    id: 5,
    slug: "cham-soc-nguoi-cao-tuoi",
    name: "Chăm sóc Người cao tuổi",
    description: "Phòng ngừa ngã, hỗ trợ vận động, chăm sóc bệnh lý mạn tính và kết nối yêu thương gia đình.",
    member_count: 890,
    joined: false,
  },
];

export default function CommunityPage() {
  const language = useUILanguage();
  const isEn = language === "en";
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language]
  );

  const { setMode } = useShellMode();
  useEffect(() => {
    setMode("explore");
  }, [setMode]);

  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [consentGranted, setConsentGranted] = useState(false);
  const [communities, setCommunities] = useState<SocialCommunity[]>([]);
  const [feed, setFeed] = useState<SocialPost[]>([]);
  const [bookmarkedPosts, setBookmarkedPosts] = useState<SocialPost[]>([]);

  // Filtering & Search
  const [selectedCommunityId, setSelectedCommunityId] = useState<number | "all">("all");
  const [authorFilter, setAuthorFilter] = useState<"all" | "official" | "peers" | "bookmarks">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals & Drawers
  const [composeOpen, setComposeOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [consentModalOpen, setConsentModalOpen] = useState(false);
  const [privacyModalOpen, setPrivacyModalOpen] = useState(false);
  const [activePost, setActivePost] = useState<SocialPost | null>(null);
  const [reportTarget, setReportTarget] = useState<{
    type: "post" | "comment";
    id: number;
    titleOrSnippet: string;
  } | null>(null);

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
      setCommunities(comm.length > 0 ? comm : CURATED_DEFAULT_TOPICS);
      setFeed(posts);

      // Attempt to load bookmarks if user has granted consent
      if (consent.granted) {
        try {
          const bookmarks = await getMyBookmarks();
          setBookmarkedPosts(bookmarks);
        } catch {
          // Non-blocking
        }
      }
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
      if (!consentGranted) {
        setConsentModalOpen(true);
        return;
      }
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
    [consentGranted, copy, isEn]
  );

  const openCompose = useCallback(() => {
    if (!consentGranted) {
      setConsentModalOpen(true);
      return;
    }
    setComposeOpen(true);
  }, [consentGranted]);

  const handleQuickReaction = useCallback(
    async (post: SocialPost, kind: ReactionKind = "helpful") => {
      if (!consentGranted) {
        setNotice(copy("community.reaction.joinToReact"));
        setConsentModalOpen(true);
        return;
      }
      try {
        await addReaction(post.id, kind);
        setFeed((prev) =>
          prev.map((p) =>
            p.id === post.id
              ? {
                  ...p,
                  reaction_count: p.reaction_count + 1,
                  user_reaction: kind,
                  reactions_breakdown: {
                    ...p.reactions_breakdown,
                    [kind]: (p.reactions_breakdown?.[kind] ?? 0) + 1,
                  },
                }
              : p
          )
        );
        setNotice(copy("community.reaction.sent"));
      } catch {
        setNotice(copy("community.reaction.error"));
      }
    },
    [consentGranted, copy]
  );

  const handleToggleBookmark = useCallback(
    async (post: SocialPost) => {
      if (!consentGranted) {
        setConsentModalOpen(true);
        return;
      }
      try {
        const res = await toggleBookmark(post.id);
        const nextBookmarked = res.bookmarked;
        setFeed((prev) =>
          prev.map((p) => (p.id === post.id ? { ...p, is_bookmarked: nextBookmarked } : p))
        );
        if (nextBookmarked) {
          setBookmarkedPosts((prev) => [
            { ...post, is_bookmarked: true },
            ...prev.filter((p) => p.id !== post.id),
          ]);
          setNotice(isEn ? "Post saved to bookmarks." : "Đã lưu bài viết.");
        } else {
          setBookmarkedPosts((prev) => prev.filter((p) => p.id !== post.id));
          setNotice(isEn ? "Post removed from bookmarks." : "Đã bỏ lưu bài viết.");
        }
      } catch {
        setNotice(isEn ? "Could not update bookmark." : "Không thể cập nhật đã lưu.");
      }
    },
    [consentGranted, isEn]
  );

  const handleDeletePost = useCallback(
    async (postId: number) => {
      try {
        await deletePost(postId);
        setFeed((prev) => prev.filter((p) => p.id !== postId));
        setBookmarkedPosts((prev) => prev.filter((p) => p.id !== postId));
        setNotice(isEn ? "Post deleted." : "Đã xóa bài viết.");
      } catch {
        setNotice(isEn ? "Failed to delete post." : "Không thể xóa bài viết.");
      }
    },
    [isEn]
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
    const sourcePosts = authorFilter === "bookmarks" ? bookmarkedPosts : feed;

    return sourcePosts.filter((post) => {
      if (hiddenPostIds.includes(post.id)) return false;
      if (selectedCommunityId !== "all" && post.community_id !== selectedCommunityId) {
        return false;
      }
      const isOfficial =
        typeof isClaraOfficial === "function"
          ? isClaraOfficial(post.author_handle) || Boolean(post.is_verified_clinician)
          : Boolean(post.is_verified_clinician);

      if (authorFilter === "official" && !isOfficial) {
        return false;
      }
      if (authorFilter === "peers" && isOfficial) {
        return false;
      }
      if (q) {
        const commName = communities.find((c) => c.id === post.community_id)?.name || "";
        const tags = Array.isArray(post.tags) ? post.tags.join(" ") : "";
        const text = `${post.title} ${post.body} ${post.author_handle} ${post.author_display_name || ""} ${commName} ${tags}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });
  }, [feed, bookmarkedPosts, hiddenPostIds, selectedCommunityId, authorFilter, searchQuery, communities]);

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
        {/* Header Action Bar: Omnisearch, Bookmarks, Profile, Compose Post */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-3.5 sm:p-4 rounded-[var(--radius-xl)] bg-[var(--surface-panel)] border border-[color:var(--shell-border)] shadow-xs">
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-sm font-bold text-[var(--text-primary)]">
              {isEn ? "Community Hub" : "Cộng đồng Sức khỏe CLARA"}
            </span>
            <Badge tone="brand" className="text-[10px] py-0.5 font-semibold">
              {isEn ? "Peer Support & Moderated" : "Chia sẻ & Đã kiểm duyệt"}
            </Badge>
          </div>

          <div className="flex flex-1 max-w-sm items-center relative">
            <div className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-[var(--text-muted)]">
              <Icon name="search" size="0.85rem" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isEn ? "Omnisearch community..." : "Tìm kiếm nhanh bài viết, tác giả, thẻ..."}
              className="block w-full pl-8 pr-7 py-1.5 bg-[var(--surface-muted)] border border-[color:var(--shell-border)] rounded-lg text-xs font-medium text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:ring-1 focus:ring-[var(--brand-500)] outline-none transition"
              data-testid="header-omnisearch-input"
            />
            {searchQuery ? (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute inset-y-0 right-0 pr-2 flex items-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                aria-label={isEn ? "Clear search" : "Xóa tìm kiếm"}
              >
                <Icon name="close" size="0.75rem" />
              </button>
            ) : null}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              variant={authorFilter === "bookmarks" ? "primary" : "ghost"}
              size="sm"
              onClick={() => setAuthorFilter(authorFilter === "bookmarks" ? "all" : "bookmarks")}
              className="text-xs font-semibold"
            >
              <Icon name="folder" size="0.85rem" className="mr-1" />
              <span>{isEn ? "Bookmarks" : "Bài viết đã lưu"}</span>
              {bookmarkedPosts.length > 0 ? (
                <span className="ml-1 text-[10px] px-1.5 py-0.2 rounded-full bg-[var(--surface-brand-soft)] text-[var(--text-brand)] font-bold">
                  {bookmarkedPosts.length}
                </span>
              ) : null}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setProfileOpen(true)}
              className="text-xs font-semibold"
            >
              <Icon name="user-card" size="0.85rem" className="mr-1" />
              <span>{isEn ? "My Profile" : "Hồ sơ cộng đồng"}</span>
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={openCompose}
              className="text-xs font-bold"
            >
              <Icon name="plus" size="0.85rem" className="mr-1" />
              <span>{isEn ? "Compose Post" : "Viết bài mới"}</span>
            </Button>
          </div>
        </div>

        {/* 1. Persistent Clinical Safety Notice Banner */}
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

        {/* 2. Multi-dimensional Topic & Author Role Navigation & Filter Bar */}
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

        {/* 3. Participation Action / Consent Prompt */}
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
              {isEn ? "Compose Post" : "Viết bài mới"}
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
              <span>
                {authorFilter === "bookmarks"
                  ? isEn
                    ? "Saved Bookmarks"
                    : "Bài viết đã lưu"
                  : copy("community.feed.heading")}
              </span>
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

          {/* 5. Loading Skeleton vs Finished Feed vs Empty State */}
          {loading ? (
            <div className="space-y-4 py-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 space-y-3 animate-pulse"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-[var(--surface-muted)]" />
                      <div className="space-y-1.5">
                        <div className="w-24 h-3 rounded bg-[var(--surface-muted)]" />
                        <div className="w-16 h-2.5 rounded bg-[var(--surface-muted)]" />
                      </div>
                    </div>
                    <div className="w-16 h-4 rounded bg-[var(--surface-muted)]" />
                  </div>
                  <div className="space-y-2">
                    <div className="w-3/4 h-5 rounded bg-[var(--surface-muted)]" />
                    <div className="w-full h-3.5 rounded bg-[var(--surface-muted)]" />
                    <div className="w-5/6 h-3.5 rounded bg-[var(--surface-muted)]" />
                  </div>
                  <div className="pt-2 flex items-center gap-4 border-t border-[color:var(--shell-border)]/40">
                    <div className="w-16 h-4 rounded bg-[var(--surface-muted)]" />
                    <div className="w-16 h-4 rounded bg-[var(--surface-muted)]" />
                  </div>
                </div>
              ))}
            </div>
          ) : filteredFeed.length === 0 ? (
            <EmptyState
              icon="groups"
              title={
                authorFilter === "bookmarks"
                  ? isEn
                    ? "No saved posts yet"
                    : "Chưa có bài viết đã lưu"
                  : copy("community.feed.empty")
              }
              description={
                authorFilter === "bookmarks"
                  ? isEn
                    ? "Bookmark useful posts by clicking the save button on any post card."
                    : "Lưu lại những bài viết bổ ích bằng cách nhấn nút Lưu trên từng bài viết."
                  : searchQuery || selectedCommunityId !== "all" || authorFilter !== "all"
                  ? isEn
                    ? "No posts matched your current filters. Try resetting search or selecting all topics."
                    : "Không tìm thấy bài viết nào phù hợp với bộ lọc. Hãy thử đặt lại tìm kiếm hoặc chọn tất cả chủ đề."
                  : isEn
                  ? "Be the first to share an experience or question with the community."
                  : "Hãy là người đầu tiên chia sẻ câu chuyện cùng cộng đồng."
              }
            >
              <div className="flex flex-col items-center gap-3 pt-2">
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {canCompose ? (
                    <Button variant="primary" size="sm" onClick={openCompose}>
                      <Icon name="plus" size="0.85rem" className="mr-1" />
                      <span>{isEn ? "Create First Post" : "Tạo bài viết đầu tiên"}</span>
                    </Button>
                  ) : null}
                  {searchQuery || selectedCommunityId !== "all" || authorFilter !== "all" ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setSearchQuery("");
                        setSelectedCommunityId("all");
                        setAuthorFilter("all");
                      }}
                    >
                      {isEn ? "Reset Filters" : "Đặt lại bộ lọc"}
                    </Button>
                  ) : null}
                </div>

                {/* Quick Topic Suggestions */}
                {communities.length > 0 && selectedCommunityId !== "all" ? (
                  <div className="pt-2 flex flex-wrap items-center justify-center gap-1.5 text-xs text-[var(--text-muted)]">
                    <span>{isEn ? "Suggested Topics:" : "Chủ đề gợi ý:"}</span>
                    {communities.slice(0, 3).map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setSelectedCommunityId(c.id)}
                        className="px-2.5 py-1 rounded-full bg-[var(--surface-muted)] text-[var(--text-primary)] hover:bg-[var(--surface-panel)] border border-[color:var(--shell-border)] cursor-pointer transition font-medium text-[11px]"
                      >
                        {c.name}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
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
                    onReaction={(p, kind) => handleQuickReaction(p, kind || "helpful")}
                    onToggleBookmark={handleToggleBookmark}
                    onReport={(p) =>
                      setReportTarget({
                        type: "post",
                        id: p.id,
                        titleOrSnippet: p.title,
                      })
                    }
                    onToggleHide={toggleHidePost}
                    onDelete={handleDeletePost}
                    canDelete={true}
                  />
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* 6. Composer Modal with Markdown Preview & Safety Box */}
      <ComposeModal
        open={composeOpen}
        onClose={() => setComposeOpen(false)}
        communities={communities}
        initialCommunityId={typeof selectedCommunityId === "number" ? selectedCommunityId : null}
        onPostCreated={load}
        createPostFn={createPost}
      />

      {/* 7. Post Detail & Threaded Comments Modal */}
      {activePost ? (
        <PostDetailDialog
          post={activePost}
          canParticipate={consentGranted}
          onClose={() => setActivePost(null)}
          onReactionAdded={(postId, kind) => {
            setFeed((prev) =>
              prev.map((p) =>
                p.id === postId
                  ? {
                      ...p,
                      reaction_count: p.reaction_count + 1,
                      user_reaction: kind,
                    }
                  : p
              )
            );
          }}
          onBookmarkToggled={(postId, bookmarked) => {
            setFeed((prev) =>
              prev.map((p) => (p.id === postId ? { ...p, is_bookmarked: bookmarked } : p))
            );
          }}
          onCommentAdded={(postId) => {
            setFeed((prev) =>
              prev.map((p) => (p.id === postId ? { ...p, comment_count: p.comment_count + 1 } : p))
            );
          }}
        />
      ) : null}

      {/* 8. Profile Drawer / Modal */}
      <ProfileDrawer
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        onProfileUpdated={() => {
          setNotice(isEn ? "Profile updated." : "Đã cập nhật hồ sơ.");
        }}
      />

      {/* 9. Participation Consent Gate Modal */}
      <ConsentGateModal
        open={consentModalOpen}
        onClose={() => setConsentModalOpen(false)}
        onConsentGranted={() => {
          setConsentGranted(true);
          setNotice(isEn ? "Community consent recorded." : "Đã đồng ý tham gia cộng đồng.");
        }}
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
    </PageShell>
  );
}
