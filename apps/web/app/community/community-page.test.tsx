import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CommunityPage from "./page";
import * as socialLib from "@/lib/social";

vi.mock("@/lib/social", () => {
  return {
    getSocialConsent: vi.fn(),
    grantSocialConsent: vi.fn(),
    revokeSocialConsent: vi.fn(),
    listCommunities: vi.fn(),
    joinCommunity: vi.fn(),
    leaveCommunity: vi.fn(),
    getFeed: vi.fn(),
    getCommunityPosts: vi.fn(),
    searchPosts: vi.fn(),
    getPost: vi.fn(),
    createPost: vi.fn(),
    deletePost: vi.fn(),
    getComments: vi.fn(),
    addComment: vi.fn(),
    deleteComment: vi.fn(),
    addReaction: vi.fn(),
    toggleReaction: vi.fn(),
    toggleBookmark: vi.fn(),
    getBookmarks: vi.fn(),
    getMyBookmarks: vi.fn(),
    getMyProfile: vi.fn(),
    updateMyProfile: vi.fn(),
    reportContent: vi.fn(),
    SocialUnavailableError: class SocialUnavailableError extends Error {
      constructor() {
        super("social_unavailable");
        this.name = "SocialUnavailableError";
      }
    },
    isSocialModerationBlock: vi.fn((err: unknown) => {
      return (err as { status?: number })?.status === 422 || (err as { response?: { status?: number } })?.response?.status === 422;
    }),
    isClaraOfficial: vi.fn((handle: string) => {
      if (!handle) return false;
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
    }),
  };
});

const MOCK_COMMUNITIES: socialLib.SocialCommunity[] = [
  {
    id: 1,
    slug: "suc-khoe-tong-quat",
    name: "Sức khỏe tổng quát",
    description: "Kinh nghiệm chăm sóc sức khỏe và lối sống lành mạnh.",
    member_count: 1420,
    joined: true,
  },
  {
    id: 2,
    slug: "tim-mach-huyet-ap",
    name: "Tim mạch & Huyết áp",
    description: "Thảo luận và chia sẻ kinh nghiệm kiểm soát huyết áp.",
    member_count: 850,
    joined: false,
  },
  {
    id: 3,
    slug: "tieu-duong-noi-tiet",
    name: "Tiểu đường & Nội tiết",
    description: "Chia sẻ chế độ ăn và theo dõi đường huyết.",
    member_count: 620,
    joined: false,
  },
];

const MOCK_FEED: socialLib.SocialPost[] = [
  {
    id: 101,
    community_id: 1,
    author_handle: "clara_official",
    author_display_name: "CLARA Bác sĩ Tư vấn",
    is_verified_clinician: true,
    title: "Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)",
    body: "Khi phát hiện méo miệng, yếu liệt tay chân hoặc nói khó, hãy gọi 115 ngay lập tức.",
    created_at: "2026-04-10T08:00:00Z",
    comment_count: 12,
    reaction_count: 48,
    is_bookmarked: false,
    reactions_breakdown: { helpful: 30, relate: 10, thanks: 8 },
    tags: ["capcuu", "dotquy"],
  },
  {
    id: 102,
    community_id: 2,
    author_handle: "nguyen_van_a",
    author_display_name: "Nguyễn Văn A",
    is_verified_clinician: false,
    title: "Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử",
    body: "Mỗi sáng mình đo lúc 7h trước khi ăn sáng và ghi vào LifeMap của CLARA, rất tiện khi đi tái khám.",
    created_at: "2026-04-11T09:30:00Z",
    comment_count: 5,
    reaction_count: 18,
    is_bookmarked: false,
    reactions_breakdown: { helpful: 12, relate: 4, thanks: 2 },
    tags: ["huyetap", "timmach"],
  },
];

const MOCK_BOOKMARKS: socialLib.SocialPost[] = [
  {
    id: 101,
    community_id: 1,
    author_handle: "clara_official",
    author_display_name: "CLARA Bác sĩ Tư vấn",
    is_verified_clinician: true,
    title: "Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)",
    body: "Khi phát hiện méo miệng, yếu liệt tay chân hoặc nói khó, hãy gọi 115 ngay lập tức.",
    created_at: "2026-04-10T08:00:00Z",
    comment_count: 12,
    reaction_count: 48,
    is_bookmarked: true,
    tags: ["capcuu", "dotquy"],
  },
];

const MOCK_COMMENTS: socialLib.SocialComment[] = [
  {
    id: 201,
    post_id: 101,
    author_handle: "nguyen_van_a",
    author_display_name: "Nguyễn Văn A",
    body: "Cảm ơn bác sĩ, thông tin rất quý báu cho gia đình có người cao tuổi.",
    created_at: "2026-04-10T09:00:00Z",
  },
  {
    id: 202,
    post_id: 101,
    parent_id: 201,
    author_handle: "bs_tran_b",
    author_display_name: "BS. Trần B",
    is_verified_clinician: true,
    body: "Cần đặc biệt lưu ý thời gian vàng cấp cứu trong vòng 3-4.5 giờ đầu.",
    created_at: "2026-04-10T10:30:00Z",
  },
];

const MOCK_PROFILE: socialLib.SocialProfile = {
  handle: "nguyen_van_a",
  display_name: "Nguyễn Văn A",
  bio: "Quan tâm đến sức khỏe tim mạch và chế độ ăn dưỡng sinh.",
  role_badge: "member",
  is_verified_clinician: false,
};

afterEach(cleanup);

describe("CommunityPage (/community - Spec v5 Section 6.72 Community Feed Archetype)", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();

    vi.mocked(socialLib.getSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: true,
    });
    vi.mocked(socialLib.listCommunities).mockResolvedValue(MOCK_COMMUNITIES);
    vi.mocked(socialLib.getFeed).mockResolvedValue(MOCK_FEED);
    vi.mocked(socialLib.getMyBookmarks).mockResolvedValue(MOCK_BOOKMARKS);
    vi.mocked(socialLib.getMyProfile).mockResolvedValue(MOCK_PROFILE);
    vi.mocked(socialLib.getComments).mockResolvedValue(MOCK_COMMENTS);
  });

  it("1. renders initial feed layout with header, persistent safety distinction banner, topic pills, and post cards", async () => {
    render(<CommunityPage />);

    // Header & CTAs
    expect(await screen.findByRole("heading", { name: "Cộng đồng", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("Cộng đồng Sức khỏe CLARA")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Viết bài mới/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Bài viết đã lưu/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Hồ sơ cộng đồng/i })).toBeInTheDocument();

    // Persistent Safety Distinction Banner
    expect(
      screen.getByText(/Cộng đồng CLARA là nơi chia sẻ kinh nghiệm và hỗ trợ lẫn nhau/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Đã kích hoạt kiểm duyệt AI")).toBeInTheDocument();
    expect(screen.getByText(/Cấp cứu khẩn cấp: 115/i)).toBeInTheDocument();

    // Topic Filter Pills
    expect(screen.getByText("Tất cả chủ đề")).toBeInTheDocument();
    expect(screen.getAllByText("Sức khỏe tổng quát").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tim mạch & Huyết áp").length).toBeGreaterThan(0);

    // Author Filter Tabs
    expect(screen.getByRole("button", { name: "Tất cả" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Chuyên gia & Bác sĩ/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Thành viên" })).toBeInTheDocument();

    // Post Card Rendering & Badges
    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();

    // Clinician Badge vs Peer Badge
    expect(screen.getByText("Bác sĩ Chuyên gia")).toBeInTheDocument();
    expect(screen.getAllByText("Thành viên").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Đã duyệt an toàn").length).toBeGreaterThan(0);
  });

  it("2. filters feed by selected topic and allows joining/leaving community", async () => {
    vi.mocked(socialLib.joinCommunity).mockResolvedValue({
      id: 2,
      slug: "tim-mach-huyet-ap",
      name: "Tim mạch & Huyết áp",
      description: "Thảo luận và chia sẻ kinh nghiệm kiểm soát huyết áp.",
      member_count: 851,
      joined: true,
    });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Select "Tim mạch & Huyết áp" community pill
    const topicBtn = screen.getByRole("button", { name: /Tim mạch & Huyết áp/i });
    fireEvent.click(topicBtn);

    // Active community banner displayed
    expect(screen.getByText("Thảo luận và chia sẻ kinh nghiệm kiểm soát huyết áp.")).toBeInTheDocument();

    // Only post from community 2 is shown
    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();

    // 1. Join community action
    const joinBtn = screen.getByRole("button", { name: "Tham gia" });
    fireEvent.click(joinBtn);

    await waitFor(() => {
      expect(socialLib.joinCommunity).toHaveBeenCalledWith(2);
    });

    // 2. Select already joined community "Sức khỏe tổng quát" and leave
    vi.mocked(socialLib.leaveCommunity).mockResolvedValue();
    const joinedTopicBtn = screen.getByRole("button", { name: /Sức khỏe tổng quát/i });
    fireEvent.click(joinedTopicBtn);

    const leaveBtn = screen.getByRole("button", { name: "Đã tham gia" });
    fireEvent.click(leaveBtn);

    await waitFor(() => {
      expect(socialLib.leaveCommunity).toHaveBeenCalledWith(1);
    });

    // Reset back to "Tất cả chủ đề"
    const allTopicsBtn = screen.getByRole("button", { name: "Tất cả chủ đề" });
    fireEvent.click(allTopicsBtn);

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
  });

  it("3. filters feed by author role: Clinicians vs Peer Members vs Bookmarks", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Filter only "Chuyên gia & Bác sĩ"
    const officialBtn = screen.getByRole("button", { name: /Chuyên gia & Bác sĩ/i });
    fireEvent.click(officialBtn);

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).not.toBeInTheDocument();

    // Filter only "Thành viên"
    const peerBtn = screen.getByRole("button", { name: "Thành viên" });
    fireEvent.click(peerBtn);

    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();

    // Switch to "Bài viết đã lưu" tab
    const bookmarksBtn = screen.getAllByRole("button", { name: /Đã lưu/i })[0];
    fireEvent.click(bookmarksBtn);

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
  });

  it("4. performs real-time search filtering across post title, body, author, and tags via both header and filter omnisearch", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // 4.1 Search by body keywords
    const searchInput = screen.getByTestId("community-search-input");
    fireEvent.change(searchInput, { target: { value: "huyết áp" } });

    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();

    // Clear search
    const clearBtn = screen.getAllByLabelText(/Xóa tìm kiếm/i)[0];
    fireEvent.click(clearBtn);

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();

    // 4.2 Search by tags via Header Omnisearch
    const headerSearch = screen.getByTestId("header-omnisearch-input");
    fireEvent.change(headerSearch, { target: { value: "dotquy" } });

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).not.toBeInTheDocument();

    // 4.3 Search by author handle
    fireEvent.change(headerSearch, { target: { value: "nguyen_van_a" } });
    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();
  });

  it("5. toggles supportive reactions (helpful, relate, thanks) and updates live count", async () => {
    vi.mocked(socialLib.addReaction).mockResolvedValue();

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Reaction 1: Helpful 👍
    const helpfulBtn = screen.getAllByTitle(/Gửi phản hồi tích cực/i)[0];
    fireEvent.click(helpfulBtn);

    await waitFor(() => {
      expect(socialLib.addReaction).toHaveBeenCalledWith(101, "helpful");
    });

    // Reaction 2: Relate 🤝
    const relateBtn = screen.getAllByTitle(/Đồng cảm/i)[0];
    fireEvent.click(relateBtn);

    await waitFor(() => {
      expect(socialLib.addReaction).toHaveBeenCalledWith(101, "relate");
    });

    // Reaction 3: Thanks 🙏
    const thanksBtn = screen.getAllByTitle(/Cảm ơn/i)[0];
    fireEvent.click(thanksBtn);

    await waitFor(() => {
      expect(socialLib.addReaction).toHaveBeenCalledWith(101, "thanks");
    });
  });

  it("6. toggles bookmark state and allows author to delete post", async () => {
    vi.mocked(socialLib.toggleBookmark).mockResolvedValue({ bookmarked: true });
    vi.mocked(socialLib.deletePost).mockResolvedValue({ deleted: true });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Bookmark toggle
    const bookmarkBtn = screen.getAllByTitle(/Lưu bài viết/i)[0];
    fireEvent.click(bookmarkBtn);

    await waitFor(() => {
      expect(socialLib.toggleBookmark).toHaveBeenCalledWith(101);
    });

    // Delete post action
    const deleteBtns = screen.getAllByRole("button", { name: /Xóa/i });
    fireEvent.click(deleteBtns[0]);

    await waitFor(() => {
      expect(socialLib.deletePost).toHaveBeenCalledWith(101);
    });

    // Verify post 101 is removed from feed
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();
  });

  it("7. opens Composer Modal, supports markdown preview, submits new post, and handles moderation block with 115 emergency guidance", async () => {
    vi.mocked(socialLib.createPost).mockResolvedValue({
      id: 103,
      community_id: 1,
      author_handle: "current_user",
      title: "Kinh nghiệm tập thể dục dưỡng sinh",
      body: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định và tinh thần minh mẫn.",
      created_at: "2026-04-12T10:00:00Z",
      comment_count: 0,
      reaction_count: 0,
    });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Open composer modal
    const composeBtn = screen.getAllByRole("button", { name: /Viết bài mới/i })[0];
    fireEvent.click(composeBtn);

    expect(screen.getByText("Chia sẻ với cộng đồng")).toBeInTheDocument();
    expect(screen.getByText(/Quy tắc an toàn & Riêng tư/i)).toBeInTheDocument();

    // Fill title and body
    const titleInput = screen.getByPlaceholderText(/Nhập tiêu đề rõ ràng cho chia sẻ/i);
    const bodyInput = screen.getByPlaceholderText(/Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm/i);

    fireEvent.change(titleInput, { target: { value: "Kinh nghiệm tập thể dục dưỡng sinh" } });
    fireEvent.change(bodyInput, { target: { value: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định và tinh thần minh mẫn." } });

    // Switch to Preview tab
    const previewTabBtn = screen.getByRole("button", { name: "Xem trước" });
    fireEvent.click(previewTabBtn);
    expect(screen.getByText(/Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định/i)).toBeInTheDocument();

    // Switch back to Write tab
    const writeTabBtn = screen.getByRole("button", { name: "Soạn thảo" });
    fireEvent.click(writeTabBtn);

    // Submit post
    const submitBtn = screen.getAllByRole("button", { name: "Đăng bài" }).pop();
    if (submitBtn) fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(socialLib.createPost).toHaveBeenCalledWith({
        communityId: 1,
        title: "Kinh nghiệm tập thể dục dưỡng sinh",
        body: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định và tinh thần minh mẫn.",
      });
    });

    // Test Moderation Error with Emergency 115 guidance
    vi.mocked(socialLib.createPost).mockRejectedValueOnce({
      status: 422,
      response: { status: 422, data: { detail: "Phát hiện dấu hiệu cấp cứu đột quỵ hoặc khó thở dữ dội." } },
    });

    fireEvent.click(composeBtn);
    const titleInput2 = screen.getByPlaceholderText(/Nhập tiêu đề rõ ràng cho chia sẻ/i);
    const bodyInput2 = screen.getByPlaceholderText(/Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm/i);

    fireEvent.change(titleInput2, { target: { value: "Người nhà bị ngất đột quỵ và khó thở dữ dội" } });
    fireEvent.change(bodyInput2, { target: { value: "Xin hỏi cần làm gì ngay bây giờ" } });

    const submitBtn2 = screen.getAllByRole("button", { name: "Đăng bài" }).pop();
    if (submitBtn2) fireEvent.click(submitBtn2);

    expect(await screen.findByText(/Dấu hiệu cấp cứu khẩn cấp: Vui lòng gọi 115 ngay lập tức/i)).toBeInTheDocument();
    expect(screen.getByText("Gọi 115")).toBeInTheDocument();
  });

  it("8. opens Post Detail & Comment Drawer, handles nested replies, comment deletion, comment reporting, and bookmarking", async () => {
    vi.mocked(socialLib.addComment).mockResolvedValue({
      id: 203,
      post_id: 101,
      parent_id: 201,
      author_handle: "current_user",
      body: "Thông tin rất hữu ích, cảm ơn BS!",
      created_at: "2026-04-10T12:00:00Z",
    });
    vi.mocked(socialLib.deleteComment).mockResolvedValue({ deleted: true });
    vi.mocked(socialLib.reportContent).mockResolvedValue();
    vi.mocked(socialLib.toggleBookmark).mockResolvedValue({ bookmarked: true });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Open detail dialog
    const postTitle = screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)");
    fireEvent.click(postTitle);

    expect(await screen.findByText("Cảm ơn bác sĩ, thông tin rất quý báu cho gia đình có người cao tuổi.")).toBeInTheDocument();
    expect(screen.getByText("Cần đặc biệt lưu ý thời gian vàng cấp cứu trong vòng 3-4.5 giờ đầu.")).toBeInTheDocument();

    // 8.1 Click Reply to comment 201
    const replyButtons = screen.getAllByRole("button", { name: "Trả lời" });
    fireEvent.click(replyButtons[0]);

    expect(screen.getByText("Đang trả lời @nguyen_van_a")).toBeInTheDocument();

    // Type comment
    const commentInput = screen.getByPlaceholderText(/Chia sẻ suy nghĩ của bạn/i);
    fireEvent.change(commentInput, { target: { value: "Thông tin rất hữu ích, cảm ơn BS!" } });

    // Submit reply comment
    const submitCommentBtn = screen.getByRole("button", { name: "Gửi bình luận" });
    fireEvent.click(submitCommentBtn);

    await waitFor(() => {
      expect(socialLib.addComment).toHaveBeenCalledWith(101, "Thông tin rất hữu ích, cảm ơn BS!", 201);
    });

    // 8.2 Delete comment 201
    const deleteCommentBtns = screen.getAllByTitle("Xóa bình luận");
    fireEvent.click(deleteCommentBtns[0]);

    await waitFor(() => {
      expect(socialLib.deleteComment).toHaveBeenCalledWith(201);
    });

    // 8.3 Report comment 202
    const reportCommentBtns = screen.getAllByRole("button", { name: "Báo cáo" });
    fireEvent.click(reportCommentBtns[0]);

    expect(screen.getByRole("heading", { name: "Báo cáo" })).toBeInTheDocument();
    const submitReportBtn = screen.getByRole("button", { name: "Gửi báo cáo" });
    fireEvent.click(submitReportBtn);

    await waitFor(() => {
      expect(socialLib.reportContent).toHaveBeenCalledWith({
        targetType: "comment",
        targetId: 202,
        reason: "misinformation",
      });
    });

    // 8.4 Toggle bookmark from within dialog
    const dialog = screen.getByRole("dialog", { name: /Hướng dẫn nhận biết các dấu hiệu sớm/i });
    const dialogBookmarkBtn = within(dialog).getByRole("button", { name: "Lưu" });
    fireEvent.click(dialogBookmarkBtn);

    await waitFor(() => {
      expect(socialLib.toggleBookmark).toHaveBeenCalledWith(101);
    });
  });

  it("9. opens Profile Drawer, displays profile information, and saves updated profile", async () => {
    vi.mocked(socialLib.updateMyProfile).mockResolvedValue({
      handle: "nguyen_van_a",
      display_name: "Nguyễn Văn A - Cập nhật",
      bio: "Đam mê rèn luyện lối sống lành mạnh.",
      role_badge: "member",
      is_verified_clinician: false,
    });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Open profile drawer
    const profileBtn = screen.getByRole("button", { name: /Hồ sơ cộng đồng/i });
    fireEvent.click(profileBtn);

    expect(await screen.findByText("Hồ sơ Cộng đồng của tôi")).toBeInTheDocument();
    expect(screen.getAllByText("@nguyen_van_a").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Zero-PII/i).length).toBeGreaterThan(0);

    // Edit display name & bio
    const nameInput = screen.getByDisplayValue("Nguyễn Văn A");
    const bioInput = screen.getByDisplayValue("Quan tâm đến sức khỏe tim mạch và chế độ ăn dưỡng sinh.");

    fireEvent.change(nameInput, { target: { value: "Nguyễn Văn A - Cập nhật" } });
    fireEvent.change(bioInput, { target: { value: "Đam mê rèn luyện lối sống lành mạnh." } });

    // Save profile
    const saveProfileBtn = screen.getByRole("button", { name: "Lưu hồ sơ" });
    fireEvent.click(saveProfileBtn);

    await waitFor(() => {
      expect(socialLib.updateMyProfile).toHaveBeenCalledWith({
        display_name: "Nguyễn Văn A - Cập nhật",
        bio: "Đam mê rèn luyện lối sống lành mạnh.",
      });
    });
  });

  it("10. opens Report Dialog and submits report with selected reason", async () => {
    vi.mocked(socialLib.reportContent).mockResolvedValue();

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    const reportBtn = screen.getAllByTitle("Báo cáo bài viết")[0];
    fireEvent.click(reportBtn);

    expect(screen.getByRole("heading", { name: "Báo cáo bài viết" })).toBeInTheDocument();
    expect(screen.getByText(/Vui lòng chọn lý do báo cáo bài viết này/i)).toBeInTheDocument();

    const submitReportBtn = screen.getByRole("button", { name: "Gửi báo cáo" });
    fireEvent.click(submitReportBtn);

    await waitFor(() => {
      expect(socialLib.reportContent).toHaveBeenCalledWith({
        targetType: "post",
        targetId: 101,
        reason: "misinformation",
      });
    });
  });

  it("11. handles unconsented state with consent card and grants consent on action", async () => {
    vi.mocked(socialLib.getSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: false,
    });
    vi.mocked(socialLib.grantSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: true,
    });

    render(<CommunityPage />);

    expect(await screen.findByText("Tham gia để đăng bài & bình luận")).toBeInTheDocument();

    const consentBtn = screen.getByRole("button", { name: "Tôi đồng ý tham gia" });
    fireEvent.click(consentBtn);

    await waitFor(() => {
      expect(socialLib.grantSocialConsent).toHaveBeenCalled();
    });
  });

  it("12. renders engaging empty state when feed has no matching posts with quick suggestions", async () => {
    vi.mocked(socialLib.getFeed).mockResolvedValue([]);

    render(<CommunityPage />);

    expect(await screen.findByText("Chưa có bài viết. Hãy là người đầu tiên chia sẻ.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tạo bài viết đầu tiên/i })).toBeInTheDocument();
  });

  it("13. renders friendly unavailable state when social platform flag is off (404)", async () => {
    vi.mocked(socialLib.getSocialConsent).mockRejectedValue(
      new socialLib.SocialUnavailableError()
    );

    render(<CommunityPage />);

    expect(await screen.findByText("Cộng đồng sắp ra mắt")).toBeInTheDocument();
  });

  it("14. opens Zero-PII & Moderation Policy modal from Safety Banner", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    const privacyLink = screen.getByRole("button", {
      name: /Chính sách bảo mật Zero-PII & Kiểm duyệt/i,
    });
    fireEvent.click(privacyLink);

    expect(
      await screen.findByText("Chính sách kiểm duyệt & Quyền riêng tư")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Tiêu chuẩn cách ly Zero-PII/i)
    ).toBeInTheDocument();
  });

  it("15. allows hiding a post and unhiding all hidden posts", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();

    // Hide post 101
    const hideBtns = screen.getAllByRole("button", { name: "Ẩn bài" });
    fireEvent.click(hideBtns[0]);

    // Post 101 should disappear
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();

    // Click "Hiện lại 1 bài đã ẩn"
    const unhideBtn = screen.getByRole("button", { name: /Hiện lại 1 bài đã ẩn/i });
    fireEvent.click(unhideBtn);

    // Post 101 is visible again
    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
  });

  it("16. prompts ConsentGateModal when unconsented user triggers quick reaction or compose", async () => {
    vi.mocked(socialLib.getSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: false,
    });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Click quick reaction on post card
    const reactionBtn = screen.getAllByTitle(/Tham gia cộng đồng để phản hồi/i)[0];
    fireEvent.click(reactionBtn);

    // ConsentGateModal should appear
    expect(
      await screen.findByText("Quy tắc văn hóa Cộng đồng Sức khỏe")
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: "Tôi đồng ý tham gia" }).length
    ).toBeGreaterThan(0);
  });
});
