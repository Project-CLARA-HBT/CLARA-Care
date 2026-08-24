import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "./runtime/motion-provider";
import { LandingNav } from "./landing-nav";

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

function renderLandingNav(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <LandingNav />
    </MotionProvider>
  );
}

describe("LandingNav (Landing v6 Floating Island Navigation)", () => {
  it("renders brand logo, tag, and navigation links in Vietnamese by default", () => {
    renderLandingNav("vi");

    // Brand and Tag
    expect(screen.getAllByText("CLARA Care").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Trợ lý Y tế An toàn").length).toBeGreaterThan(0);

    // Nav anchor links
    const howLink = screen.getByRole("link", { name: "Cách hoạt động" });
    expect(howLink).toHaveAttribute("href", "#how-it-works");

    const chatLink = screen.getByRole("link", { name: "Tính năng" });
    expect(chatLink).toHaveAttribute("href", "#chat");

    const safetyLink = screen.getByRole("link", { name: "An toàn" });
    expect(safetyLink).toHaveAttribute("href", "#safety");

    const clinicalLink = screen.getByRole("link", { name: "Chuyên gia" });
    expect(clinicalLink).toHaveAttribute("href", "#clinical-transition");

    // Login link
    const loginLink = screen.getByRole("link", { name: "Đăng nhập" });
    expect(loginLink).toHaveAttribute("href", "/login");

    // Primary CTA link
    const ctaLink = screen.getByRole("link", { name: /Hỏi CLARA/i });
    expect(ctaLink).toHaveAttribute("href", "/chat");
  });

  it("switches language between VI and EN using setLanguage", () => {
    renderLandingNav("vi");

    // Initially Vietnamese
    expect(screen.getByRole("link", { name: "Cách hoạt động" })).toBeInTheDocument();

    // Click EN button
    const enButton = screen.getAllByRole("button", { name: "EN" })[0];
    fireEvent.click(enButton);

    // English copy should appear
    expect(screen.getByRole("link", { name: "How It Works" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Features" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Safety" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Clinical" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign In" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ask CLARA/i })).toBeInTheDocument();

    // Switch back to VI
    const viButton = screen.getAllByRole("button", { name: "VI" })[0];
    fireEvent.click(viButton);
    expect(screen.getByRole("link", { name: "Cách hoạt động" })).toBeInTheDocument();
  });

  it("opens and closes mobile modal drawer with escape key and close button", () => {
    renderLandingNav("vi");

    // Mobile menu drawer initially closed
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Click hamburger button to open
    const openBtn = screen.getByRole("button", { name: "Mở menu điều hướng" });
    fireEvent.click(openBtn);

    // Dialog drawer is visible
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();

    // Press Escape key
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Reopen and close via close button
    fireEvent.click(screen.getByRole("button", { name: "Mở menu điều hướng" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    const closeBtn = screen.getByRole("button", { name: "Đóng menu điều hướng" });
    fireEvent.click(closeBtn);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders floating chrome with scroll state change", () => {
    const { container } = renderLandingNav("vi");
    const nav = container.querySelector("nav");
    expect(nav).toHaveClass("clara-floating-chrome");
    expect(nav).toHaveClass("rounded-full");
    expect(nav).toHaveClass("max-w-[1200px]");

    // Trigger scroll
    fireEvent.scroll(window, { target: { scrollY: 100 } });
  });
});
