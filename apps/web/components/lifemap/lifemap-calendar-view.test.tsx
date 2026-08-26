import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  LifeMapCalendarView,
  type CalendarEventItem,
} from "./lifemap-calendar-view";

afterEach(cleanup);
beforeEach(() => {
  vi.resetAllMocks();
});

const mockEvents: CalendarEventItem[] = [
  {
    id: "evt-med-1",
    date: "2026-08-10",
    time: "08:00",
    title: "Amlodipine 5mg",
    category: "medication",
    dosage: "1 viên sáng",
    status: "completed",
    adherencePercent: 100,
    description: "Đã uống thuốc đúng giờ",
  },
  {
    id: "evt-med-2",
    date: "2026-08-10",
    time: "20:00",
    title: "Metformin 500mg",
    category: "medication",
    dosage: "1 viên tối",
    status: "completed",
    adherencePercent: 100,
    description: "Đã uống sau ăn tối",
  },
  {
    id: "evt-apt-1",
    date: "2026-08-15",
    time: "09:30",
    title: "Tái khám Tim mạch định kỳ",
    category: "appointment",
    doctorName: "BS. Trần Văn Hoàng",
    location: "BV Bạch Mai",
    status: "scheduled",
    description: "Khám định kỳ 3 tháng",
  },
  {
    id: "evt-lab-1",
    date: "2026-08-15",
    time: "07:30",
    title: "Xét nghiệm sinh hóa máu HbA1c",
    category: "lab",
    location: "Trung tâm Xét nghiệm",
    status: "scheduled",
  },
  {
    id: "evt-sym-1",
    date: "2026-08-18",
    time: "14:00",
    title: "Đau đầu nhẹ vùng trán",
    category: "symptom",
    severity: "mild",
    status: "mild",
    description: "Đau âm ỉ sau khi làm việc máy tính",
  },
  {
    id: "evt-alert-1",
    date: "2026-08-22",
    time: "07:15",
    title: "Cảnh báo: Huyết áp tăng cao 152/96 mmHg",
    category: "alert",
    status: "warning",
    metrics: { "Huyết áp": "152/96 mmHg", "Nhịp tim": "88 bpm" },
    description: "Vượt ngưỡng an toàn 140/90",
  },
];

describe("LifeMapCalendarView", () => {
  it("renders calendar matrix with month/year navigation, weekday headers, and stats", () => {
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        language="vi"
      />,
    );

    // 1. Title & stats
    expect(screen.getByText("Bản đồ sức khỏe LifeMap")).toBeInTheDocument();
    expect(screen.getByTestId("stat-adherence-rate")).toBeInTheDocument();
    expect(screen.getByTestId("stat-appointments-count")).toHaveTextContent("2");
    expect(screen.getByTestId("stat-symptoms-count")).toHaveTextContent("1");
    expect(screen.getByTestId("stat-alerts-count")).toHaveTextContent("1");

    // 2. Weekday headers in Vietnamese
    expect(screen.getByText("T2")).toBeInTheDocument();
    expect(screen.getByText("CN")).toBeInTheDocument();

    // 3. Month & year selectors
    const selectMonth = screen.getByTestId("select-month") as HTMLSelectElement;
    expect(selectMonth.value).toBe("7"); // 0-indexed: August is 7

    const selectYear = screen.getByTestId("select-year") as HTMLSelectElement;
    expect(selectYear.value).toBe("2026");
  });

  it("renders all 4 daily status dots (🟢, 🔵, 🟡, 🔴) on matching dates", () => {
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        language="vi"
      />,
    );

    // 🟢 Medication full adherence dot on 2026-08-10
    const cellMed = screen.getByTestId("calendar-cell-2026-08-10");
    expect(cellMed.querySelector("[data-testid='dot-adherence']")).toBeInTheDocument();

    // 🔵 Appointment & Lab dot on 2026-08-15
    const cellApt = screen.getByTestId("calendar-cell-2026-08-15");
    expect(cellApt.querySelector("[data-testid='dot-appointment']")).toBeInTheDocument();

    // 🟡 Mild Symptom flare-up dot on 2026-08-18
    const cellSym = screen.getByTestId("calendar-cell-2026-08-18");
    expect(cellSym.querySelector("[data-testid='dot-symptom']")).toBeInTheDocument();

    // 🔴 Abnormal Vital / BP Alert dot on 2026-08-22
    const cellAlert = screen.getByTestId("calendar-cell-2026-08-22");
    expect(cellAlert.querySelector("[data-testid='dot-alert']")).toBeInTheDocument();
  });

  it("navigates months smoothly via next/prev buttons and month select", () => {
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        language="vi"
      />,
    );

    const nextBtn = screen.getByTestId("btn-next-month");
    fireEvent.click(nextBtn);

    const selectMonth = screen.getByTestId("select-month") as HTMLSelectElement;
    expect(selectMonth.value).toBe("8"); // September (8)

    const prevBtn = screen.getByTestId("btn-prev-month");
    fireEvent.click(prevBtn);
    expect(selectMonth.value).toBe("7"); // Back to August (7)
  });

  it("filters dots by category when clicking filter pills", () => {
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        language="vi"
      />,
    );

    const cellMed = screen.getByTestId("calendar-cell-2026-08-10");
    const cellAlert = screen.getByTestId("calendar-cell-2026-08-22");

    // Filter only Alert (🔴)
    fireEvent.click(screen.getByTestId("filter-cat-alert"));
    expect(cellMed.querySelector("[data-testid='dot-adherence']")).not.toBeInTheDocument();
    expect(cellAlert.querySelector("[data-testid='dot-alert']")).toBeInTheDocument();

    // Filter only Medication (🟢)
    fireEvent.click(screen.getByTestId("filter-cat-medication"));
    expect(cellMed.querySelector("[data-testid='dot-adherence']")).toBeInTheDocument();
    expect(cellAlert.querySelector("[data-testid='dot-alert']")).not.toBeInTheDocument();

    // Reset to All
    fireEvent.click(screen.getByTestId("filter-cat-all"));
    expect(cellMed.querySelector("[data-testid='dot-adherence']")).toBeInTheDocument();
    expect(cellAlert.querySelector("[data-testid='dot-alert']")).toBeInTheDocument();
  });

  it("opens 1-click day inspection drawer on date click and displays recorded events", async () => {
    const onSelectDateMock = vi.fn();
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        onSelectDate={onSelectDateMock}
        language="vi"
      />,
    );

    // Click on 2026-08-15 (Appointment & Lab)
    const cellApt = screen.getByTestId("calendar-cell-2026-08-15");
    fireEvent.click(cellApt);

    expect(onSelectDateMock).toHaveBeenCalledTimes(1);

    // Inspection Drawer opens
    await waitFor(() => {
      expect(screen.getByTestId("day-inspection-drawer")).toBeInTheDocument();
    });

    expect(screen.getByText("Tái khám Tim mạch định kỳ")).toBeInTheDocument();
    expect(screen.getByText("BS. Trần Văn Hoàng")).toBeInTheDocument();
    expect(screen.getByText("Xét nghiệm sinh hóa máu HbA1c")).toBeInTheDocument();
  });

  it("supports 1-click adding a new event via 'Thêm sự kiện cho ngày này'", async () => {
    const onAddEventMock = vi.fn();
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        onAddEvent={onAddEventMock}
        language="vi"
      />,
    );

    // Click on 2026-08-18
    const cellSym = screen.getByTestId("calendar-cell-2026-08-18");
    fireEvent.click(cellSym);

    // Open add event form
    const addBtn = screen.getByTestId("btn-open-add-event");
    fireEvent.click(addBtn);

    // Form inputs
    const inputTitle = screen.getByTestId("input-new-title");
    fireEvent.change(inputTitle, { target: { value: "Đo Huyết áp trưa 130/85" } });

    const selectCategory = screen.getByTestId("select-new-category");
    fireEvent.change(selectCategory, { target: { value: "alert" } });

    const submitBtn = screen.getByTestId("btn-submit-new-event");
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(onAddEventMock).toHaveBeenCalledWith(
        expect.objectContaining({
          date: "2026-08-18",
          title: "Đo Huyết áp trưa 130/85",
          category: "alert",
        }),
      );
    });

    // The newly created event should now appear in the event list for that day
    expect(screen.getByText("Đo Huyết áp trưa 130/85")).toBeInTheDocument();
  });

  it("renders in English when language prop is set to 'en'", () => {
    render(
      <LifeMapCalendarView
        initialDate="2026-08-01"
        events={mockEvents}
        language="en"
      />,
    );

    expect(screen.getByText("LifeMap Health Calendar")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Mon")).toBeInTheDocument();
    expect(screen.getByText("Sun")).toBeInTheDocument();
    expect(screen.getByText("Medication Adherence")).toBeInTheDocument();
    expect(screen.getByText("Visits & Lab Tests")).toBeInTheDocument();
    expect(screen.getByText("Logged Symptoms")).toBeInTheDocument();
    expect(screen.getByText("Abnormal Alerts")).toBeInTheDocument();
  });
});
