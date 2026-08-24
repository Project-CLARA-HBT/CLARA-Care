import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { PhrScene } from "./phr";

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

function renderPhrScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <PhrScene />
    </MotionProvider>
  );
}

describe("PhrScene (Landing v7 Bounded PHR Sharing)", () => {
  it("renders landing scene with id='phr', scale='standard', tone='canvas'", () => {
    const { container } = renderPhrScene("vi");
    const section = container.querySelector("section#phr");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "phr");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderPhrScene("vi");
    const copy = LANDING_COPY_V7.vi.phr;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getAllByText(copy.description).length).toBeGreaterThan(0);
  });

  it("renders PhrDemo with PermissionGate artwork and both permitted and blocked columns", () => {
    renderPhrScene("vi");
    const copy = LANDING_COPY_V7.vi.phr;

    expect(screen.getByTestId("phr-demo")).toBeInTheDocument();
    expect(screen.getByTestId("permission-gate")).toBeInTheDocument();
    expect(screen.getByTestId("phr-permitted-column")).toBeInTheDocument();
    expect(screen.getByTestId("phr-blocked-column")).toBeInTheDocument();
    expect(screen.getByText(`“${copy.statement}”`)).toBeInTheDocument();
  });

  it("renders correctly in English when language is switched", () => {
    renderPhrScene("en");
    const copy = LANDING_COPY_V7.en.phr;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(`“${copy.statement}”`)).toBeInTheDocument();
  });
});
