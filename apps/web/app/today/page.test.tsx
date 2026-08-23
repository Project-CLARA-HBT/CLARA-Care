import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TodayPage from "./page";
import * as lifemapModule from "@/lib/lifemap";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

const mockWeek = [
  { date: "2026-08-01", completed_count: 1 },
  { date: "2026-08-02", completed_count: 0 },
  { date: "2026-08-03", completed_count: 2 },
  { date: "2026-08-04", completed_count: 1 },
  { date: "2026-08-05", completed_count: 0 },
  { date: "2026-08-06", completed_count: 1 },
  { date: "2026-08-07", completed_count: 1 },
];

afterEach(cleanup);

beforeEach(() => {
  mockPush.mockReset();
  vi.restoreAllMocks();
});

describe("TodayPage Modernized UI", () => {
  it("renders active state with hero greeting, dominant next task card, timeline, and side widgets", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [
        {
          id: "task-1",
          title: "Tái khám Tim mạch",
          due_at: "2026-08-07T14:30:00Z",
          status: "accepted",
          version: 1,
          episode_id: "ep-1",
          episode_title: "Theo dõi tăng huyết áp",
        },
        {
          id: "task-2",
          title: "Đo huyết áp buổi tối",
          due_at: "2026-08-07T19:00:00Z",
          status: "accepted",
          version: 1,
          episode_id: "ep-1",
          episode_title: "Theo dõi tăng huyết áp",
        },
      ],
      episodes: [
        { id: "ep-1", title: "Theo dõi tăng huyết áp", priority: "routine" },
      ],
      pending_confirmation_count: 1,
      completed_today_count: 1,
      activity_days: mockWeek,
    });

    render(<TodayPage />);

    // Check Hero Greeting & Progress Pills
    await waitFor(() => {
      expect(screen.getByText("Nhịp điệu chăm sóc hôm nay")).toBeInTheDocument();
    });
    expect(screen.getByText("2 việc đang chờ")).toBeInTheDocument();
    expect(screen.getByText("1 việc đã hoàn thành hôm nay")).toBeInTheDocument();
    expect(screen.getByText("Không có cảnh báo mới")).toBeInTheDocument();

    // Check Dominant Next Task Card
    expect(screen.getByText("Nhiệm vụ tiếp theo")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Tái khám Tim mạch" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Theo dõi tăng huyết áp")[0]).toBeInTheDocument();
    // Check In-situ completion trigger & link
    expect(screen.getAllByRole("button", { name: "Xác nhận hoàn tất" })[0]).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /Xem việc/ })[0]).toHaveAttribute(
      "href",
      "/today/tasks/task-1",
    );

    // Check Upcoming Timeline Card
    expect(
      screen.getByRole("heading", { name: "Lịch trình hôm nay" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Đo huyết áp buổi tối")).toBeInTheDocument();

    // Check Pending Confirmation notice
    expect(screen.getByText(/Chưa dùng làm kết luận/)).toBeInTheDocument();

    // Check Journey Preview
    expect(screen.getByText("Hành trình đang mở")).toBeInTheDocument();

    // Check Side Widgets: Emergency Medical ID (without hardcoded blood type)
    expect(screen.getByText("Thẻ y tế khẩn cấp")).toBeInTheDocument();
    expect(screen.queryByText("O+")).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Xem thẻ cấp cứu/ }),
    ).toHaveAttribute("href", "/you/profile");

    // Check Side Widgets: Quick Shortcuts
    expect(screen.getByText("Hỏi về sức khỏe")).toBeInTheDocument();
    expect(screen.getByText("Kiểm tra thuốc")).toBeInTheDocument();

    // Check Hardcoded vitals removed from side widgets
    expect(screen.queryByText("Chỉ số sức khỏe gần đây")).not.toBeInTheDocument();
    expect(screen.queryByText("128/78")).not.toBeInTheDocument();

    // Check Side Widgets: Weekly Progress
    expect(screen.getByText("5/7 ngày có việc hoàn thành")).toBeInTheDocument();
  });

  it("handles ask prompt submit in today search bar", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [],
      episodes: [{ id: "ep-1", title: "Khám định kỳ", priority: "routine" }],
      pending_confirmation_count: 0,
      completed_today_count: 1,
      activity_days: mockWeek,
    });

    render(<TodayPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Hỏi về thuốc, triệu chứng hoặc kế hoạch chăm sóc…")).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText("Hỏi về thuốc, triệu chứng hoặc kế hoạch chăm sóc…");
    fireEvent.change(input, { target: { value: "thuốc huyết áp" } });

    const submitBtn = screen.getByRole("button", { name: "Hỏi về sức khỏe" });
    fireEvent.click(submitBtn);

    expect(mockPush).toHaveBeenCalledWith("/chat?q=thu%E1%BB%91c%20huy%E1%BA%BFt%20%C3%A1p");
  });

  it("renders completed state when all tasks for today are done", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [],
      episodes: [{ id: "ep-1", title: "Theo dõi đường huyết", priority: "routine" }],
      pending_confirmation_count: 0,
      completed_today_count: 2,
      activity_days: mockWeek,
    });

    render(<TodayPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Bạn đã hoàn thành các việc hôm nay" })).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Cập nhật thay đổi" })).toHaveAttribute("href", "/lifemap");
    expect(screen.getByText("5/7 ngày có việc hoàn thành")).toBeInTheDocument();
  });

  it("renders first-time state with 3-step onboarding guide", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [],
      episodes: [],
      pending_confirmation_count: 0,
      completed_today_count: 0,
      activity_days: mockWeek.map((d) => ({ ...d, completed_count: 0 })),
    });

    render(<TodayPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Bạn chưa có việc cần làm hôm nay" })).toBeInTheDocument();
    });
    expect(screen.getByText(/CLARA không tự thêm việc thay bạn/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bắt đầu hành trình" })).toHaveAttribute("href", "/lifemap/new");
    expect(screen.getByText("Chọn điều muốn theo dõi")).toBeInTheDocument();
    expect(screen.getByText("Thêm việc phù hợp")).toBeInTheDocument();
    expect(screen.getByText("Xem việc trong Hôm nay")).toBeInTheDocument();
  });

  it("renders error retry banner when API load fails", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockRejectedValue(new Error("Network connection error"));

    render(<TodayPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
    });
  });
});
