import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { FaqScene } from "./faq-scene";

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

function renderFaqScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <FaqScene />
    </MotionProvider>
  );
}

describe("FaqScene (Landing v6 FAQ Accordion Scene)", () => {
  it("renders landing scene with id='faq', scale='standard', tone='canvas'", () => {
    const { container } = renderFaqScene("vi");
    const section = container.querySelector("section#faq");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "faq");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V6.vi.faq;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders real button elements with aria-expanded, aria-controls, and accessible disclosure semantics", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V6.vi.faq;

    // All questions should have button triggers
    copy.items.forEach((item, index) => {
      const button = screen.getByRole("button", { name: new RegExp(item.question, "i") });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute("id", `faq-header-${index}`);
      expect(button).toHaveAttribute("aria-controls", `faq-panel-${index}`);

      if (index === 0) {
        expect(button).toHaveAttribute("aria-expanded", "true");
        const panel = screen.getByRole("region");
        expect(panel).toHaveAttribute("id", `faq-panel-${index}`);
        expect(panel).toHaveAttribute("aria-labelledby", `faq-header-${index}`);
        expect(panel).toHaveTextContent(item.answer);
      } else {
        expect(button).toHaveAttribute("aria-expanded", "false");
      }
    });
  });

  it("toggles accordion items when buttons are clicked", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V6.vi.faq;

    const firstBtn = screen.getByRole("button", { name: new RegExp(copy.items[0].question, "i") });
    const secondBtn = screen.getByRole("button", { name: new RegExp(copy.items[1].question, "i") });

    // Initially first is open
    expect(firstBtn).toHaveAttribute("aria-expanded", "true");
    expect(secondBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(copy.items[0].answer)).toBeInTheDocument();

    // Click second item -> opens second item, closes first item
    fireEvent.click(secondBtn);
    expect(firstBtn).toHaveAttribute("aria-expanded", "false");
    expect(secondBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText(copy.items[1].answer)).toBeInTheDocument();
    expect(screen.queryByText(copy.items[0].answer)).not.toBeInTheDocument();

    // Click second item again -> closes second item
    fireEvent.click(secondBtn);
    expect(secondBtn).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(copy.items[1].answer)).not.toBeInTheDocument();
  });

  it("renders English copy when language is set to English", () => {
    renderFaqScene("en");
    const copy = LANDING_COPY_V6.en.faq;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
    expect(screen.getByText(copy.items[0].question)).toBeInTheDocument();
    expect(screen.getByText(copy.items[0].answer)).toBeInTheDocument();
  });
});
