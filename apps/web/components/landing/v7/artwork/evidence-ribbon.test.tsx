import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import EvidenceRibbonDefault, {
  EvidenceRibbon,
  type EvidenceRibbonProps,
} from "./evidence-ribbon";

describe("EvidenceRibbon Artwork Component (Landing v7)", () => {
  it("exports both named and default EvidenceRibbon component", () => {
    expect(EvidenceRibbon).toBeDefined();
    expect(EvidenceRibbonDefault).toBeDefined();
    expect(EvidenceRibbon).toBe(EvidenceRibbonDefault);
  });

  it("renders with default props without errors", () => {
    const { container } = render(<EvidenceRibbon />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("aria-hidden", "true");
    expect(root).toHaveAttribute("data-artwork", "evidence-ribbon");
    expect(root).toHaveAttribute("data-variant", "horizontal");
    expect(root).toHaveAttribute("data-tone", "azure");
    expect(root).toHaveAttribute("data-active", "false");

    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("viewBox", "0 0 480 100");
  });

  it("applies custom className and style props", () => {
    const { container } = render(
      <EvidenceRibbon className="custom-ribbon-class" style={{ zIndex: 10 }} />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("custom-ribbon-class");
    expect(root.style.zIndex).toBe("10");
  });

  it.each(["horizontal", "vertical", "curved", "connector"] as const)(
    "renders correctly for variant %s",
    (variant) => {
      const { container } = render(<EvidenceRibbon variant={variant} active={true} />);
      const root = container.firstElementChild as HTMLElement;
      expect(root).toHaveAttribute("data-variant", variant);

      const svg = container.querySelector("svg");
      expect(svg).toBeInTheDocument();
      expect(svg?.getAttribute("viewBox")).toBeTruthy();

      const paths = container.querySelectorAll("svg path");
      expect(paths.length).toBeGreaterThan(1);
    }
  );

  it.each(["azure", "mint", "iris"] as const)("supports tone palette %s", (tone) => {
    const { container } = render(<EvidenceRibbon tone={tone} active={true} />);
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute("data-tone", tone);

    const linearGradients = container.querySelectorAll("linearGradient");
    expect(linearGradients.length).toBeGreaterThan(0);
  });

  it("handles active state toggle and ribbon path classes", () => {
    const { container, rerender } = render(<EvidenceRibbon active={false} />);
    let root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute("data-active", "false");
    expect(root.className).toContain("opacity-75");

    rerender(<EvidenceRibbon active={true} />);
    root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute("data-active", "true");
    expect(root.className).toContain("opacity-100");

    const ribbonPaths = container.querySelectorAll(".clara-ribbon-path");
    expect(ribbonPaths.length).toBeGreaterThan(0);
  });

  it("contains anchor node and destination source beacon", () => {
    const { container } = render(<EvidenceRibbon variant="horizontal" active={true} />);
    expect(container.querySelector("#claim-anchor-node")).toBeInTheDocument();
    expect(container.querySelector("#waypoint-bridge-node")).toBeInTheDocument();
    expect(container.querySelector("#source-beacon-node")).toBeInTheDocument();
  });
});
