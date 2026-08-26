import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

// Components under test
import MedicalConsentPage from "./legal/consent/page";
import CookiePolicyPage from "./legal/cookies/page";
import ContactPage from "./contact/page";
import SafetyManifestoPage from "./safety/page";
import SourcesCatalogPage from "./sources/page";
import RootConsentPage, { metadata as consentMetadata } from "./consent/page";
import RootCookiesPage, { metadata as cookiesMetadata } from "./cookies/page";
import RootTermsPage, { metadata as termsMetadata } from "./terms/page";
import RootPrivacyPage, { metadata as privacyMetadata } from "./privacy/page";

import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_PHONE,
  LEGAL_OPERATOR_NAME,
  LEGAL_POLICY_VERSION,
  LEGAL_PRIMARY_DOMAIN,
  LEGAL_UPDATED_AT,
} from "@/lib/legal";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
  }),
  useSearchParams: () => new Map(),
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

afterEach(cleanup);

describe("1. /legal/consent and /consent — Comprehensive Clinical Consent Agreement", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders /legal/consent with mandatory acceptance gates, emergency fast-path 115, and Zero-CoT records", () => {
    const { container } = render(<MedicalConsentPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Đồng thuận sử dụng y tế & Ranh giới lâm sàng/i,
      }),
    ).toBeInTheDocument();

    // Mandatory acceptance gates for clinical features
    expect(screen.getByText(/Tủ thuốc cá nhân & Tự dùng thuốc \(Self-Medication\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Hàng rào an toàn lâm sàng \(CareGuard\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Hội chẩn đa tác tử \(Clinical Council\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Trợ lý ghi chép y khoa \(Scribe\):/i)).toBeInTheDocument();

    // Clarification that AI does not issue prescriptions or definitive diagnoses
    expect(
      screen.getByText(/KHÔNG PHẢI là bác sĩ/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Ranh giới lâm sàng theo Luật Khám bệnh, chữa bệnh số 15\/2023\/QH15:/i),
    ).toBeInTheDocument();

    // Fast-path emergency escalation (115) protocols
    expect(screen.getByText(/KHI GẶP TÌNH HUỐNG Y TẾ NGUY CẤP:/i)).toBeInTheDocument();
    const telLink = screen.getByRole("link", { name: /GỌI NGAY CẤP CỨU 115/i });
    expect(telLink).toHaveAttribute("href", "tel:115");

    // Consent withdrawal mechanisms and audit logging
    expect(screen.getByRole("heading", { name: /7\. Quyền rút lại đồng thuận & Quản trị quyền dữ liệu \(DSAR\)/i })).toBeInTheDocument();
    expect(screen.getByText(/Chuẩn Zero-CoT bất biến:/i)).toBeInTheDocument();
    expect(screen.getByText(/Bản ghi đồng thuận phi định danh:/i)).toBeInTheDocument();

    // Related controls contain direct link to personal consent ledger
    expect(screen.getAllByRole("link", { name: /Sổ cái đồng thuận cá nhân/i })[0]).toHaveAttribute("href", "/account/consent");
  });

  it("renders /consent root wrapper with canonical alternate to /legal/consent", () => {
    expect(consentMetadata.alternates?.canonical).toBe("/legal/consent");
    const { container } = render(<RootConsentPage />);
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Đồng thuận sử dụng y tế & Ranh giới lâm sàng/i,
      }),
    ).toBeInTheDocument();
  });
});

describe("2. /legal/cookies and /cookies — Detailed Cookie Policy & Management Controls", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders /legal/cookies with essential session cookies, security tokens, preferences, and zero ad tracking", () => {
    const { container } = render(<CookiePolicyPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Legal Reader");

    expect(screen.getByRole("heading", { level: 1, name: /Chính sách cookie/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Cookie là gì/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Các nhóm cookie được sử dụng/i).length).toBeGreaterThan(0);

    // Essential session cookies
    expect(screen.getByText("clara_access_token")).toBeInTheDocument();
    expect(screen.getByText("clara_refresh_token")).toBeInTheDocument();
    expect(screen.getByText("clara_client_session")).toBeInTheDocument();

    // Security tokens (CSRF & X-Session)
    expect(screen.getByText("clara_csrf_token")).toBeInTheDocument();
    expect(screen.getByText(/X-Session-ID \/ clara_sec_nonce/i)).toBeInTheDocument();

    // Preferences & UI settings
    expect(screen.getByText("clara-theme")).toBeInTheDocument();
    expect(screen.getByText("clara-ui-language")).toBeInTheDocument();
    expect(screen.getByText("clara-reduced-motion")).toBeInTheDocument();

    // Zero third-party ad tracking guarantee
    expect(screen.getByText(/Zero Third-Party Ad Tracking & Zero Profiling/i)).toBeInTheDocument();
    expect(screen.getByText(/KHÔNG có cookie quảng cáo của bên thứ ba/i)).toBeInTheDocument();

    // Cookie management controls
    expect(screen.getByTestId("cookie-manager-controls")).toBeInTheDocument();
    const clearBtn = screen.getByTestId("clear-preferences-btn");
    fireEvent.click(clearBtn);
    expect(screen.getByText(/Đã đặt lại các tùy chọn giao diện về mặc định hệ thống/i)).toBeInTheDocument();
  });

  it("renders /cookies root wrapper with canonical alternate to /legal/cookies", () => {
    expect(cookiesMetadata.alternates?.canonical).toBe("/legal/cookies");
    render(<RootCookiesPage />);
    expect(screen.getByRole("heading", { level: 1, name: /Chính sách cookie/i })).toBeInTheDocument();
  });
});

describe("3. /contact — Professional Contact Page & Multi-Channel Support", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders /contact with 4 dedicated channels, emergency disclaimer, compliance address, and interactive form", () => {
    const { container } = render(<ContactPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Contact Hub");

    // Title
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Liên hệ & Trung tâm hỗ trợ chuyên môn/i,
      }),
    ).toBeInTheDocument();

    // Breadcrumb and SLA badges
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
    expect(screen.getByText(/Bảo mật Zero-PII/i)).toBeInTheDocument();
    expect(screen.getByText(/Phản hồi: 24 - 72h/i)).toBeInTheDocument();

    // Emergency 115 disclaimer
    expect(screen.getByText(/Cảnh báo cấp cứu y tế khẩn cấp \(115\)/i)).toBeInTheDocument();
    const emergencyCallLink = screen.getByRole("link", { name: /GỌI NGAY CẤP CỨU 115/i });
    expect(emergencyCallLink).toHaveAttribute("href", "tel:115");

    // 4 Contact channels: Patient Support, Clinician Advisory, Research Inquiries, DPO
    expect(screen.getByText(/1\. Hỗ trợ người bệnh & Người dùng cá nhân/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Ban cố vấn y khoa & Bác sĩ lâm sàng/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Hợp tác nghiên cứu & Dữ liệu y học/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Cán bộ bảo vệ dữ liệu \(DPO\) & DSAR/i)).toBeInTheDocument();

    // Channel scopes and details
    expect(screen.getByText(/Doctor onboarding, Council review, Scribe verification/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Nghị định 13\/2023\/NĐ-CP/i).length).toBeGreaterThan(0);

    // Compliance address and operator details
    expect(screen.getByText(LEGAL_OPERATOR_NAME)).toBeInTheDocument();
    expect(screen.getByText(`https://${LEGAL_PRIMARY_DOMAIN}`)).toBeInTheDocument();
    expect(screen.getByText(/08:00 - 18:00 \(Thứ 2 - Thứ 6\)/i)).toBeInTheDocument();

    // Quick navigation links
    expect(screen.getByRole("link", { name: /Quyền riêng tư & DSAR/i })).toHaveAttribute("href", "/legal/privacy");
    expect(screen.getByRole("link", { name: /Đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");
    expect(screen.getAllByRole("link", { name: /Tuyên ngôn an toàn/i })[0]).toHaveAttribute("href", "/safety");

    // Structured Feedback Form
    expect(screen.getByTestId("contact-feedback-form")).toBeInTheDocument();
    expect(screen.getByLabelText(/Họ và tên/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Email liên hệ/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Tiêu đề yêu cầu/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Nội dung chi tiết/i)).toBeInTheDocument();
  });

  it("validates form inputs and submits structured inquiry with ticket confirmation", () => {
    vi.useFakeTimers();
    render(<ContactPage />);

    const submitBtn = screen.getByTestId("contact-submit-btn");

    // Attempt submission with empty inputs -> validation errors shown
    fireEvent.click(submitBtn);
    expect(screen.getByText(/Vui lòng nhập họ và tên của bạn/i)).toBeInTheDocument();

    // Test category selector switch
    const clinicianCategoryBtn = screen.getByRole("button", { name: /Cố vấn y khoa/i });
    fireEvent.click(clinicianCategoryBtn);

    // Fill valid data
    const nameInput = screen.getByLabelText(/Họ và tên/i);
    const emailInput = screen.getByLabelText(/Email liên hệ/i);
    const subjectInput = screen.getByLabelText(/Tiêu đề yêu cầu/i);
    const messageInput = screen.getByLabelText(/Nội dung chi tiết/i);

    fireEvent.change(nameInput, { target: { value: "Bác sĩ Trần Văn B" } });
    fireEvent.change(emailInput, { target: { value: "tran.van.b@hospital.vn" } });
    fireEvent.change(subjectInput, { target: { value: "Góp ý chuyên môn phác đồ HFrEF" } });
    fireEvent.change(messageInput, { target: { value: "Xin chào, tôi muốn góp ý về khuyến cáo SGLT2i trong hội đồng Council." } });

    act(() => {
      fireEvent.click(submitBtn);
    });

    // Fast-forward timer for fake submission inside act
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByTestId("contact-form-success")).toBeInTheDocument();
    expect(screen.getByText(/Tiếp nhận thành công/i)).toBeInTheDocument();
    expect(screen.getByText(/tran.van.b@hospital.vn/i)).toBeInTheDocument();

    // Verify modal receipt dialog can be opened
    const viewReceiptBtn = screen.getByTestId("view-receipt-btn");
    fireEvent.click(viewReceiptBtn);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Biên nhận yêu cầu hỗ trợ/i)).toBeInTheDocument();

    // Close modal
    const closeModalBtn = screen.getByRole("button", { name: /Đóng biên nhận/i });
    fireEvent.click(closeModalBtn);

    // Test reset button
    const submitAnotherBtn = screen.getByTestId("submit-another-btn");
    fireEvent.click(submitAnotherBtn);
    expect(screen.getByTestId("contact-feedback-form")).toBeInTheDocument();

    vi.useRealTimers();
  });
});

describe("4. /safety — Comprehensive Clinical Safety Manifesto", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders /safety with 5 clinical safety tiers, FIDES matrix, Zero-CoT protocol, and emergency fast-path", () => {
    const { container } = render(<SafetyManifestoPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Safety Manifesto");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Tuyên ngôn An toàn Lâm sàng & Hàng rào Bảo vệ Đa tầng/i,
      }),
    ).toBeInTheDocument();

    // 5 Clinical Safety Tiers
    expect(screen.getByText(/Tầng 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Phân loại & Chuyển hướng Cấp cứu Khẩn cấp \(115 Fast-Path\)/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 2/i)).toBeInTheDocument();
    expect(screen.getByText(/Hàng rào Pháp lý & Ranh giới Lâm sàng \(Legal Hard-Guards\)/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Hệ thống Xác thực Dược lý FIDES \(Drug Interaction & Dosage Guard\)/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 4/i)).toBeInTheDocument();
    expect(screen.getByText(/Hội chẩn Đa tác tử & Neo giữ Y văn \(Multi-Agent Council & Grounding\)/i)).toBeInTheDocument();

    expect(screen.getByText(/Tầng 5/i)).toBeInTheDocument();
    expect(screen.getByText(/Giám sát & Xác nhận Chuyên môn Bác sĩ \(Human-In-The-Loop Sign-Off\)/i)).toBeInTheDocument();

    // Deep Dive: FIDES Verification Matrix
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /Hệ thống Xác minh Dược lâm sàng FIDES \(Verification Matrix\)/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/1\. Bóc tách Tuyên bố/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Đối chiếu Y văn Số hóa/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Ngắt mạch An toàn \(Kill-Switch\)/i)).toBeInTheDocument();

    // Zero-hallucination guardrails & Zero-CoT
    expect(screen.getByText(/Chuẩn Zero-CoT & Zero-PII/i)).toBeInTheDocument();
    expect(screen.getByText(/Bảo mật Chuỗi Suy luận Zero-CoT/i)).toBeInTheDocument();
    expect(screen.getByText(/Nguyên tắc Fail-Closed \(Đóng khi nghi ngờ\)/i)).toBeInTheDocument();

    // Direct links to /sources and /legal/consent
    expect(screen.getByRole("link", { name: /Khám phá Danh mục nguồn y văn/i })).toHaveAttribute("href", "/sources");
    expect(screen.getByRole("link", { name: /Xem Thỏa thuận đồng thuận y tế/i })).toHaveAttribute("href", "/legal/consent");
  });
});

describe("5. /sources — Exhaustive Medical & Pharmacopoeia Sources Catalog", () => {
  beforeEach(() => {
    cleanup();
  });

  it("renders /sources with Dược thư Quốc gia VN, DrugBank, US FDA DailyMed, PubMed, and Bộ Y Tế Guidelines", () => {
    const { container } = render(<SourcesCatalogPage />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_LEGAL");
    expect(root).toHaveAttribute("data-layout-archetype", "Sources Catalog");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /Danh mục Nguồn Y văn & Dược thư Tham chiếu/i,
      }),
    ).toBeInTheDocument();

    // All primary catalog sources present
    expect(screen.getByText("Dược thư Quốc gia Việt Nam")).toBeInTheDocument();
    expect(screen.getByText("DrugBank Comprehensive Pharmacoinformatics Database")).toBeInTheDocument();
    expect(screen.getByText("Hướng dẫn Chẩn đoán và Điều trị của Bộ Y Tế Việt Nam")).toBeInTheDocument();
    expect(screen.getByText("US FDA DailyMed & National Drug Code Directory")).toBeInTheDocument();
    expect(screen.getByText("PubMed / MEDLINE & Living Evidence Repositories")).toBeInTheDocument();
    expect(screen.getByText("WHO Guidelines & Model List of Essential Medicines (EML)")).toBeInTheDocument();

    // RAG Grounding Ingestion Pipeline explanation
    expect(screen.getByText(/Quy trình Tuyển chọn, Kiểm định & Neo giữ Tri thức Y khoa/i)).toBeInTheDocument();
    expect(screen.getByText(/Tuyển chọn Nguồn Cấp 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Chuẩn hóa Thuật ngữ/i)).toBeInTheDocument();
    expect(screen.getByText(/Xác thực chéo FIDES/i)).toBeInTheDocument();
  });

  it("filters sources catalog by search query and category tabs", () => {
    render(<SourcesCatalogPage />);

    const searchInput = screen.getByRole("searchbox");

    // Filter by search query
    fireEvent.change(searchInput, { target: { value: "DrugBank" } });
    expect(screen.getByText("DrugBank Comprehensive Pharmacoinformatics Database")).toBeInTheDocument();
    expect(screen.queryByText("US FDA DailyMed & National Drug Code Directory")).toBeNull();

    // Clear search
    fireEvent.change(searchInput, { target: { value: "" } });
    expect(screen.getByText("US FDA DailyMed & National Drug Code Directory")).toBeInTheDocument();

    // Filter by Category tab
    const guidelinesTab = screen.getByRole("tab", { name: /Phác đồ Bộ Y Tế/i });
    fireEvent.click(guidelinesTab);
    expect(screen.getByText("Hướng dẫn Chẩn đoán và Điều trị của Bộ Y Tế Việt Nam")).toBeInTheDocument();
    expect(screen.queryByText("DrugBank Comprehensive Pharmacoinformatics Database")).toBeNull();

    // Expand citation details
    const citationTrigger = screen.getByRole("button", { name: /Xem định dạng trích dẫn & Bản quyền/i });
    fireEvent.click(citationTrigger);
    expect(screen.getByText(/Ví dụ trích dẫn y khoa chuẩn \(Citation Example\):/i)).toBeInTheDocument();
    expect(screen.getByText(/Quyết định số 5481\/QĐ-BYT/i)).toBeInTheDocument();
  });
});

describe("6. /terms and /privacy aliases", () => {
  it("renders /terms root wrapper with canonical alternate to /legal/terms", () => {
    expect(termsMetadata.alternates?.canonical).toBe("/legal/terms");
    render(<RootTermsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Điều khoản sử dụng & Thỏa thuận người dùng/i }),
    ).toBeInTheDocument();
  });

  it("renders /privacy root wrapper with canonical alternate to /legal/privacy", () => {
    expect(privacyMetadata.alternates?.canonical).toBe("/legal/privacy");
    render(<RootPrivacyPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Chính sách quyền riêng tư & Bảo vệ dữ liệu cá nhân/i }),
    ).toBeInTheDocument();
  });
});
