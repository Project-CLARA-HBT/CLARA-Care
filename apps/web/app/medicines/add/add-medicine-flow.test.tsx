import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    createMedicationCourse: vi.fn(),
    replace,
    refresh,
    router: { replace, refresh },
  };
});

vi.mock("next/navigation", () => ({ useRouter: () => mocks.router }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/lib/medication-courses", () => ({
  createMedicationCourse: mocks.createMedicationCourse,
}));

import AddMedicineFlow from "./add-medicine-flow";

beforeEach(() => {
  vi.clearAllMocks();
  mocks.createMedicationCourse.mockResolvedValue({ id: "med-1" });
});

afterEach(cleanup);

async function advance(label = "Tiếp tục") {
  fireEvent.click(screen.getByRole("button", { name: label }));
  await waitFor(() => expect(screen.getByText(/Bước/)).toBeInTheDocument());
}

describe("AddMedicineFlow", () => {
  it("keeps one concept per step and focuses the required identity input", () => {
    render(<AddMedicineFlow />);
    const name = screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn");

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Nhập ít nhất 2 ký tự");
    expect(name).toHaveFocus();
    expect(mocks.createMedicationCourse).not.toHaveBeenCalled();
    expect(screen.getByRole("navigation", { name: "Tiến trình" })).toHaveTextContent("Bước 1 / 4");
  });

  it("does not put health content in navigation and submits only on review", async () => {
    render(<AddMedicineFlow />);
    fireEvent.change(screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn"), {
      target: { value: "  Metformin  " },
    });
    await advance();
    fireEvent.change(screen.getByLabelText(/Liều ghi trên nhãn/), {
      target: { value: "500 mg" },
    });
    await advance();
    fireEvent.change(screen.getByLabelText(/Lịch dùng ghi trên nhãn hoặc đơn/), {
      target: { value: "Buổi tối" },
    });
    await advance();

    expect(screen.getByText("Metformin")).toBeInTheDocument();
    expect(mocks.createMedicationCourse).not.toHaveBeenCalled();
    expect(window.location.search).not.toContain("Metformin");

    fireEvent.click(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" }));
    await waitFor(() => {
      expect(mocks.createMedicationCourse).toHaveBeenCalledWith({
        medication_name: "Metformin",
        dose_text: "500 mg",
        route_text: undefined,
        form_text: undefined,
        schedule_text: "Buổi tối",
        drugbank_id: undefined,
      });
      expect(mocks.replace).toHaveBeenCalledWith("/medicines?tab=list");
      expect(mocks.refresh).toHaveBeenCalled();
    });
  });

  it("keeps API error detail out of the primary view and allows a retry", async () => {
    mocks.createMedicationCourse.mockRejectedValue(new Error("internal-secret-token"));
    render(<AddMedicineFlow />);
    fireEvent.change(screen.getByLabelText("Tên thuốc trên nhãn hoặc đơn"), {
      target: { value: "Metformin" },
    });
    await advance();
    await advance();
    await advance();
    fireEvent.click(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Chưa thể lưu thuốc lúc này");
    expect(alert).not.toHaveTextContent("internal-secret-token");
    expect(screen.getByRole("button", { name: "Lưu thuốc đã xác nhận" })).toBeEnabled();
  });
});
