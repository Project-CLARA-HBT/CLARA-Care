import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { FinalCtaScene } from "./final-cta-scene";

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

function renderFinalCtaScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <FinalCtaScene />
    </MotionProvider>
  );
}

describe("FinalCtaScene (Landing v6 Final CTA Scene)", () => {
  it("renders signature visual release scene with id='cta', scale='signature', tone='azure'", () => {
    const { container } = renderFinalCtaScene("vi");
    const section = container.querySelector("section#cta");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "cta");
    expect(section).toHaveAttribute("data-scene-scale", "signature");
    expect(section).toHaveAttribute("data-scene-tone", "azure");
  });

  it("renders small CLARA Orb icon, eyebrow, headline, description, primary CTA, secondary CTA and security badge in Vietnamese", () => {
    renderFinalCtaScene("vi");
    const copy = LANDING_COPY_V6.vi.finalCta;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();

    const primaryLink = screen.getByRole("link", { name: new RegExp(copy.primaryCta, "i") });
    expect(primaryLink).toBeInTheDocument();
    expect(primaryLink).toHaveAttribute("href", "/chat");

    const secondaryLink = screen.getByRole("link", { name: new RegExp(copy.secondaryCta, "i") });
    expect(secondaryLink).toBeInTheDocument();
    expect(secondaryLink).toHaveAttribute("href", "#safety");

    expect(screen.getByText(copy.securityBadge)).toBeInTheDocument();
  });

  it("renders correctly in English when language is 'en'", () => {
    renderFinalCtaScene("en");
    const copy = LANDING_COPY_V6.en.finalCta;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();

    const primaryLink = screen.getByRole("link", { name: new RegExp(copy.primaryCta, "i") });
    expect(primaryLink).toBeInTheDocument();
    expect(primaryLink).toHaveAttribute("href", "/chat");

    const secondaryLink = screen.getByRole("link", { name: new RegExp(copy.secondaryCta, "i") });
    expect(secondaryLink).toBeInTheDocument();
    expect(secondaryLink).toHaveAttribute("href", "#safety");

    expect(screen.getByText(copy.securityBadge)).toBeInTheDocument();
  });
});
