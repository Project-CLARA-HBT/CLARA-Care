import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import LegalHubPage from "./page";
import PrivacyPolicyPage from "./privacy/page";
import TermsOfServicePage from "./terms/page";
import MedicalConsentPage from "./consent/page";
import CookiePolicyPage from "./cookies/page";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

afterEach(cleanup);

describe("LegalHubPage (/legal - Spec v5 Section 6.7 Legal Index)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders public legal header with title, policy version, updated date, and navigation links", () => {
    const { container } = render(<LegalHubPage />);

    // Header eyebrow and title
    expect(screen.getByText(/The Clara Care · Legal Index/i)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: /Thỏa thuận người dùng & Trung tâm pháp lý/i }),
    ).toBeInTheDocument();

    // Navigation links
    const homeLink = screen.getByRole("link", { name: /Về trang chủ/i });
    expect(homeLink).toHaveAttribute("href", "/");

    const guideLink = screen.getByRole("link", { name: /Trung tâm hướng dẫn/i });
    expect(guideLink).toHaveAttribute("href", "/huong-dan");

    const loginLink = screen.getByRole("link", { name: /Đăng nhập/i });
    expect(loginLink).toHaveAttribute("href", "/login");

    // Version and metadata badges
    expect(screen.getAllByText(new RegExp(`Phiên bản: ${LEGAL_POLICY_VERSION}`)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(new RegExp(`Cập nhật: ${LEGAL_UPDATED_AT}`)).length).toBeGreaterThan(0);
    expect(screen.getByText(LEGAL_PRIMARY_DOMAIN)).toBeInTheDocument();
    expect(screen.getByText(/Nghị định 13\/2023\/NĐ-CP & Luật AI 134\/2025/i)).toBeInTheDocument();

    // Verify no legacy chrome-shell / chrome-panel classes
    expect(container.querySelector(".chrome-shell")).toBeNull();
    expect(container.querySelector(".chrome-panel")).toBeNull();
  });

  it("renders editorial intro explaining CLARA's privacy, transparency, and data boundaries", () => {
    render(<LegalHubPage />);

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /Cam kết bảo vệ dữ liệu, tính minh bạch và ranh giới lâm sàng/i,
      }),
    ).toBeInTheDocument();

    // Privacy & Zero-CoT
    expect(screen.getByText(/1\. Quyền riêng tư & Chuẩn Zero-CoT/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Dữ liệu sức khỏe cá nhân \(PHR\) và các nội dung trao đổi lâm sàng được bảo vệ nghiêm ngặt/i),
    ).toBeInTheDocument();

    // AI Transparency
    expect(screen.getByText(/2\. Minh bạch hệ thống AI \(Luật 134\/2025\)/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Mọi khuyến nghị y khoa đều minh bạch về họ mô hình AI suy luận/i),
    ).toBeInTheDocument();

    // Data Boundaries & Clinical Safety
    expect(screen.getByText(/3\. Ranh giới dữ liệu & Trách nhiệm lâm sàng/i)).toBeInTheDocument();
    expect(
      screen.getByText(/CLARA là trợ lý tham vấn và hỗ trợ ra quyết định lâm sàng/i),
    ).toBeInTheDocument();
  });

  it("renders 4 legal topics as vertical list rows with descriptions, revision dates, and arrow indicators", () => {
    render(<LegalHubPage />);

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /Danh mục văn bản pháp lý chính thức/i,
      }),
    ).toBeInTheDocument();

    // 1. Terms of Service
    const termsLink = screen.getByRole("link", { name: /Điều khoản sử dụng/i });
    expect(termsLink).toHaveAttribute("href", "/legal/terms");
    expect(
      screen.getByText(
        /Quy định quyền và nghĩa vụ pháp lý khi sử dụng dịch vụ The Clara Care/i,
      ),
    ).toBeInTheDocument();

    // 2. Privacy Policy
    const privacyLink = screen.getByRole("link", { name: /Chính sách quyền riêng tư/i });
    expect(privacyLink).toHaveAttribute("href", "/legal/privacy");
    expect(
      screen.getByText(
        /Mô tả chi tiết cách thức thu thập, xử lý, bảo vệ dữ liệu cá nhân & PHR theo Nghị định 13\/2023\/NĐ-CP/i,
      ),
    ).toBeInTheDocument();

    // 3. Medical Consent
    const consentLink = screen.getByRole("link", { name: /Đồng thuận y tế/i });
    expect(consentLink).toHaveAttribute("href", "/legal/consent");
    expect(
      screen.getByText(
        /Điều khoản bắt buộc trước khi sử dụng các tính năng có tác động lâm sàng/i,
      ),
    ).toBeInTheDocument();

    // 4. Cookie Policy
    const cookiesLink = screen.getByRole("link", { name: /Chính sách cookie/i });
    expect(cookiesLink).toHaveAttribute("href", "/legal/cookies");
    expect(
      screen.getByText(
        /Chi tiết về cookie cần thiết, cookie chức năng lưu tùy chọn giao diện/i,
      ),
    ).toBeInTheDocument();

    // Verify arrow indicators are present inside rows
    const listItems = screen.getAllByRole("listitem");
    expect(listItems).toHaveLength(4);
    listItems.forEach((item) => {
      const arrowIcon = item.querySelector('[data-icon="arrow-right"]');
      expect(arrowIcon).toBeInTheDocument();
    });
  });

  it("renders Data Protection Officer (DPO) and compliance contact block", () => {
    render(<LegalHubPage />);

    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /Cán bộ bảo vệ dữ liệu \(DPO\) & Thông tin tuân thủ/i,
      }),
    ).toBeInTheDocument();

    // DPO Contact
    const dpoEmailLink = screen.getByRole("link", { name: LEGAL_CONTACT_EMAIL });
    expect(dpoEmailLink).toHaveAttribute("href", `mailto:${LEGAL_CONTACT_EMAIL}`);

    const phoneLink = screen.getByRole("link", { name: LEGAL_CONTACT_PHONE });
    expect(phoneLink).toHaveAttribute("href", `tel:${LEGAL_CONTACT_PHONE.replace(/\s+/g, "")}`);

    // Operator and domain
    expect(screen.getByText(LEGAL_OPERATOR_NAME)).toBeInTheDocument();
    expect(screen.getByText(`https://${LEGAL_PRIMARY_DOMAIN}`)).toBeInTheDocument();
    expect(screen.getByText(/Trong 72 giờ làm việc/i)).toBeInTheDocument();
  });
});

describe("PrivacyPolicyPage (/legal/privacy - Spec v5 Section 6.10 Legal Document Reader)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders Legal Reader shell with max-w-3xl constrained editorial body and sticky SectionIndex", () => {
    const { container } = render(<PrivacyPolicyPage />);

    // Header title and metadata
    expect(
      screen.getByRole("heading", { level: 1, name: /Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân/i }),
    ).toBeInTheDocument();

    // Constrained editorial reading body
    const mainEl = container.querySelector("main");
    expect(mainEl).not.toBeNull();
    expect(mainEl?.className).toContain("max-w-3xl");

    // SectionIndex is rendered
    expect(screen.getByRole("navigation", { name: "Mục lục điều hướng" })).toBeInTheDocument();
    expect(screen.getByText(/Mục lục điều khoản/i)).toBeInTheDocument();
    expect(screen.getAllByText(/1\. Phạm vi áp dụng & Phân định vai trò/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/3\. Cam kết Zero-PII & Chuẩn Zero-CoT/i).length).toBeGreaterThan(0);

    // Verify no legacy chrome classes
    expect(container.querySelector(".chrome-shell")).toBeNull();
    expect(container.querySelector(".chrome-panel")).toBeNull();
  });

  it("renders revision metadata, Vietnamese legal citations, and zero-PII / Zero-CoT guarantees", () => {
    render(<PrivacyPolicyPage />);

    // Metadata badges
    expect(screen.getByText(`Phiên bản: ${LEGAL_POLICY_VERSION}`)).toBeInTheDocument();
    expect(screen.getByText(`Cập nhật: ${LEGAL_UPDATED_AT}`)).toBeInTheDocument();
    expect(screen.getAllByText(LEGAL_PRIMARY_DOMAIN).length).toBeGreaterThan(0);

    // Vietnamese Legal Citations
    expect(screen.getAllByText(/Luật Khám bệnh 2023 · NĐ 13\/2023 · Luật AI 134\/2025/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Luật Khám bệnh, chữa bệnh 2023 \(Luật số 15\/2023\/QH15\)/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Điều 2 và Điều 9 Nghị định 13\/2023\/NĐ-CP/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Luật Trí tuệ nhân tạo số 134\/2025\/QH15/i).length).toBeGreaterThan(0);

    // Zero-PII and Zero-CoT explicit guarantees
    expect(screen.getAllByText(/Bảo đảm Zero-CoT · Zero-PII Telemetry/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/1\. Zero-PII Telemetry \(Không thu thập PII trong hệ thống giám sát\)/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Chuẩn Zero-CoT \(Zero Chain-of-Thought Retention\)/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Tuyệt đối không dùng dữ liệu người dùng để huấn luyện AI công cộng/i)).toBeInTheDocument();

    // Processors and DPO contact
    expect(screen.getByText(/YEScale — điểm cuối DeepSeek/i)).toBeInTheDocument();
    const emailLinks = screen.getAllByRole("link", { name: LEGAL_CONTACT_EMAIL });
    expect(emailLinks.length).toBeGreaterThan(0);
    expect(emailLinks[0]).toHaveAttribute("href", `mailto:${LEGAL_CONTACT_EMAIL}`);
  });

  it("renders all 11 Data Subject Rights (DSAR) under Decree 13/2023/ND-CP", () => {
    render(<PrivacyPolicyPage />);

    expect(screen.getByText(/1\. Quyền được biết/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Quyền đồng ý & rút đồng thuận/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Quyền truy cập & xem dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Quyền xóa dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/5\. Quyền hạn chế xử lý/i)).toBeInTheDocument();
    expect(screen.getByText(/6\. Quyền cung cấp dữ liệu \(Portability\)/i)).toBeInTheDocument();
    expect(screen.getByText(/7\. Quyền phản đối xử lý dữ liệu/i)).toBeInTheDocument();
    expect(screen.getByText(/8\. Quyền khiếu nại & khởi kiện/i)).toBeInTheDocument();
    expect(screen.getAllByText(/72 giờ làm việc/i).length).toBeGreaterThan(0);
  });
});

describe("TermsOfServicePage (/legal/terms - Spec v5 Section 6.11 Legal Document Reader)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders Legal Reader layout with constrained max-w-3xl body and SectionIndex", () => {
    const { container } = render(<TermsOfServicePage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Điều khoản sử dụng & Thỏa thuận người dùng/i }),
    ).toBeInTheDocument();

    const mainEl = container.querySelector("main");
    expect(mainEl).not.toBeNull();
    expect(mainEl?.className).toContain("max-w-3xl");

    expect(screen.getByRole("navigation", { name: "Mục lục điều hướng" })).toBeInTheDocument();
    expect(screen.getAllByText(/Điều 1: Giải thích từ ngữ/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Điều 5: Ranh giới y tế & Giới hạn lâm sàng/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Điều 6: Bảo mật, Zero-PII & Chuẩn Zero-CoT/i).length).toBeGreaterThan(0);

    expect(container.querySelector(".chrome-shell")).toBeNull();
  });

  it("renders Vietnamese statutory citations, clinical disclaimer under Law on Medical Examination 2023, and entity info", () => {
    render(<TermsOfServicePage />);

    // Vietnamese Legal Citations
    expect(screen.getAllByText(/Luật Khám bệnh, chữa bệnh số 15\/2023\/QH15/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Nghị định số 13\/2023\/NĐ-CP/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Luật Trí tuệ nhân tạo số 134\/2025\/QH15/i).length).toBeGreaterThan(0);

    // Clinical Disclaimer under Law 2023
    expect(screen.getByText(/TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM LÂM SÀNG QUAN TRỌNG:/i)).toBeInTheDocument();
    expect(
      screen.getByText(
        /The Clara Care KHÔNG PHẢI là cơ sở khám bệnh, chữa bệnh/i,
      ),
    ).toBeInTheDocument();

    // Zero-CoT / Zero-PII standards
    expect(screen.getByText(/Bảo đảm Zero-CoT:/i)).toBeInTheDocument();
    expect(screen.getByText(/Zero-PII Telemetry:/i)).toBeInTheDocument();

    // Entity Information
    expect(screen.getAllByText(LEGAL_OPERATOR_NAME).length).toBeGreaterThan(0);
    expect(screen.getAllByText(new RegExp(LEGAL_PRIMARY_DOMAIN)).length).toBeGreaterThan(0);
  });
});

describe("MedicalConsentPage (/legal/consent - Spec v5 Section 6.8 Legal Document Reader)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders Legal Reader layout with constrained max-w-3xl body and SectionIndex", () => {
    const { container } = render(<MedicalConsentPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Đồng thuận sử dụng y tế & Ranh giới lâm sàng/i }),
    ).toBeInTheDocument();

    const mainEl = container.querySelector("main");
    expect(mainEl).not.toBeNull();
    expect(mainEl?.className).toContain("max-w-3xl");

    expect(screen.getByRole("navigation", { name: "Mục lục điều hướng" })).toBeInTheDocument();
    expect(screen.getAllByText(/1\. Bản chất hệ thống AI hỗ trợ lâm sàng/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/4\. Yêu cầu xác nhận chuyên môn y tế/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/5\. Luồng xử lý tình huống khẩn cấp \(115\)/i).length).toBeGreaterThan(0);

    expect(container.querySelector(".chrome-shell")).toBeNull();
  });

  it("renders mandatory gated scope, emergency fast-path 115, and Zero-CoT/Zero-PII consent records", () => {
    render(<MedicalConsentPage />);

    // Mandatory gated scope
    expect(screen.getByText(/Tủ thuốc cá nhân & Tự dùng thuốc \(Self-Medication\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Hàng rào an toàn lâm sàng \(CareGuard\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Hội chẩn đa tác tử \(Clinical Council\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Trợ lý ghi chép y khoa \(Scribe\):/i)).toBeInTheDocument();

    // Emergency fast-path 115
    expect(screen.getByText(/KHI GẶP TÌNH HUỐNG Y TẾ NGUY CẤP:/i)).toBeInTheDocument();
    const tel115Link = screen.getByRole("link", { name: /GỌI NGAY CẤP CỨU 115/i });
    expect(tel115Link).toHaveAttribute("href", "tel:115");

    // Zero-CoT & Zero-PII consent audit guarantees
    expect(screen.getByText(/Bản ghi đồng thuận phi định danh:/i)).toBeInTheDocument();
    expect(screen.getByText(/Chuẩn Zero-CoT bất biến:/i)).toBeInTheDocument();

    // Citations
    expect(screen.getByText(/Ranh giới lâm sàng theo Luật Khám bệnh, chữa bệnh số 15\/2023\/QH15:/i)).toBeInTheDocument();
    expect(screen.getAllByText(new RegExp(LEGAL_POLICY_VERSION)).length).toBeGreaterThan(0);
  });
});

describe("CookiePolicyPage (/legal/cookies - Spec v5 Section 6.9 Legal Document Reader)", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders Legal Reader layout with constrained max-w-3xl body and SectionIndex", () => {
    const { container } = render(<CookiePolicyPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /Chính sách cookie/i }),
    ).toBeInTheDocument();

    const mainEl = container.querySelector("main");
    expect(mainEl).not.toBeNull();
    expect(mainEl?.className).toContain("max-w-3xl");

    expect(screen.getByRole("navigation", { name: "Mục lục điều hướng" })).toBeInTheDocument();
    expect(screen.getAllByText(/Cookie là gì/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Nhóm cookie sử dụng/i).length).toBeGreaterThan(0);

    expect(container.querySelector(".chrome-shell")).toBeNull();
  });
});

