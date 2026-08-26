import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import TodayTaskDetailPage from "./page";
import * as lifemapModule from "@/lib/lifemap";

const mockParams = { taskId: "task-101" };

vi.mock("next/navigation", () => ({
  useParams: () => mockParams,
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

afterEach(cleanup);

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("TodayTaskDetailPage (/today/tasks/[taskId])", () => {
  it("renders loading state initially and then displays task details", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [
        {
          id: "task-101",
          title: "Uống thuốc Amlodipine 5mg sau ăn sáng",
          due_at: "2026-08-07T08:30:00Z",
          status: "accepted",
          version: 2,
          episode_id: "ep-1",
          episode_title: "Kiểm soát huyết áp",
        },
      ],
      episodes: [{ id: "ep-1", title: "Kiểm soát huyết áp", priority: "routine" }],
      pending_confirmation_count: 0,
      completed_today_count: 0,
    });

    render(<TodayTaskDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Uống thuốc Amlodipine 5mg sau ăn sáng" }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Việc đã được bạn chấp nhận")).toBeInTheDocument();
    expect(screen.getByText("Thời điểm")).toBeInTheDocument();
    expect(screen.getByText(/Chỉ xác nhận khi bạn đã thực hiện việc này/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Xác nhận hoàn tất" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quay lại danh sách" })).toHaveAttribute(
      "href",
      "/today",
    );
  });

  it("completes task on 1-click action and shows congratulations state", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [
        {
          id: "task-101",
          title: "Uống thuốc Amlodipine 5mg sau ăn sáng",
          due_at: "2026-08-07T08:30:00Z",
          status: "accepted",
          version: 2,
        },
      ],
      episodes: [],
      pending_confirmation_count: 0,
    });

    const completeSpy = vi
      .spyOn(lifemapModule, "completeLifeMapTask")
      .mockResolvedValue(undefined);

    render(<TodayTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Xác nhận hoàn tất" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Xác nhận hoàn tất" }));

    await waitFor(() => {
      expect(screen.getByText("Đã ghi nhận hoàn tất")).toBeInTheDocument();
    });

    expect(completeSpy).toHaveBeenCalledWith("task-101", 2);
    expect(
      screen.getByText("CLARA không tự suy diễn thêm hành động chăm sóc từ việc này."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quay lại Hôm nay" })).toHaveAttribute(
      "href",
      "/today",
    );
  });

  it("renders empty state when task is not found in today's agenda", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockResolvedValue({
      generated_at: "2026-08-07T08:00:00Z",
      tasks: [],
      episodes: [],
      pending_confirmation_count: 0,
    });

    render(<TodayTaskDetailPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Việc này không còn trong danh sách hôm nay"),
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "Có thể việc đã hoàn tất, được điều chỉnh, hoặc bạn đang mở một liên kết cũ.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quay lại Hôm nay" })).toHaveAttribute(
      "href",
      "/today",
    );
  });

  it("handles loading failure with inline error and retry affordance", async () => {
    vi.spyOn(lifemapModule, "getLifeMapToday").mockRejectedValue(new Error("Network timeout"));

    render(<TodayTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Thử lại" })).toBeInTheDocument();
    });
  });
});
