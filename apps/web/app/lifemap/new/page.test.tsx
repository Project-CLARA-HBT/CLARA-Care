import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    createEpisode: vi.fn(),
    createTask: vi.fn(),
    push,
    replace,
    refresh,
    router: { push, replace, refresh },
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => mocks.router,
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/lifemap", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/lifemap")>();
  return {
    ...original,
    createLifeMapEpisode: mocks.createEpisode,
    createLifeMapTask: mocks.createTask,
  };
});

import JourneyCreationWizardPage from "./page";

describe("JourneyCreationWizardPage (Spec v5 Section 6.17)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.createEpisode.mockResolvedValue({ id: "ep-12345" });
    mocks.createTask.mockResolvedValue({ id: "task-67890" });
  });

  afterEach(cleanup);

  it("renders Step 1: Goal Selection with quick templates and validates inputs", async () => {
    render(<JourneyCreationWizardPage />);

    expect(screen.getByText("LifeMap")).toBeInTheDocument();
    expect(screen.getByText("Mục tiêu sức khỏe của bạn là gì?")).toBeInTheDocument();

    // Template options exist
    expect(screen.getByText("Kiểm soát huyết áp & tim mạch")).toBeInTheDocument();
    expect(screen.getByText("Ổn định đường huyết & dinh dưỡng")).toBeInTheDocument();

    // Trying to proceed without input triggers error
    const nextBtn = screen.getByRole("button", { name: "Chọn một mục tiêu" });
    fireEvent.click(nextBtn);

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Vui lòng nhập tên hành trình/ }),
    ).toBeInTheDocument();
    expect(mocks.createEpisode).not.toHaveBeenCalled();
  });

  it("populates form when clicking a quick template and advances to Step 2", async () => {
    render(<JourneyCreationWizardPage />);

    // Click on template
    const templateBtn = screen.getByText("Kiểm soát huyết áp & tim mạch");
    fireEvent.click(templateBtn);

    const titleInput = screen.getByLabelText("Tên hành trình sức khỏe") as HTMLInputElement;
    expect(titleInput.value).toBe("Kiểm soát huyết áp & tim mạch");

    const nextBtn = screen.getByRole("button", { name: "Chọn một mục tiêu" });
    fireEvent.click(nextBtn);

    // Advances to Step 2: Condition Intake
    expect(
      screen.getByText("Thông tin bệnh lý & Triệu chứng ban đầu"),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Bệnh lý / Chẩn đoán liên quan")).toBeInTheDocument();
    expect(screen.getByLabelText("Mức ưu tiên theo dõi")).toBeInTheDocument();
  });

  it("completes full 4-step wizard workflow and commits the journey", async () => {
    render(<JourneyCreationWizardPage />);

    // Step 1: Goal Selection
    const titleInput = screen.getByLabelText("Tên hành trình sức khỏe");
    fireEvent.change(titleInput, { target: { value: "Phục hồi khớp gối" } });

    const goalInput = screen.getByLabelText("Mục tiêu cụ thể / Kết quả mong đợi");
    fireEvent.change(goalInput, { target: { value: "Đi lại không đau và gập gối 90 độ" } });

    fireEvent.click(screen.getByRole("button", { name: "Chọn một mục tiêu" }));

    // Step 2: Condition Intake
    await waitFor(() => {
      expect(
        screen.getByText("Thông tin bệnh lý & Triệu chứng ban đầu"),
      ).toBeInTheDocument();
    });

    const conditionSelect = screen.getByLabelText("Bệnh lý / Chẩn đoán liên quan");
    fireEvent.change(conditionSelect, { target: { value: "arthritis" } });

    const symptomsInput = screen.getByPlaceholderText(
      "Ví dụ: Hay đau nhức gáy vào sáng sớm, chóng mặt khi đổi tư thế đột ngột...",
    );
    fireEvent.change(symptomsInput, { target: { value: "Cứng khớp vào buổi sáng" } });

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    // Step 3: Target Milestone Planning
    await waitFor(() => {
      expect(screen.getByText("Lập kế hoạch mốc mục tiêu")).toBeInTheDocument();
    });

    const m1Input = screen.getByLabelText("Mốc mục tiêu đầu tiên (Milestone 1)");
    fireEvent.change(m1Input, { target: { value: "Tập vật lý trị liệu 14 ngày liên tục" } });

    const cadenceSelect = screen.getByLabelText("Tần suất theo dõi");
    fireEvent.change(cadenceSelect, { target: { value: "daily" } });

    fireEvent.click(screen.getByRole("button", { name: "Tiếp tục" }));

    // Step 4: Commitment & Review
    await waitFor(() => {
      expect(screen.getByText("Cam kết & Khởi động hành trình")).toBeInTheDocument();
      expect(screen.getByText("Phục hồi khớp gối")).toBeInTheDocument();
      expect(screen.getByText("Đi lại không đau và gập gối 90 độ")).toBeInTheDocument();
    });

    const commitBtn = screen.getByRole("button", { name: "Cam kết & Bắt đầu hành trình" });

    // Trying to submit without checking the commitment box triggers validation
    fireEvent.click(commitBtn);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Vui lòng đánh dấu xác nhận cam kết/ }),
    ).toBeInTheDocument();
    expect(mocks.createEpisode).not.toHaveBeenCalled();

    // Check the commitment checkbox
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();

    // Commit journey
    fireEvent.click(commitBtn);

    await waitFor(() => {
      expect(mocks.createEpisode).toHaveBeenCalledWith({
        title: "Phục hồi khớp gối",
        goal: "Đi lại không đau và gập gối 90 độ",
        priority: "routine",
      });
      expect(mocks.createTask).toHaveBeenCalledWith("ep-12345", {
        title: "Tập vật lý trị liệu 14 ngày liên tục",
        due_at: undefined,
      });
      expect(mocks.push).toHaveBeenCalledWith("/lifemap/timeline");
    });
  });

  it("supports Back button navigation across wizard steps without losing state", async () => {
    render(<JourneyCreationWizardPage />);

    // Step 1 -> Step 2
    fireEvent.change(screen.getByLabelText("Tên hành trình sức khỏe"), {
      target: { value: "Ổn định đường huyết" },
    });
    fireEvent.change(screen.getByLabelText("Mục tiêu cụ thể / Kết quả mong đợi"), {
      target: { value: "HbA1c < 6.5%" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Chọn một mục tiêu" }));

    // On Step 2
    await waitFor(() => {
      expect(
        screen.getByText("Thông tin bệnh lý & Triệu chứng ban đầu"),
      ).toBeInTheDocument();
    });

    // Click Back
    fireEvent.click(screen.getByRole("button", { name: "Quay lại" }));

    // Back on Step 1 with preserved values
    expect(screen.getByText("Mục tiêu sức khỏe của bạn là gì?")).toBeInTheDocument();
    expect((screen.getByLabelText("Tên hành trình sức khỏe") as HTMLInputElement).value).toBe(
      "Ổn định đường huyết",
    );
  });
});
