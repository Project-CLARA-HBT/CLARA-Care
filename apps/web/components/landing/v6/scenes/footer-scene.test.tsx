import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { FooterScene } from "./footer-scene";

beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

function renderFooterScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <FooterScene />
    </MotionProvider>
  );
}

describe("FooterScene (Landing v6 Semantic Footer)", () => {
  it("renders semantic footer element with id='footer'", () => {
    const { container } = renderFooterScene("vi");
    const footer = container.querySelector("footer#footer");
    expect(footer).toBeInTheDocument();
  });

  it("renders brand column with tagline and medical disclaimer", () => {
    renderFooterScene("vi");

    // Brand and tagline
    expect(screen.getByText("CLARA Care")).toBeInTheDocument();
    expect(
      screen.getByText("Trợ lý AI Lâm sàng & Y tế An toàn cho Người Việt")
    ).toBeInTheDocument();

    // Disclaimer
    expect(
      screen.getByText(/không thay thế chẩn đoán, điều trị hay lời khuyên của bác sĩ chuyên khoa/i)
    ).toBeInTheDocument();
  });

  it("renders 4 clear link columns with correct headings and links", () => {
    renderFooterScene("vi");

    // Column headings
    expect(screen.getByRole("heading", { name: "Sản phẩm" })).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Chuyên gia & Lâm sàng" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Tin cậy & An toàn" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Hỗ trợ & Pháp lý" })
    ).toBeInTheDocument();

    // Product links
    expect(screen.getByRole("link", { name: "Trò chuyện CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Dòng thời gian LifeMap" })).toHaveAttribute("href", "/lifemap");
    expect(screen.getByRole("link", { name: "Tủ thuốc & Tương tác" })).toHaveAttribute("href", "/medicines");
    expect(screen.getByRole("link", { name: "Hồ sơ Sức khỏe Cá nhân" })).toHaveAttribute("href", "/phr");

    // Clinical links
    expect(screen.getByRole("link", { name: "Tổng quan Lâm sàng" })).toHaveAttribute("href", "/clinical");
    expect(screen.getByRole("link", { name: "Hội đồng Council" })).toHaveAttribute("href", "/council");
    expect(screen.getByRole("link", { name: "Trợ lý Ghi chép Scribe" })).toHaveAttribute("href", "/scribe");
    expect(screen.getByRole("link", { name: "Trung tâm Bằng chứng" })).toHaveAttribute("href", "/research");

    // Trust links
    expect(screen.getByRole("link", { name: "Kiểm chứng FIDES" })).toHaveAttribute("href", "/safety");
    expect(screen.getByRole("link", { name: "Bảo mật Dữ liệu" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Nguồn Y văn Chuẩn" })).toHaveAttribute("href", "/sources");
    expect(screen.getByRole("link", { name: "Tiêu chuẩn Lâm sàng" })).toHaveAttribute("href", "/clinical-standards");

    // Company / Support links
    expect(screen.getByRole("link", { name: "Hướng dẫn Sử dụng" })).toHaveAttribute("href", "/huong-dan");
    expect(screen.getByRole("link", { name: "Điều khoản Dịch vụ" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Chính sách Bảo mật" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Liên hệ Đội ngũ" })).toHaveAttribute("href", "/contact");
  });

  it("renders bottom row with copyright, terms, privacy, consent links", () => {
    renderFooterScene("vi");

    // Copyright
    expect(
      screen.getByText("© 2026 CLARA Care System. All rights reserved.")
    ).toBeInTheDocument();

    // Legal links
    expect(screen.getByRole("link", { name: "Điều khoản" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Bảo mật" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Đồng thuận Y tế" })).toHaveAttribute("href", "/consent");
  });

  it("supports switching language between VI and EN", () => {
    renderFooterScene("vi");

    // Initially Vietnamese
    expect(screen.getByRole("heading", { name: "Sản phẩm" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Điều khoản" })).toBeInTheDocument();

    // Switch to English
    const enButton = screen.getByRole("button", { name: "English" });
    fireEvent.click(enButton);

    // English copy should now be rendered
    expect(screen.getByRole("heading", { name: "Product" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Clinical & Pro" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Trust & Safety" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Support & Legal" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Medical Consent" })).toHaveAttribute("href", "/consent");

    // Tagline in English
    expect(
      screen.getByText("Safety-First Clinical & Health AI Assistant for Vietnam")
    ).toBeInTheDocument();

    // Switch back to Vietnamese
    const viButton = screen.getByRole("button", { name: "Tiếng Việt" });
    fireEvent.click(viButton);

    expect(screen.getByRole("heading", { name: "Sản phẩm" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Điều khoản" })).toBeInTheDocument();
  });
});
