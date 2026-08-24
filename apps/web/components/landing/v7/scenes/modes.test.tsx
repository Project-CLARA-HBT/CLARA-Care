import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { ModesScene } from "./modes";

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

function renderModesScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <ModesScene />
    </MotionProvider>
  );
}

describe("ModesScene (Landing v7 Spatial Peak 4 Adaptive Modes)", () => {
  it("renders landing scene with id='adaptive-modes', scale='signature', tone='canvas'", () => {
    const { container } = renderModesScene("vi");
    const section = container.querySelector("section#adaptive-modes");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "adaptive-modes");
    expect(section).toHaveAttribute("data-scene-scale", "signature");
    expect(section).toHaveAttribute("data-scene-tone", "canvas");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderModesScene("vi");
    const copy = LANDING_COPY_V7.vi.adaptive;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders AdaptiveShellDemo and ClaraOrb artwork", () => {
    const { container } = renderModesScene("vi");
    expect(screen.getByTestId("adaptive-shell-demo")).toBeInTheDocument();
    expect(container.querySelector("[data-artwork='clara-orb']")).toBeInTheDocument();
  });

  it("renders correctly in English when language is switched", () => {
    renderModesScene("en");
    const copy = LANDING_COPY_V7.en.adaptive;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: copy.title, level: 2 })).toBeInTheDocument();
  });
});
