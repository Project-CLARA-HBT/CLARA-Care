import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { PrivacyScene } from "./privacy-scene";

beforeAll(() => {
  class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  Object.defineProperty(window, "IntersectionObserver", {
    writable: true,
    configurable: true,
    value: MockIntersectionObserver,
  });

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

function renderPrivacyScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <PrivacyScene />
    </MotionProvider>
  );
}

describe("PrivacyScene (Landing v6 Privacy and Permission Boundary Scene)", () => {
  it("renders landing scene with id='privacy', scale='standard', tone='canvas'", () => {
    const { container } = renderPrivacyScene("vi");
    const section = container.querySelector("section#privacy");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "privacy");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderPrivacyScene("vi");
    const copy = LANDING_COPY_V6.vi.privacy;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders diagram components for source, gate, destination, allowed, blocked, and revoke notes in Vietnamese", () => {
    renderPrivacyScene("vi");
    const copy = LANDING_COPY_V6.vi.privacy;

    expect(screen.getByText(copy.diagram.source)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.gate)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.destination)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.allowedNote)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.blockedNote)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.revokeNote)).toBeInTheDocument();
  });

  it("renders diagram and copy correctly in English", () => {
    renderPrivacyScene("en");
    const copy = LANDING_COPY_V6.en.privacy;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.source)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.gate)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.destination)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.allowedNote)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.blockedNote)).toBeInTheDocument();
    expect(screen.getByText(copy.diagram.revokeNote)).toBeInTheDocument();
  });

  it("allows toggling revocation state interactively", () => {
    renderPrivacyScene("vi");

    const revokeBtn = screen.getByRole("button", { name: /Thử nghiệm thu hồi/i });
    expect(revokeBtn).toBeInTheDocument();

    // Click revoke
    fireEvent.click(revokeBtn);
    expect(screen.getByText(/Đã ngắt quyền truy cập/i)).toBeInTheDocument();
    expect(screen.getByText(/Gói chia sẻ đã bị thu hồi/i)).toBeInTheDocument();

    // Click restore
    const restoreBtn = screen.getByRole("button", { name: /Khôi phục gói chia sẻ/i });
    fireEvent.click(restoreBtn);
    expect(screen.getByText(/Cổng bảo vệ đang hoạt động/i)).toBeInTheDocument();
    expect(screen.getByText(/Gói tóm tắt lâm sàng/i)).toBeInTheDocument();
  });

  it("renders Zero-CoT guarantees cards", () => {
    renderPrivacyScene("vi");

    expect(screen.getByText("Cách ly suy luận Zero-CoT")).toBeInTheDocument();
    expect(screen.getByText("Tuyệt đối không huấn luyện")).toBeInTheDocument();
    expect(screen.getByText("Chủ quyền & Thu hồi tức thì")).toBeInTheDocument();
  });
});
