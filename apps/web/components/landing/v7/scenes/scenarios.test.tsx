import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { ScenariosScene } from "./scenarios";

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

function renderScenariosScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <ScenariosScene />
    </MotionProvider>
  );
}

describe("ScenariosScene (Landing v7 Human Everyday Scenarios)", () => {
  it("renders landing scene with id='scenarios', scale='standard', tone='canvas'", () => {
    const { container } = renderScenariosScene("vi");
    const section = container.querySelector("section#scenarios");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "scenarios");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderScenariosScene("vi");
    const copy = LANDING_COPY_V7.vi.scenarios;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders all scenario cards with quotes, context, ScenarioPath artwork, and resolutions", () => {
    const { container } = renderScenariosScene("vi");
    const copy = LANDING_COPY_V7.vi.scenarios;

    copy.items.forEach((item) => {
      expect(screen.getByText(`“${item.quote}”`)).toBeInTheDocument();
      expect(screen.getByText(item.context)).toBeInTheDocument();
      expect(screen.getByText(item.resolution)).toBeInTheDocument();
    });

    // ScenarioPath SVGs should be present in each card
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(copy.items.length);
  });

  it("supports interaction state on mouse enter/leave and focus", () => {
    renderScenariosScene("vi");
    const copy = LANDING_COPY_V7.vi.scenarios;
    const firstQuote = screen.getByText(`“${copy.items[0].quote}”`);
    const card = firstQuote.closest("div[class*='w-full']") as HTMLElement;
    expect(card).toBeInTheDocument();

    fireEvent.mouseEnter(card);
    fireEvent.mouseLeave(card);
  });

  it("renders correctly in English when language is switched", () => {
    renderScenariosScene("en");
    const copy = LANDING_COPY_V7.en.scenarios;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(`“${copy.items[0].quote}”`)).toBeInTheDocument();
    expect(screen.getByText(copy.items[0].context)).toBeInTheDocument();
    expect(screen.getByText(copy.items[0].resolution)).toBeInTheDocument();
  });
});
