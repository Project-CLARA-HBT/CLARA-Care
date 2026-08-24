import React from "react";
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MotionProvider } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { MedicinesScene } from "./medicines";

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

function renderMedicinesScene(initialLanguage: "vi" | "en" = "vi") {
  return render(
    <MotionProvider initialLanguage={initialLanguage}>
      <MedicinesScene />
    </MotionProvider>
  );
}

describe("MedicinesScene (Landing v7 Unified Medicines Workspace)", () => {
  it("renders landing scene with id='medicines', scale='standard', tone='mint'", () => {
    const { container } = renderMedicinesScene("vi");
    const section = container.querySelector("section#medicines");
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute("data-scene-id", "medicines");
    expect(section).toHaveAttribute("data-scene-scale", "standard");
    expect(section).toHaveAttribute("data-scene-tone", "mint");
  });

  it("renders SceneHeader with eyebrow, title, and description in Vietnamese by default", () => {
    renderMedicinesScene("vi");
    const copy = LANDING_COPY_V7.vi.medicines;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getAllByText(copy.title).length).toBeGreaterThan(0);
    expect(screen.getByText(copy.description)).toBeInTheDocument();
  });

  it("renders MedicinesDemo workspace with tabs and truth reminders", () => {
    renderMedicinesScene("vi");
    const copy = LANDING_COPY_V7.vi.medicines;

    expect(screen.getByTestId("medicines-demo")).toBeInTheDocument();
    expect(screen.getByTestId("tab-current")).toBeInTheDocument();
    expect(screen.getByTestId("tab-needs-confirmation")).toBeInTheDocument();
    expect(screen.getByTestId("tab-safety")).toBeInTheDocument();
    expect(screen.getByTestId("tab-cabinet")).toBeInTheDocument();
    expect(screen.getByTestId("semantic-truth-reminder")).toBeInTheDocument();
    expect(screen.getByText(copy.truthNote)).toBeInTheDocument();
  });

  it("renders correctly in English when language is switched", () => {
    renderMedicinesScene("en");
    const copy = LANDING_COPY_V7.en.medicines;

    expect(screen.getByText(copy.eyebrow)).toBeInTheDocument();
    expect(screen.getAllByText(copy.title).length).toBeGreaterThan(0);
    expect(screen.getByText(copy.truthNote)).toBeInTheDocument();
  });
});
