import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/lib/http-client";
import {
  SocialUnavailableError,
  isSocialModerationBlock,
  isClaraOfficial,
  getSocialErrorMessage,
  getSocialConsent,
  grantSocialConsent,
  revokeSocialConsent,
  getMyProfile,
  updateMyProfile,
  listCommunities,
  joinCommunity,
  leaveCommunity,
  getFeed,
  getCommunityPosts,
  searchPosts,
  getPost,
  createPost,
  deletePost,
  getComments,
  addComment,
  deleteComment,
  toggleReaction,
  addReaction,
  toggleBookmark,
  getBookmarks,
  getMyBookmarks,
  reportContent,
  listReports,
  actOnReport,
  type SocialProfile,
  type SocialCommunity,
  type SocialPost,
  type SocialComment,
  type SocialReaction,
  type SocialBookmark,
  type SocialReport,
  type PostFilters,
  type SocialConsentStatus,
  type ReactionKind,
} from "./social";

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe("Social Domain Interfaces & Types", () => {
  it("verifies SocialPost interface has all required fields", () => {
    const post: SocialPost = {
      id: 101,
      community_id: 1,
      community_name: "Tim mạch & Huyết áp",
      author_handle: "bs_alice",
      author_display_name: "BS. Alice",
      is_verified_clinician: true,
      title: "Chỉ số huyết áp chuẩn",
      body: "Huyết áp tâm thu dưới 120 là mức tối ưu.",
      moderation_status: "approved",
      comment_count: 3,
      reaction_count: 12,
      user_reaction: "helpful",
      is_bookmarked: true,
      reactions_breakdown: { helpful: 10, thanks: 2 },
      created_at: "2026-08-25T08:00:00Z",
      updated_at: "2026-08-25T08:05:00Z",
      tags: ["cardio", "tips"],
    };

    expect(post.id).toBe(101);
    expect(post.community_id).toBe(1);
    expect(post.community_name).toBe("Tim mạch & Huyết áp");
    expect(post.author_handle).toBe("bs_alice");
    expect(post.author_display_name).toBe("BS. Alice");
    expect(post.is_verified_clinician).toBe(true);
    expect(post.title).toBe("Chỉ số huyết áp chuẩn");
    expect(post.body).toBe("Huyết áp tâm thu dưới 120 là mức tối ưu.");
    expect(post.moderation_status).toBe("approved");
    expect(post.comment_count).toBe(3);
    expect(post.reaction_count).toBe(12);
    expect(post.user_reaction).toBe("helpful");
    expect(post.is_bookmarked).toBe(true);
    expect(post.reactions_breakdown).toEqual({ helpful: 10, thanks: 2 });
    expect(post.created_at).toBe("2026-08-25T08:00:00Z");
    expect(post.updated_at).toBe("2026-08-25T08:05:00Z");
    expect(post.tags).toEqual(["cardio", "tips"]);
  });

  it("verifies SocialComment interface has all required fields", () => {
    const comment: SocialComment = {
      id: 201,
      post_id: 101,
      parent_id: 100,
      author_handle: "nguyen_a",
      author_display_name: "Nguyen Van A",
      is_verified_clinician: false,
      body: "Cảm ơn bác sĩ nhiều.",
      moderation_status: "approved",
      created_at: "2026-08-25T08:30:00Z",
      updated_at: "2026-08-25T08:31:00Z",
    };

    expect(comment.id).toBe(201);
    expect(comment.post_id).toBe(101);
    expect(comment.parent_id).toBe(100);
    expect(comment.author_handle).toBe("nguyen_a");
    expect(comment.author_display_name).toBe("Nguyen Van A");
    expect(comment.is_verified_clinician).toBe(false);
    expect(comment.body).toBe("Cảm ơn bác sĩ nhiều.");
    expect(comment.moderation_status).toBe("approved");
    expect(comment.created_at).toBe("2026-08-25T08:30:00Z");
    expect(comment.updated_at).toBe("2026-08-25T08:31:00Z");
  });

  it("verifies SocialProfile, SocialCommunity, SocialReaction, SocialBookmark, SocialReport, PostFilters, SocialConsentStatus", () => {
    const profile: SocialProfile = {
      handle: "clara_user",
      display_name: "User One",
      bio: "Health enthusiast",
      role_badge: "clinician",
      is_verified_clinician: true,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    };
    expect(profile.handle).toBe("clara_user");
    expect(profile.status).toBe("active");

    const community: SocialCommunity = {
      id: 1,
      slug: "cardiology",
      name: "Tim mạch & Huyết áp",
      description: "Trao đổi về sức khỏe tim mạch",
      member_count: 150,
      joined: true,
      is_curated: true,
      created_at: "2026-01-01T00:00:00Z",
    };
    expect(community.name).toBe("Tim mạch & Huyết áp");
    expect(community.is_curated).toBe(true);

    const reactionKind: ReactionKind = "helpful";
    const reaction: SocialReaction = {
      id: 1,
      post_id: 101,
      user_id: 42,
      kind: reactionKind,
      created_at: "2026-08-25T08:35:00Z",
    };
    expect(reaction.kind).toBe("helpful");

    const bookmark: SocialBookmark = {
      id: 5,
      user_id: 42,
      post_id: 101,
      created_at: "2026-08-25T08:40:00Z",
    };
    expect(bookmark.post_id).toBe(101);

    const report: SocialReport = {
      id: 99,
      reporter_id: 42,
      target_type: "post",
      target_id: 101,
      reason: "misinformation",
      detail: "Không đúng thông tin hướng dẫn của Bộ Y tế",
      status: "open",
      created_at: "2026-08-25T08:50:00Z",
      resolved_at: "2026-08-25T09:00:00Z",
    };
    expect(report.status).toBe("open");
    expect(report.resolved_at).toBe("2026-08-25T09:00:00Z");

    const filters: PostFilters = {
      community_id: 1,
      q: "huyết áp",
      author_role: "verified",
      limit: 20,
      offset: 0,
    };
    expect(filters.author_role).toBe("verified");

    const consentStatus: SocialConsentStatus = {
      consent_type: "social_participation_v1",
      granted: true,
    };
    expect(consentStatus.granted).toBe(true);
  });
});

describe("Utility Classifiers & Error Handling", () => {
  describe("SocialUnavailableError", () => {
    it("is a named Error subclass with social_unavailable message", () => {
      const err = new SocialUnavailableError();
      expect(err).toBeInstanceOf(Error);
      expect(err.name).toBe("SocialUnavailableError");
      expect(err.message).toBe("social_unavailable");
    });
  });

  describe("isSocialModerationBlock", () => {
    it("is true for a 422 error object with response.status or direct status", () => {
      expect(isSocialModerationBlock({ response: { status: 422 } })).toBe(true);
      expect(isSocialModerationBlock({ status: 422 })).toBe(true);
    });

    it("is false for other HTTP statuses", () => {
      expect(isSocialModerationBlock({ response: { status: 404 } })).toBe(false);
      expect(isSocialModerationBlock({ response: { status: 500 } })).toBe(false);
      expect(isSocialModerationBlock({ response: { status: 200 } })).toBe(false);
      expect(isSocialModerationBlock({ status: 400 })).toBe(false);
    });

    it("is false for non-error shapes", () => {
      expect(isSocialModerationBlock(new Error("boom"))).toBe(false);
      expect(isSocialModerationBlock(null)).toBe(false);
      expect(isSocialModerationBlock(undefined)).toBe(false);
      expect(isSocialModerationBlock("nope")).toBe(false);
    });
  });

  describe("isClaraOfficial", () => {
    it("recognizes official, clinician and moderator prefixes (case insensitive)", () => {
      expect(isClaraOfficial("clara_assistant")).toBe(true);
      expect(isClaraOfficial("CLARA_OFFICIAL")).toBe(true);
      expect(isClaraOfficial("dr_john")).toBe(true);
      expect(isClaraOfficial("bs_nguyen")).toBe(true);
      expect(isClaraOfficial("bacsi_hoa")).toBe(true);
      expect(isClaraOfficial("duocsi_phuc")).toBe(true);
      expect(isClaraOfficial("expert_cardio")).toBe(true);
      expect(isClaraOfficial("mod_support")).toBe(true);
      expect(isClaraOfficial("moh_official_account")).toBe(true);
    });

    it("returns false for regular peer handles or empty strings", () => {
      expect(isClaraOfficial("user123")).toBe(false);
      expect(isClaraOfficial("nguyen_van_a")).toBe(false);
      expect(isClaraOfficial("patient_peer")).toBe(false);
      expect(isClaraOfficial("")).toBe(false);
    });
  });

  describe("getSocialErrorMessage", () => {
    it("extracts detail message from response error if available", () => {
      const err = { response: { data: { detail: "Nội dung không hợp lệ." } } };
      expect(getSocialErrorMessage(err, "Fallback")).toBe("Nội dung không hợp lệ.");
    });

    it("returns fallback message when detail is missing or whitespace", () => {
      expect(getSocialErrorMessage({}, "Fallback")).toBe("Fallback");
      expect(getSocialErrorMessage({ response: { data: { detail: "  " } } }, "Fallback")).toBe("Fallback");
      expect(getSocialErrorMessage(new Error("Network Error"), "Fallback")).toBe("Fallback");
    });
  });
});

describe("Social API Client Functions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Consent operations", () => {
    it("getSocialConsent calls GET /social/consent", async () => {
      const mockConsent: SocialConsentStatus = { consent_type: "social_participation_v1", granted: true };
      mockApi.get.mockResolvedValueOnce({ data: mockConsent });

      const res = await getSocialConsent();
      expect(mockApi.get).toHaveBeenCalledWith("/social/consent");
      expect(res).toEqual(mockConsent);
    });

    it("grantSocialConsent calls POST /social/consent with empty object", async () => {
      const mockConsent: SocialConsentStatus = { consent_type: "social_participation_v1", granted: true };
      mockApi.post.mockResolvedValueOnce({ data: mockConsent });

      const res = await grantSocialConsent();
      expect(mockApi.post).toHaveBeenCalledWith("/social/consent", {});
      expect(res).toEqual(mockConsent);
    });

    it("revokeSocialConsent calls DELETE /social/consent", async () => {
      const mockConsent: SocialConsentStatus = { consent_type: "social_participation_v1", granted: false };
      mockApi.delete.mockResolvedValueOnce({ data: mockConsent });

      const res = await revokeSocialConsent();
      expect(mockApi.delete).toHaveBeenCalledWith("/social/consent");
      expect(res).toEqual(mockConsent);
    });
  });

  describe("Profile operations", () => {
    it("getMyProfile calls GET /social/me/profile", async () => {
      const profile: SocialProfile = {
        handle: "clara_me",
        display_name: "Dr. Clara",
        bio: "Medical advisor",
        role_badge: "clinician",
        is_verified_clinician: true,
      };
      mockApi.get.mockResolvedValueOnce({ data: profile });

      const res = await getMyProfile();
      expect(mockApi.get).toHaveBeenCalledWith("/social/me/profile");
      expect(res).toEqual(profile);
    });

    it("updateMyProfile calls PATCH /social/me/profile with payload", async () => {
      const updated: SocialProfile = {
        handle: "clara_me",
        display_name: "Dr. Clara Updated",
        bio: "New bio",
        role_badge: "clinician",
        is_verified_clinician: true,
      };
      mockApi.patch.mockResolvedValueOnce({ data: updated });

      const res = await updateMyProfile({ display_name: "Dr. Clara Updated", bio: "New bio" });
      expect(mockApi.patch).toHaveBeenCalledWith("/social/me/profile", {
        display_name: "Dr. Clara Updated",
        bio: "New bio",
      });
      expect(res).toEqual(updated);
    });
  });

  describe("Community operations", () => {
    it("listCommunities calls GET /social/communities and handles empty or non-array data", async () => {
      const communities: SocialCommunity[] = [
        { id: 1, slug: "general", name: "Sức khỏe chung", description: "Mô tả", member_count: 50, joined: true },
      ];
      mockApi.get.mockResolvedValueOnce({ data: communities });

      const res = await listCommunities();
      expect(mockApi.get).toHaveBeenCalledWith("/social/communities");
      expect(res).toEqual(communities);

      mockApi.get.mockResolvedValueOnce({ data: null });
      const emptyRes = await listCommunities();
      expect(emptyRes).toEqual([]);
    });

    it("joinCommunity calls POST /social/communities/:id/join", async () => {
      const joinedComm: SocialCommunity = {
        id: 1,
        slug: "general",
        name: "Sức khỏe chung",
        description: "Mô tả",
        member_count: 51,
        joined: true,
      };
      mockApi.post.mockResolvedValueOnce({ data: joinedComm });

      const res = await joinCommunity(1);
      expect(mockApi.post).toHaveBeenCalledWith("/social/communities/1/join", {});
      expect(res).toEqual(joinedComm);
    });

    it("leaveCommunity calls POST /social/communities/:id/leave", async () => {
      const leftComm: SocialCommunity = {
        id: 1,
        slug: "general",
        name: "Sức khỏe chung",
        description: "Mô tả",
        member_count: 50,
        joined: false,
      };
      mockApi.post.mockResolvedValueOnce({ data: leftComm });

      const res = await leaveCommunity(1);
      expect(mockApi.post).toHaveBeenCalledWith("/social/communities/1/leave", {});
      expect(res).toEqual(leftComm);
    });
  });

  describe("Feed & Search operations", () => {
    it("getFeed calls GET /social/feed with PostFilters object", async () => {
      const posts: SocialPost[] = [
        {
          id: 1,
          community_id: 2,
          community_name: "Nhi khoa",
          author_handle: "peer1",
          author_display_name: "Peer One",
          is_verified_clinician: false,
          title: "Bài viết 1",
          body: "Nội dung bài viết",
          comment_count: 0,
          reaction_count: 2,
          created_at: "2026-08-25T00:00:00Z",
        },
      ];
      mockApi.get.mockResolvedValueOnce({ data: posts });

      const filters: PostFilters = { community_id: 2, author_role: "verified", limit: 15, offset: 5 };
      const res = await getFeed(filters);
      expect(mockApi.get).toHaveBeenCalledWith("/social/feed", { params: filters });
      expect(res).toEqual(posts);
    });

    it("getFeed supports legacy limit and offset numbers and handles default undefined params", async () => {
      mockApi.get.mockResolvedValueOnce({ data: [] });
      await getFeed(10, 20);
      expect(mockApi.get).toHaveBeenCalledWith("/social/feed", { params: { limit: 10, offset: 20 } });

      mockApi.get.mockResolvedValueOnce({ data: null });
      const resDefault = await getFeed();
      expect(mockApi.get).toHaveBeenCalledWith("/social/feed", { params: undefined });
      expect(resDefault).toEqual([]);
    });

    it("getCommunityPosts calls GET /social/communities/:id/posts", async () => {
      mockApi.get.mockResolvedValueOnce({ data: [] });
      await getCommunityPosts(3, 10, 5);
      expect(mockApi.get).toHaveBeenCalledWith("/social/communities/3/posts", {
        params: { limit: 10, offset: 5 },
      });
    });

    it("searchPosts calls GET /social/posts/search with query and params", async () => {
      const posts: SocialPost[] = [
        {
          id: 2,
          community_id: 1,
          author_handle: "peer2",
          title: "Tìm kiếm thuốc",
          body: "Cách dùng paracetamol an toàn",
          comment_count: 1,
          reaction_count: 5,
          created_at: "2026-08-25T00:00:00Z",
        },
      ];
      mockApi.get.mockResolvedValueOnce({ data: posts });

      const res = await searchPosts("paracetamol", { community_id: 1, limit: 10 });
      expect(mockApi.get).toHaveBeenCalledWith("/social/posts/search", {
        params: { q: "paracetamol", community_id: 1, limit: 10 },
      });
      expect(res).toEqual(posts);
    });
  });

  describe("Post CRUD & Bookmarking", () => {
    it("getPost calls GET /social/posts/:id", async () => {
      const post: SocialPost = {
        id: 10,
        community_id: 1,
        author_handle: "bs_duc",
        title: "Dinh dưỡng người cao tuổi",
        body: "Bổ sung canxi và vitamin D.",
        comment_count: 2,
        reaction_count: 8,
        created_at: "2026-08-25T00:00:00Z",
      };
      mockApi.get.mockResolvedValueOnce({ data: post });

      const res = await getPost(10);
      expect(mockApi.get).toHaveBeenCalledWith("/social/posts/10");
      expect(res).toEqual(post);
    });

    it("createPost calls POST /social/posts with snake_case community_id and optional tags", async () => {
      const newPost: SocialPost = {
        id: 11,
        community_id: 3,
        author_handle: "me",
        title: "Tập thể dục buổi sáng",
        body: "Đi bộ 30 phút mỗi ngày.",
        tags: ["exercise", "lifestyle"],
        comment_count: 0,
        reaction_count: 0,
        created_at: "2026-08-25T00:00:00Z",
      };
      mockApi.post.mockResolvedValueOnce({ data: newPost });

      const res = await createPost({
        community_id: 3,
        title: "Tập thể dục buổi sáng",
        body: "Đi bộ 30 phút mỗi ngày.",
        tags: ["exercise", "lifestyle"],
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts", {
        community_id: 3,
        title: "Tập thể dục buổi sáng",
        body: "Đi bộ 30 phút mỗi ngày.",
        tags: ["exercise", "lifestyle"],
      });
      expect(res).toEqual(newPost);
    });

    it("createPost supports camelCase communityId and default community_id 0", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { id: 12 } });

      await createPost({
        communityId: 4,
        title: "Title",
        body: "Body",
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts", {
        community_id: 4,
        title: "Title",
        body: "Body",
      });

      mockApi.post.mockResolvedValueOnce({ data: { id: 13 } });
      await createPost({
        title: "Title without community",
        body: "Body",
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts", {
        community_id: 0,
        title: "Title without community",
        body: "Body",
      });
    });

    it("deletePost calls DELETE /social/posts/:id", async () => {
      mockApi.delete.mockResolvedValueOnce({ data: { deleted: true } });

      const res = await deletePost(10);
      expect(mockApi.delete).toHaveBeenCalledWith("/social/posts/10");
      expect(res).toEqual({ deleted: true });
    });

    it("toggleBookmark calls POST /social/posts/:id/bookmark", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { bookmarked: true } });

      const res = await toggleBookmark(15);
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/15/bookmark", {});
      expect(res).toEqual({ bookmarked: true });
    });

    it("getBookmarks and getMyBookmarks call GET /social/me/bookmarks", async () => {
      const bookmarkedPosts: SocialPost[] = [
        {
          id: 15,
          community_id: 1,
          author_handle: "author1",
          title: "Bookmarked post",
          body: "Details",
          comment_count: 1,
          reaction_count: 4,
          is_bookmarked: true,
          created_at: "2026-08-25T00:00:00Z",
        },
      ];
      mockApi.get.mockResolvedValueOnce({ data: bookmarkedPosts });

      const res = await getBookmarks({ limit: 10, offset: 0 });
      expect(mockApi.get).toHaveBeenCalledWith("/social/me/bookmarks", { params: { limit: 10, offset: 0 } });
      expect(res).toEqual(bookmarkedPosts);

      mockApi.get.mockResolvedValueOnce({ data: bookmarkedPosts });
      const resMy = await getMyBookmarks({ limit: 5 });
      expect(mockApi.get).toHaveBeenCalledWith("/social/me/bookmarks", { params: { limit: 5 } });
      expect(resMy).toEqual(bookmarkedPosts);

      mockApi.get.mockResolvedValueOnce({ data: null });
      const emptyBookmarks = await getBookmarks();
      expect(emptyBookmarks).toEqual([]);
    });
  });

  describe("Comment operations", () => {
    it("getComments calls GET /social/posts/:id/comments with number or params object or defaults", async () => {
      const comments: SocialComment[] = [
        {
          id: 1,
          post_id: 10,
          parent_id: null,
          author_handle: "user_a",
          body: "Ý kiến rất hay",
          created_at: "2026-08-25T01:00:00Z",
        },
      ];
      mockApi.get.mockResolvedValueOnce({ data: comments });

      const res = await getComments(10, 20, 0);
      expect(mockApi.get).toHaveBeenCalledWith("/social/posts/10/comments", {
        params: { limit: 20, offset: 0 },
      });
      expect(res).toEqual(comments);

      mockApi.get.mockResolvedValueOnce({ data: comments });
      const resParams = await getComments(10, { limit: 10, offset: 5 });
      expect(mockApi.get).toHaveBeenCalledWith("/social/posts/10/comments", {
        params: { limit: 10, offset: 5 },
      });
      expect(resParams).toEqual(comments);

      mockApi.get.mockResolvedValueOnce({ data: null });
      const resDefault = await getComments(10);
      expect(mockApi.get).toHaveBeenCalledWith("/social/posts/10/comments", {
        params: { limit: 50, offset: 0 },
      });
      expect(resDefault).toEqual([]);
    });

    it("addComment supports payload object with parent_id", async () => {
      const createdComment: SocialComment = {
        id: 2,
        post_id: 10,
        parent_id: 1,
        author_handle: "user_b",
        body: "Đồng ý với bác",
        created_at: "2026-08-25T01:05:00Z",
      };
      mockApi.post.mockResolvedValueOnce({ data: createdComment });

      const res = await addComment(10, { body: "Đồng ý với bác", parent_id: 1 });
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/10/comments", {
        body: "Đồng ý với bác",
        parent_id: 1,
      });
      expect(res).toEqual(createdComment);
    });

    it("addComment supports legacy string payload and parentId arg", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { id: 3 } });

      await addComment(10, "Bình luận dạng text", 1);
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/10/comments", {
        body: "Bình luận dạng text",
        parent_id: 1,
      });

      mockApi.post.mockResolvedValueOnce({ data: { id: 4 } });
      await addComment(10, "Bình luận không có parent");
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/10/comments", {
        body: "Bình luận không có parent",
      });
    });

    it("deleteComment calls DELETE /social/comments/:id", async () => {
      mockApi.delete.mockResolvedValueOnce({ data: { deleted: true } });

      const res = await deleteComment(2);
      expect(mockApi.delete).toHaveBeenCalledWith("/social/comments/2");
      expect(res).toEqual({ deleted: true });
    });
  });

  describe("Reactions & Reports", () => {
    it("toggleReaction and addReaction call POST /social/posts/:id/reactions", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { ok: true } });

      const res = await toggleReaction(10, "thanks");
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/10/reactions", { kind: "thanks" });
      expect(res).toEqual({ ok: true });

      mockApi.post.mockResolvedValueOnce({ data: { ok: true } });
      await addReaction(10, "relate");
      expect(mockApi.post).toHaveBeenCalledWith("/social/posts/10/reactions", { kind: "relate" });
    });

    it("reportContent calls POST /social/reports with payload object", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { reported: true } });

      const res = await reportContent({
        target_type: "post",
        target_id: 10,
        reason: "spam",
        detail: "Quảng cáo thực phẩm chức năng sai quy định",
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/reports", {
        target_type: "post",
        target_id: 10,
        reason: "spam",
        detail: "Quảng cáo thực phẩm chức năng sai quy định",
      });
      expect(res).toEqual({ reported: true });
    });

    it("reportContent supports camelCase fallback parameters and default values", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { reported: true } });

      await reportContent({
        targetType: "comment",
        targetId: 5,
        reason: "harassment",
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/reports", {
        target_type: "comment",
        target_id: 5,
        reason: "harassment",
        detail: "harassment",
      });

      mockApi.post.mockResolvedValueOnce({ data: { reported: true } });
      await reportContent({
        reason: "other",
      });
      expect(mockApi.post).toHaveBeenCalledWith("/social/reports", {
        target_type: "post",
        target_id: 0,
        reason: "other",
        detail: "other",
      });
    });
  });

  describe("Admin Moderation Queue", () => {
    it("listReports calls GET /social/moderation/reports", async () => {
      const reports: SocialReport[] = [
        {
          id: 1,
          target_type: "post",
          target_id: 10,
          reason: "misinformation",
          status: "open",
          created_at: "2026-08-25T02:00:00Z",
        },
      ];
      mockApi.get.mockResolvedValueOnce({ data: reports });

      const res = await listReports();
      expect(mockApi.get).toHaveBeenCalledWith("/social/moderation/reports");
      expect(res).toEqual(reports);

      mockApi.get.mockResolvedValueOnce({ data: null });
      const emptyReports = await listReports();
      expect(emptyReports).toEqual([]);
    });

    it("actOnReport calls POST /social/moderation/reports/:id/action", async () => {
      mockApi.post.mockResolvedValueOnce({ data: { ok: true } });

      await actOnReport(1, "remove");
      expect(mockApi.post).toHaveBeenCalledWith("/social/moderation/reports/1/action", {
        action: "remove",
      });
    });
  });

  describe("Guarded 404 & Error Handling across methods", () => {
    it("translates response 404 errors into SocialUnavailableError", async () => {
      const notFoundError = { response: { status: 404 } };
      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getSocialConsent()).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(grantSocialConsent()).rejects.toThrow(SocialUnavailableError);

      mockApi.delete.mockRejectedValueOnce(notFoundError);
      await expect(revokeSocialConsent()).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getMyProfile()).rejects.toThrow(SocialUnavailableError);

      mockApi.patch.mockRejectedValueOnce(notFoundError);
      await expect(updateMyProfile({ bio: "test" })).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(listCommunities()).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(joinCommunity(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(leaveCommunity(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getFeed()).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getCommunityPosts(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(searchPosts("query")).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getPost(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(createPost({ title: "T", body: "B" })).rejects.toThrow(SocialUnavailableError);

      mockApi.delete.mockRejectedValueOnce(notFoundError);
      await expect(deletePost(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getComments(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(addComment(1, "comment")).rejects.toThrow(SocialUnavailableError);

      mockApi.delete.mockRejectedValueOnce(notFoundError);
      await expect(deleteComment(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(toggleReaction(1, "helpful")).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(toggleBookmark(1)).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getBookmarks()).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(reportContent({ reason: "spam" })).rejects.toThrow(SocialUnavailableError);

      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(listReports()).rejects.toThrow(SocialUnavailableError);

      mockApi.post.mockRejectedValueOnce(notFoundError);
      await expect(actOnReport(1, "dismiss")).rejects.toThrow(SocialUnavailableError);
    });

    it("translates direct status 404 errors into SocialUnavailableError", async () => {
      const notFoundError = { status: 404 };
      mockApi.get.mockRejectedValueOnce(notFoundError);
      await expect(getFeed()).rejects.toThrow(SocialUnavailableError);
    });

    it("rethrows non-404 errors as-is", async () => {
      const serverError = new Error("500 Internal Server Error");
      mockApi.get.mockRejectedValueOnce(serverError);
      await expect(getFeed()).rejects.toThrow("500 Internal Server Error");

      const validationError = { response: { status: 422, data: { detail: "Blocked" } } };
      mockApi.post.mockRejectedValueOnce(validationError);
      await expect(createPost({ title: "T", body: "B" })).rejects.toEqual(validationError);
    });
  });
});
