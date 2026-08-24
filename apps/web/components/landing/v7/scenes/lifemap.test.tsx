import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { LifeMapScene } from "./lifemap";

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

function renderLifeMapScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <LifeMapScene />
    </MotionProvider>
  );
}

describe("LifeMapScene (Landing v7 Spatial Peak 3)", () => {
  it("renders landing scene with id='lifemap', scale='signature', tone='azure'", () => {
    const { container } = renderLifeMapScene("vi");
    const section = container.querySelector("section#lifemap");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "lifemap");
    expect(section).toHaveAttribute("data-scene-scale", "signature");
    expect(section).toHaveAttribute("data-scene-tone", "azure");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderLifeMapScene("vi");
    const copy = LANDING_COPY_V7.vi.lifemap;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getAllByText(copy.title).length).toBeGreaterThan(0);
    expect(screen.getAllByText(copy.description).length).toBeGreaterThan(0);
  });

  it("renders LifeMapDemo wrapped inside spatial stage with today beacon and temporal ribbon", () => {
    const { container } = renderLifeMapScene("vi");
    expect(screen.getByTestId("lifemap-demo")).toBeInTheDocument();
    expect(container.querySelector("[data-artwork='today-beacon']")).toBeInTheDocument();
    expect(container.querySelector("[data-artwork='temporal-ribbon']")).toBeInTheDocument();
    expect(screen.getByTestId("lifemap-insight-callout")).toBeInTheDocument();
  });

  it("renders correctly in English when language is switched", () => {
    renderLifeMapScene("en");
    const copy = LANDING_COPY_V7.en.lifemap;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getAllByText(copy.title).length).toBeGreaterThan(0);
    expect(screen.getAllByText(copy.description).length).toBeGreaterThan(0);
  });
});
