import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LifeMapDemoDefault, { LifeMapDemo } from "./lifemap-demo";
import { MotionProvider } from "../runtime/motion-provider";

describe("LifeMapDemo (Landing v7 Interactive Signature Demo)", () => {
  it("exports both named and default LifeMapDemo", () => {
    expect(LifeMapDemo).toBeDefined();
    expect(LifeMapDemoDefault).toBeDefined();
    expect(LifeMapDemo).toBe(LifeMapDemoDefault);
  });

  it("renders the 4-month longitudinal timeline milestones (Tháng 4 -> Tháng 5 -> Tháng 6 -> Hôm nay)", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <LifeMapDemo />
      </MotionProvider>
    );

    expect(screen.getByTestId("lifemap-demo")).toBeInTheDocument();

    // Check title and description
    expect(screen.getByText("Sức khỏe không phải một bức ảnh tĩnh.")).toBeInTheDocument();
    expect(
      screen.getByText(/LifeMap liên kết các triệu chứng, lần đổi thuốc và kết quả xét nghiệm/i)
    ).toBeInTheDocument();

    // Check 4 timeline stages
    expect(screen.getAllByText("Tháng 4").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tháng 5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Tháng 6").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hôm nay").length).toBeGreaterThan(0);

    // Check titles for events
    expect(screen.getAllByText("Khởi phát triệu chứng").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bắt đầu phác đồ thuốc").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Khám tái khám định kỳ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Câu hỏi về điều chỉnh giờ uống").length).toBeGreaterThan(0);

    // Check artwork components
    expect(screen.getAllByTestId("today-beacon").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("region", { name: /LifeMap Longitudinal Temporal Ribbon/i })
    ).toBeInTheDocument();
  });

  it("renders the prominent Floating Context Insight Callout with action button", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <LifeMapDemo />
      </MotionProvider>
    );

    const insightCallout = screen.getByTestId("lifemap-insight-callout");
    expect(insightCallout).toBeInTheDocument();

    // Tag
    expect(screen.getByText("PHÁT HIỆN TỪ LIFEMAP")).toBeInTheDocument();

    // Prominent insight text
    expect(
      screen.getByText("Có một thay đổi đáng chú ý kể từ lần trước")
    ).toBeInTheDocument();

    // Insight body
    expect(
      screen.getByText(/Huyết áp của bạn đã duy trì ở mức mục tiêu 60 ngày liên tục/i)
    ).toBeInTheDocument();

    // Action button
    const actionBtn = screen.getByTestId("lifemap-insight-action-btn");
    expect(actionBtn).toBeInTheDocument();
    expect(actionBtn).toHaveTextContent("Xem toàn bộ dòng thời gian");

    // Click action button triggers confirmation banner
    fireEvent.click(actionBtn);
    expect(screen.getByTestId("lifemap-insight-feedback")).toBeInTheDocument();
    expect(
      screen.getByText(/Đã đồng bộ toàn bộ dữ liệu 4 tháng vào không gian phân tích LifeMap/i)
    ).toBeInTheDocument();
  });

  it("interactively updates the detail card when selecting milestones", () => {
    const onMilestoneChange = vi.fn();
    render(
      <MotionProvider initialLanguage="vi">
        <LifeMapDemo onMilestoneChange={onMilestoneChange} />
      </MotionProvider>
    );

    const detailCard = screen.getByTestId("lifemap-detail-card");
    expect(detailCard).toBeInTheDocument();

    // Default milestone is 3 (Hôm nay / Today)
    expect(screen.getAllByText(/Câu hỏi về điều chỉnh giờ uống/i).length).toBeGreaterThan(0);

    // Switch to Milestone 0 (Tháng 4) using quick tab
    const tabMonth4 = screen.getByRole("tab", { name: "Tháng 4" });
    fireEvent.click(tabMonth4);

    expect(onMilestoneChange).toHaveBeenCalledWith(0);
    expect(screen.getAllByText(/Khởi phát triệu chứng/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Xuất hiện cơn đau đầu âm ỉ vùng chẩm vào buổi sáng sớm/i).length
    ).toBeGreaterThan(0);

    // Switch to Milestone 1 (Tháng 5)
    const tabMonth5 = screen.getByRole("tab", { name: "Tháng 5" });
    fireEvent.click(tabMonth5);

    expect(onMilestoneChange).toHaveBeenCalledWith(1);
    expect(screen.getAllByText(/Bắt đầu phác đồ thuốc/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/Bác sĩ chỉ định Amlodipine 5mg\/ngày/i).length
    ).toBeGreaterThan(0);

    // Switch to Milestone 2 (Tháng 6)
    const tabMonth6 = screen.getByRole("tab", { name: "Tháng 6" });
    fireEvent.click(tabMonth6);

    expect(onMilestoneChange).toHaveBeenCalledWith(2);
    expect(screen.getAllByText(/Khám tái khám định kỳ/i).length).toBeGreaterThan(0);
  });

  it("supports keyboard navigation and stepper controls", () => {
    const onMilestoneChange = vi.fn();
    render(
      <MotionProvider initialLanguage="vi">
        <LifeMapDemo onMilestoneChange={onMilestoneChange} />
      </MotionProvider>
    );

    // Initial selected is Hôm nay (idx 3)
    let prevBtn = screen.getByRole("button", { name: /Mốc trước/i });
    expect(prevBtn).not.toBeDisabled();

    // Click Previous -> selects index 2 (Tháng 6)
    fireEvent.click(prevBtn);
    expect(onMilestoneChange).toHaveBeenLastCalledWith(2);

    // Click Previous -> selects index 1 (Tháng 5)
    prevBtn = screen.getByRole("button", { name: /Mốc trước/i });
    fireEvent.click(prevBtn);
    expect(onMilestoneChange).toHaveBeenLastCalledWith(1);

    // Click Previous -> selects index 0 (Tháng 4)
    prevBtn = screen.getByRole("button", { name: /Mốc trước/i });
    fireEvent.click(prevBtn);
    expect(onMilestoneChange).toHaveBeenLastCalledWith(0);
    expect(screen.getByRole("button", { name: /Mốc trước/i })).toBeDisabled();

    // Next button moves forward
    let nextBtn = screen.getByRole("button", { name: /Mốc tiếp theo/i });
    fireEvent.click(nextBtn);
    expect(onMilestoneChange).toHaveBeenLastCalledWith(1);

    // Keyboard ArrowRight on quick tab
    const tabMonth5 = screen.getByRole("tab", { name: "Tháng 5" });
    fireEvent.keyDown(tabMonth5, { key: "ArrowRight" });
    expect(onMilestoneChange).toHaveBeenLastCalledWith(2);

    // Keyboard ArrowLeft
    const tabMonth6 = screen.getByRole("tab", { name: "Tháng 6" });
    fireEvent.keyDown(tabMonth6, { key: "ArrowLeft" });
    expect(onMilestoneChange).toHaveBeenLastCalledWith(1);
  });

  it("dismisses insight feedback banner when dismiss button is clicked", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <LifeMapDemo />
      </MotionProvider>
    );

    const actionBtn = screen.getByTestId("lifemap-insight-action-btn");
    fireEvent.click(actionBtn);

    const feedback = screen.getByTestId("lifemap-insight-feedback");
    expect(feedback).toBeInTheDocument();

    const dismissBtn = screen.getByRole("button", { name: "Đóng" });
    fireEvent.click(dismissBtn);

    expect(screen.queryByTestId("lifemap-insight-feedback")).not.toBeInTheDocument();
  });

  it("renders correctly in English when language is 'en'", () => {
    render(
      <MotionProvider initialLanguage="en">
        <LifeMapDemo />
      </MotionProvider>
    );

    expect(screen.getByText("Health is not a static snapshot.")).toBeInTheDocument();
    expect(screen.getAllByText("April").length).toBeGreaterThan(0);
    expect(screen.getAllByText("May").length).toBeGreaterThan(0);
    expect(screen.getAllByText("June").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Today").length).toBeGreaterThan(0);

    // English Insight Callout
    expect(screen.getByText("LIFEMAP INSIGHT")).toBeInTheDocument();
    expect(
      screen.getByText("Notable change observed since your last review")
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Your blood pressure has remained at target range for 60 consecutive days/i)
    ).toBeInTheDocument();

    const actionBtn = screen.getByTestId("lifemap-insight-action-btn");
    expect(actionBtn).toHaveTextContent("Explore Full Health Timeline");
  });
});
