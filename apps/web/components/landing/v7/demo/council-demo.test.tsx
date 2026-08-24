import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import CouncilDemoDefault, { CouncilDemo } from "./council-demo";
import { MotionProvider } from "../runtime/motion-provider";

describe("CouncilDemo (Landing v7 Interactive Deliberation Demo)", () => {
  it("exports both named and default CouncilDemo", () => {
    expect(CouncilDemo).toBeDefined();
    expect(CouncilDemoDefault).toBeDefined();
    expect(CouncilDemo).toBe(CouncilDemoDefault);
  });

  it("renders with default props, governance disclaimer, and integrated DecisionField", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <CouncilDemo />
      </MotionProvider>
    );

    expect(screen.getByTestId("council-demo")).toBeInTheDocument();
    expect(screen.getByTestId("decision-field")).toBeInTheDocument();

    // Disclaimer
    expect(
      screen.getByText(/CLARA không tự quyết định điều trị/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bác sĩ giữ quyền tối cao")
    ).toBeInTheDocument();

    // 3 specialties
    expect(screen.getAllByText("Tim mạch").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Thận học").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dược lâm sàng").length).toBeGreaterThan(0);

    // 4 Deliberation Tabs
    expect(screen.getByRole("tab", { name: /1\. Khuyến nghị/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /2\. Điểm bất đồng/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /3\. Chưa chắc chắn/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /4\. Bước tiếp theo/i })).toBeInTheDocument();

    // Default stage is 1: Multidisciplinary Recommendation
    expect(screen.getByRole("tab", { name: /1\. Khuyến nghị/i })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: /1\. Khuyến nghị/i })).toBeInTheDocument();
    expect(screen.getByText(/Đồng thuận đa khoa/i)).toBeInTheDocument();
  });

  it("smoothly transitions tabs and updates stage content with accent color halo", () => {
    const onStageChange = vi.fn();
    render(
      <MotionProvider initialLanguage="vi">
        <CouncilDemo onStageChange={onStageChange} />
      </MotionProvider>
    );

    // Click Stage 2: Disagreements
    const disagreementsTab = screen.getByRole("tab", { name: /2\. Điểm bất đồng/i });
    fireEvent.click(disagreementsTab);

    expect(onStageChange).toHaveBeenCalledWith(2);
    expect(disagreementsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Cần bác sĩ phán quyết/i)).toBeInTheDocument();

    // Click Stage 3: Uncertainty
    const uncertaintyTab = screen.getByRole("tab", { name: /3\. Chưa chắc chắn/i });
    fireEvent.click(uncertaintyTab);

    expect(onStageChange).toHaveBeenCalledWith(3);
    expect(uncertaintyTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Thiếu dữ liệu/i)).toBeInTheDocument();

    // Click Stage 4: Next Steps
    const nextStepsTab = screen.getByRole("tab", { name: /4\. Bước tiếp theo/i });
    fireEvent.click(nextStepsTab);

    expect(onStageChange).toHaveBeenCalledWith(4);
    expect(nextStepsTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Kế hoạch đề xuất/i)).toBeInTheDocument();
  });

  it("synchronizes with external activeStage prop", () => {
    const { rerender } = render(
      <MotionProvider initialLanguage="vi">
        <CouncilDemo activeStage={1} />
      </MotionProvider>
    );

    expect(screen.getByRole("tab", { name: /1\. Khuyến nghị/i })).toHaveAttribute("aria-selected", "true");

    // Rerender with activeStage=2
    rerender(
      <MotionProvider initialLanguage="vi">
        <CouncilDemo activeStage={2} />
      </MotionProvider>
    );

    expect(screen.getByRole("tab", { name: /2\. Điểm bất đồng/i })).toHaveAttribute("aria-selected", "true");
  });

  it("renders properly in English when language is 'en'", () => {
    render(
      <MotionProvider initialLanguage="en">
        <CouncilDemo />
      </MotionProvider>
    );

    expect(screen.getByText(/Physician Holds Ultimate Authority/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /1\. Recommendation/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /2\. Disagreements/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /3\. Uncertainty/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /4\. Next Steps/i })).toBeInTheDocument();
  });
});
