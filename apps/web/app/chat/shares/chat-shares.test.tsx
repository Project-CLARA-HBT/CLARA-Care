import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import ChatShareManagementPage from "./page";
import * as workspaceModule from "@/lib/workspace";

vi.mock("@/lib/workspace", () => ({
  listWorkspaceShares: vi.fn(),
  createWorkspaceConversationShare: vi.fn(),
  revokeWorkspaceConversationShare: vi.fn(),
}));

describe("ChatShareManagementPage (Spec v5 Section 6.35 - Shared Conversations Library)", () => {
  const mockShares: workspaceModule.WorkspaceConversationShareListItem[] = [
    {
      share_id: 101,
      conversation_id: 123,
      conversation_title: "Tư vấn thuốc huyết áp Amlodipine",
      message_count: 6,
      is_active: true,
      expires_at: new Date(Date.now() + 6 * 24 * 60 * 60 * 1000).toISOString(), // 6 days in future
      created_at: "2026-08-01T10:00:00Z",
      updated_at: "2026-08-01T10:00:00Z",
    },
    {
      share_id: 102,
      conversation_id: 124,
      conversation_title: "Hỏi về chỉ số đường huyết sau ăn",
      message_count: 3,
      is_active: true,
      expires_at: new Date(Date.now() + 10 * 60 * 60 * 1000).toISOString(), // 10 hours in future
      created_at: "2026-08-02T11:00:00Z",
      updated_at: "2026-08-02T11:00:00Z",
    },
    {
      share_id: 103,
      conversation_id: 125,
      conversation_title: "Tra cứu tương tác thuốc Metformin và Panadol",
      message_count: 8,
      is_active: false,
      expires_at: "2026-07-20T00:00:00Z",
      created_at: "2026-07-15T09:00:00Z",
      updated_at: "2026-07-20T00:00:00Z",
    },
    {
      share_id: 104,
      conversation_id: 126,
      conversation_title: "Hỏi đáp dị ứng Paracetamol",
      message_count: 2,
      is_active: true,
      expires_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // Expired yesterday
      created_at: "2026-07-10T09:00:00Z",
      updated_at: "2026-07-10T09:00:00Z",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceModule.listWorkspaceShares).mockResolvedValue(mockShares);
    vi.mocked(workspaceModule.createWorkspaceConversationShare).mockResolvedValue({
      share_id: 101,
      conversation_id: 123,
      share_token: "rotated-token-abc",
      public_url: "https://clara.care/share/rotated-token-abc",
      is_active: true,
      created_at: "2026-08-01T10:00:00Z",
      updated_at: "2026-08-05T10:00:00Z",
    });
    vi.mocked(workspaceModule.revokeWorkspaceConversationShare).mockResolvedValue({
      revoked: true,
    });
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("renders 1. Header + back to Chat navigation link, title, and description", async () => {
    render(<ChatShareManagementPage />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Quản lý liên kết chia sẻ");
    expect(screen.getByRole("link", { name: /Quay lại Hỏi CLARA/i })).toHaveAttribute("href", "/chat");

    await waitFor(() => {
      expect(workspaceModule.listWorkspaceShares).toHaveBeenCalled();
    });
  });

  it("renders 2. Active shares list rows with Title, Recipient, Shared at, Expiry countdown, Access count, Rotate button, and Revoke button", async () => {
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("active-shares-list")).toBeInTheDocument();
    });

    const activeList = screen.getByTestId("active-shares-list");

    // Check row 123
    expect(activeList).toHaveTextContent("#123");
    expect(activeList).toHaveTextContent("Tư vấn thuốc huyết áp Amlodipine");
    expect(activeList).toHaveTextContent("Liên kết công khai");
    expect(activeList).toHaveTextContent("Chia sẻ lúc");
    expect(activeList).toHaveTextContent("Thời hạn");
    expect(activeList).toHaveTextContent("Lượt truy cập: 6");
    expect(screen.getByTestId("rotate-token-btn-123")).toBeInTheDocument();
    expect(screen.getByTestId("revoke-btn-123")).toBeInTheDocument();

    // Check row 124 (expiring in ~10h)
    expect(activeList).toHaveTextContent("#124");
    expect(activeList).toHaveTextContent("Hỏi về chỉ số đường huyết sau ăn");
    expect(screen.getByTestId("rotate-token-btn-124")).toBeInTheDocument();
    expect(screen.getByTestId("revoke-btn-124")).toBeInTheDocument();
  });

  it("renders 3. Expired/revoked shares archive section with archive rows", async () => {
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("archive-shares-list")).toBeInTheDocument();
    });

    const archiveList = screen.getByTestId("archive-shares-list");

    // Revoked row 125
    expect(archiveList).toHaveTextContent("#125");
    expect(archiveList).toHaveTextContent("Tra cứu tương tác thuốc Metformin và Panadol");
    expect(archiveList).toHaveTextContent("Đã thu hồi");
    expect(screen.getByTestId("reissue-btn-125")).toBeInTheDocument();

    // Expired row 126
    expect(archiveList).toHaveTextContent("#126");
    expect(archiveList).toHaveTextContent("Hỏi đáp dị ứng Paracetamol");
    expect(archiveList).toHaveTextContent("Đã hết hạn");
    expect(screen.getByTestId("reissue-btn-126")).toBeInTheDocument();
  });

  it("renders 4. Empty state when there are no shares", async () => {
    vi.mocked(workspaceModule.listWorkspaceShares).mockResolvedValueOnce([]);
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("shares-empty-state")).toBeInTheDocument();
    });

    expect(screen.getByText("Chưa có liên kết chia sẻ nào.")).toBeInTheDocument();
  });

  it("handles rotating token button: calls API, writes to clipboard, and shows success notice", async () => {
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("rotate-token-btn-123")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("rotate-token-btn-123"));

    await waitFor(() => {
      expect(workspaceModule.createWorkspaceConversationShare).toHaveBeenCalledWith(123, {
        rotate: true,
      });
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("https://clara.care/share/rotated-token-abc");
    });

    expect(screen.getByText("Đã cấp liên kết mới và sao chép vào bộ nhớ tạm.")).toBeInTheDocument();
  });

  it("handles revoking share: opens confirmation modal, confirms, calls API, and refreshes list", async () => {
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("revoke-btn-123")).toBeInTheDocument();
    });

    // Click revoke button to open confirmation modal
    fireEvent.click(screen.getByTestId("revoke-btn-123"));

    expect(screen.getByTestId("revoke-confirm-modal")).toBeInTheDocument();
    expect(screen.getByText("Thu hồi liên kết chia sẻ?")).toBeInTheDocument();

    // Confirm revocation
    fireEvent.click(screen.getByTestId("confirm-revoke-btn"));

    await waitFor(() => {
      expect(workspaceModule.revokeWorkspaceConversationShare).toHaveBeenCalledWith(123);
    });

    expect(screen.getByText("Đã thu hồi liên kết của cuộc trò chuyện #123.")).toBeInTheDocument();
  });

  it("filters shares using tabs and search query", async () => {
    render(<ChatShareManagementPage />);

    await waitFor(() => {
      expect(screen.getByTestId("active-shares-list")).toBeInTheDocument();
      expect(screen.getByTestId("archive-shares-list")).toBeInTheDocument();
    });

    // Filter to active only
    fireEvent.click(screen.getByTestId("filter-active"));
    expect(screen.getByTestId("active-shares-list")).toBeInTheDocument();
    expect(screen.queryByTestId("archive-shares-list")).not.toBeInTheDocument();

    // Filter to archive only
    fireEvent.click(screen.getByTestId("filter-archive"));
    expect(screen.queryByTestId("active-shares-list")).not.toBeInTheDocument();
    expect(screen.getByTestId("archive-shares-list")).toBeInTheDocument();

    // Switch back to all and search
    fireEvent.click(screen.getByTestId("filter-all"));
    const searchInput = screen.getByTestId("shares-search-input");
    fireEvent.change(searchInput, { target: { value: "Amlodipine" } });

    expect(screen.getByTestId("active-shares-list")).toHaveTextContent("Tư vấn thuốc huyết áp Amlodipine");
    expect(screen.getByTestId("active-shares-list")).not.toHaveTextContent("Hỏi về chỉ số đường huyết sau ăn");
  });
});
