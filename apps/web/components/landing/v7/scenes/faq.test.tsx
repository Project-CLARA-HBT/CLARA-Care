import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { FaqScene } from "./faq";

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

describe("FaqScene (Landing v7 FAQ Accordion Scene)", () => {
  it("renders landing scene with id='faq', scale='standard', tone='canvas'", () => {
    const { container } = renderFaqScene("vi");
    const section = container.querySelector("section#faq");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "faq");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V7.vi.faq;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders real button elements with aria-expanded, aria-controls, and accessible disclosure semantics", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V7.vi.faq;

    copy.items.forEach((item) => {
      const button = screen.getByRole("button", { name: new RegExp(item.question, "i") });
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute("aria-expanded", "false");
      const controlsId = button.getAttribute("aria-controls");
      expect(controlsId).toBeTruthy();
    });
  });

  it("toggles accordion items when buttons are clicked", () => {
    renderFaqScene("vi");
    const copy = LANDING_COPY_V7.vi.faq;

    const firstBtn = screen.getByRole("button", { name: new RegExp(copy.items[0].question, "i") });
    const secondBtn = screen.getByRole("button", { name: new RegExp(copy.items[1].question, "i") });

    // Initially collapsed
    expect(firstBtn).toHaveAttribute("aria-expanded", "false");
    expect(secondBtn).toHaveAttribute("aria-expanded", "false");

    // Click first item -> opens first item
    fireEvent.click(firstBtn);
    expect(firstBtn).toHaveAttribute("aria-expanded", "true");
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
});
