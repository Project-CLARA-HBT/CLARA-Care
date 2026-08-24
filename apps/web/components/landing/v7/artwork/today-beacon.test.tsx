import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TodayBeaconDefault, {
  TodayBeacon,
  type TodayBeaconTone,
  type TodayBeaconSize,
  type TodayBeaconPlacement,
} from "./today-beacon";

describe("TodayBeacon Artwork Component (Landing v7 Spatial Anchor)", () => {
  it("exports both named TodayBeacon and default export", () => {
    expect(TodayBeacon).toBeDefined();
    expect(TodayBeaconDefault).toBeDefined();
    expect(TodayBeacon).toBe(TodayBeaconDefault);
  });

  it("renders with default props (active=true, label='Hôm nay', tone='azure', size='md')", () => {
    render(<TodayBeacon />);
    const beacon = screen.getByTestId("today-beacon");

    expect(beacon).toBeInTheDocument();
    expect(beacon).toHaveAttribute("data-artwork", "today-beacon");
    expect(beacon).toHaveAttribute("data-active", "true");
    expect(beacon).toHaveAttribute("data-tone", "azure");
    expect(beacon).toHaveAttribute("data-size", "md");
    expect(beacon).toHaveAttribute("aria-label", "Hôm nay");

    expect(screen.getByText("Hôm nay")).toBeInTheDocument();
  });

  it("renders custom label and custom className", () => {
    render(<TodayBeacon label="Current Milestone" className="custom-timeline-anchor" />);
    const beacon = screen.getByTestId("today-beacon");

    expect(beacon.className).toContain("custom-timeline-anchor");
    expect(screen.getByText("Current Milestone")).toBeInTheDocument();
    expect(beacon).toHaveAttribute("aria-label", "Current Milestone");
  });

  it.each(["azure", "mint", "iris"] as TodayBeaconTone[])(
    "renders correctly for tone '%s'",
    (tone) => {
      render(<TodayBeacon tone={tone} label={`Tone ${tone}`} />);
      const beacon = screen.getByTestId("today-beacon");
      expect(beacon).toHaveAttribute("data-tone", tone);
      expect(screen.getByText(`Tone ${tone}`)).toBeInTheDocument();
    }
  );

  it.each(["sm", "md", "lg"] as TodayBeaconSize[])(
    "renders correctly for size variant '%s'",
    (size) => {
      render(<TodayBeacon size={size} />);
      const beacon = screen.getByTestId("today-beacon");
      expect(beacon).toHaveAttribute("data-size", size);
    }
  );

  it("handles active=false state gracefully without active ping animation layers", () => {
    const { container, rerender } = render(<TodayBeacon active={false} />);
    const beacon = screen.getByTestId("today-beacon");
    expect(beacon).toHaveAttribute("data-active", "false");

    // Ping animation elements should not be pulsing in inactive state
    const pingAnimations = container.querySelectorAll(".motion-safe\\:animate-\\[ping_3\\.2s_cubic-bezier\\(0\\,0\\,0\\.2\\,1\\)_infinite\\]");
    expect(pingAnimations.length).toBe(0);

    rerender(<TodayBeacon active={true} />);
    expect(screen.getByTestId("today-beacon")).toHaveAttribute("data-active", "true");
    const activePing = container.querySelectorAll(".motion-safe\\:animate-\\[ping_3\\.2s_cubic-bezier\\(0\\,0\\,0\\.2\\,1\\)_infinite\\]");
    expect(activePing.length).toBeGreaterThan(0);
  });

  it("renders concentric ring waves and spatial crosshair lines inside SVG", () => {
    const { container } = render(<TodayBeacon tone="azure" active={true} />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    const circles = svg?.querySelectorAll("circle");
    // Outer wave (r=28), Middle wave (r=20), Inner wave (r=14), Core sphere (r=8.5), Pin dot (r=1.75)
    expect(circles?.length).toBeGreaterThanOrEqual(5);

    const crosshairLines = svg?.querySelectorAll("line");
    // North, South, West, East calibration ticks
    expect(crosshairLines?.length).toBe(4);
  });

  it("supports label placement variants ('right', 'bottom', 'top', 'badge', 'none')", () => {
    const placements: TodayBeaconPlacement[] = ["right", "bottom", "top", "badge"];

    placements.forEach((placement) => {
      const { unmount } = render(<TodayBeacon labelPlacement={placement} label="Present" />);
      expect(screen.getByText("Present")).toBeInTheDocument();
      unmount();
    });

    // Placement 'none' should not render label text badge
    render(<TodayBeacon labelPlacement="none" label="Hidden Label" />);
    expect(screen.queryByText("Hidden Label")).toBeNull();
  });

  it("supports showLabel=false to hide badge while keeping accessible aria-label", () => {
    render(<TodayBeacon showLabel={false} label="Accessible Only" />);
    expect(screen.queryByText("Accessible Only")).toBeNull();
    expect(screen.getByTestId("today-beacon")).toHaveAttribute("aria-label", "Accessible Only");
  });

  it("supports interactive click handler and keyboard navigation", () => {
    const onClick = vi.fn();
    render(<TodayBeacon onClick={onClick} label="Interactive Today" />);

    const beacon = screen.getByRole("button", { name: "Interactive Today" });
    expect(beacon).toBeInTheDocument();

    fireEvent.click(beacon);
    expect(onClick).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(beacon, { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(2);

    fireEvent.keyDown(beacon, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(3);
  });

  it("includes Reduced Motion motion-reduce utilities for calm accessibility", () => {
    const { container } = render(<TodayBeacon active={true} />);
    const reducedMotionNodes = container.querySelectorAll(".motion-reduce\\:animate-none");
    expect(reducedMotionNodes.length).toBeGreaterThan(0);

    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("class")).toContain("motion-reduce:transform-none");
  });

  it("ensures zero clinical severity / emergency / diagnostic leakage", () => {
    const { container } = render(<TodayBeacon tone="azure" label="Hôm nay" />);
    const html = container.innerHTML.toLowerCase();

    expect(html).not.toContain("emergency");
    expect(html).not.toContain("triage");
    expect(html).not.toContain("critical");
    expect(html).not.toContain("warning");
    expect(html).not.toContain("diagnosis");
  });
});
