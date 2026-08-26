import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import EvidenceRibbonDefault, {
  EvidenceRibbon,
  TONE_CONFIG,
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
    expect(svg).toHaveAttribute("focusable", "false");
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

    const config = TONE_CONFIG[tone];
    expect(config.glowColor).toBeTruthy();
    expect(config.lightHeadStop).toBe("#FFFFFF");
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

  it("contains anchor node, waypoint bridge, and destination source beacon", () => {
    const { container } = render(<EvidenceRibbon variant="horizontal" active={true} />);
    expect(container.querySelector("#claim-anchor-node")).toBeInTheDocument();
    expect(container.querySelector("#waypoint-bridge-node")).toBeInTheDocument();
    expect(container.querySelector("#source-beacon-node")).toBeInTheDocument();
  });

  it("includes SVG filter with glowing drop shadow and feDropShadow primitive", () => {
    const { container } = render(<EvidenceRibbon active={true} tone="azure" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.style.filter).toContain("drop-shadow(0 0 8px rgba(14, 165, 233, 0.4))");

    const feDropShadow = container.querySelector("feDropShadow");
    expect(feDropShadow).toBeInTheDocument();
    expect(feDropShadow?.getAttribute("flood-color")).toBe("rgba(14, 165, 233, 0.4)");
  });

  it("renders traveling gradient light head in Enhanced and Standard tiers", () => {
    const { container } = render(
      <EvidenceRibbon active={true} motionTier="enhanced" variant="horizontal" />
    );
    const gradHead = container.querySelector("linearGradient[id^='ribbon-grad-head-']");
    expect(gradHead).toBeInTheDocument();

    const ribbonPaths = container.querySelectorAll(".clara-ribbon-path");
    expect(ribbonPaths.length).toBeGreaterThan(0);
  });

  it("degrades gracefully to static clean gradient path in Lite or Reduced motion tiers", () => {
    const { container } = render(
      <EvidenceRibbon active={true} motionTier="lite" variant="horizontal" />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root).toHaveAttribute("data-motion-tier", "lite");

    // In Lite tier, active animated dash paths are disabled in favor of static clean path
    const animatedPaths = container.querySelectorAll(".clara-ribbon-path");
    expect(animatedPaths.length).toBe(0);

    const staticPaths = container.querySelectorAll("path");
    expect(staticPaths.length).toBeGreaterThan(0);
  });

  it("renders connector variant with intake nodes and convergence hub", () => {
    const { container } = render(<EvidenceRibbon variant="connector" active={true} />);
    expect(container.querySelector("#claim-anchor-node-top")).toBeInTheDocument();
    expect(container.querySelector("#claim-anchor-node-bottom")).toBeInTheDocument();
    expect(container.querySelector("#convergence-hub-node")).toBeInTheDocument();
    expect(container.querySelector("#source-beacon-node")).toBeInTheDocument();
  });
});
