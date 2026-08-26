import type { ReactNode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => {
  const push = vi.fn();
  const replace = vi.fn();
  const refresh = vi.fn();
  return {
    getToday: vi.fn(),
    listVisits: vi.fn(),
    getDisputes: vi.fn(),
    disputeEvent: vi.fn(),
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
    getLifeMapToday: mocks.getToday,
    getLifeMapDisputes: mocks.getDisputes,
    disputeLifeMapEvent: mocks.disputeEvent,
  };
});

vi.mock("@/lib/visit-family", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/visit-family")>();
  return {
    ...original,
    listVisits: mocks.listVisits,
  };
});

import JourneyTimelinePage from "./page";

describe("JourneyTimelinePage (Spec v5 Section 6.18)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getToday.mockResolvedValue({
      generated_at: "2026-08-10T00:00:00Z",
      tasks: [],
      episodes: [],
      pending_confirmation_count: 0,
    });
    mocks.listVisits.mockResolvedValue([]);
    mocks.getDisputes.mockResolvedValue([]);
    mocks.disputeEvent.mockResolvedValue(undefined);
  });

  afterEach(cleanup);

  it("renders the Journey Timeline Expanded header, actions, and stream", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    expect(
      screen.getByRole("heading", { name: "Dòng thời gian sức khỏe mở rộng" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Tạo hành trình mới")).toBeInTheDocument();
    expect(screen.getByText("Ghi nhật ký")).toBeInTheDocument();
    expect(screen.getByText("Chuẩn bị buổi khám")).toBeInTheDocument();

    // Seed events are present
    expect(
      screen.getByText("Khởi động hành trình Kiểm soát huyết áp"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Ghi nhận chỉ số huyết áp sáng: 128/82 mmHg"),
    ).toBeInTheDocument();
    expect(screen.getByText("Tái khám Tim mạch định kỳ")).toBeInTheDocument();
  });

  it("switches bitemporal perspective between Valid Time and System Time", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    const validTimeBtn = screen.getByRole("button", {
      name: "Thời gian diễn ra (Valid Time)",
    });
    const systemTimeBtn = screen.getByRole("button", {
      name: "Thời gian ghi nhận (System Time)",
    });

    expect(validTimeBtn).toBeInTheDocument();
    expect(systemTimeBtn).toBeInTheDocument();

    fireEvent.click(systemTimeBtn);
    // Perspective state toggles cleanly
    expect(systemTimeBtn).toHaveClass("bg-[var(--surface-panel)]");

    fireEvent.click(validTimeBtn);
    expect(validTimeBtn).toHaveClass("bg-[var(--surface-panel)]");
  });

  it("filters timeline stream by plain-language milestone categories and search query", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    // 1. Filter by Thăm khám lâm sàng (Doctor Visits)
    const encountersFilterBtn = screen.getByRole("button", { name: "Thăm khám lâm sàng" });
    fireEvent.click(encountersFilterBtn);

    expect(screen.getByText("Tái khám Tim mạch định kỳ")).toBeInTheDocument();
    expect(
      screen.queryByText("Khởi động hành trình Kiểm soát huyết áp"),
    ).not.toBeInTheDocument();

    // 2. Filter by Thuốc & Dược phẩm (Medication Changes)
    const medicationFilterBtn = screen.getByRole("button", { name: "Thuốc & Dược phẩm" });
    fireEvent.click(medicationFilterBtn);

    expect(
      screen.getByText("Đổi đơn thuốc: Chuyển sang Amlodipine 5mg"),
    ).toBeInTheDocument();
    expect(screen.queryByText("Tái khám Tim mạch định kỳ")).not.toBeInTheDocument();

    // 3. Filter by Xét nghiệm & Cận lâm sàng (Blood Tests / Labs)
    const labsFilterBtn = screen.getByRole("button", { name: "Xét nghiệm & Cận lâm sàng" });
    fireEvent.click(labsFilterBtn);

    expect(
      screen.getByText("Xét nghiệm máu: Bộ mỡ máu & HbA1c"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Đổi đơn thuốc: Chuyển sang Amlodipine 5mg"),
    ).not.toBeInTheDocument();

    // 4. Filter by Báo cáo & Giấy tờ (Monitoring Reports)
    const reportsFilterBtn = screen.getByRole("button", { name: "Báo cáo & Giấy tờ" });
    fireEvent.click(reportsFilterBtn);

    expect(
      screen.getByText("Báo cáo theo dõi: Tổng kết huyết áp 7 ngày liên tục"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Xét nghiệm máu: Bộ mỡ máu & HbA1c"),
    ).not.toBeInTheDocument();

    // 5. Filter by Mốc hành trình (Milestones)
    const milestoneFilterBtn = screen.getByRole("button", { name: "Mốc hành trình" });
    fireEvent.click(milestoneFilterBtn);

    expect(
      screen.getByText("Khởi động hành trình Kiểm soát huyết áp"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Ghi nhận chỉ số huyết áp sáng: 128/82 mmHg"),
    ).not.toBeInTheDocument();

    // Reset to all and search
    const allFilterBtn = screen.getByRole("button", { name: "Tất cả sự kiện" });
    fireEvent.click(allFilterBtn);

    const searchInput = screen.getByPlaceholderText(
      "Tìm kiếm sự kiện, triệu chứng, ghi chú, bác sĩ...",
    );
    fireEvent.change(searchInput, { target: { value: "Omron" } });

    expect(
      screen.getByText("Ghi nhận chỉ số huyết áp sáng: 128/82 mmHg"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Khởi động hành trình Kiểm soát huyết áp"),
    ).not.toBeInTheDocument();
  });

  it("opens Audit Provenance Inspector modal when clicking inspect audit link", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    const inspectBtns = screen.getAllByText("Xem nhật ký kiểm toán & nguồn");
    fireEvent.click(inspectBtns[0]);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByText(/Thời điểm diễn ra/i)).toBeInTheDocument();
      expect(screen.getByText(/Thời điểm ghi nhận vào hệ thống/i)).toBeInTheDocument();
      expect(screen.getByText("Revision #1")).toBeInTheDocument();
    });

    // Close modal
    fireEvent.click(screen.getByRole("button", { name: "Đóng chi tiết" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("opens dispute modal and submits a dispute against a timeline event", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    const disputeBtns = screen.getAllByText("Khiếu nại / Báo sai");
    fireEvent.click(disputeBtns[0]);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByLabelText("Câu trả lời của bạn")).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const reasonInput = within(dialog).getByLabelText("Câu trả lời của bạn");
    fireEvent.change(reasonInput, {
      target: { value: "Chỉ số huyết áp này đo vào buổi tối chứ không phải sáng." },
    });

    const submitDisputeBtn = within(dialog).getByRole("button", { name: "Khiếu nại / Báo sai" });
    fireEvent.click(submitDisputeBtn);

    await waitFor(() => {
      expect(mocks.disputeEvent).toHaveBeenCalled();
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("adds a new journal entry via the modal", async () => {
    await act(async () => {
      render(<JourneyTimelinePage />);
    });

    // Open journal modal
    const newJournalBtn = screen.getByRole("button", { name: "Ghi nhật ký" });
    fireEvent.click(newJournalBtn);

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Ghi nhật ký sức khỏe mới" })).toBeInTheDocument();
    });

    const dialog = screen.getByRole("dialog");
    const titleInput = within(dialog).getByLabelText("Tiêu đề nhật ký");
    fireEvent.change(titleInput, { target: { value: "Đo nhịp tim sau khi chạy bộ: 88 bpm" } });

    const contentInput = within(dialog).getByLabelText("Nội dung chi tiết");
    fireEvent.change(contentInput, {
      target: { value: "Cảm giác bình thường, không khó thở, uống 500ml nước điện giải." },
    });

    const saveBtn = within(dialog).getByRole("button", { name: "Lưu vào dòng thời gian" });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(
        screen.getByText("Đo nhịp tim sau khi chạy bộ: 88 bpm"),
      ).toBeInTheDocument();
    });
  });
});
