import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

import ClaraKp3Landing from "@/components/landing/clara-kp3-landing";

describe("ClaraKp3Landing (Spec v5 Section 6.1 - Marketing Landing Archetype)", () => {
  it("renders with PUBLIC_MARKETING shell mode and Marketing Landing layout archetype", () => {
    const { container } = render(<ClaraKp3Landing />);
    const root = container.firstChild as HTMLElement;

    expect(root).toHaveAttribute("data-shell-mode", "PUBLIC_MARKETING");
    expect(root).toHaveAttribute("data-layout-archetype", "Marketing Landing");
  });

  it("renders clean unauthenticated navigation header with Login and Register CTAs and Guide link", () => {
    render(<ClaraKp3Landing />);

    // Brand mark
    expect(screen.getAllByText(/Clara Care/i).length).toBeGreaterThan(0);

    // Login & Register CTAs in header
    const loginLinks = screen.getAllByRole("link", { name: /đăng nhập/i });
    expect(loginLinks.length).toBeGreaterThan(0);
    expect(loginLinks[0]).toHaveAttribute("href", "/login");

    const registerLinks = screen.getAllByRole("link", { name: /đăng ký/i });
    expect(registerLinks.length).toBeGreaterThan(0);
    expect(registerLinks[0]).toHaveAttribute("href", "/register");

    // Help / Guides link in header
    const guideLinks = screen.getAllByRole("link", { name: /hướng dẫn/i });
    expect(guideLinks.length).toBeGreaterThan(0);
    expect(guideLinks.some((l) => l.getAttribute("href") === "/huong-dan")).toBe(true);
  });

  it("renders Spatial Editorial hero with clinical assistant value proposition and safety badges (FIDES & Zero-CoT)", () => {
    render(<ClaraKp3Landing />);

    // Clinical assistant value proposition
    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /trợ lý ai lâm sàng/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/không thay thế đánh giá chuyên môn của bác sĩ/i)).toBeInTheDocument();

    // Safety badges
    expect(screen.getAllByText("FIDES Guardrail Verified").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Zero-CoT Privacy Safe").length).toBeGreaterThan(0);

    // Primary & Secondary CTAs
    const chatCta = screen.getAllByRole("link", { name: /dùng thử clara chat/i });
    expect(chatCta.length).toBeGreaterThan(0);
    expect(chatCta[0]).toHaveAttribute("href", "/chat");

    const pathwayCta = screen.getByRole("link", { name: /xem cách hoạt động/i });
    expect(pathwayCta).toHaveAttribute("href", "#pathways");
  });

  it("renders Interactive Feature Preview with selectable tabs (DDI, Council, Scribe, PHR)", () => {
    render(<ClaraKp3Landing />);

    // Tab buttons exist
    const ddiTab = screen.getByRole("button", { name: /tương tác thuốc & fides/i });
    const councilTab = screen.getByRole("button", { name: /hội chẩn đa chuyên khoa/i });
    const scribeTab = screen.getByRole("button", { name: /ghi chép lâm sàng & soap/i });
    const phrTab = screen.getByRole("button", { name: /hồ sơ sức khỏe & lifemap/i });

    expect(ddiTab).toBeInTheDocument();
    expect(councilTab).toBeInTheDocument();
    expect(scribeTab).toBeInTheDocument();
    expect(phrTab).toBeInTheDocument();

    // Default DDI tab content
    expect(screen.getByText(/kiểm tra tương tác đa thuốc/i)).toBeInTheDocument();
    expect(screen.getAllByText(/dược thư quốc gia việt nam/i).length).toBeGreaterThan(0);

    // Switch to Council AI tab
    fireEvent.click(councilTab);
    expect(screen.getByText(/tổng hợp góc nhìn đa chuyên khoa/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /mở hội chẩn council/i })).toHaveAttribute(
      "href",
      "/council",
    );

    // Switch to Scribe tab
    fireEvent.click(scribeTab);
    expect(screen.getByText(/chuẩn hóa ghi chú khám bệnh soap tự động/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /dùng thử scribe y khoa/i })).toHaveAttribute(
      "href",
      "/scribe",
    );

    // Switch to PHR tab
    fireEvent.click(phrTab);
    expect(screen.getByText(/hồ sơ sức khỏe cá nhân & dòng thời gian lifemap/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /xem hồ sơ sức khỏe/i })).toHaveAttribute(
      "href",
      "/phr",
    );
  });

  it("renders Clinician, Personal, and Evidence pathways with respective CTAs", () => {
    render(<ClaraKp3Landing />);

    // Personal pathway
    expect(screen.getByText(/phân hệ cá nhân — spatial health companion/i)).toBeInTheDocument();
    expect(screen.getByText(/tủ thuốc thông minh \(self-med\)/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /bắt đầu với tài khoản cá nhân/i })).toHaveAttribute(
      "href",
      "/register",
    );

    // Clinician pathway
    expect(screen.getByText(/phân hệ lâm sàng — spatial clinical instrument/i)).toBeInTheDocument();
    expect(screen.getByText(/hội chẩn đa chuyên khoa \(council ai\)/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /đăng nhập cổng bác sĩ/i })).toHaveAttribute(
      "href",
      "/login",
    );

    // Evidence pathway
    expect(screen.getByText(/phân hệ bằng chứng — editorial evidence workstation/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /tra cứu bằng chứng y khoa/i })).toHaveAttribute(
      "href",
      "/chat",
    );
  });

  it("renders Trust & Safety Invariants strip and 3-step workflow", () => {
    render(<ClaraKp3Landing />);

    // Safety Invariants
    expect(screen.getByText(/bốn rào chắn bảo vệ y tế & quyền riêng tư/i)).toBeInTheDocument();
    expect(screen.getByText(/kiểm chứng fides \(fides verification\)/i)).toBeInTheDocument();
    expect(screen.getByText(/bảo mật tuyệt đối zero-cot/i)).toBeInTheDocument();

    // 3-step workflow
    expect(screen.getByText(/quy trình 3 bước từ/i)).toBeInTheDocument();
    expect(screen.getAllByText("01").length).toBeGreaterThan(0);
    expect(screen.getAllByText("02").length).toBeGreaterThan(0);
    expect(screen.getAllByText("03").length).toBeGreaterThan(0);
  });

  it("renders footer with explicit links to /legal and /huong-dan and medical disclaimer", () => {
    render(<ClaraKp3Landing />);

    // Explicit link to /legal
    const legalLink = screen.getByRole("link", { name: /trung tâm pháp lý \(\/legal\)/i });
    expect(legalLink).toBeInTheDocument();
    expect(legalLink).toHaveAttribute("href", "/legal");

    // Explicit link to /huong-dan
    const guideLink = screen.getByRole("link", { name: /trung tâm hướng dẫn \(\/huong-dan\)/i });
    expect(guideLink).toBeInTheDocument();
    expect(guideLink).toHaveAttribute("href", "/huong-dan");

    // Sub-legal links
    expect(screen.getByRole("link", { name: /chính sách quyền riêng tư/i })).toHaveAttribute(
      "href",
      "/legal/privacy",
    );
    expect(screen.getByRole("link", { name: /điều khoản dịch vụ/i })).toHaveAttribute(
      "href",
      "/legal/terms",
    );
    expect(screen.getByRole("link", { name: /đồng thuận y tế/i })).toHaveAttribute(
      "href",
      "/legal/consent",
    );

    // Contact info
    expect(screen.getByText("clara@thiennn.icu")).toBeInTheDocument();
    expect(screen.getByText("0853374247")).toBeInTheDocument();

    // Medical disclaimer
    expect(screen.getByText(/không thay thế bác sĩ hoặc quyết định chuyên môn y tế/i)).toBeInTheDocument();
  });

  it("uses bundled semantic icons with no raw material symbol font classes", () => {
    const { container } = render(<ClaraKp3Landing />);

    expect(container.querySelectorAll(".material-symbols-outlined")).toHaveLength(0);
    expect(container.querySelectorAll("[data-icon]").length).toBeGreaterThan(15);
  });
});
