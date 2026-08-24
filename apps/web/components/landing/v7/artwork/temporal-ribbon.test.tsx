import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import TemporalRibbonDefault, {
  TemporalRibbon,
  getCategoryBadgeClass,
  DEFAULT_TEMPORAL_EVENTS,
  type TemporalEvent,
} from "./temporal-ribbon";

describe("TemporalRibbon Artwork Component (Landing v7 LifeMap Longitudinal Continuum)", () => {
  it("exports both named and default TemporalRibbon component", () => {
    expect(TemporalRibbon).toBeDefined();
    expect(TemporalRibbonDefault).toBeDefined();
    expect(TemporalRibbon).toBe(TemporalRibbonDefault);
  });

  it("renders with default props and connects historical events to Today", () => {
    const { container } = render(<TemporalRibbon />);
    const root = screen.getByTestId("temporal-ribbon");

    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute("data-artwork", "temporal-ribbon");
    expect(root).toHaveAttribute("data-selected-index", "3"); // Default to Today (4th event)
    expect(root).toHaveAttribute("data-progress", "1.00");

    // Header checks
    expect(screen.getByText(/LIFEMAP LONGITUDINAL CONTINUUM/i)).toBeInTheDocument();
    expect(screen.getByText(/Dòng thời gian sức khỏe liên tục/i)).toBeInTheDocument();
    expect(screen.getByText(/4 Mốc liên kết/i)).toBeInTheDocument();

    // Default timeline events check
    expect(screen.getAllByText("Khởi phát triệu chứng").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bắt đầu phác đồ thuốc").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Khám tái khám định kỳ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Câu hỏi về điều chỉnh giờ uống").length).toBeGreaterThan(0);

    // Desktop SVG timeline check
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();

    // TodayBeacon anchor presence
    const beacons = screen.getAllByTestId("today-beacon");
    expect(beacons.length).toBeGreaterThan(0);
  });

  it("accepts custom events array and custom className", () => {
    const customEvents: TemporalEvent[] = [
      {
        period: "Tuần 1",
        title: "Ghi nhận chỉ số HA cao",
        detail: "Đo tại nhà 150/95 mmHg, ghi chép vào sổ theo dõi.",
        category: "Triệu chứng",
        emphasis: "past",
      },
      {
        period: "Tuần 2",
        title: "Bác sĩ điều chỉnh liều",
        detail: "Tăng liều Losartan từ 25mg lên 50mg mỗi sáng.",
        category: "Kê đơn",
        emphasis: "recent",
      },
      {
        period: "Hôm nay",
        title: "Đạt huyết áp mục tiêu",
        detail: "Huyết áp ổn định 120/80 mmHg liên tục 7 ngày.",
        category: "Tương tác mới",
        emphasis: "today",
      },
    ];

    render(
      <TemporalRibbon
        events={customEvents}
        className="custom-lifemap-ribbon"
        ariaLabel="Custom LifeMap Flow"
      />
    );

    const root = screen.getByTestId("temporal-ribbon");
    expect(root.className).toContain("custom-lifemap-ribbon");
    expect(root).toHaveAttribute("aria-label", "Custom LifeMap Flow");

    expect(screen.getAllByText("Ghi nhận chỉ số HA cao").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bác sĩ điều chỉnh liều").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Đạt huyết áp mục tiêu").length).toBeGreaterThan(0);
  });

  it("handles controlled selectedIndex and updates active stage", () => {
    const { rerender } = render(<TemporalRibbon selectedIndex={0} />);
    let root = screen.getByTestId("temporal-ribbon");
    expect(root).toHaveAttribute("data-selected-index", "0");

    // Detail panel reflects stage 0
    expect(screen.getByText("Mốc 1/4 • Tháng 4")).toBeInTheDocument();

    rerender(<TemporalRibbon selectedIndex={2} />);
    root = screen.getByTestId("temporal-ribbon");
    expect(root).toHaveAttribute("data-selected-index", "2");
    expect(screen.getByText("Mốc 3/4 • Tháng 6")).toBeInTheDocument();
  });

  it("triggers onSelect callback when clicking desktop milestone cards", () => {
    const onSelect = vi.fn();
    render(<TemporalRibbon onSelect={onSelect} />);

    // Click stage 1 card (Tháng 5)
    const tab1 = screen.getByTestId("desktop-tab-1");
    fireEvent.click(tab1);

    expect(onSelect).toHaveBeenCalledWith(1);
    expect(screen.getByTestId("temporal-ribbon")).toHaveAttribute("data-selected-index", "1");
  });

  it("supports keyboard navigation with ArrowLeft and ArrowRight on desktop tabs", () => {
    const onSelect = vi.fn();
    render(<TemporalRibbon selectedIndex={1} onSelect={onSelect} />);

    const currentTab = screen.getByTestId("desktop-tab-1");

    // Press ArrowRight -> moves to stage 2
    fireEvent.keyDown(currentTab, { key: "ArrowRight" });
    expect(onSelect).toHaveBeenCalledWith(2);

    // Press ArrowLeft -> moves to stage 0
    fireEvent.keyDown(currentTab, { key: "ArrowLeft" });
    expect(onSelect).toHaveBeenCalledWith(0);
  });

  it("clamps progress correctly between 0 and 1", () => {
    const { rerender } = render(<TemporalRibbon progress={-0.5} />);
    expect(screen.getByTestId("temporal-ribbon")).toHaveAttribute("data-progress", "0.00");

    rerender(<TemporalRibbon progress={0.75} />);
    expect(screen.getByTestId("temporal-ribbon")).toHaveAttribute("data-progress", "0.75");

    rerender(<TemporalRibbon progress={1.8} />);
    expect(screen.getByTestId("temporal-ribbon")).toHaveAttribute("data-progress", "1.00");
  });

  it("renders mobile vertical temporal ribbon with node anchors and buttons", () => {
    const onSelect = vi.fn();
    const { container } = render(<TemporalRibbon onSelect={onSelect} />);

    // Vertical track line
    const mobileTrack = container.querySelector(".bg-gradient-to-b.from-\\[\\#94A3B8\\]");
    expect(mobileTrack).toBeInTheDocument();

    const mobileView = screen.getByTestId("mobile-timeline-view");
    expect(mobileView).toBeInTheDocument();

    // Click mobile stage 2 button
    const mobileTab2 = screen.getByTestId("mobile-tab-2");
    fireEvent.click(mobileTab2);
    expect(onSelect).toHaveBeenCalledWith(2);
  });

  it("returns appropriate badge classes via getCategoryBadgeClass helper", () => {
    expect(getCategoryBadgeClass("Hôm nay", "today")).toContain("bg-[#EFF7FF]");
    expect(getCategoryBadgeClass("Triệu chứng", "past")).toContain("bg-[#FEF3F2]");
    expect(getCategoryBadgeClass("Kê đơn", "past")).toContain("bg-[#F5F3FF]");
    expect(getCategoryBadgeClass("Tái khám", "recent")).toContain("bg-[#ECFDF8]");
    expect(getCategoryBadgeClass("Khác", "past")).toContain("bg-[#F1F5F9]");
  });

  it("includes graceful reduced-motion utilities for accessibility", () => {
    const { container } = render(<TemporalRibbon />);
    const reducedMotionNodes = container.querySelectorAll(".motion-reduce\\:animate-none");
    expect(reducedMotionNodes.length).toBeGreaterThan(0);
  });

  it("verifies DEFAULT_TEMPORAL_EVENTS length and structure", () => {
    expect(DEFAULT_TEMPORAL_EVENTS.length).toBe(4);
    expect(DEFAULT_TEMPORAL_EVENTS[3].emphasis).toBe("today");
    expect(DEFAULT_TEMPORAL_EVENTS[0].emphasis).toBe("past");
  });
});
