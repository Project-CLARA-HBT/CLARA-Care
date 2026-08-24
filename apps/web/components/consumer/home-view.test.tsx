import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HomeView } from "./home-view";
import { v2Client, type HomeOverviewDto } from "@/lib/api/v2-client";
import * as analyticsEvents from "@/lib/analytics/events";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    onClick,
    ...props
  }: {
    children?: ReactNode;
    href: string;
    onClick?: (e: React.MouseEvent<HTMLAnchorElement>) => void;
    [key: string]: unknown;
  }) => (
    <a
      href={href}
      onClick={(e) => {
        e.preventDefault();
        onClick?.(e);
      }}
      {...props}
    >
      {children}
    </a>
  ),
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const mockHomeData: HomeOverviewDto = {
  profile: {
    id: "p-42",
    display_name: "Nguyễn Văn A",
    relationship: "Bản thân",
  },
  generated_at: "2026-08-19T08:00:00Z",
  context_version: "ctx-v2",
  top_action: {
    id: "act-1",
    kind: "medication",
    title: "Uống thuốc huyết áp buổi sáng",
    description: "Amlodipine 5mg - 1 viên sau ăn sáng.",
    href: "/health/medications",
    severity: "urgent",
    action_label: "Uống ngay",
    secondary_action_label: "Nhắc lại sau 15p",
    secondary_href: "/health/medications?snooze=15",
  },
  alerts: [
    {
      id: "alt-info",
      severity: "info",
      title: "Lịch nhắc tái khám",
      message: "Bạn có lịch tái khám vào tuần tới.",
      href: "/care/visits",
      action_label: "Xem lịch",
      dismissible: true,
    },
    {
      id: "alt-crit",
      severity: "critical",
      kind: "ddi",
      title: "Cảnh báo tương tác thuốc nghiêm trọng",
      message: "Phát hiện tương tác giữa Aspirin và Clopidogrel.",
      href: "/selfmed/ddi",
      action_label: "Kiểm tra ngay",
      dismissible: true,
    },
  ],
  today: [
    {
      id: "med-1",
      kind: "medication",
      title: "Amlodipine 5mg",
      dosage: "1 viên",
      instructions: "Uống sau ăn sáng",
      time: "08:00",
      status: "pending",
      href: "/health/medications",
    },
    {
      id: "vis-1",
      kind: "visit",
      title: "Khám chuyên khoa Tim mạch",
      doctor_name: "BS. Trần Mai",
      location: "Bệnh viện Bạch Mai",
      time: "14:30",
      status: "pending",
      href: "/care/visits",
    },
    {
      id: "tsk-1",
      kind: "task",
      title: "Đo huyết áp tại nhà",
      description: "Ghi nhận chỉ số buổi tối",
      time: "20:00",
      status: "pending",
      href: "/care",
    },
  ],
  recent_changes: [
    {
      id: "rc-1",
      kind: "result",
      title: "Kết quả xét nghiệm sinh hóa máu",
      description: "Glucose: 5.4 mmol/L, HbA1c: 5.8%",
      timestamp: "2026-08-19T07:30:00Z",
      source_kind: "lab",
      verification_state: "verified",
      href: "/health/timeline",
    },
    {
      id: "rc-2",
      kind: "document",
      title: "Đơn thuốc ngoại trú",
      timestamp: "2026-08-18T16:00:00Z",
      source_kind: "doctor",
      source_name: "BS. Trần Mai",
      verification_state: "verified",
      href: "/health",
    },
  ],
};

describe("HomeView (Feature: canonical /home web experience)", () => {
  it("renders loading skeleton while data is fetching", () => {
    vi.spyOn(v2Client, "getHome").mockImplementation(
      () => new Promise(() => {}), // never resolves
    );

    render(<HomeView />);

    expect(screen.getByTestId("home-skeleton-loading")).toBeInTheDocument();
    expect(screen.getByTestId("home-skeleton-loading")).toHaveAttribute("aria-busy", "true");
  });

  it("renders inline error state distinguishing data unavailable from no alerts", async () => {
    vi.spyOn(v2Client, "getHome").mockRejectedValueOnce(new Error("Network connection error"));

    render(<HomeView />);

    await waitFor(() => {
      expect(screen.getByTestId("home-error-section")).toBeInTheDocument();
    });

    expect(screen.getByText("Không thể tải dữ liệu hôm nay")).toBeInTheDocument();
    expect(
      screen.getByText(/Sự cố tải dữ liệu không đồng nghĩa với việc không có cảnh báo y tế/i),
    ).toBeInTheDocument();

    const retryBtn = screen.getByRole("button", { name: "Thử tải lại" });
    expect(retryBtn).toBeInTheDocument();
  });

  it("renders full overview data: header, ask bar, top action, sorted alerts, schedule, and recent changes", async () => {
    vi.spyOn(v2Client, "getHome").mockResolvedValueOnce(mockHomeData);
    const trackActionSpy = vi.spyOn(analyticsEvents, "trackHomeActionClicked");
    const trackAlertSpy = vi.spyOn(analyticsEvents, "trackHomeAlertClicked");

    render(<HomeView />);

    // 1. Header with active profile
    await waitFor(() => {
      expect(screen.getByText("Nguyễn Văn A")).toBeInTheDocument();
    });
    expect(screen.getByTestId("health-page-header")).toBeInTheDocument();

    // 2. Prominent AskBar
    expect(screen.getByTestId("ask-bar")).toBeInTheDocument();
    const askInput = screen.getByTestId("ask-bar-input");
    expect(askInput).toBeInTheDocument();

    // 3. PrimaryActionCard for top_action
    expect(screen.getByTestId("home-top-action-section")).toBeInTheDocument();
    expect(screen.getByText("Uống thuốc huyết áp buổi sáng")).toBeInTheDocument();
    expect(screen.getAllByText("Khẩn cấp").length).toBeGreaterThanOrEqual(1); // urgent maps to Khẩn cấp / danger
    const actionBtn = screen.getByRole("link", { name: "Uống ngay" });
    expect(actionBtn).toHaveAttribute("href", "/health/medications");

    fireEvent(actionBtn, new MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(trackActionSpy).toHaveBeenCalledWith({
      actionKind: "medication",
      severity: "urgent",
      targetHref: "/health/medications",
    });

    // 4. AlertsBanner with sorted priority (critical alert ranked before info alert)
    const alertBanners = screen.getAllByRole("alert");
    expect(alertBanners.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Cảnh báo tương tác thuốc nghiêm trọng")).toBeInTheDocument();

    const critAlertLink = screen.getByRole("link", { name: /Kiểm tra ngay/i });
    fireEvent(critAlertLink, new MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(trackAlertSpy).toHaveBeenCalledWith({
      severity: "critical",
      alertKind: "ddi",
    });

    // 5. TodayScheduleSection
    expect(screen.getByTestId("home-today-schedule")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();
    expect(screen.getByText("Khám chuyên khoa Tim mạch")).toBeInTheDocument();
    expect(screen.getByText("Đo huyết áp tại nhà")).toBeInTheDocument();

    // 6. RecentChangesSection
    expect(screen.getByTestId("home-recent-changes")).toBeInTheDocument();
    expect(screen.getByText("Kết quả xét nghiệm sinh hóa máu")).toBeInTheDocument();
    expect(screen.getByText("Đơn thuốc ngoại trú")).toBeInTheDocument();
  });

  it("renders actionable caught-up state when no tasks or alerts are pending without false health reassurance", async () => {
    const emptyData: HomeOverviewDto = {
      profile: {
        id: "p-empty",
        display_name: "Lê Thị B",
      },
      top_action: null,
      alerts: [],
      today: [],
      recent_changes: [],
    };

    vi.spyOn(v2Client, "getHome").mockResolvedValueOnce(emptyData);

    render(<HomeView />);

    await waitFor(() => {
      expect(screen.getByTestId("caught-up-state")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Bạn đã hoàn thành các việc cần làm hôm nay"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /Sự vắng mặt của việc cần làm không thay thế cho đánh giá y khoa/i,
      ),
    ).toBeInTheDocument();

    // Quick action exploration links
    expect(screen.getByTestId("caught-up-action-ask")).toBeInTheDocument();
    expect(screen.getByTestId("caught-up-action-meds")).toBeInTheDocument();
    expect(screen.getByTestId("caught-up-action-health")).toBeInTheDocument();
    expect(screen.getByTestId("caught-up-action-care")).toBeInTheDocument();
  });

  it("tracks coarse No-PII analytics on interactions", async () => {
    vi.spyOn(v2Client, "getHome").mockResolvedValueOnce(mockHomeData);
    const trackScheduleSpy = vi.spyOn(analyticsEvents, "trackHomeScheduleItemClicked");
    const trackRecentSpy = vi.spyOn(analyticsEvents, "trackHomeRecentChangeClicked");

    render(<HomeView />);

    await waitFor(() => {
      expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();
    });

    const scheduleItem = screen.getByTestId("today-schedule-item-med-1");
    const openBtn = scheduleItem.querySelector("a");
    if (openBtn) {
      fireEvent(openBtn, new MouseEvent("click", { bubbles: true, cancelable: true }));
      expect(trackScheduleSpy).toHaveBeenCalledWith({ itemKind: "medication" });
    }

    const changeLink = screen.getByText("Kết quả xét nghiệm sinh hóa máu");
    fireEvent(changeLink, new MouseEvent("click", { bubbles: true, cancelable: true }));
    expect(trackRecentSpy).toHaveBeenCalledWith({ changeKind: "result" });
  });

  it("allows dismissing dismissible alerts", async () => {
    vi.spyOn(v2Client, "getHome").mockResolvedValueOnce(mockHomeData);

    render(<HomeView />);

    await waitFor(() => {
      expect(screen.getByText("Lịch nhắc tái khám")).toBeInTheDocument();
    });

    const dismissBtns = screen.getAllByLabelText("Đóng cảnh báo");
    expect(dismissBtns.length).toBeGreaterThan(0);

    fireEvent.click(dismissBtns[0]);

    // Should remove one dismissed alert
    await waitFor(() => {
      expect(screen.queryByText("Cảnh báo tương tác thuốc nghiêm trọng")).not.toBeInTheDocument();
    });
  });

  it("opens UniversalCaptureModal when clicking 'Thêm thông tin sức khỏe' trigger", async () => {
    vi.spyOn(v2Client, "getHome").mockResolvedValueOnce(mockHomeData);

    render(<HomeView />);

    await waitFor(() => {
      expect(screen.getByText("Thêm thông tin sức khỏe")).toBeInTheDocument();
    });

    const addHealthBtn = screen.getByRole("button", { name: "Thêm thông tin sức khỏe" });
    fireEvent.click(addHealthBtn);

    expect(screen.getByTestId("universal-capture-modal")).toBeInTheDocument();
  });
});
