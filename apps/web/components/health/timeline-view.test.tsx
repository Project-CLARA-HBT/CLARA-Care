import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TimelineView } from "./timeline-view";
import { v2Client, type HealthTimelineResponseDto } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/health/timeline",
}));

afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
});

const mockTimelineData: HealthTimelineResponseDto = {
  items: [
    {
      id: "evt-1",
      kind: "medication_change",
      title: "Bắt đầu uống Amlodipine 5mg",
      summary: "Bác sĩ kê đơn sau khi chỉ số huyết áp cao",
      effective_at: "2026-08-19T08:00:00Z",
      state: "confirmed",
      source: {
        kind: "doctor",
        name: "BS. Trần Mai",
        verification_state: "verified",
      },
      revisions: [
        {
          id: "rev-1",
          modified_at: "2026-08-19 09:00",
          modified_by: "BS. Trần Mai",
          summary: "Điều chỉnh liều từ 2.5mg lên 5mg",
          previous_value: "2.5mg/ngày",
          new_value: "5mg/ngày",
        },
      ],
    },
    {
      id: "evt-2",
      kind: "result",
      title: "Xét nghiệm sinh hóa máu định kỳ",
      summary: "HbA1c: 5.8%, Glucose: 5.4 mmol/L",
      effective_at: "2026-08-15T07:30:00Z",
      state: "imported",
      source: {
        kind: "lab",
        name: "BV Bạch Mai",
      },
    },
  ],
  next_cursor: "cur-2",
  total: 2,
};

describe("TimelineView Component", () => {
  it("renders filter controls, event list, and source/state badges", async () => {
    vi.spyOn(v2Client, "getHealthTimeline").mockResolvedValue(mockTimelineData);

    render(<TimelineView />);

    await waitFor(() => {
      expect(screen.getByText("Bắt đầu uống Amlodipine 5mg")).toBeInTheDocument();
    });

    // 1. Period filters
    expect(screen.getByTestId("filter-period-recent")).toBeInTheDocument();
    expect(screen.getByTestId("filter-period-month")).toBeInTheDocument();
    expect(screen.getByTestId("filter-period-year")).toBeInTheDocument();
    expect(screen.getByTestId("filter-period-all")).toBeInTheDocument();

    // 2. Type filters
    expect(screen.getByTestId("filter-type-medication")).toBeInTheDocument();
    expect(screen.getByTestId("filter-type-result")).toBeInTheDocument();

    // 3. Events rendered
    expect(screen.getByTestId("timeline-event-evt-1")).toBeInTheDocument();
    expect(screen.getByTestId("timeline-event-evt-2")).toBeInTheDocument();

    // 4. Source and state badges
    expect(screen.getByTestId("health-state-badge-confirmed")).toBeInTheDocument();
    expect(screen.getByTestId("source-badge-doctor")).toBeInTheDocument();
  });

  it("filters events by search query", async () => {
    vi.spyOn(v2Client, "getHealthTimeline").mockResolvedValue(mockTimelineData);

    render(<TimelineView />);

    await waitFor(() => {
      expect(screen.getByText("Bắt đầu uống Amlodipine 5mg")).toBeInTheDocument();
    });

    const searchInput = screen.getByTestId("timeline-search-input");
    fireEvent.change(searchInput, { target: { value: "Sinh hóa" } });

    await waitFor(() => {
      expect(screen.queryByText("Bắt đầu uống Amlodipine 5mg")).not.toBeInTheDocument();
      expect(screen.getByText("Xét nghiệm sinh hóa máu định kỳ")).toBeInTheDocument();
    });
  });

  it("opens Revision History Inspector when clicking history button (HEALTH-004)", async () => {
    vi.spyOn(v2Client, "getHealthTimeline").mockResolvedValue(mockTimelineData);

    render(<TimelineView />);

    await waitFor(() => {
      expect(screen.getByTestId("btn-inspect-revision-evt-1")).toBeInTheDocument();
    });

    const historyBtn = screen.getByTestId("btn-inspect-revision-evt-1");
    fireEvent.click(historyBtn);

    expect(screen.getByText("Lịch sử sửa đổi & Kiểm toán")).toBeInTheDocument();
    expect(screen.getByText("Điều chỉnh liều từ 2.5mg lên 5mg")).toBeInTheDocument();
    expect(screen.getByText("- 2.5mg/ngày")).toBeInTheDocument();
    expect(screen.getByText("+ 5mg/ngày")).toBeInTheDocument();
  });

  it("handles loading more events when pagination cursor exists", async () => {
    const timelineSpy = vi
      .spyOn(v2Client, "getHealthTimeline")
      .mockImplementation((params) => {
        if (params?.cursor === "cur-2") {
          return Promise.resolve({
            items: [
              {
                id: "evt-3",
                kind: "visit",
                title: "Khám định kỳ tổng quát",
                effective_at: "2026-08-01",
                state: "confirmed",
              },
            ],
            next_cursor: null,
          });
        }
        return Promise.resolve(mockTimelineData);
      });

    render(<TimelineView />);

    await waitFor(() => {
      expect(screen.getByTestId("timeline-pagination")).toBeInTheDocument();
    });

    const loadMoreBtn = screen.getByRole("button", { name: "Tải thêm sự kiện" });
    fireEvent.click(loadMoreBtn);

    await waitFor(() => {
      expect(timelineSpy).toHaveBeenCalledTimes(2);
    });
  });
});
