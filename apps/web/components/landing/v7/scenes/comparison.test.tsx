import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { ComparisonScene } from "./comparison";

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

function renderComparisonScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <ComparisonScene />
    </MotionProvider>
  );
}

describe("ComparisonScene (Landing v7 Multi-Tier Safety Comparison)", () => {
  it("renders landing scene with id='comparison', scale='standard', tone='canvas'", () => {
    const { container } = renderComparisonScene("vi");
    const section = container.querySelector("section#comparison");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "comparison");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description", () => {
    renderComparisonScene("vi");
    const copy = LANDING_COPY_V7.vi.comparison;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders Generic AI Chatbot column with all steps and drawback warning", () => {
    renderComparisonScene("vi");
    const copy = LANDING_COPY_V7.vi.comparison;

    expect(screen.getByText(copy.genericAi.title)).toBeInTheDocument();
    copy.genericAi.flow.forEach((step) => {
      const elements = screen.getAllByText(step);
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(copy.genericAi.drawback)).toBeInTheDocument();
  });

  it("renders CLARA Care Pipeline column with 7 tiers, FIDES check, LifeMap and benefit guarantee", () => {
    renderComparisonScene("vi");
    const copy = LANDING_COPY_V7.vi.comparison;

    expect(screen.getByText(copy.claraCare.title)).toBeInTheDocument();
    copy.claraCare.flow.forEach((step) => {
      const elements = screen.getAllByText(step);
      expect(elements.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("FIDES Check")).toBeInTheDocument();
    expect(screen.getByText("LifeMap")).toBeInTheDocument();
    expect(screen.getByText(copy.claraCare.benefit)).toBeInTheDocument();
  });

  it("renders English copy when language is set to English", () => {
    renderComparisonScene("en");
    const copy = LANDING_COPY_V7.en.comparison;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByText(copy.genericAi.title)).toBeInTheDocument();
    expect(screen.getByText(copy.claraCare.title)).toBeInTheDocument();
    expect(screen.getByText(copy.genericAi.drawback)).toBeInTheDocument();
    expect(screen.getByText(copy.claraCare.benefit)).toBeInTheDocument();
  });
});
