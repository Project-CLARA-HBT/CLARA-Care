import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import MedicinesDemoDefault, { MedicinesDemo } from "./medicines-demo";
import { MotionProvider } from "../runtime/motion-provider";

describe("MedicinesDemo (Landing v7 Interactive Demo)", () => {
  it("exports both named and default MedicinesDemo", () => {
    expect(MedicinesDemo).toBeDefined();
    expect(MedicinesDemoDefault).toBeDefined();
    expect(MedicinesDemo).toBe(MedicinesDemoDefault);
  });

  it("renders unified medication workspace with default 'Đang dùng' tab", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <MedicinesDemo />
      </MotionProvider>
    );

    // Header & Badge
    expect(screen.getByText("Không gian Quản lý Thuốc Thống nhất")).toBeInTheDocument();
    expect(screen.getByText("CareGuard Engine")).toBeInTheDocument();

    // Tabs
    expect(screen.getByTestId("tab-current")).toHaveTextContent("Đang dùng (2)");
    expect(screen.getByTestId("tab-needs-confirmation")).toHaveTextContent("Cần xác nhận (1)");
    expect(screen.getByTestId("tab-safety")).toHaveTextContent("Kiểm tra an toàn FIDES");
    expect(screen.getByTestId("tab-cabinet")).toHaveTextContent("Tủ thuốc gia đình (5)");

    // Active tab is 'current'
    expect(screen.getByTestId("tab-current")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("tab-needs-confirmation")).toHaveAttribute("aria-selected", "false");

    // Active meds are displayed in list
    expect(screen.getByTestId("med-item-med-1")).toBeInTheDocument();
    expect(screen.getByTestId("med-item-med-2")).toBeInTheDocument();

    // Inspector shows selected med details
    expect(screen.getByTestId("inspector-med-name")).toHaveTextContent("Metformin HCl");
    expect(screen.getByTestId("inspector-med-dosage")).toHaveTextContent("500 mg");
    expect(screen.getByTestId("inspector-med-schedule")).toHaveTextContent("1 viên × 2 lần/ngày (Sau bữa ăn chính)");
    expect(screen.getByTestId("inspector-med-notes")).toHaveTextContent(
      "Theo dõi chức năng thận định kỳ. Tránh uống khi bụng rỗng để giảm kích ứng tiêu hóa."
    );

    // Semantic Truth Reminder
    const reminder = screen.getByTestId("semantic-truth-reminder");
    expect(reminder).toBeInTheDocument();
    expect(reminder).toHaveTextContent("Tủ thuốc lưu trữ ≠ Thuốc đang uống hàng ngày");
  });

  it("switches tabs and updates medication list and inspector", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <MedicinesDemo />
      </MotionProvider>
    );

    // Switch to 'Cần xác nhận' tab
    const needsConfTab = screen.getByTestId("tab-needs-confirmation");
    fireEvent.click(needsConfTab);

    expect(needsConfTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("med-item-med-3")).toBeInTheDocument();
    expect(screen.queryByTestId("med-item-med-4")).not.toBeInTheDocument();

    // Inspector updates to Gliclazide MR
    expect(screen.getByTestId("inspector-med-name")).toHaveTextContent("Gliclazide MR");
    expect(screen.getByTestId("inspector-med-dosage")).toHaveTextContent("30 mg");

    // Switch to 'Tủ thuốc' tab
    const cabinetTab = screen.getByTestId("tab-cabinet");
    fireEvent.click(cabinetTab);

    expect(cabinetTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("med-item-med-4")).toBeInTheDocument();
    expect(screen.getByTestId("med-item-med-5")).toBeInTheDocument();

    // Inspector updates to Paracetamol
    expect(screen.getByTestId("inspector-med-name")).toHaveTextContent("Paracetamol");
  });

  it("updates right inspector when selecting a medication from the list", () => {
    render(
      <MotionProvider initialLanguage="vi">
        <MedicinesDemo />
      </MotionProvider>
    );

    // Click Amlodipine in current tab
    const amlodipineBtn = screen.getByTestId("med-item-med-2");
    fireEvent.click(amlodipineBtn);

    expect(screen.getByTestId("inspector-med-name")).toHaveTextContent("Amlodipine Besylate");
    expect(screen.getByTestId("inspector-med-dosage")).toHaveTextContent("5 mg");
    expect(screen.getByTestId("inspector-med-schedule")).toHaveTextContent("1 viên × 1 lần/ngày (08:00 sáng)");
    expect(screen.getByTestId("inspector-med-notes")).toHaveTextContent(
      "Duy trì uống đúng giờ mỗi ngày. Đã kiểm tra: Không đối kháng nguy hiểm với Metformin."
    );
  });

  it("renders correctly in English when language is 'en'", () => {
    render(
      <MotionProvider initialLanguage="en">
        <MedicinesDemo />
      </MotionProvider>
    );

    expect(screen.getByText("Unified Medication Workspace")).toBeInTheDocument();
    expect(screen.getByTestId("tab-current")).toHaveTextContent("Active (2)");
    expect(screen.getByTestId("tab-needs-confirmation")).toHaveTextContent("Needs Review (1)");
    expect(screen.getByTestId("tab-safety")).toHaveTextContent("FIDES Safety Check");
    expect(screen.getByTestId("tab-cabinet")).toHaveTextContent("Cabinet Storage (5)");

    // Status pills in English
    expect(screen.getAllByText("✓ Active").length).toBeGreaterThan(0);

    // Semantic truth reminder in English
    const reminder = screen.getByTestId("semantic-truth-reminder");
    expect(reminder).toHaveTextContent("Cabinet inventory ≠ Active daily intake");
  });
});
