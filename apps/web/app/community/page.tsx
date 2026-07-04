"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import PostDetailDialog from "@/components/community/post-detail-dialog";
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

const DISCLAIMER =
  "Cộng đồng CLARA là nơi chia sẻ kinh nghiệm và hỗ trợ lẫn nhau. Đây KHÔNG phải tư vấn y tế: " +
  "không kê đơn, chẩn đoán hay chỉ định liều dùng. Nội dung được kiểm duyệt để giữ an toàn. " +
  "Trường hợp khẩn cấp, hãy gọi 115.";

export default function CommunityPage() {
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
        setError("Không thể tải cộng đồng lúc này. Vui lòng thử lại.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onGrantConsent = useCallback(async () => {
    try {
      await grantSocialConsent();
      setConsentGranted(true);
    } catch {
      setError("Không thể ghi nhận đồng ý. Vui lòng thử lại.");
    }
  }, []);

  const onJoin = useCallback(async (id: number) => {
    try {
      await joinCommunity(id);
      setCommunities((prev) =>
        prev.map((c) => (c.id === id ? { ...c, joined: true, member_count: c.member_count + 1 } : c))
      );
    } catch {
      setError("Không thể tham gia cộng đồng. Vui lòng thử lại.");
    }
  }, []);

  const openCompose = useCallback(() => {
    setComposeError(null);
    setComposeTitle("");
    setComposeBody("");
    setComposeCommunity(communities[0]?.id ?? null);
    setComposeOpen(true);
  }, [communities]);

  const submitPost = useCallback(async () => {
    if (composeCommunity == null) {
      setComposeError("Vui lòng chọn cộng đồng.");
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
        setComposeError(
          "Nội dung không phù hợp quy tắc cộng đồng (không kê đơn/chẩn đoán/liều dùng cá nhân) " +
            "hoặc có dấu hiệu khẩn cấp. Vui lòng chỉnh sửa."
        );
      } else {
        setComposeError("Không thể đăng bài. Vui lòng thử lại.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [composeCommunity, composeTitle, composeBody, load]);

  const canCompose = useMemo(
    () => consentGranted && communities.length > 0,
    [consentGranted, communities.length]
  );

  if (unavailable) {
    return (
      <PageShell title="Cộng đồng" description="Kết nối và chia sẻ cùng cộng đồng sức khỏe CLARA.">
        <div className="rounded-2xl border border-[var(--border-subtle)] p-8 text-center">
          <p className="text-lg font-semibold text-[var(--text-primary)]">Cộng đồng sắp ra mắt</p>
          <p className="mt-2 text-sm text-[var(--text-secondary)]">
            Tính năng cộng đồng sức khỏe đang được chuẩn bị và sẽ sớm mở.
          </p>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="Cộng đồng" description="Kết nối và chia sẻ cùng cộng đồng sức khỏe CLARA.">
      <div className="space-y-5">
        <div className="rounded-xl border border-amber-300/50 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-700/40 dark:bg-amber-950/30 dark:text-amber-200">
          {DISCLAIMER}
        </div>

        {error ? (
          <div className="rounded-xl border border-red-300/50 bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-200">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="text-sm text-[var(--text-secondary)]">Đang tải…</p>
        ) : (
          <>
            {!consentGranted ? (
              <div className="rounded-2xl border border-[var(--border-subtle)] p-5">
                <p className="font-semibold text-[var(--text-primary)]">Tham gia để đăng bài & bình luận</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">
                  Bạn vẫn có thể đọc bài. Đồng ý quy tắc cộng đồng để tham gia chia sẻ.
                </p>
                <button
                  type="button"
                  onClick={onGrantConsent}
                  className="mt-3 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white"
                >
                  Tôi đồng ý tham gia
                </button>
              </div>
            ) : (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={openCompose}
                  disabled={!canCompose}
                  className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  Đăng bài
                </button>
              </div>
            )}

            {communities.length > 0 ? (
              <section>
                <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">Cộng đồng</h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {communities.map((c) => (
                    <div key={c.id} className="rounded-2xl border border-[var(--border-subtle)] p-4">
                      <p className="font-semibold text-[var(--text-primary)]">{c.name}</p>
                      <p className="mt-1 line-clamp-2 text-sm text-[var(--text-secondary)]">{c.description}</p>
                      <p className="mt-2 text-xs text-[var(--text-secondary)]">{c.member_count} thành viên</p>
                      <button
                        type="button"
                        onClick={() => onJoin(c.id)}
                        disabled={c.joined}
                        className="mt-3 w-full rounded-lg border border-[var(--border-subtle)] px-3 py-1.5 text-sm font-medium disabled:opacity-60"
                      >
                        {c.joined ? "Đã tham gia" : "Tham gia"}
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            <section>
              <h2 className="mb-3 text-lg font-semibold text-[var(--text-primary)]">Bảng tin</h2>
              {feed.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)]">
                  Chưa có bài viết. Hãy là người đầu tiên chia sẻ.
                </p>
              ) : (
                <div className="space-y-3">
                  {feed.map((post) => (
                    <article
                      key={post.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => setActivePost(post)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setActivePost(post);
                        }
                      }}
                      className="cursor-pointer rounded-2xl border border-[var(--border-subtle)] p-4 transition-colors hover:border-[var(--accent)]"
                    >
                      <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                        <span className="font-medium text-[var(--text-primary)]">@{post.author_handle}</span>
                        <span>·</span>
                        <span>{new Date(post.created_at).toLocaleDateString("vi-VN")}</span>
                      </div>
                      <h3 className="mt-2 font-semibold text-[var(--text-primary)]">{post.title}</h3>
                      <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-sm text-[var(--text-secondary)]">{post.body}</p>
                      <div className="mt-3 flex gap-4 text-xs text-[var(--text-secondary)]">
                        <span>{post.comment_count} bình luận</span>
                        <span>{post.reaction_count} phản hồi tích cực</span>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

      {composeOpen ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
          <div className="w-full max-w-lg rounded-2xl bg-[var(--surface)] p-5 shadow-xl">
            <h3 className="text-lg font-semibold text-[var(--text-primary)]">Chia sẻ với cộng đồng</h3>
            <div className="mt-4 space-y-3">
              <label className="block text-sm">
                <span className="text-[var(--text-secondary)]">Cộng đồng</span>
                <select
                  value={composeCommunity ?? ""}
                  onChange={(e) => setComposeCommunity(Number(e.target.value))}
                  className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2"
                >
                  {communities.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="text-[var(--text-secondary)]">Tiêu đề</span>
                <input
                  value={composeTitle}
                  onChange={(e) => setComposeTitle(e.target.value)}
                  maxLength={200}
                  className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2"
                />
              </label>
              <label className="block text-sm">
                <span className="text-[var(--text-secondary)]">Nội dung</span>
                <textarea
                  value={composeBody}
                  onChange={(e) => setComposeBody(e.target.value)}
                  rows={5}
                  maxLength={5000}
                  className="mt-1 w-full rounded-lg border border-[var(--border-subtle)] bg-transparent px-3 py-2"
                />
              </label>
              {composeError ? <p className="text-sm text-red-600 dark:text-red-400">{composeError}</p> : null}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setComposeOpen(false)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-[var(--text-secondary)]"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={submitPost}
                disabled={submitting || !composeTitle.trim() || !composeBody.trim()}
                className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {submitting ? "Đang đăng…" : "Đăng bài"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

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
