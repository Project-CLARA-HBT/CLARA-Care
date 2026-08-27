import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  SafetyBanner,
  TopicFilterBar,
  PostCard,
  ComposeModal,
  ReportModal,
  PrivacyModal,
  PostDetailDialog,
} from "@/components/community";
import * as socialLib from "@/lib/social";

vi.mock("@/lib/social", () => {
  return {
    getComments: vi.fn(),
    addComment: vi.fn(),
    addReaction: vi.fn(),
    reportContent: vi.fn(),
    isSocialModerationBlock: vi.fn((err: unknown) => {
      return (err as { status?: number })?.status === 422;
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
];

const MOCK_POST: socialLib.SocialPost = {
  id: 101,
  community_id: 1,
  author_handle: "clara_official",
  title: "Hướng dẫn nhận biết dấu hiệu sớm",
  body: "Nội dung bài viết y khoa chính thống từ CLARA.",
  created_at: "2026-04-10T08:00:00Z",
  comment_count: 3,
  reaction_count: 25,
};

const MOCK_COMMENTS: socialLib.SocialComment[] = [
  {
    id: 201,
    post_id: 101,
    author_handle: "nguyen_van_a",
    body: "Cảm ơn bác sĩ, bài viết rất hữu ích cho người cao tuổi!",
    created_at: "2026-04-10T09:00:00Z",
  },
  {
    id: 202,
    post_id: 101,
    author_handle: "bs_tran_b",
    body: "Nếu có thêm triệu chứng chóng mặt kéo dài hãy tái khám chuyên khoa.",
    created_at: "2026-04-10T10:30:00Z",
  },
];

afterEach(cleanup);

describe("Community Sub-components Audit & Verification", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  describe("SafetyBanner", () => {
    it("renders medical safety notice, emergency hotline 115, and triggers privacy policy modal callback", () => {
      const onOpenPrivacy = vi.fn();
      render(<SafetyBanner onOpenPrivacyPolicy={onOpenPrivacy} />);

      expect(screen.getByText(/Lưu ý an toàn y tế & Chia sẻ đồng cấp/i)).toBeInTheDocument();
      expect(screen.getByText("Đã kích hoạt kiểm duyệt AI")).toBeInTheDocument();
      expect(screen.getByText(/Cấp cứu khẩn cấp: 115/i)).toBeInTheDocument();

      const policyBtn = screen.getByRole("button", {
        name: /Chính sách bảo mật Zero-PII & Kiểm duyệt/i,
      });
      fireEvent.click(policyBtn);
      expect(onOpenPrivacy).toHaveBeenCalledTimes(1);
    });
  });

  describe("TopicFilterBar", () => {
    it("supports topic switching, author filter toggle, search query input, and join/leave toggle", () => {
      const onSelectCommunity = vi.fn();
      const onSelectAuthorFilter = vi.fn();
      const onSearchChange = vi.fn();
      const onToggleJoin = vi.fn();

      render(
        <TopicFilterBar
          communities={MOCK_COMMUNITIES}
          selectedCommunityId={1}
          onSelectCommunity={onSelectCommunity}
          authorFilter="all"
          onSelectAuthorFilter={onSelectAuthorFilter}
          searchQuery=""
          onSearchChange={onSearchChange}
          onToggleJoinCommunity={onToggleJoin}
          activeCommunity={MOCK_COMMUNITIES[0]}
        />
      );

      // Topic pill click
      const topicBtn = screen.getByRole("button", { name: /Tim mạch & Huyết áp/i });
      fireEvent.click(topicBtn);
      expect(onSelectCommunity).toHaveBeenCalledWith(2);

      // Author filter click
      const officialBtn = screen.getByRole("button", { name: /Chuyên gia/i });
      fireEvent.click(officialBtn);
      expect(onSelectAuthorFilter).toHaveBeenCalledWith("official");

      // Search input change
      const searchInput = screen.getByTestId("community-search-input");
      fireEvent.change(searchInput, { target: { value: "huyết áp" } });
      expect(onSearchChange).toHaveBeenCalledWith("huyết áp");

      // Active community join toggle
      const joinToggleBtn = screen.getByRole("button", { name: "Đã tham gia" });
      fireEvent.click(joinToggleBtn);
      expect(onToggleJoin).toHaveBeenCalledWith(MOCK_COMMUNITIES[0]);
    });
  });

  describe("PostCard", () => {
    it("renders post card with official verification badge, interaction triggers, and hides/reports", () => {
      const onOpenDetail = vi.fn();
      const onReaction = vi.fn();
      const onReport = vi.fn();
      const onToggleHide = vi.fn();

      render(
        <PostCard
          post={MOCK_POST}
          community={MOCK_COMMUNITIES[0]}
          canParticipate={true}
          onOpenDetail={onOpenDetail}
          onReaction={onReaction}
          onReport={onReport}
          onToggleHide={onToggleHide}
        />
      );

      expect(screen.getByText("Hướng dẫn nhận biết dấu hiệu sớm")).toBeInTheDocument();
      expect(screen.getByText("Bác sĩ Chuyên gia")).toBeInTheDocument();
      expect(screen.getByText("Đã duyệt an toàn")).toBeInTheDocument();

      // Open detail on click
      const postTitle = screen.getByText("Hướng dẫn nhận biết dấu hiệu sớm");
      fireEvent.click(postTitle);
      expect(onOpenDetail).toHaveBeenCalledWith(MOCK_POST);

      // Reaction
      const reactBtn = screen.getByTitle(/Gửi phản hồi tích cực/i);
      fireEvent.click(reactBtn);
      expect(onReaction).toHaveBeenCalledWith(MOCK_POST);

      // Report
      const reportBtn = screen.getByTitle("Báo cáo bài viết");
      fireEvent.click(reportBtn);
      expect(onReport).toHaveBeenCalledWith(MOCK_POST);

      // Hide
      const hideBtn = screen.getByTitle(/Ẩn bài viết khỏi bảng tin/i);
      fireEvent.click(hideBtn);
      expect(onToggleHide).toHaveBeenCalledWith(MOCK_POST.id);
    });
  });

  describe("ComposeModal", () => {
    it("renders form fields, validates input, and handles submission", async () => {
      const onClose = vi.fn();
      const onPostCreated = vi.fn();
      const createPostFn = vi.fn().mockResolvedValue({ id: 105 });

      render(
        <ComposeModal
          open={true}
          onClose={onClose}
          communities={MOCK_COMMUNITIES}
          initialCommunityId={1}
          onPostCreated={onPostCreated}
          createPostFn={createPostFn}
        />
      );

      expect(screen.getByText("Chia sẻ với cộng đồng")).toBeInTheDocument();
      expect(screen.getByText(/Quy tắc an toàn & Riêng tư/i)).toBeInTheDocument();

      const titleInput = screen.getByPlaceholderText(/Nhập tiêu đề rõ ràng cho chia sẻ/i);
      const bodyInput = screen.getByPlaceholderText(/Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm/i);

      fireEvent.change(titleInput, { target: { value: "Kinh nghiệm rèn luyện thể thao" } });
      fireEvent.change(bodyInput, { target: { value: "Tập yoga nhẹ nhàng giúp cải thiện giấc ngủ." } });

      const submitBtn = screen.getByRole("button", { name: "Đăng bài" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(createPostFn).toHaveBeenCalledWith({
          communityId: 1,
          title: "Kinh nghiệm rèn luyện thể thao",
          body: "Tập yoga nhẹ nhàng giúp cải thiện giấc ngủ.",
        });
        expect(onPostCreated).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });

    it("displays moderation block error when submission violates safety gate (422)", async () => {
      const onClose = vi.fn();
      const onPostCreated = vi.fn();
      const createPostFn = vi.fn().mockRejectedValue({
        status: 422,
        response: { status: 422 },
      });

      render(
        <ComposeModal
          open={true}
          onClose={onClose}
          communities={MOCK_COMMUNITIES}
          initialCommunityId={1}
          onPostCreated={onPostCreated}
          createPostFn={createPostFn}
        />
      );

      const titleInput = screen.getByPlaceholderText(/Nhập tiêu đề rõ ràng cho chia sẻ/i);
      const bodyInput = screen.getByPlaceholderText(/Mô tả bối cảnh, thắc mắc hoặc kinh nghiệm/i);

      fireEvent.change(titleInput, { target: { value: "Uống thuốc này đi" } });
      fireEvent.change(bodyInput, { target: { value: "Tôi khuyên bạn uống 500mg paracetamol 4 lần một ngày." } });

      const submitBtn = screen.getByRole("button", { name: "Đăng bài" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(
          screen.getByText(/Nội dung không phù hợp quy tắc cộng đồng \(không kê đơn\/chẩn đoán\/liều dùng cá nhân\)/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe("ReportModal", () => {
    it("submits content report with selected violation reason", async () => {
      const onClose = vi.fn();
      const onSuccess = vi.fn();
      const onError = vi.fn();
      const reportFn = vi.fn().mockResolvedValue({});

      render(
        <ReportModal
          open={true}
          target={{
            type: "post",
            id: 101,
            titleOrSnippet: "Tiêu đề bài viết cần báo cáo",
          }}
          onClose={onClose}
          onSuccess={onSuccess}
          onError={onError}
          reportFn={reportFn}
        />
      );

      expect(screen.getByRole("heading", { name: "Báo cáo bài viết" })).toBeInTheDocument();
      expect(screen.getByText('"Tiêu đề bài viết cần báo cáo"')).toBeInTheDocument();

      const submitBtn = screen.getByRole("button", { name: "Gửi báo cáo" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(reportFn).toHaveBeenCalledWith({
          targetType: "post",
          targetId: 101,
          reason: "misinformation",
        });
        expect(onSuccess).toHaveBeenCalled();
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe("PrivacyModal", () => {
    it("renders Zero-PII isolation standard and ML safety engine descriptions", () => {
      const onClose = vi.fn();
      render(<PrivacyModal open={true} onClose={onClose} />);

      expect(screen.getByRole("heading", { name: "Chính sách kiểm duyệt & Quyền riêng tư" })).toBeInTheDocument();
      expect(screen.getByText("Tiêu chuẩn cách ly Zero-PII")).toBeInTheDocument();
      expect(screen.getByText("Kiểm duyệt an toàn tự động (ML)")).toBeInTheDocument();
      expect(screen.getByText("Phát hiện khẩn cấp y tế")).toBeInTheDocument();

      const closeBtn = screen.getAllByRole("button", { name: "Đóng" }).pop();
      if (closeBtn) {
        fireEvent.click(closeBtn);
      }
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("PostDetailDialog", () => {
    it("loads and displays comments, allows adding comment and sending reactions", async () => {
      vi.mocked(socialLib.getComments).mockResolvedValue(MOCK_COMMENTS);
      vi.mocked(socialLib.addComment).mockResolvedValue({
        id: 203,
        post_id: 101,
        author_handle: "me",
        body: "Đồng quan điểm với chia sẻ trên.",
        created_at: "2026-04-10T11:00:00Z",
      });
      vi.mocked(socialLib.addReaction).mockResolvedValue();

      const onClose = vi.fn();
      const onCommentAdded = vi.fn();

      render(
        <PostDetailDialog
          post={MOCK_POST}
          canParticipate={true}
          onClose={onClose}
          onCommentAdded={onCommentAdded}
        />
      );

      expect(screen.getByRole("heading", { name: "Hướng dẫn nhận biết dấu hiệu sớm" })).toBeInTheDocument();

      // Wait for comments to load
      expect(
        await screen.findByText("Cảm ơn bác sĩ, bài viết rất hữu ích cho người cao tuổi!")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Nếu có thêm triệu chứng chóng mặt kéo dài hãy tái khám chuyên khoa.")
      ).toBeInTheDocument();

      // Add comment
      const commentInput = screen.getByPlaceholderText(/Chia sẻ suy nghĩ của bạn/i);
      fireEvent.change(commentInput, { target: { value: "Đồng quan điểm với chia sẻ trên." } });

      const submitCommentBtn = screen.getByRole("button", { name: "Gửi bình luận" });
      fireEvent.click(submitCommentBtn);

      await waitFor(() => {
        expect(socialLib.addComment).toHaveBeenCalledWith(101, "Đồng quan điểm với chia sẻ trên.");
        expect(onCommentAdded).toHaveBeenCalledWith(101);
      });

      // Send supportive reaction (relate)
      const relateBtn = screen.getAllByRole("button").find((btn) =>
        btn.textContent?.includes("community.reaction.relate") ||
        btn.textContent?.includes("Đồng cảm")
      );
      if (relateBtn) {
        fireEvent.click(relateBtn);
      }

      await waitFor(() => {
        expect(socialLib.addReaction).toHaveBeenCalledWith(101, "relate");
      });
    });
  });
});
