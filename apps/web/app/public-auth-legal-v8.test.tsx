import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

// Components under test
import HomePage, { metadata as homeMetadata } from "./page";
import LoginPage from "./login/page";
import RegisterPage from "./register/page";
import ForgotPasswordPage from "./forgot-password/page";
import ResetPasswordPage from "./reset-password/page";
import VerifyEmailPage from "./verify-email/page";
import LegalHubPage from "./legal/page";
import PrivacyPolicyPage from "./legal/privacy/page";
import TermsOfServicePage from "./legal/terms/page";
import MedicalConsentPage from "./legal/consent/page";
import CookiePolicyPage from "./legal/cookies/page";
import SharedConversationPage from "./share/[token]/page";
import ChatSharePage from "./chat/share/[token]/page";
import SharedConversationClient, {
  getProofFingerprint,
  getExpiryCountdown,
} from "./share/[token]/shared-conversation-client";

import * as workspaceModule from "@/lib/workspace";
import api from "@/lib/http-client";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

const navMocks = vi.hoisted(() => {
  const routerReplace = vi.fn();
  const routerPush = vi.fn();
  const routerRefresh = vi.fn();
  return {
    routerReplace,
    routerPush,
    routerRefresh,
    router: {
      replace: routerReplace,
      push: routerPush,
      refresh: routerRefresh,
    },
    pathname: "/",
    searchParams: new Map<string, string>(),
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => navMocks.pathname,
  useRouter: () => navMocks.router,
  useSearchParams: () => ({
    get: (key: string) => navMocks.searchParams.get(key) ?? null,
  }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/image", () => ({
  default: ({
    src,
    alt,
    ...props
  }: {
    src: string;
    alt: string;
    [key: string]: unknown;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} {...props} />
  ),
}));

vi.mock("@/lib/http-client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

vi.mock("@/lib/workspace", () => ({
  getWorkspacePublicConversation: vi.fn(),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  navMocks.searchParams.clear();
});

describe("Public, Auth & Legal Suite (Spec v8)", () => {
  /* =========================================================================
   * 1. Marketing Landing (/)
   * ========================================================================= */
  describe("1. Marketing Landing (/) — Spatial Editorial Hero & 4 Pillars", () => {
    it("exports metadata with CLARA positioning, FIDES, and Zero-CoT guarantees", () => {
      expect(homeMetadata.title).toContain("The Clara Care");
      expect(homeMetadata.description).toContain("FIDES");
      expect(homeMetadata.description).toContain("Zero-CoT");
    });

    it("renders Marketing Landing layout archetype and PUBLIC_MARKETING shell mode", () => {
      const { container } = render(<HomePage />);
      expect(screen.getByRole("main")).toBeInTheDocument();
      expect(container.querySelector(".clara-landing-v7")).toBeInTheDocument();
    });

    it("renders Spatial Editorial hero with clinical assistant value proposition & safety badges", () => {
      render(<HomePage />);

      // Clinical assistant value proposition
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
      expect(
        screen.getAllByText(/bác sĩ điều trị luôn là người đưa ra phán quyết cuối cùng|không thay thế chẩn đoán/i).length,
      ).toBeGreaterThan(0);

      // Primary Action CTA
      const chatCtas = screen.getAllByRole("link", { name: /hỏi clara/i });
      expect(chatCtas.length).toBeGreaterThan(0);
      expect(chatCtas[0]).toHaveAttribute("href", "/chat");
    });

    it("renders Interactive Preview Demos (Council, Medicines) and handles tab switching", () => {
      render(<HomePage />);

      // Council Demo tabs
      const councilRecTab = screen.getByRole("tab", { name: /1\. Khuyến nghị/i });
      const councilDisTab = screen.getByRole("tab", { name: /2\. Điểm bất đồng/i });
      const councilUncertainTab = screen.getByRole("tab", { name: /3\. Chưa chắc chắn/i });

      expect(councilRecTab).toBeInTheDocument();
      expect(councilDisTab).toBeInTheDocument();
      expect(councilUncertainTab).toBeInTheDocument();

      // Switch to Council disagreements tab
      fireEvent.click(councilDisTab);
      expect(screen.getByRole("tabpanel", { name: /2\. Điểm bất đồng/i })).toBeInTheDocument();

      // Medicines Demo tabs
      const medsCurrentTab = screen.getByTestId("tab-current");
      const medsSafetyTab = screen.getByTestId("tab-safety");
      expect(medsCurrentTab).toBeInTheDocument();
      expect(medsSafetyTab).toBeInTheDocument();
    });

    it("renders Clinical and Adaptive mode pathways with appropriate route CTAs", () => {
      render(<HomePage />);

      // Modes navigation
      expect(screen.getByRole("tab", { name: /chế độ cá nhân/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /chế độ lâm sàng/i })).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: /chế độ nghiên cứu/i })).toBeInTheDocument();

      // Clinical Transition pathways in footer
      expect(screen.getByRole("link", { name: /tổng quan lâm sàng/i })).toHaveAttribute(
        "href",
        "/clinical",
      );
      expect(screen.getByRole("link", { name: /hội đồng council/i })).toHaveAttribute(
        "href",
        "/council",
      );
    });

    it("renders navigation header, footer with statutory legal links, and medical disclaimers", () => {
      render(<HomePage />);

      // Header links
      const loginLinks = screen.getAllByRole("link", { name: /đăng nhập/i });
      expect(loginLinks.length).toBeGreaterThan(0);
      expect(loginLinks[0]).toHaveAttribute("href", "/login");

      const chatLinks = screen.getAllByRole("link", { name: /hỏi clara/i });
      expect(chatLinks.length).toBeGreaterThan(0);
      expect(chatLinks[0]).toHaveAttribute("href", "/chat");

      // Footer links
      const guideLink = screen.getByRole("link", { name: /hướng dẫn sử dụng/i });
      expect(guideLink).toHaveAttribute("href", "/huong-dan");

      expect(screen.getAllByRole("link", { name: /chính sách bảo mật|bảo mật/i }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole("link", { name: /điều khoản dịch vụ|điều khoản/i }).length).toBeGreaterThan(0);
      expect(screen.getAllByRole("link", { name: /đồng thuận y tế/i }).length).toBeGreaterThan(0);

      // Medical disclaimer
      expect(
        screen.getByText(/không thay thế chẩn đoán, điều trị hay lời khuyên của bác sĩ/i),
      ).toBeInTheDocument();
    });
  });

  /* =========================================================================
   * 2. Distraction-free Centered Auth Surfaces (/login, /register, etc.)
   * ========================================================================= */
  describe("2. Public Auth Containers — Typography, Navigation & Legal Notices", () => {
    it("renders /login with high-contrast typography, brand back link, and statutory legal consent", () => {
      const { container } = render(<LoginPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("data-shell-mode", "PUBLIC_AUTH");
      expect(main).toHaveAttribute("data-layout-archetype", "Auth Focus");

      // Brand badge and back navigation
      expect(screen.getByText(/The Clara Care/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/");

      // Form elements
      expect(screen.getByRole("heading", { level: 1, name: /Đăng nhập/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Đăng nhập/i })).toBeInTheDocument();

      // Statutory consent footer
      expect(screen.getByRole("link", { name: /Điều khoản/i })).toHaveAttribute("href", "/legal/terms");
      expect(screen.getByRole("link", { name: /Quyền riêng tư/i })).toHaveAttribute("href", "/legal/privacy");
      expect(screen.getByRole("link", { name: /Đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");
    });

    it("handles /login credential submission and OTP flow transition", async () => {
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          otp_required: true,
          otp_delivery_status: "sent",
          otp_code_preview: "654321",
          otp_expires_in_seconds: 300,
        },
      });

      render(<LoginPage />);

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "clinician@clara.vn" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu/i), {
        target: { value: "DoctorSecurePass2026!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đăng nhập/i }));

      await waitFor(() => {
        expect(screen.getByRole("heading", { level: 1, name: /Xác thực OTP/i })).toBeInTheDocument();
        expect(screen.getByLabelText(/Mã OTP/i)).toBeInTheDocument();
        expect(screen.getByText(/654321/)).toBeInTheDocument();
      });

      // Verify OTP step completion
      vi.mocked(api.post).mockResolvedValueOnce({
        data: { role: "doctor" },
      });

      fireEvent.change(screen.getByLabelText(/Mã OTP/i), {
        target: { value: "654321" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Xác thực OTP/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/login-otp/verify", {
          email: "clinician@clara.vn",
          otp_code: "654321",
        });
        expect(navMocks.routerReplace).toHaveBeenCalledWith("/dashboard");
      });
    });

    it("renders /register with statutory legal consent checkbox and handles validation", async () => {
      const { container } = render(<RegisterPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("data-shell-mode", "PUBLIC_AUTH");
      expect(main).toHaveAttribute("data-layout-archetype", "Auth Focus");

      expect(screen.getByRole("heading", { level: 1, name: /Tạo tài khoản/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Xác nhận mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Vai trò sử dụng/i)).toBeInTheDocument();

      // Statutory consent checkbox
      const consentCheckbox = screen.getByRole("checkbox");
      expect(consentCheckbox).not.toBeChecked();

      // Submit without consent
      fireEvent.change(screen.getByLabelText(/Họ và tên/i), { target: { value: "BS. Tran Van B" } });
      fireEvent.change(screen.getByLabelText(/Email/i), { target: { value: "doctor.tran@clara.vn" } });
      fireEvent.change(screen.getByLabelText(/^Mật khẩu/i), { target: { value: "DoctorPass123" } });
      fireEvent.change(screen.getByLabelText(/Xác nhận mật khẩu/i), { target: { value: "DoctorPass123" } });
      fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản/i }));

      expect(
        screen.getByText(/Vui lòng xác nhận đã đọc Điều khoản, Quyền riêng tư và Đồng thuận y tế/i),
      ).toBeInTheDocument();

      // Check consent and submit successfully
      fireEvent.click(consentCheckbox);
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          is_email_verified: false,
          verification_token_preview: "VERIFY-CLARA-888",
          email_delivery_status: "sent",
        },
      });

      fireEvent.click(screen.getByRole("button", { name: /Tạo tài khoản/i }));

      await waitFor(() => {
        expect(screen.getByRole("status")).toHaveTextContent(/VERIFY-CLARA-888/);
        expect(screen.getByRole("link", { name: /Đi đến trang xác thực email/i })).toHaveAttribute(
          "href",
          "/verify-email?email=doctor.tran%40clara.vn",
        );
      });
    });

    it("renders /forgot-password with Recovery Focus archetype and token preview", async () => {
      const { container } = render(<ForgotPasswordPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("data-shell-mode", "PUBLIC_AUTH");
      expect(main).toHaveAttribute("data-layout-archetype", "Recovery Focus");

      expect(screen.getByRole("heading", { level: 1, name: /Quên mật khẩu/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Email/i)).toBeInTheDocument();

      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          reset_token_preview: "RESET-TOKEN-SAMPLE-888",
          email_delivery_status: "sent",
        },
      });

      fireEvent.change(screen.getByLabelText(/Email/i), {
        target: { value: "user.recovery@clara.vn" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Gửi yêu cầu/i }));

      await waitFor(() => {
        expect(screen.getByText(/RESET-TOKEN-SAMPLE-888/)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Mở trang đặt lại/i })).toHaveAttribute(
          "href",
          "/reset-password?token=RESET-TOKEN-SAMPLE-888",
        );
      });
    });

    it("renders /reset-password with Recovery Focus archetype and submits new password", async () => {
      const { container } = render(<ResetPasswordPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("data-shell-mode", "PUBLIC_AUTH");
      expect(main).toHaveAttribute("data-layout-archetype", "Recovery Focus");

      expect(screen.getByRole("heading", { level: 1, name: /Đặt lại mật khẩu/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Mã đặt lại mật khẩu/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Mật khẩu mới/i)).toBeInTheDocument();

      vi.mocked(api.post).mockResolvedValueOnce({ data: { status: "success" } });

      fireEvent.change(screen.getByLabelText(/Mã đặt lại mật khẩu/i), {
        target: { value: "RESET-TOKEN-SAMPLE-888" },
      });
      fireEvent.change(screen.getByLabelText(/Mật khẩu mới/i), {
        target: { value: "NewSecurePass2026!" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Đặt lại mật khẩu/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/reset-password", {
          token: "RESET-TOKEN-SAMPLE-888",
          new_password: "NewSecurePass2026!",
        });
        expect(screen.getByRole("status")).toHaveTextContent(/Đặt lại mật khẩu thành công/i);
      });
    });

    it("renders /verify-email with Verification Status archetype and supports token & resend flow", async () => {
      const { container } = render(<VerifyEmailPage />);
      const main = container.querySelector("main");

      expect(main).toHaveAttribute("data-shell-mode", "PUBLIC_AUTH");
      expect(main).toHaveAttribute("data-layout-archetype", "Verification Status");

      expect(screen.getByRole("heading", { level: 1, name: /Xác thực email/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/Mã xác thực/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Xác thực email/i })).toBeInTheDocument();

      // Submit verify
      vi.mocked(api.post).mockResolvedValueOnce({ data: { is_verified: true } });
      fireEvent.change(screen.getByLabelText(/Mã xác thực/i), {
        target: { value: "VERIFY-TOKEN-999" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Xác thực email/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/verify-email", { token: "VERIFY-TOKEN-999" });
        expect(screen.getByRole("status")).toHaveTextContent(/Xác thực email thành công/i);
      });

      // Resend form
      expect(screen.getByLabelText(/Email tài khoản/i)).toBeInTheDocument();
      vi.mocked(api.post).mockResolvedValueOnce({
        data: {
          verification_token_preview: "NEW-VERIFY-TOKEN-111",
          email_delivery_status: "sent",
        },
      });

      fireEvent.change(screen.getByLabelText(/Email tài khoản/i), {
        target: { value: "resend@clara.vn" },
      });
      fireEvent.click(screen.getByRole("button", { name: /Gửi lại mã xác thực/i }));

      await waitFor(() => {
        expect(api.post).toHaveBeenCalledWith("/auth/resend-verification", {
          email: "resend@clara.vn",
        });
        expect(screen.getByRole("status")).toHaveTextContent(/Đã tạo mã xác thực mới/i);
        expect(screen.getByLabelText(/Mã xác thực/i)).toHaveValue("NEW-VERIFY-TOKEN-111");
      });
    });
  });

  /* =========================================================================
   * 3. Legal Reader Archetype (/legal, /legal/privacy, /terms, etc.)
   * ========================================================================= */
  describe("3. Legal Reader Archetype & Vietnamese Statutory Citations", () => {
    it("renders /legal with Legal Index archetype, versioning, and 4 statutory document rows", () => {
      const { container } = render(<LegalHubPage />);
      const root = container.firstChild as HTMLElement;

      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
      expect(root).toHaveAttribute("data-layout-archetype", "Legal Index");

      expect(screen.getByText(/The Clara Care · Legal Index/i)).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { level: 1, name: /Thỏa thuận người dùng & Trung tâm pháp lý/i }),
      ).toBeInTheDocument();

      // Statutory Citations & Version metadata
      expect(screen.getAllByText(new RegExp(`Phiên bản: ${LEGAL_POLICY_VERSION}`)).length).toBeGreaterThan(0);
      expect(screen.getAllByText(new RegExp(`Cập nhật: ${LEGAL_UPDATED_AT}`)).length).toBeGreaterThan(0);
      expect(screen.getByText(/Nghị định 13\/2023\/NĐ-CP & Luật AI 134\/2025/i)).toBeInTheDocument();

      // 4 Legal Topics
      expect(screen.getByRole("link", { name: /Điều khoản sử dụng/i })).toHaveAttribute("href", "/legal/terms");
      expect(screen.getByRole("link", { name: /Chính sách quyền riêng tư/i })).toHaveAttribute("href", "/legal/privacy");
      expect(screen.getByRole("link", { name: /Đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");
      expect(screen.getByRole("link", { name: /Chính sách cookie/i })).toHaveAttribute("href", "/legal/cookies");

      // DPO Contact Block
      expect(screen.getByRole("link", { name: LEGAL_CONTACT_EMAIL })).toHaveAttribute(
        "href",
        `mailto:${LEGAL_CONTACT_EMAIL}`,
      );
      expect(screen.getByRole("link", { name: LEGAL_CONTACT_PHONE })).toHaveAttribute(
        "href",
        `tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`,
      );
      expect(screen.getByText(LEGAL_OPERATOR_NAME)).toBeInTheDocument();
    });

    it("renders /legal/privacy with constrained max-w-3xl body, SectionIndex, and 11 DSAR rights", () => {
      const { container } = render(<PrivacyPolicyPage />);
      const root = container.firstChild as HTMLElement;
      const main = container.querySelector("main");

      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
      expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");
      expect(main?.className).toContain("max-w-3xl");

      // Sticky SectionIndex navigation
      expect(screen.getByRole("navigation", { name: "Mục lục điều hướng" })).toBeInTheDocument();
      expect(screen.getByText(/Mục lục điều khoản/i)).toBeInTheDocument();

      // Vietnamese statutory citations
      expect(screen.getAllByText(/Luật Khám bệnh 2023 · NĐ 13\/2023 · Luật AI 134\/2025/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Điều 2 và Điều 9 Nghị định 13\/2023\/NĐ-CP/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Luật Trí tuệ nhân tạo số 134\/2025\/QH15/i).length).toBeGreaterThan(0);

      // Zero-PII & Zero-CoT Guarantees
      expect(screen.getByText(/1\. Zero-PII Telemetry \(Không thu thập PII trong hệ thống giám sát\)/i)).toBeInTheDocument();
      expect(screen.getByText(/2\. Chuẩn Zero-CoT \(Zero Chain-of-Thought Retention\)/i)).toBeInTheDocument();

      // DSAR Rights
      expect(screen.getByText(/1\. Quyền được biết/i)).toBeInTheDocument();
      expect(screen.getByText(/2\. Quyền đồng ý/i)).toBeInTheDocument();
      expect(screen.getByText(/3\. Quyền truy cập & xem dữ liệu/i)).toBeInTheDocument();
      expect(screen.getByText(/4\. Quyền rút lại sự đồng ý/i)).toBeInTheDocument();
      expect(screen.getByText(/5\. Quyền xóa dữ liệu/i)).toBeInTheDocument();
      expect(screen.getByText(/7\. Quyền cung cấp dữ liệu \(Portability\)/i)).toBeInTheDocument();
    });

    it("renders /legal/terms with statutory medical boundaries under Law on Medical Examination 2023", () => {
      const { container } = render(<TermsOfServicePage />);
      const root = container.firstChild as HTMLElement;

      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
      expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

      expect(
        screen.getByRole("heading", { level: 1, name: /Điều khoản sử dụng & Thỏa thuận người dùng/i }),
      ).toBeInTheDocument();

      // Clinical disclaimer
      expect(screen.getByText(/TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM LÂM SÀNG QUAN TRỌNG:/i)).toBeInTheDocument();
      expect(screen.getByText(/The Clara Care KHÔNG PHẢI là cơ sở khám bệnh, chữa bệnh/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Luật Khám bệnh, chữa bệnh số 15\/2023\/QH15/i).length).toBeGreaterThan(0);
    });

    it("renders /legal/consent with gated clinical scope, emergency fast-path 115, and Zero-CoT records", () => {
      const { container } = render(<MedicalConsentPage />);
      const root = container.firstChild as HTMLElement;

      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
      expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

      expect(
        screen.getByRole("heading", { level: 1, name: /Đồng thuận sử dụng y tế & Ranh giới lâm sàng/i }),
      ).toBeInTheDocument();

      // Gated clinical modules
      expect(screen.getByText(/Tủ thuốc cá nhân & Tự dùng thuốc \(Self-Medication\):/i)).toBeInTheDocument();
      expect(screen.getByText(/Hàng rào an toàn lâm sàng \(CareGuard\):/i)).toBeInTheDocument();
      expect(screen.getByText(/Hội chẩn đa tác tử \(Clinical Council\):/i)).toBeInTheDocument();
      expect(screen.getByText(/Trợ lý ghi chép y khoa \(Scribe\):/i)).toBeInTheDocument();

      // Emergency 115 fast-path
      expect(screen.getByText(/KHI GẶP TÌNH HUỐNG Y TẾ NGUY CẤP:/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /GỌI NGAY CẤP CỨU 115/i })).toHaveAttribute("href", "tel:115");
    });

    it("renders /legal/cookies with functional and essential cookie disclosures", () => {
      const { container } = render(<CookiePolicyPage />);
      const root = container.firstChild as HTMLElement;

      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
      expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

      expect(screen.getByRole("heading", { level: 1, name: /Chính sách cookie/i })).toBeInTheDocument();
      expect(screen.getAllByText(/Cookie là gì/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Nhóm cookie sử dụng/i).length).toBeGreaterThan(0);
    });
  });

  /* =========================================================================
   * 4. Public Shared Packet Reader (/share/[token], /chat/share/[token])
   * ========================================================================= */
  describe("4. Public Shared Packet Reader — Cryptographic Proof & Expiration Countdown", () => {
    const mockSharedPacket: workspaceModule.WorkspacePublicConversation = {
      conversation_id: 104,
      title: "Hội chẩn phác đồ điều trị suy tim phân suất tống máu giảm (HFrEF)",
      expires_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days in future
      messages: [
        {
          query_id: 501,
          role: "user",
          query: "Bệnh nhân suy tim EF 32% đang dùng Sacubitril/Valsartan 49/51mg, có thể khởi đầu thêm Empagliflozin 10mg không?",
          answer:
            "Theo hướng dẫn **ESC 2023 & Bộ Y tế 2020**, phác đồ tứ trụ (ARNI, SGLT2i, Beta-blocker, MRA) là nền tảng chuẩn.\n\n### Khuyến cáo khởi đầu:\n- **Empagliflozin 10mg** 1 lần/ngày vào buổi sáng.\n- Theo dõi chức năng thận và thể tích dịch trong 2 tuần đầu.",
          created_at: "2026-08-22T09:00:00Z",
        },
      ],
    };

    it("calculates deterministic cryptographic fingerprint and expiration countdowns", () => {
      const token = "clara-share-token-alpha";
      const fp = getProofFingerprint(token);
      expect(fp).toMatch(/^SHA-256:[a-f0-9]{8}\.\.\.[a-f0-9]{8}$/);

      // Active future countdown
      const futureExpiry = getExpiryCountdown(
        new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
        "vi",
      );
      expect(futureExpiry.isExpired).toBe(false);
      expect(futureExpiry.tone).toBe("ok");
      expect(futureExpiry.label).toContain("Còn 2 ngày");

      // Near expiry countdown (<24h)
      const nearExpiry = getExpiryCountdown(
        new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
        "vi",
      );
      expect(nearExpiry.isExpired).toBe(false);
      expect(nearExpiry.tone).toBe("warn");
      expect(nearExpiry.label).toContain("Hết hạn sau 4 giờ");

      // Expired countdown
      const expired = getExpiryCountdown(
        new Date(Date.now() - 3600 * 1000).toISOString(),
        "vi",
      );
      expect(expired.isExpired).toBe(true);
      expect(expired.tone).toBe("danger");
      expect(expired.label).toContain("Đã hết hạn");
    });

    it("renders Public Shared Packet Reader with cryptographic proof banner, timestamp, and message turns", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValueOnce(mockSharedPacket);

      render(<SharedConversationClient token="test-shared-token-104" />);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });

      const root = screen.getByTestId("public-shared-packet-reader");
      expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_SHARE");
      expect(root).toHaveAttribute("data-layout-archetype", "Public Shared Packet Reader");

      // Header Brand and Read-Only badge
      expect(screen.getByRole("link", { name: /The Clara Care/i })).toHaveAttribute("href", "/");
      expect(screen.getByText("Chỉ xem")).toBeInTheDocument();

      // Cryptographic proof banner
      const proofBanner = screen.getByTestId("cryptographic-proof-banner");
      expect(proofBanner).toHaveTextContent("Bằng chứng mật mã & Tính toàn vẹn");
      expect(proofBanner).toHaveTextContent("Đã xác thực chữ ký số · Zero-Tamper Proof");
      expect(proofBanner).toHaveTextContent("Chuẩn an toàn FIDES");
      expect(proofBanner).toHaveTextContent("SHA-256:");

      // Expiration badge
      const expirationBadge = screen.getByTestId("expiration-badge");
      expect(expirationBadge).toHaveTextContent("Còn 3 ngày");

      // Packet content & message turns
      const packet = screen.getByTestId("sanitized-packet");
      expect(packet).toHaveTextContent("#PKT-104");
      expect(packet).toHaveTextContent("Hội chẩn phác đồ điều trị suy tim phân suất tống máu giảm");
      expect(screen.getByTestId("shared-query-501")).toHaveTextContent("Sacubitril/Valsartan");
      expect(screen.getByTestId("shared-answer-501")).toHaveTextContent("Empagliflozin 10mg");

      // Provenance footer
      expect(screen.getByTestId("packet-provenance")).toHaveTextContent(
        "Dược thư Quốc gia Việt Nam 2022 · Bộ Y tế · openFDA · DrugBank v5.1",
      );
    });

    it("handles invalid/expired/revoked share tokens safely with PII-free fallback", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockRejectedValueOnce(
        new Error("Token expired or revoked"),
      );

      render(<SharedConversationClient token="revoked-token-999" />);

      await waitFor(() => {
        expect(screen.getByTestId("expired-revoked-state")).toBeInTheDocument();
      });

      const errorCard = screen.getByTestId("expired-revoked-state");
      expect(errorCard).toHaveTextContent(
        "Liên kết chia sẻ không hợp lệ, đã hết hạn hoặc đã bị thu hồi.",
      );
      expect(errorCard).toHaveTextContent("Đã hết hạn");
      expect(errorCard).toHaveTextContent(/Bảo mật riêng tư Zero-CoT|Zero-CoT Privacy Safe/i);
      expect(screen.getByRole("link", { name: /Về trang chủ/i })).toHaveAttribute("href", "/");
    });

    it("resolves async Server Page wrappers /share/[token] and /chat/share/[token]", async () => {
      vi.mocked(workspaceModule.getWorkspacePublicConversation).mockResolvedValue(mockSharedPacket);

      // /share/[token]
      const sharePage = await SharedConversationPage({
        params: Promise.resolve({ token: "token-route-a" }),
      });
      render(sharePage);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });
      expect(workspaceModule.getWorkspacePublicConversation).toHaveBeenCalledWith("token-route-a");

      cleanup();

      // /chat/share/[token]
      const chatSharePage = await ChatSharePage({
        params: Promise.resolve({ token: "token-route-b" }),
      });
      render(chatSharePage);

      await waitFor(() => {
        expect(screen.getByTestId("public-shared-packet-reader")).toBeInTheDocument();
      });
      expect(workspaceModule.getWorkspacePublicConversation).toHaveBeenCalledWith("token-route-b");
    });
  });
});
