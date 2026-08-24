import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { FooterScene } from "./footer";

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

describe("FooterScene (Landing v7 Semantic Footer)", () => {
  it("renders semantic footer element with id='footer'", () => {
    const { container } = renderFooterScene("vi");
    const footer = container.querySelector("footer#footer");
    expect(footer).toBeInTheDocument();
  });

  it("renders brand column with tagline and medical disclaimer", () => {
    renderFooterScene("vi");

    expect(screen.getByText("CLARA Care")).toBeInTheDocument();
    expect(
      screen.getByText("Trợ lý AI Lâm sàng & Y tế An toàn cho Người Việt")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/không thay thế chẩn đoán, điều trị hay lời khuyên của bác sĩ chuyên khoa/i)
    ).toBeInTheDocument();
  });

  it("renders 4 clear link columns with correct headings and links", () => {
    renderFooterScene("vi");

    expect(screen.getByRole("heading", { name: "Sản phẩm" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Chuyên gia & Lâm sàng" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tin cậy & An toàn" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Hỗ trợ & Pháp lý" })).toBeInTheDocument();

    // Verify key links
    expect(screen.getByRole("link", { name: "Trò chuyện CLARA" })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: "Dòng thời gian LifeMap" })).toHaveAttribute("href", "/lifemap");
    expect(screen.getByRole("link", { name: "Tổng quan Lâm sàng" })).toHaveAttribute("href", "/clinical");
    expect(screen.getByRole("link", { name: "Kiểm chứng FIDES" })).toHaveAttribute("href", "/safety");
  });

  it("renders bottom row with copyright, legal links, and language switcher", () => {
    renderFooterScene("vi");

    expect(screen.getByText("© 2026 CLARA Care System. All rights reserved.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Điều khoản" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Bảo mật" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Đồng thuận Y tế" })).toHaveAttribute("href", "/consent");

    const viBtn = screen.getByRole("button", { name: "Tiếng Việt" });
    const enBtn = screen.getByRole("button", { name: "English" });

    expect(viBtn).toHaveAttribute("aria-pressed", "true");
    expect(enBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(enBtn);
    expect(enBtn).toHaveAttribute("aria-pressed", "true");
    expect(viBtn).toHaveAttribute("aria-pressed", "false");
  });
});
