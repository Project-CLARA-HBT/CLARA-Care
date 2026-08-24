import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DecisionField } from "./decision-field";

describe("DecisionField Artwork Component", () => {
  it("renders with default props (activeStage=1)", () => {
    render(<DecisionField />);
    const root = screen.getByTestId("decision-field");
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("data-active-stage", "1");
    expect(screen.getByText("Council Multi-Specialty Convergence Field")).toBeInTheDocument();
    expect(screen.getAllByText("Tim mạch").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Thận học").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dược lâm sàng").length).toBeGreaterThan(0);
  });

  it("applies custom className", () => {
    render(<DecisionField className="custom-test-class" />);
    const root = screen.getByTestId("decision-field");
    expect(root.className).toContain("custom-test-class");
  });

  it.each([1, 2, 3, 4] as const)("renders correctly for activeStage %d", (stage) => {
    render(<DecisionField activeStage={stage} />);
    const root = screen.getByTestId("decision-field");
    expect(root).toHaveAttribute("data-active-stage", String(stage));
  });

  it("clamps out-of-range activeStage correctly", () => {
    const { rerender } = render(<DecisionField activeStage={0} />);
    expect(screen.getByTestId("decision-field")).toHaveAttribute("data-active-stage", "1");

    rerender(<DecisionField activeStage={99} />);
    expect(screen.getByTestId("decision-field")).toHaveAttribute("data-active-stage", "4");
  });

  it("triggers onStageChange when stage tabs or interactive layers are clicked", () => {
    const onStageChange = vi.fn();
    render(<DecisionField activeStage={1} onStageChange={onStageChange} />);

    // Click stage 2 button
    const stage2Btn = screen.getByRole("tab", { name: /02/i });
    fireEvent.click(stage2Btn);
    expect(onStageChange).toHaveBeenCalledWith(2);

    // Click stage 4 button
    const stage4Btn = screen.getByRole("tab", { name: /04/i });
    fireEvent.click(stage4Btn);
    expect(onStageChange).toHaveBeenCalledWith(4);
  });

  it("contains SVG converging stream elements and specialty accents", () => {
    const { container } = render(<DecisionField activeStage={2} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg?.querySelector("#stream-cardiology")).toBeInTheDocument();
    expect(svg?.querySelector("#stream-nephrology")).toBeInTheDocument();
    expect(svg?.querySelector("#stream-pharmacology")).toBeInTheDocument();
    expect(svg?.querySelector("#decision-result-plane")).toBeInTheDocument();
  });
});
