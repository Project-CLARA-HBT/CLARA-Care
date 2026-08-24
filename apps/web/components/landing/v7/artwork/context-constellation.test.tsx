import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ContextConstellationDefault, {
  ContextConstellation,
} from "./context-constellation";

describe("ContextConstellation Artwork Component (Landing v7)", () => {
  it("exports both named and default component cleanly", () => {
    expect(ContextConstellation).toBeDefined();
    expect(ContextConstellationDefault).toBeDefined();
    expect(ContextConstellation).toBe(ContextConstellationDefault);
  });

  it("renders with default props (progress=0.5, language='vi')", () => {
    render(<ContextConstellation />);
    const root = screen.getByTestId("context-constellation");
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("data-artwork", "context-constellation");
    expect(root).toHaveAttribute("data-progress", "0.50");
    expect(root).toHaveAttribute("data-language", "vi");

    // Vietnamese titles check
    expect(screen.getAllByText("CLARA Core").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Thuốc đang dùng").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Thay đổi gần đây").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hồ sơ sức khỏe").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Câu hỏi trước đây").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Nguồn y văn đối chiếu").length).toBeGreaterThan(0);
  });

  it("renders English copy when language='en'", () => {
    render(<ContextConstellation language="en" />);
    const root = screen.getByTestId("context-constellation");
    expect(root).toHaveAttribute("data-language", "en");

    expect(screen.getAllByText("Active Medications").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Recent Changes").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Health Record").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Prior Questions").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Evidence Sources").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Safety Convergence Engine").length).toBeGreaterThan(0);
  });

  it("clamps progress between 0 and 1 correctly", () => {
    const { rerender } = render(<ContextConstellation progress={-0.8} />);
    expect(screen.getByTestId("context-constellation")).toHaveAttribute("data-progress", "0.00");

    rerender(<ContextConstellation progress={1.5} />);
    expect(screen.getByTestId("context-constellation")).toHaveAttribute("data-progress", "1.00");

    rerender(<ContextConstellation progress={0.75} />);
    expect(screen.getByTestId("context-constellation")).toHaveAttribute("data-progress", "0.75");
  });

  it("highlights activeNodeId when provided (direct id or alias)", () => {
    const { rerender } = render(<ContextConstellation activeNodeId="medications" />);
    expect(screen.getByTestId("context-constellation")).toHaveAttribute("data-active-node", "medications");

    const medButtons = screen.getAllByRole("button", { name: /Thuốc đang dùng/i });
    expect(medButtons.length).toBeGreaterThan(0);
    expect(medButtons[0]).toHaveAttribute("aria-pressed", "true");

    // Test alias matching
    rerender(<ContextConstellation activeNodeId="recentChanges" />);
    const changeButtons = screen.getAllByRole("button", { name: /Thay đổi gần đây/i });
    expect(changeButtons[0]).toHaveAttribute("aria-pressed", "true");
  });

  it("invokes onNodeClick callback when nodes or central core are clicked", () => {
    const onNodeClick = vi.fn();
    render(<ContextConstellation onNodeClick={onNodeClick} language="vi" />);

    // Click medications card
    const medButtons = screen.getAllByRole("button", { name: /Thuốc đang dùng/i });
    fireEvent.click(medButtons[0]);
    expect(onNodeClick).toHaveBeenCalledWith("medications");

    // Click CLARA Core button
    const coreButtons = screen.getAllByRole("button", { name: /CLARA Core/i });
    fireEvent.click(coreButtons[0]);
    expect(onNodeClick).toHaveBeenCalledWith("clara-core");

    // Click Health Record
    const recordButtons = screen.getAllByRole("button", { name: /Hồ sơ sức khỏe/i });
    fireEvent.click(recordButtons[0]);
    expect(onNodeClick).toHaveBeenCalledWith("health-record");
  });

  it("renders SVG connector canvas on desktop with particle animations and paths", () => {
    const { container } = render(<ContextConstellation progress={0.6} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThan(5);

    const particles = container.querySelectorAll("animateMotion");
    expect(particles.length).toBe(5);
  });

  it("applies custom className", () => {
    render(<ContextConstellation className="test-custom-constellation" />);
    const root = screen.getByTestId("context-constellation");
    expect(root.className).toContain("test-custom-constellation");
  });
});
