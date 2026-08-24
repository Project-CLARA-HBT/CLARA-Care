import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import SharedConversationPage from "./page";
import SharedConversationClient, {
  getProofFingerprint,
  getExpiryCountdown,
} from "./shared-conversation-client";
import ChatSharePage from "@/app/chat/share/[token]/page";
import * as workspaceModule from "@/lib/workspace";
import { isPublicRoute } from "@/lib/navigation.access";

vi.mock("@/lib/workspace", () => ({
  getWorkspacePublicConversation: vi.fn(),
}));

describe("Public Shared Packet Reader (Spec v5 Section 6.11, 6.12)", () => {
  const mockConversation: workspaceModule.WorkspacePublicConversation = {
    conversation_id: 88,
    title: "Tư vấn điều trị tăng huyết áp nguyên phát",
    expires_at: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(), // 5 days in future
    messages: [
      {
        query_id: 1001,
        role: "user",
        query: "Bác sĩ cho tôi hỏi liều dùng khởi đầu của Amlodipine 5mg khi phối hợp với Perindopril?",
        answer:
          "**Amlodipine 5mg** thường được phối hợp với **Perindopril 4mg hoặc 5mg** một lần mỗi ngày vào buổi sáng.\n\n### Hướng dẫn sử dụng\n1. Uống cùng một thời điểm mỗi ngày.\n2. Theo dõi huyết áp tại nhà định kỳ.\n3. Thông báo ngay nếu có hiện tượng phù mắt cá chân hoặc ho khan khan kéo dài.",
        created_at: "2026-08-20T08:30:00Z",
      },
      {
        query_id: 1002,
        role: "assistant",
        query: "Tôi có cần xét nghiệm chức năng thận trước khi dùng không?",
        answer:
          "Có, cần làm xét nghiệm **chức năng thận (Creatinine/eGFR)** và **Điện giải đồ (Kali máu)** trước khi khởi đầu phác đồ chứa ức chế men chuyển (ACEi).",
        created_at: "2026-08-20T08:35:00Z",
      },
    ],
  };

  const mockResearchReport: workspaceModule.WorkspacePublicConversation = {
    conversation_id: 99,
    title: "Báo cáo nghiên cứu y khoa về SGLT2i",
    expires_at: null, // No expiry
    messages: [
      {
        query_id: 2001,
        role: "research_report",
        query: "Tổng hợp bằng chứng lâm sàng về hiệu quả bảo vệ tim mạch của Dapagliflozin",
        answer:
          "## Tổng quan bằng chứng lâm sàng\nNghiên cứu DAPA-HF và DELIVER cho thấy Dapagliflozin giảm 18% nguy cơ tử vong do tim mạch hoặc nhập viện vì suy tim.",
        created_at: "2026-08-21T14:00:00Z",
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Route classification and public shell suppression", () => {
    it("recognizes /share/[token] and /chat/share/[token] as public capability routes", () => {
      expect(isPublicRoute("/share/test-capability-token")).toBe(true);
      expect(isPublicRoute("/chat/share/test-capability-token")).toBe(true);
      expect(isPublicRoute("/phr/shared/test-phr-token")).toBe(true);
      // Authenticated paths remain protected
      expect(isPublicRoute("/chat")).toBe(false);
      expect(isPublicRoute("/chat/shares")).toBe(false);
      expect(isPublicRoute("/home")).toBe(false);
    });

    it("generates deterministic SHA-256 cryptographic fingerprints", () => {
      const fp1 = getProofFingerprint("token-alpha-123");
      const fp2 = getProofFingerprint("token-alpha-123");
      const fp3 = getProofFingerprint("token-beta-456");

      expect(fp1).toBe(fp2);
      expect(fp1).toMatch(/^SHA-256:[a-f0-9]{8}\.\.\.[a-f0-9]{8}$/);
      expect(fp1).not.toBe(fp3);
    });

    it("calculates accurate expiry countdowns for active, near-expiry, and expired states", () => {
      // No expiry
      const noExp = getExpiryCountdown(null, "vi");
      expect(noExp.isExpired).toBe(false);
      expect(noExp.tone).toBe("neutral");

      // 5 days future
      const future = getExpiryCountdown(
        new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
        "vi",
      );
      expect(future.isExpired).toBe(false);
      expect(future.tone).toBe("ok");
      expect(future.label).toContain("Còn 5 ngày");

      // 6 hours future
      const soon = getExpiryCountdown(
        new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(),
        "vi",
      );
      expect(soon.isExpired).toBe(false);
      expect(soon.tone).toBe("warn");
      expect(soon.label).toContain("Hết hạn sau 6 giờ");

      // Expired 1 hour ago
      const expired = getExpiryCountdown(
        new Date(Date.now() - 60 * 60 * 1000).toISOString(),
        "vi",
      );
      expect(expired.isExpired).toBe(true);
      expect(expired.tone).toBe("danger");
      expect(expired.label).toContain("Đã hết hạn");
    });
  });

  describe("SharedConversationClient component rendering", () => {
    it("renders Shell: PUBLIC_SHARE, Archetype: Public Shared Packet Reader attributes", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      render(<SharedConversationClient token="test-token-123" />);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });

      const root = screen.getByTestId("public-shared-packet-reader");
      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_SHARE");
      expect(root).toHaveAttribute(
        "data-layout-archetype",
        "Public Shared Packet Reader",
      );
    });

    it("renders Standalone Brand Header with read-only badge and no authenticated navigation", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      render(<SharedConversationClient token="test-token-123" />);

      await waitFor(() => {
        expect(screen.getByRole("link", { name: /The Clara Care/i })).toBeInTheDocument();
      });

      expect(screen.getByText("Chỉ xem")).toBeInTheDocument();
      // Brand link points to home
      expect(screen.getByRole("link", { name: /The Clara Care/i })).toHaveAttribute(
        "href",
        "/",
      );
    });

    it("renders Cryptographic Proof & Signature Banner with tamper-proof badges", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      render(<SharedConversationClient token="test-token-123" />);

      await waitFor(() => {
        expect(screen.getByTestId("cryptographic-proof-banner")).toBeInTheDocument();
      });

      const banner = screen.getByTestId("cryptographic-proof-banner");
      expect(banner).toHaveTextContent("Bằng chứng mật mã & Tính toàn vẹn");
      expect(banner).toHaveTextContent("Đã xác thực chữ ký số · Zero-Tamper Proof");
      expect(banner).toHaveTextContent("Chuẩn an toàn FIDES");
      expect(banner).toHaveTextContent("SHA-256:");
    });

    it("renders Verified Clinical Timestamp and Expiration Badge", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      render(<SharedConversationClient token="test-token-123" />);

      await waitFor(() => {
        expect(screen.getByTestId("clinical-timestamp")).toBeInTheDocument();
      });

      const timestampCard = screen.getByTestId("clinical-timestamp");
      expect(timestampCard).toHaveTextContent("Thời điểm xác thực lâm sàng");
      expect(timestampCard).toHaveTextContent("Dữ liệu được xác thực và niêm phong mật mã");

      const expiryCard = screen.getByTestId("expiration-badge");
      expect(expiryCard).toHaveTextContent("Liên kết hết hạn");
      expect(expiryCard).toHaveTextContent("Còn 5 ngày");
    });

    it("renders Sanitized Conversation Packet with title, ID, safety notice, and message turns", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      render(<SharedConversationClient token="test-token-123" />);

      await waitFor(() => {
        expect(screen.getByTestId("sanitized-packet")).toBeInTheDocument();
      });

      const packet = screen.getByTestId("sanitized-packet");
      expect(packet).toHaveTextContent("#PKT-88");
      expect(packet).toHaveTextContent("Tư vấn điều trị tăng huyết áp nguyên phát");
      expect(packet).toHaveTextContent("2 lượt trao đổi");
      expect(packet).toHaveTextContent("Lưu ý an toàn: Gói dữ liệu lâm sàng");

      // Verify Query Turns
      expect(screen.getByTestId("shared-query-1001")).toHaveTextContent(
        "Bác sĩ cho tôi hỏi liều dùng khởi đầu của Amlodipine 5mg",
      );
      expect(screen.getByTestId("shared-query-1001")).toHaveTextContent(
        "Người hỏi / Bệnh nhân",
      );

      // Verify Answer Turns
      expect(screen.getByTestId("shared-answer-1001")).toHaveTextContent(
        "Amlodipine 5mg",
      );
      expect(screen.getByTestId("shared-answer-1001")).toHaveTextContent(
        "Trợ lý AI CLARA",
      );
      expect(screen.getByTestId("shared-answer-1001")).toHaveTextContent(
        "Tổng hợp AI & Đối chiếu FIDES",
      );

      // Verify Provenance
      expect(screen.getByTestId("packet-provenance")).toHaveTextContent(
        "Dược thư Quốc gia Việt Nam 2022 · Bộ Y tế · openFDA · DrugBank v5.1",
      );
    });

    it("renders Medical Research Report role when sharing research outputs", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockResearchReport,
      );

      render(<SharedConversationClient token="research-token-789" />);

      await waitFor(() => {
        expect(screen.getByTestId("sanitized-packet")).toBeInTheDocument();
      });

      expect(screen.getByText("Báo cáo nghiên cứu y khoa")).toBeInTheDocument();
      expect(screen.getByText(/Nghiên cứu DAPA-HF và DELIVER/i)).toBeInTheDocument();
    });

    it("renders Expired/Revoked/Invalid State gracefully with PII-free warning", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockRejectedValue(
        new Error("Public share unavailable"),
      );

      render(<SharedConversationClient token="invalid-or-revoked-token" />);

      await waitFor(() => {
        expect(screen.getByTestId("expired-revoked-state")).toBeInTheDocument();
      });

      const errorCard = screen.getByTestId("expired-revoked-state");
      expect(errorCard).toHaveTextContent(
        "Liên kết chia sẻ không hợp lệ, đã hết hạn hoặc đã bị thu hồi.",
      );
      expect(errorCard).toHaveTextContent("Đã hết hạn");
      expect(errorCard).toHaveTextContent("Zero-CoT Privacy Safe");
      expect(screen.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute(
        "href",
        "/",
      );
    });
  });

  describe("Async Server Page Components", () => {
    it("renders /share/[token] page with resolved params", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      const page = await SharedConversationPage({
        params: Promise.resolve({ token: "share-page-token" }),
      });

      render(page);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });
      expect(workspaceModule.getWorkspacePublicConversation).toHaveBeenCalledWith(
        "share-page-token",
      );
    });

    it("renders /chat/share/[token] page with resolved params", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(
        mockConversation,
      );

      const page = await ChatSharePage({
        params: Promise.resolve({ token: "chat-share-page-token" }),
      });

      render(page);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });
      expect(workspaceModule.getWorkspacePublicConversation).toHaveBeenCalledWith(
        "chat-share-page-token",
      );
    });
  });
});
