import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { ScenarioPath } from "./scenario-path";

describe("ScenarioPath Artwork Component", () => {
  it("renders with default props without errors", () => {
    const { container } = render(<ScenarioPath />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("viewBox", "0 0 600 140");
  });

  it("accepts and applies custom className and style props", () => {
    const { container } = render(
      <ScenarioPath className="custom-scenario-path-class" style={{ opacity: 0.8 }} />
    );
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("custom-scenario-path-class");
    expect(root.style.opacity).toBe("0.8");
  });

  it("handles active state properly", () => {
    const { container, rerender } = render(<ScenarioPath active={false} />);
    let root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("opacity-75");

    rerender(<ScenarioPath active={true} />);
    root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("opacity-100");

    // Glow and active paths should be present when active
    const paths = container.querySelectorAll("svg path");
    expect(paths.length).toBeGreaterThan(2);
  });

  it.each([0, 1, 2, 3, 4, 7])("renders distinct path variants for index %d", (index) => {
    const { container } = render(<ScenarioPath index={index} active={true} />);
    const paths = container.querySelectorAll("svg path");
    expect(paths.length).toBeGreaterThan(0);
    const dAttr = paths[0]?.getAttribute("d");
    expect(dAttr).toBeTruthy();
  });

  it("includes gradient defs and marker arrow for directional guidance", () => {
    const { container } = render(<ScenarioPath index={0} active={true} />);
    const marker = container.querySelector("marker");
    expect(marker).toBeInTheDocument();
    expect(marker?.querySelector("path")).toBeInTheDocument();

    const linearGradients = container.querySelectorAll("linearGradient");
    expect(linearGradients.length).toBeGreaterThanOrEqual(1);
  });
});
