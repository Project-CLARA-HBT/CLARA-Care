import type { ReactNode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getMedicationCourses: vi.fn(),
  checkDrugBankDdi: vi.fn(),
  correctMedicationCourse: vi.fn(),
  endMedicationCourse: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/lib/medication-courses", () => mocks);

import MedicinesListTab from "./list-tab";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getMedicationCourses.mockResolvedValue([]);
});

afterEach(cleanup);

describe("MedicinesListTab", () => {
  it("gives a first-time user exactly one medication-add action", async () => {
    render(<MedicinesListTab />);

    await waitFor(() => expect(screen.getByText("Chưa có thuốc nào")).toBeInTheDocument());

    const addLinks = screen.getAllByRole("link", { name: "Thêm thuốc theo từng bước" });
    expect(addLinks).toHaveLength(1);
    expect(addLinks[0]).toHaveAttribute("href", "/medicines/add");
    expect(screen.getByText("Thêm thuốc theo nhãn hoặc đơn của bạn")).toBeInTheDocument();
    expect(screen.getByText("Xác nhận thông tin trước khi theo dõi")).toBeInTheDocument();
    expect(screen.getByText("Kiểm tra an toàn khi có đủ thông tin")).toBeInTheDocument();
  });

  it("directs an active list to the one CareGuard interaction surface", async () => {
    mocks.getMedicationCourses.mockResolvedValue([
      {
        id: "med-1",
        version: 1,
        medication_name: "Thuốc đã xác nhận",
        dose_text: "",
        schedule_text: "",
        route_text: "",
        form_text: "",
        drugbank_id: null,
        status: "active",
        reconciliation_status: "matched",
      },
    ]);
    render(<MedicinesListTab />);

    const safetyLink = await screen.findByRole("link", { name: "Kiểm tra an toàn tương tác" });
    expect(safetyLink).toHaveAttribute("href", "/medicines?tab=safety");
    expect(screen.queryByRole("button", { name: "Kiểm tra tương tác DrugBank" })).not.toBeInTheDocument();
  });
});
