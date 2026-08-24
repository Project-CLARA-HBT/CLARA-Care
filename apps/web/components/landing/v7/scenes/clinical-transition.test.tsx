import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { ClinicalTransitionScene } from "./clinical-transition";

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

function renderClinicalTransitionScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <ClinicalTransitionScene />
    </MotionProvider>
  );
}

describe("ClinicalTransitionScene (Landing v7 Visual Silence)", () => {
  it("renders landing scene with id='clinical-transition', scale='transition', tone='mint'", () => {
    const { container } = renderClinicalTransitionScene("vi");
    const section = container.querySelector("section#clinical-transition");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "clinical-transition");
    expect(section).toHaveAttribute("data-scene-scale", "transition");
    expect(section).toHaveAttribute("data-scene-tone", "mint");
  });

  it("renders tranquil editorial headline and subheadline with ClaraOrb anchor", () => {
    const { container } = renderClinicalTransitionScene("vi");
    const copy = LANDING_COPY_V7.vi.clinicalTransition;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("Công cụ chuyên sâu"))).toBeInTheDocument();
    expect(screen.getByText(copy.subheadline)).toBeInTheDocument();
    expect(container.querySelector("[data-artwork='clara-orb']")).toBeInTheDocument();
  });

  it("renders beginning of DecisionField convergence thread SVG", () => {
    const { container } = renderClinicalTransitionScene("vi");
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Tim mạch")).toBeInTheDocument();
    expect(screen.getByText("Thận học")).toBeInTheDocument();
    expect(screen.getByText("Dược lâm sàng")).toBeInTheDocument();
  });

  it("renders correctly in English when language is switched", () => {
    renderClinicalTransitionScene("en");
    const copy = LANDING_COPY_V7.en.clinicalTransition;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("Specialized tools"))).toBeInTheDocument();
    expect(screen.getByText(copy.subheadline)).toBeInTheDocument();
    expect(screen.getByText("Cardiology")).toBeInTheDocument();
    expect(screen.getByText("Nephrology")).toBeInTheDocument();
    expect(screen.getByText("Pharmacology")).toBeInTheDocument();
  });
});
