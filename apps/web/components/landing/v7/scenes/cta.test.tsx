import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { CtaScene } from "./cta";

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

function renderCtaScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <CtaScene />
    </MotionProvider>
  );
}

describe("CtaScene (Landing v7 Final CTA Scene)", () => {
  it("renders landing scene with id='cta', scale='signature', tone='azure'", () => {
    const { container } = renderCtaScene("vi");
    const section = container.querySelector("section#cta");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "cta");
    expect(section).toHaveAttribute("data-scene-scale", "signature");
    expect(section).toHaveAttribute("data-scene-tone", "azure");
  });

  it("renders ClaraOrb artwork anchor", () => {
    const { container } = renderCtaScene("vi");
    const orb = container.querySelector("[data-artwork='clara-orb']");
    expect(orb).toBeInTheDocument();
  });

  it("renders eyebrow, title, and description", () => {
    renderCtaScene("vi");
    const copy = LANDING_COPY_V7.vi.finalCta;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders primary and secondary CTA buttons linking to destinations", () => {
    renderCtaScene("vi");
    const copy = LANDING_COPY_V7.vi.finalCta;

    const primaryLink = screen.getByRole("link", { name: new RegExp(copy.primaryCta, "i") });
    expect(primaryLink).toHaveAttribute("href", "/chat");

    const secondaryLink = screen.getByRole("link", { name: new RegExp(copy.secondaryCta, "i") });
    expect(secondaryLink).toHaveAttribute("href", "#safety");
  });

  it("renders security badge in footer of CTA", () => {
    renderCtaScene("vi");
    const copy = LANDING_COPY_V7.vi.finalCta;
    expect(screen.getByText(copy.securityBadge)).toBeInTheDocument();
  });
});
