import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CommunityPage from "./page";
import * as socialLib from "@/lib/social";

vi.mock("@/lib/social", () => {
  return {
    getSocialConsent: vi.fn(),
    grantSocialConsent: vi.fn(),
    listCommunities: vi.fn(),
    joinCommunity: vi.fn(),
    leaveCommunity: vi.fn(),
    getFeed: vi.fn(),
    createPost: vi.fn(),
    addReaction: vi.fn(),
    reportContent: vi.fn(),
    SocialUnavailableError: class SocialUnavailableError extends Error {
      constructor() {
        super("social_unavailable");
        this.name = "SocialUnavailableError";
      }
    },
    isSocialModerationBlock: vi.fn((err: unknown) => {
      return (err as { status?: number })?.status === 422;
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
];

const MOCK_FEED: socialLib.SocialPost[] = [
  {
    id: 101,
    community_id: 1,
    author_handle: "clara_official",
    title: "Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)",
    body: "Khi phát hiện méo miệng, yếu liệt tay chân hoặc nói khó, hãy gọi 115 ngay lập tức.",
    created_at: "2026-04-10T08:00:00Z",
    comment_count: 12,
    reaction_count: 48,
  },
  {
    id: 102,
    community_id: 2,
    author_handle: "nguyen_van_a",
    title: "Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử",
    body: "Mỗi sáng mình đo lúc 7h trước khi ăn sáng và ghi vào LifeMap của CLARA, rất tiện khi đi tái khám.",
    created_at: "2026-04-11T09:30:00Z",
    comment_count: 5,
    reaction_count: 18,
  },
];

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
  });

  it("renders the Community Feed with EXPLORE shell, safety distinction banner, topic filters, and post list", async () => {
    render(<CommunityPage />);

    // Header & Safety Banner
    expect(await screen.findByRole("heading", { name: "Cộng đồng", level: 1 })).toBeInTheDocument();
    expect(
      screen.getByText(/Cộng đồng CLARA là nơi chia sẻ kinh nghiệm/i)
    ).toBeInTheDocument();
    expect(screen.getByText("Đã kích hoạt kiểm duyệt AI")).toBeInTheDocument();

    // Filter controls
    expect(screen.getByText("Tất cả chủ đề")).toBeInTheDocument();
    expect(screen.getAllByText("Sức khỏe tổng quát").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tim mạch & Huyết áp").length).toBeGreaterThan(0);

    // Post items rendered
    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
  });

  it("distinguishes between CLARA Official / Verified Clinicians and Peer Community members with badges", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Official badge for @clara_official
    expect(screen.getByText("CLARA Chuyên gia")).toBeInTheDocument();

    // Peer badge for @nguyen_van_a
    expect(screen.getAllByText("Thành viên").length).toBeGreaterThan(0);

    // Moderation badge
    expect(screen.getAllByText("Đã duyệt an toàn").length).toBeGreaterThan(0);
  });

  it("shows consent card when user has not granted social consent, and grants consent on action", async () => {
    vi.mocked(socialLib.getSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: false,
    });
    vi.mocked(socialLib.grantSocialConsent).mockResolvedValue({
      consent_type: "social_general",
      granted: true,
    });

    render(<CommunityPage />);

    expect(
      await screen.findByText("Tham gia để đăng bài & bình luận")
    ).toBeInTheDocument();

    const consentBtn = screen.getByRole("button", { name: "Tôi đồng ý tham gia" });
    fireEvent.click(consentBtn);

    await waitFor(() => {
      expect(socialLib.grantSocialConsent).toHaveBeenCalled();
    });
  });

  it("filters feed by author type (CLARA Official vs Peer Community)", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Filter only CLARA & Chuyên gia
    const officialBtn = screen.getByRole("button", { name: "CLARA & Chuyên gia" });
    fireEvent.click(officialBtn);

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).not.toBeInTheDocument();

    // Filter only Peer Community
    const peerBtn = screen.getByRole("button", { name: "Thành viên" });
    fireEvent.click(peerBtn);

    expect(
      screen.getByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).not.toBeInTheDocument();
  });

  it("filters feed by search keywords in community search input", async () => {
    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    const searchInput = screen.getByTestId("community-search-input");
    fireEvent.change(searchInput, { target: { value: "đột quỵ" } });

    expect(
      screen.getByText("Hướng dẫn nhận biết các dấu hiệu sớm của đột quỵ (FAST)")
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Kinh nghiệm theo dõi huyết áp tại nhà bằng sổ điện tử")
    ).not.toBeInTheDocument();
  });

  it("opens Compose Dialog, fills inputs, and submits new post", async () => {
    vi.mocked(socialLib.createPost).mockResolvedValue({
      id: 103,
      community_id: 1,
      author_handle: "current_user",
      title: "Chia sẻ bài tập thể dục buổi sáng",
      body: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định hơn.",
      created_at: "2026-04-12T10:00:00Z",
      comment_count: 0,
      reaction_count: 0,
    });

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    // Open compose modal
    const composeBtn = screen.getByRole("button", { name: /Đăng bài/i });
    fireEvent.click(composeBtn);

    expect(screen.getByText("Chia sẻ với cộng đồng")).toBeInTheDocument();
    expect(screen.getByText(/Quy tắc an toàn/i)).toBeInTheDocument();

    // Enter title & body
    const titleInput = screen.getByPlaceholderText(
      /Nhập tiêu đề rõ ràng cho chia sẻ/i
    );
    const bodyInput = screen.getByPlaceholderText(
      /Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm/i
    );

    fireEvent.change(titleInput, { target: { value: "Chia sẻ bài tập thể dục buổi sáng" } });
    fireEvent.change(bodyInput, { target: { value: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định hơn." } });

    // Submit post
    const submitBtn = screen.getAllByRole("button", { name: "Đăng bài" }).pop();
    if (submitBtn) {
      fireEvent.click(submitBtn);
    }

    await waitFor(() => {
      expect(socialLib.createPost).toHaveBeenCalledWith({
        communityId: 1,
        title: "Chia sẻ bài tập thể dục buổi sáng",
        body: "Mỗi sáng đi bộ 30 phút giúp huyết áp ổn định hơn.",
      });
    });
  });

  it("sends supportive reactions and tracks count", async () => {
    vi.mocked(socialLib.addReaction).mockResolvedValue();

    render(<CommunityPage />);

    await screen.findByRole("heading", { name: "Cộng đồng", level: 1 });

    const reactionBtn = screen.getAllByTitle(/Gửi phản hồi tích cực/i)[0];
    fireEvent.click(reactionBtn);

    await waitFor(() => {
      expect(socialLib.addReaction).toHaveBeenCalledWith(101, "helpful");
    });
  });

  it("opens report modal when reporting violating content", async () => {
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

  it("renders friendly unavailable state when social platform flag is off (404)", async () => {
    vi.mocked(socialLib.getSocialConsent).mockRejectedValue(
      new socialLib.SocialUnavailableError()
    );

    render(<CommunityPage />);

    expect(await screen.findByText("Cộng đồng sắp ra mắt")).toBeInTheDocument();
  });
});
