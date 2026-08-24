import type { ReactNode } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  getMedicationCourses: vi.fn(),
  checkDrugBankDdi: vi.fn(),
  correctMedicationCourse: vi.fn(),
  endMedicationCourse: vi.fn(),
  getCabinet: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("@/lib/medication-courses", () => ({
  getMedicationCourses: mocks.getMedicationCourses,
  checkDrugBankDdi: mocks.checkDrugBankDdi,
  correctMedicationCourse: mocks.correctMedicationCourse,
  endMedicationCourse: mocks.endMedicationCourse,
}));

vi.mock("@/lib/selfmed", () => ({
  getCabinet: mocks.getCabinet,
}));

import MedicinesListTab from "./list-tab";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.getMedicationCourses.mockResolvedValue([]);
  mocks.getCabinet.mockResolvedValue({ cabinet_id: 1, label: "Tủ thuốc gia đình", items: [] });
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

  it("renders the 4 distinct visual domains according to Spec v5 Section 6.27", async () => {
    mocks.getMedicationCourses.mockResolvedValue([
      {
        id: "med-confirmed",
        version: 1,
        medication_name: "Metformin",
        dose_text: "500 mg",
        schedule_text: "Sáng 1 viên",
        route_text: "Uống",
        form_text: "Viên nén",
        drugbank_id: "DB00331",
        status: "active",
        reconciliation_status: "matched",
      },
      {
        id: "med-unresolved",
        version: 1,
        medication_name: "Thuốc đề xuất chưa rõ liều",
        dose_text: "",
        schedule_text: "",
        route_text: "",
        form_text: "",
        drugbank_id: null,
        status: "active",
        reconciliation_status: "unmatched",
      },
    ]);

    mocks.getCabinet.mockResolvedValue({
      cabinet_id: 1,
      label: "Tủ thuốc gia đình",
      items: [
        {
          id: 101,
          drug_name: "Paracetamol",
          dosage: "500 mg",
          source: "ocr",
          quantity: 2,
          expires_on: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    });

    render(<MedicinesListTab />);

    // Domain 1: Active confirmed
    expect(await screen.findByText("Metformin")).toBeInTheDocument();
    expect(screen.getByText("Thuốc đang sử dụng (Đã xác nhận)")).toBeInTheDocument();
    expect(screen.getByText("DrugBank ID: DB00331")).toBeInTheDocument();

    // Domain 2: Unresolved proposal
    expect(screen.getByText("Thuốc đề xuất chưa rõ liều")).toBeInTheDocument();
    expect(screen.getByText("Chưa đối chiếu chuẩn")).toBeInTheDocument();

    // Domain 3: Safety ActionObject
    expect(
      screen.getAllByText("Kiểm tra tương tác thuốc (Drug Interaction Guard)")[0],
    ).toBeInTheDocument();
    expect(screen.getByText("DrugBank v5.1 & FIDES")).toBeInTheDocument();

    // Domain 4: Home Cabinet as secondary inventory
    expect(screen.getByText("Tủ thuốc gia đình (Tồn kho dự phòng)")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Thuốc trong tủ là tồn kho dự trữ gia đình. Chưa được đưa vào đơn thuốc đang dùng thực tế.",
      ),
    ).toBeInTheDocument();
  });
});
