"use client";

import React, { useCallback, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import { Sheet } from "@/components/ui/sheet";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type CalendarEventCategory =
  | "medication"
  | "appointment"
  | "lab"
  | "symptom"
  | "alert"
  | "metric";

export type EventSeverity = "mild" | "moderate" | "severe";

export interface CalendarEventItem {
  id: string;
  date: string; // ISO date format: YYYY-MM-DD
  time?: string; // HH:mm format
  title: string;
  category: CalendarEventCategory;
  description?: string;
  status?: "completed" | "scheduled" | "missed" | "warning" | "mild" | "normal" | string;
  metrics?: Record<string, string | number>;
  location?: string;
  doctorName?: string;
  dosage?: string;
  adherencePercent?: number; // 0 - 100
  severity?: EventSeverity;
}

export interface LifeMapCalendarViewProps {
  events?: CalendarEventItem[];
  initialDate?: Date | string;
  language?: "vi" | "en";
  title?: string;
  description?: string;
  hideHeader?: boolean;
  readOnly?: boolean;
  onSelectDate?: (date: Date, events: CalendarEventItem[]) => void;
  onAddEvent?: (newEvent: Omit<CalendarEventItem, "id"> & { id?: string }) => void | Promise<void>;
  onDeleteEvent?: (eventId: string) => void | Promise<void>;
  className?: string;
}

export type LifemapCalendarViewProps = LifeMapCalendarViewProps;
export type CalendarEvent = CalendarEventItem;

const DICTIONARY = {
  vi: {
    calendarTitle: "Bản đồ sức khỏe LifeMap",
    calendarSubtitle: "Theo dõi tuân thủ dùng thuốc, triệu chứng, lịch khám và chỉ số theo ngày",
    prevMonth: "Tháng trước",
    nextMonth: "Tháng sau",
    today: "Hôm nay",
    month: "Tháng",
    year: "Năm",
    filterLabel: "Bộ lọc sự kiện:",
    filterAll: "Tất cả sự kiện",
    filterMedication: "🟢 Uống thuốc",
    filterAppointment: "🔵 Lịch khám & Xét nghiệm",
    filterSymptom: "🟡 Triệu chứng",
    filterAlert: "🔴 Cảnh báo",
    statAdherence: "Tuân thủ thuốc",
    statAppointments: "Khám & Xét nghiệm",
    statSymptoms: "Triệu chứng",
    statAlerts: "Cảnh báo chỉ số",
    legendTitle: "Ký hiệu trạng thái hàng ngày:",
    dotAdherence: "Uống thuốc đầy đủ (Adherence 100%)",
    dotAppointment: "Có lịch khám bác sĩ / Xét nghiệm",
    dotSymptom: "Triệu chứng nhẹ cần theo dõi",
    dotAlert: "Cảnh báo huyết áp / chỉ số bất thường",
    drawerTitle: "Sự kiện ngày {date}",
    drawerSubtitle: "{count} sự kiện được ghi nhận",
    addEventBtn: "Thêm sự kiện cho ngày này",
    addEventFormTitle: "Ghi nhận sự kiện mới",
    categoryLabel: "Phân loại sự kiện",
    catMedication: "🟢 Uống thuốc & Tuân thủ",
    catAppointment: "🔵 Lịch khám bác sĩ",
    catLab: "🔵 Xét nghiệm cận lâm sàng",
    catSymptom: "🟡 Ghi nhận triệu chứng",
    catAlert: "🔴 Cảnh báo / Đo chỉ số bất thường",
    titleLabel: "Tiêu đề / Tên sự kiện",
    titlePlaceholder: "Ví dụ: Uống Amlodipine 5mg, Tái khám Tim mạch, Đau đầu nhẹ...",
    timeLabel: "Thời gian thực hiện",
    dosageLabel: "Liều dùng / Chi tiết thuốc",
    dosagePlaceholder: "Ví dụ: 1 viên sau ăn sáng",
    doctorLabel: "Bác sĩ / Nơi khám",
    doctorPlaceholder: "Ví dụ: BS. Trần Văn Hoàng - BV Bạch Mai",
    symptomSeverityLabel: "Mức độ triệu chứng",
    severityMild: "Nhẹ (Theo dõi tại nhà)",
    severityModerate: "Vừa phải",
    severitySevere: "Nặng / Cần chú ý",
    metricValueLabel: "Chỉ số / Giá trị đo lường",
    metricValuePlaceholder: "Ví dụ: 145/95 mmHg, 78 bpm, 5.8 mmol/L",
    notesLabel: "Ghi chú bổ sung",
    notesPlaceholder: "Nhập thêm thông tin chi tiết nếu có...",
    saveEventBtn: "Lưu sự kiện",
    savingEvent: "Đang lưu...",
    cancelBtn: "Hủy bỏ",
    deleteEventBtn: "Xóa",
    emptyDayTitle: "Chưa có sự kiện nào trong ngày",
    emptyDayDesc: "Chưa có lịch uống thuốc, buổi khám hoặc triệu chứng nào được ghi nhận cho ngày này.",
    firstEventCta: "Thêm sự kiện đầu tiên cho ngày này",
    eventsSectionTitle: "Danh sách sự kiện đã ghi nhận",
    adherenceFullBadge: "100% Thuốc",
    adherencePartialBadge: "Một phần",
    weekdays: ["T2", "T3", "T4", "T5", "T6", "T7", "CN"],
    weekdaysAria: ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"],
    months: [
      "Tháng 1",
      "Tháng 2",
      "Tháng 3",
      "Tháng 4",
      "Tháng 5",
      "Tháng 6",
      "Tháng 7",
      "Tháng 8",
      "Tháng 9",
      "Tháng 10",
      "Tháng 11",
      "Tháng 12",
    ],
    statusCompleted: "Đã uống / Đã hoàn thành",
    statusScheduled: "Đã lên lịch",
    statusWarning: "Cảnh báo chỉ số",
    statusMild: "Triệu chứng nhẹ",
    viewDetails: "Chi tiết",
    closeDrawer: "Đóng chi tiết",
    actions: "Thao tác",
  },
  en: {
    calendarTitle: "LifeMap Health Calendar",
    calendarSubtitle: "Track medication adherence, symptoms, appointments, and vitals day-by-day",
    prevMonth: "Previous month",
    nextMonth: "Next month",
    today: "Today",
    month: "Month",
    year: "Year",
    filterLabel: "Event filter:",
    filterAll: "All events",
    filterMedication: "🟢 Medication",
    filterAppointment: "🔵 Visits & Labs",
    filterSymptom: "🟡 Symptoms",
    filterAlert: "🔴 Alerts",
    statAdherence: "Medication Adherence",
    statAppointments: "Visits & Lab Tests",
    statSymptoms: "Logged Symptoms",
    statAlerts: "Abnormal Alerts",
    legendTitle: "Daily status dots:",
    dotAdherence: "Full adherence (100%)",
    dotAppointment: "Doctor appointment / Lab test",
    dotSymptom: "Mild symptom to monitor",
    dotAlert: "Blood pressure / Abnormal alert",
    drawerTitle: "Events for {date}",
    drawerSubtitle: "{count} recorded events",
    addEventBtn: "Add event for this date",
    addEventFormTitle: "Record New Health Event",
    categoryLabel: "Event Category",
    catMedication: "🟢 Medication Adherence",
    catAppointment: "🔵 Doctor Appointment",
    catLab: "🔵 Lab Test",
    catSymptom: "🟡 Symptom Flare-up",
    catAlert: "🔴 Alert / Abnormal Reading",
    titleLabel: "Title / Event Name",
    titlePlaceholder: "E.g., Took Amlodipine 5mg, Cardiology visit, Mild headache...",
    timeLabel: "Time",
    dosageLabel: "Dosage / Medication details",
    dosagePlaceholder: "E.g., 1 pill after breakfast",
    doctorLabel: "Doctor / Clinic",
    doctorPlaceholder: "E.g., Dr. Tran Van Hoang - Bach Mai Hospital",
    symptomSeverityLabel: "Symptom Severity",
    severityMild: "Mild (Monitor at home)",
    severityModerate: "Moderate",
    severitySevere: "Severe / Needs attention",
    metricValueLabel: "Measurement / Value",
    metricValuePlaceholder: "E.g., 145/95 mmHg, 78 bpm, 5.8 mmol/L",
    notesLabel: "Additional Notes",
    notesPlaceholder: "Enter extra details or instructions...",
    saveEventBtn: "Save Event",
    savingEvent: "Saving...",
    cancelBtn: "Cancel",
    deleteEventBtn: "Delete",
    emptyDayTitle: "No events recorded for this date",
    emptyDayDesc: "No medication schedules, doctor visits, or symptoms logged yet.",
    firstEventCta: "Add the first event for this date",
    eventsSectionTitle: "Recorded Events",
    adherenceFullBadge: "100% Meds",
    adherencePartialBadge: "Partial",
    weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    weekdaysAria: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    months: [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ],
    statusCompleted: "Completed / Taken",
    statusScheduled: "Scheduled",
    statusWarning: "Abnormal warning",
    statusMild: "Mild symptom",
    viewDetails: "Details",
    closeDrawer: "Close details",
    actions: "Actions",
  },
};

function formatDateToIso(year: number, month: number, day: number): string {
  const m = String(month + 1).padStart(2, "0");
  const d = String(day).padStart(2, "0");
  return `${year}-${m}-${d}`;
}

function generateDemoEvents(referenceDate: Date): CalendarEventItem[] {
  const year = referenceDate.getFullYear();
  const month = referenceDate.getMonth();

  const events: CalendarEventItem[] = [];

  // Generate daily medication adherence for previous days of the month
  const today = new Date();
  const isCurrentMonth = today.getFullYear() === year && today.getMonth() === month;
  const maxDay = isCurrentMonth ? today.getDate() : 28;

  for (let d = 1; d <= maxDay; d++) {
    const dateStr = formatDateToIso(year, month, d);
    // Most days have 100% adherence (🟢)
    const isMissed = d === 4 || d === 12;
    events.push({
      id: `med-${dateStr}-morning`,
      date: dateStr,
      time: "08:00",
      title: "Amlodipine 5mg (Huyết áp)",
      category: "medication",
      dosage: "1 viên sau ăn sáng",
      status: isMissed ? "missed" : "completed",
      adherencePercent: isMissed ? 50 : 100,
      description: isMissed ? "Quên uống liều sáng" : "Đã uống đầy đủ đúng giờ",
    });
    events.push({
      id: `med-${dateStr}-evening`,
      date: dateStr,
      time: "20:00",
      title: "Metformin 500mg (Đường huyết)",
      category: "medication",
      dosage: "1 viên sau ăn tối",
      status: "completed",
      adherencePercent: isMissed ? 50 : 100,
      description: "Đã uống đầy đủ",
    });
  }

  // Doctor appointment (🔵)
  events.push({
    id: `apt-${year}-${month}-03`,
    date: formatDateToIso(year, month, 3),
    time: "09:30",
    title: "Tái khám Tim mạch định kỳ",
    category: "appointment",
    doctorName: "BS. Trần Văn Hoàng",
    location: "Bệnh viện Bạch Mai - Phòng khám 204",
    status: "completed",
    description: "Khám tim mạch định kỳ, kiểm tra huyết áp và điện tâm đồ.",
  });

  // Lab test (🔵)
  events.push({
    id: `lab-${year}-${month}-05`,
    date: formatDateToIso(year, month, 5),
    time: "08:00",
    title: "Xét nghiệm máu: Bộ mỡ máu & HbA1c",
    category: "lab",
    location: "Trung tâm Xét nghiệm Medlatec",
    status: "completed",
    metrics: {
      "HbA1c": "5.6%",
      "Cholesterol": "4.8 mmol/L",
      "Triglyceride": "1.6 mmol/L",
    },
    description: "Các chỉ số đều trong ngưỡng an toàn, tiếp tục duy trì chế độ ăn lành mạnh.",
  });

  // Upcoming appointment (🔵)
  events.push({
    id: `apt-${year}-${month}-24`,
    date: formatDateToIso(year, month, Math.min(24, new Date(year, month + 1, 0).getDate())),
    time: "14:00",
    title: "Khám chuyên khoa Dinh dưỡng & Nội tiết",
    category: "appointment",
    doctorName: "BS. Nguyễn Mai Anh",
    location: "Phòng khám Đa khoa CLARA Care",
    status: "scheduled",
    description: "Tư vấn thực đơn kiểm soát huyết áp và đường huyết.",
  });

  // Mild Symptom flare-up (🟡)
  events.push({
    id: `sym-${year}-${month}-07`,
    date: formatDateToIso(year, month, 7),
    time: "15:30",
    title: "Đau đầu nhẹ vùng thái dương",
    category: "symptom",
    severity: "mild",
    status: "mild",
    description: "Đau đầu sau khi làm việc máy tính liên tục 4 tiếng, đã nghỉ ngơi 30 phút và uống nước.",
  });

  events.push({
    id: `sym-${year}-${month}-16`,
    date: formatDateToIso(year, month, 16),
    time: "10:15",
    title: "Chóng mặt nhẹ khi thay đổi tư thế",
    category: "symptom",
    severity: "mild",
    status: "mild",
    description: "Cảm giác hơi choáng khi đứng dậy nhanh sau giấc ngủ trưa.",
  });

  // Blood pressure abnormal alert (🔴)
  events.push({
    id: `alert-${year}-${month}-11`,
    date: formatDateToIso(year, month, 11),
    time: "07:30",
    title: "Cảnh báo: Huyết áp sáng tăng cao (148/95 mmHg)",
    category: "alert",
    severity: "moderate",
    status: "warning",
    metrics: {
      "Huyết áp": "148/95 mmHg",
      "Nhịp tim": "84 bpm",
    },
    description: "Huyết áp tâm thu > 140 mmHg. Đã uống thuốc theo đơn và đo lại sau 2 giờ (xuống 132/84 mmHg).",
  });

  events.push({
    id: `alert-${year}-${month}-19`,
    date: formatDateToIso(year, month, 19),
    time: "19:45",
    title: "Huyết áp tối tăng nhẹ (142/90 mmHg)",
    category: "alert",
    severity: "moderate",
    status: "warning",
    metrics: {
      "Huyết áp": "142/90 mmHg",
      "Nhịp tim": "76 bpm",
    },
    description: "Cần theo dõi sát chỉ số trong 3 ngày tới.",
  });

  return events;
}

export function LifeMapCalendarView({
  events: propEvents,
  initialDate,
  language: propLanguage,
  title,
  description,
  hideHeader = false,
  readOnly = false,
  onSelectDate,
  onAddEvent,
  onDeleteEvent,
  className = "",
}: LifeMapCalendarViewProps) {
  const uiLanguage = useUILanguage();
  const lang = propLanguage || uiLanguage || "vi";
  const dict = DICTIONARY[lang] || DICTIONARY.vi;

  const [currentDate, setCurrentDate] = useState<Date>(() => {
    if (initialDate instanceof Date) return initialDate;
    if (typeof initialDate === "string") {
      const parsed = new Date(initialDate);
      if (!isNaN(parsed.getTime())) return parsed;
    }
    return new Date();
  });

  const [localEvents, setLocalEvents] = useState<CalendarEventItem[]>(() => {
    if (propEvents && propEvents.length > 0) return propEvents;
    return generateDemoEvents(currentDate);
  });

  // Sync prop events if passed externally
  React.useEffect(() => {
    if (propEvents) {
      setLocalEvents(propEvents);
    }
  }, [propEvents]);

  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<
    "all" | "medication" | "appointment_lab" | "symptom" | "alert"
  >("all");

  const [inspectingDateStr, setInspectingDateStr] = useState<string | null>(null);
  const [isAddingEvent, setIsAddingEvent] = useState(false);

  // New Event Form State
  const [newCategory, setNewCategory] = useState<CalendarEventCategory>("medication");
  const [newTitle, setNewTitle] = useState("");
  const [newTime, setNewTime] = useState("08:00");
  const [newDosage, setNewDosage] = useState("");
  const [newDoctor, setNewDoctor] = useState("");
  const [newSeverity, setNewSeverity] = useState<EventSeverity>("mild");
  const [newMetricValue, setNewMetricValue] = useState("");
  const [newNotes, setNewNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // Navigation handlers
  const handlePrevMonth = useCallback(() => {
    setCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  }, []);

  const handleNextMonth = useCallback(() => {
    setCurrentDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  }, []);

  const handleToday = useCallback(() => {
    const today = new Date();
    setCurrentDate(today);
    const todayStr = formatDateToIso(today.getFullYear(), today.getMonth(), today.getDate());
    setInspectingDateStr(todayStr);
  }, []);

  const handleMonthChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newMonth = parseInt(e.target.value, 10);
      setCurrentDate((prev) => new Date(prev.getFullYear(), newMonth, 1));
    },
    [],
  );

  const handleYearChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const newYear = parseInt(e.target.value, 10);
      setCurrentDate((prev) => new Date(newYear, prev.getMonth(), 1));
    },
    [],
  );

  // Group events by date string (YYYY-MM-DD)
  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEventItem[]>();
    for (const evt of localEvents) {
      const dateKey = evt.date.split("T")[0];
      const existing = map.get(dateKey) || [];
      existing.push(evt);
      map.set(dateKey, existing);
    }
    return map;
  }, [localEvents]);

  // Compute status dots for any date
  const getDayStatus = useCallback(
    (dateStr: string) => {
      const dayEvts = eventsByDate.get(dateStr) || [];

      // 🟢 Full medication adherence
      const medEvts = dayEvts.filter((e) => e.category === "medication");
      const hasMedication = medEvts.length > 0;
      const allMedsTaken =
        hasMedication &&
        medEvts.every(
          (e) =>
            e.status === "completed" ||
            (e.adherencePercent !== undefined && e.adherencePercent >= 100),
        );
      const hasFullAdherence = hasMedication && allMedsTaken;

      // 🔵 Doctor appointment or lab test
      const hasAppointmentOrLab = dayEvts.some(
        (e) => e.category === "appointment" || e.category === "lab",
      );

      // 🟡 Symptom flare-up
      const hasSymptomFlareUp = dayEvts.some((e) => e.category === "symptom");

      // 🔴 Blood pressure or abnormal alert
      const hasAbnormalAlert = dayEvts.some(
        (e) =>
          e.category === "alert" ||
          e.status === "warning" ||
          (e.category === "metric" && e.status === "warning"),
      );

      return {
        hasFullAdherence,
        hasAppointmentOrLab,
        hasSymptomFlareUp,
        hasAbnormalAlert,
        count: dayEvts.length,
        events: dayEvts,
      };
    },
    [eventsByDate],
  );

  // Calculate Monthly Stats
  const monthlyStats = useMemo(() => {
    let totalMedDays = 0;
    let fullAdherenceDays = 0;
    let appointmentCount = 0;
    let symptomCount = 0;
    let alertCount = 0;

    const daysInMonth = new Date(year, month + 1, 0).getDate();

    for (let d = 1; d <= daysInMonth; d++) {
      const dStr = formatDateToIso(year, month, d);
      const dayEvts = eventsByDate.get(dStr) || [];

      const medEvts = dayEvts.filter((e) => e.category === "medication");
      if (medEvts.length > 0) {
        totalMedDays++;
        if (
          medEvts.every(
            (e) =>
              e.status === "completed" ||
              (e.adherencePercent !== undefined && e.adherencePercent >= 100),
          )
        ) {
          fullAdherenceDays++;
        }
      }

      appointmentCount += dayEvts.filter(
        (e) => e.category === "appointment" || e.category === "lab",
      ).length;
      symptomCount += dayEvts.filter((e) => e.category === "symptom").length;
      alertCount += dayEvts.filter(
        (e) => e.category === "alert" || e.status === "warning",
      ).length;
    }

    const adherenceRate =
      totalMedDays > 0 ? Math.round((fullAdherenceDays / totalMedDays) * 100) : 100;

    return {
      adherenceRate,
      appointmentCount,
      symptomCount,
      alertCount,
    };
  }, [eventsByDate, year, month]);

  // Construct Calendar Grid (Monday-first)
  const calendarCells = useMemo(() => {
    const firstDayIndex = (new Date(year, month, 1).getDay() + 6) % 7; // 0 = Mon, 6 = Sun
    const daysInCurrentMonth = new Date(year, month + 1, 0).getDate();
    const daysInPrevMonth = new Date(year, month, 0).getDate();

    const cells: Array<{
      date: Date;
      dateStr: string;
      dayNumber: number;
      isCurrentMonth: boolean;
      isToday: boolean;
    }> = [];

    const today = new Date();
    const todayStr = formatDateToIso(today.getFullYear(), today.getMonth(), today.getDate());

    // Leading days from previous month
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const d = daysInPrevMonth - i;
      const prevMonthDate = new Date(year, month - 1, d);
      const prevMonthYear = prevMonthDate.getFullYear();
      const prevMonthMonth = prevMonthDate.getMonth();
      const dStr = formatDateToIso(prevMonthYear, prevMonthMonth, d);
      cells.push({
        date: prevMonthDate,
        dateStr: dStr,
        dayNumber: d,
        isCurrentMonth: false,
        isToday: dStr === todayStr,
      });
    }

    // Days in current month
    for (let d = 1; d <= daysInCurrentMonth; d++) {
      const currDate = new Date(year, month, d);
      const dStr = formatDateToIso(year, month, d);
      cells.push({
        date: currDate,
        dateStr: dStr,
        dayNumber: d,
        isCurrentMonth: true,
        isToday: dStr === todayStr,
      });
    }

    // Trailing days from next month to fill grid (target 35 or 42 cells)
    const totalFilled = cells.length;
    const totalNeeded = totalFilled > 35 ? 42 : 35;
    const trailingCount = totalNeeded - totalFilled;

    for (let d = 1; d <= trailingCount; d++) {
      const nextMonthDate = new Date(year, month + 1, d);
      const nextMonthYear = nextMonthDate.getFullYear();
      const nextMonthMonth = nextMonthDate.getMonth();
      const dStr = formatDateToIso(nextMonthYear, nextMonthMonth, d);
      cells.push({
        date: nextMonthDate,
        dateStr: dStr,
        dayNumber: d,
        isCurrentMonth: false,
        isToday: dStr === todayStr,
      });
    }

    return cells;
  }, [year, month]);

  // Click on a day cell opens the 1-click inspection drawer
  const handleCellClick = useCallback(
    (date: Date, dateStr: string) => {
      setInspectingDateStr(dateStr);
      setIsAddingEvent(false);
      const dayEvts = eventsByDate.get(dateStr) || [];
      if (onSelectDate) {
        onSelectDate(date, dayEvts);
      }
    },
    [eventsByDate, onSelectDate],
  );

  // Add event handler
  const handleSaveNewEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inspectingDateStr || !newTitle.trim()) return;

    setIsSubmitting(true);
    try {
      const newEvt: CalendarEventItem = {
        id: `evt-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        date: inspectingDateStr,
        time: newTime.trim() || undefined,
        title: newTitle.trim(),
        category: newCategory,
        description: newNotes.trim() || undefined,
        status:
          newCategory === "medication"
            ? "completed"
            : newCategory === "alert"
              ? "warning"
              : newCategory === "symptom"
                ? newSeverity
                : "scheduled",
        dosage: newCategory === "medication" && newDosage ? newDosage.trim() : undefined,
        doctorName: newCategory === "appointment" && newDoctor ? newDoctor.trim() : undefined,
        severity: newCategory === "symptom" ? newSeverity : undefined,
        metrics:
          newMetricValue && (newCategory === "alert" || newCategory === "metric")
            ? { "Chỉ số": newMetricValue.trim() }
            : undefined,
        adherencePercent: newCategory === "medication" ? 100 : undefined,
      };

      setLocalEvents((prev) => [newEvt, ...prev]);

      if (onAddEvent) {
        await onAddEvent(newEvt);
      }

      // Reset form
      setNewTitle("");
      setNewNotes("");
      setNewDosage("");
      setNewDoctor("");
      setNewMetricValue("");
      setIsAddingEvent(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteEvent = async (eventId: string) => {
    setLocalEvents((prev) => prev.filter((e) => e.id !== eventId));
    if (onDeleteEvent) {
      await onDeleteEvent(eventId);
    }
  };

  const inspectingEvents = inspectingDateStr
    ? eventsByDate.get(inspectingDateStr) || []
    : [];

  const inspectingDateObj = inspectingDateStr
    ? new Date(`${inspectingDateStr}T00:00:00`)
    : new Date();

  const inspectingDateFormatted = inspectingDateStr
    ? formatLocaleDate(lang, inspectingDateObj, {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";

  const inspectingDayStatus = inspectingDateStr ? getDayStatus(inspectingDateStr) : null;

  // Year options for dropdown
  const currentYear = new Date().getFullYear();
  const yearOptions = [
    currentYear - 2,
    currentYear - 1,
    currentYear,
    currentYear + 1,
    currentYear + 2,
  ];

  return (
    <div
      className={`space-y-6 ${className}`}
      data-testid="lifemap-calendar-view"
    >
      {/* Calendar Header & Controls */}
      <SurfaceCard className="overflow-hidden border border-[var(--shell-border)] shadow-sm">
        {!hideHeader && (
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--shell-border)] px-5 py-4 bg-[var(--surface-panel)]">
            <div className="flex items-center gap-3">
              <span
                className="grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-lg)] bg-[var(--surface-brand-soft)] text-[var(--brand-600)]"
                aria-hidden="true"
              >
                <Icon name="calendar" size={20} />
              </span>
              <div>
                <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)]">
                  {title || dict.calendarTitle}
                </h2>
                <p className="text-xs text-[var(--text-secondary)]">
                  {description || dict.calendarSubtitle}
                </p>
              </div>
            </div>

            {/* Quick Today Jump Button */}
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon="calendar"
                onClick={handleToday}
                data-testid="btn-jump-today"
              >
                {dict.today}
              </Button>
            </div>
          </div>
        )}

        {/* Navigation & Month/Year Selectors Strip */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 border-b border-[var(--shell-border)] bg-[var(--surface-muted)]/40">
          {/* Month Navigation Controls */}
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon="arrow-left"
              onClick={handlePrevMonth}
              aria-label={dict.prevMonth}
              data-testid="btn-prev-month"
            />
            <div className="flex items-center gap-2">
              <select
                aria-label={dict.month}
                value={month}
                onChange={handleMonthChange}
                data-testid="select-month"
                className="rounded-lg border border-[var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-sm font-semibold text-[var(--text-primary)] shadow-xs hover:border-[var(--shell-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]"
              >
                {dict.months.map((mName, idx) => (
                  <option key={idx} value={idx}>
                    {mName}
                  </option>
                ))}
              </select>

              <select
                aria-label={dict.year}
                value={year}
                onChange={handleYearChange}
                data-testid="select-year"
                className="rounded-lg border border-[var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-sm font-semibold text-[var(--text-primary)] shadow-xs hover:border-[var(--shell-border-strong)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]"
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="secondary"
              size="sm"
              icon="arrow-right"
              onClick={handleNextMonth}
              aria-label={dict.nextMonth}
              data-testid="btn-next-month"
            />
          </div>

          {/* Category Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs font-semibold text-[var(--text-secondary)] mr-1 hidden md:inline">
              {dict.filterLabel}
            </span>
            <button
              type="button"
              data-testid="filter-cat-all"
              onClick={() => setSelectedCategoryFilter("all")}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedCategoryFilter === "all"
                  ? "bg-[var(--brand-600)] text-white shadow-xs"
                  : "bg-[var(--surface-panel)] border border-[var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {dict.filterAll}
            </button>
            <button
              type="button"
              data-testid="filter-cat-medication"
              onClick={() => setSelectedCategoryFilter("medication")}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedCategoryFilter === "medication"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "bg-[var(--surface-panel)] border border-[var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {dict.filterMedication}
            </button>
            <button
              type="button"
              data-testid="filter-cat-appointment"
              onClick={() => setSelectedCategoryFilter("appointment_lab")}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedCategoryFilter === "appointment_lab"
                  ? "bg-sky-600 text-white shadow-xs"
                  : "bg-[var(--surface-panel)] border border-[var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {dict.filterAppointment}
            </button>
            <button
              type="button"
              data-testid="filter-cat-symptom"
              onClick={() => setSelectedCategoryFilter("symptom")}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedCategoryFilter === "symptom"
                  ? "bg-amber-600 text-white shadow-xs"
                  : "bg-[var(--surface-panel)] border border-[var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {dict.filterSymptom}
            </button>
            <button
              type="button"
              data-testid="filter-cat-alert"
              onClick={() => setSelectedCategoryFilter("alert")}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold transition-all ${
                selectedCategoryFilter === "alert"
                  ? "bg-rose-600 text-white shadow-xs"
                  : "bg-[var(--surface-panel)] border border-[var(--shell-border)] text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              }`}
            >
              {dict.filterAlert}
            </button>
          </div>
        </div>

        {/* Monthly Summary Statistics Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-[var(--surface-panel)] border-b border-[var(--shell-border)]">
          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[var(--surface-muted)]/50 border border-[var(--shell-border)]/60">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-emerald-500/10 text-emerald-600">
              <Icon name="check" size={18} />
            </span>
            <div className="min-w-0">
              <span className="text-[0.6875rem] font-medium text-[var(--text-secondary)] block truncate">
                {dict.statAdherence}
              </span>
              <span
                data-testid="stat-adherence-rate"
                className="text-base font-bold text-[var(--text-primary)]"
              >
                {monthlyStats.adherenceRate}%
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[var(--surface-muted)]/50 border border-[var(--shell-border)]/60">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sky-500/10 text-sky-600">
              <Icon name="clinical-notes" size={18} />
            </span>
            <div className="min-w-0">
              <span className="text-[0.6875rem] font-medium text-[var(--text-secondary)] block truncate">
                {dict.statAppointments}
              </span>
              <span
                data-testid="stat-appointments-count"
                className="text-base font-bold text-[var(--text-primary)]"
              >
                {monthlyStats.appointmentCount}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[var(--surface-muted)]/50 border border-[var(--shell-border)]/60">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-amber-500/10 text-amber-600">
              <Icon name="body" size={18} />
            </span>
            <div className="min-w-0">
              <span className="text-[0.6875rem] font-medium text-[var(--text-secondary)] block truncate">
                {dict.statSymptoms}
              </span>
              <span
                data-testid="stat-symptoms-count"
                className="text-base font-bold text-[var(--text-primary)]"
              >
                {monthlyStats.symptomCount}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-[var(--surface-muted)]/50 border border-[var(--shell-border)]/60">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-rose-500/10 text-rose-600">
              <Icon name="warning" size={18} />
            </span>
            <div className="min-w-0">
              <span className="text-[0.6875rem] font-medium text-[var(--text-secondary)] block truncate">
                {dict.statAlerts}
              </span>
              <span
                data-testid="stat-alerts-count"
                className="text-base font-bold text-[var(--text-primary)]"
              >
                {monthlyStats.alertCount}
              </span>
            </div>
          </div>
        </div>

        {/* Legend Ribbon */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 bg-[var(--surface-muted)]/30 border-b border-[var(--shell-border)] text-xs text-[var(--text-secondary)]">
          <span className="font-semibold">{dict.legendTitle}</span>
          <div className="flex flex-wrap items-center gap-4">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" />
              <span>{dict.dotAdherence}</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-sky-500 ring-2 ring-sky-500/20" />
              <span>{dict.dotAppointment}</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500 ring-2 ring-amber-500/20" />
              <span>{dict.dotSymptom}</span>
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500 ring-2 ring-rose-500/20" />
              <span>{dict.dotAlert}</span>
            </span>
          </div>
        </div>

        {/* Calendar Grid Matrix */}
        <div
          role="grid"
          aria-label={`${dict.calendarTitle} - ${dict.months[month]} ${year}`}
          className="p-3 sm:p-5 transition-all duration-300 ease-in-out"
        >
          {/* Weekdays Row */}
          <div role="row" className="grid grid-cols-7 gap-1.5 sm:gap-2 mb-2">
            {dict.weekdays.map((wName, idx) => (
              <div
                key={idx}
                role="columnheader"
                aria-label={dict.weekdaysAria[idx]}
                className="py-2 text-center text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]"
              >
                {wName}
              </div>
            ))}
          </div>

          {/* Day Cells Matrix */}
          <div className="grid grid-cols-7 gap-1.5 sm:gap-2.5">
            {calendarCells.map((cell) => {
              const status = getDayStatus(cell.dateStr);
              const isInspecting = inspectingDateStr === cell.dateStr;

              // Filter matching
              const shouldShowDot = (dotType: "med" | "apt" | "sym" | "alert") => {
                if (selectedCategoryFilter === "all") return true;
                if (selectedCategoryFilter === "medication" && dotType === "med") return true;
                if (selectedCategoryFilter === "appointment_lab" && dotType === "apt") return true;
                if (selectedCategoryFilter === "symptom" && dotType === "sym") return true;
                if (selectedCategoryFilter === "alert" && dotType === "alert") return true;
                return false;
              };

              const showGreen = status.hasFullAdherence && shouldShowDot("med");
              const showBlue = status.hasAppointmentOrLab && shouldShowDot("apt");
              const showYellow = status.hasSymptomFlareUp && shouldShowDot("sym");
              const showRed = status.hasAbnormalAlert && shouldShowDot("alert");

              // Heat background color
              let heatBg = "bg-[var(--surface-panel)]";
              if (!cell.isCurrentMonth) {
                heatBg = "bg-[var(--surface-muted)]/30 opacity-45";
              } else if (status.hasAbnormalAlert && shouldShowDot("alert")) {
                heatBg = "bg-rose-500/5 hover:bg-rose-500/10";
              } else if (status.hasFullAdherence && shouldShowDot("med")) {
                heatBg = "bg-emerald-500/5 hover:bg-emerald-500/10";
              }

              return (
                <button
                  key={cell.dateStr}
                  type="button"
                  role="gridcell"
                  data-testid={`calendar-cell-${cell.dateStr}`}
                  aria-selected={isInspecting}
                  aria-label={`${cell.dayNumber} ${dict.months[cell.date.getMonth()]} ${cell.date.getFullYear()}, ${status.count} ${dict.statSymptoms}`}
                  onClick={() => handleCellClick(cell.date, cell.dateStr)}
                  className={`group relative flex flex-col justify-between min-h-[76px] sm:min-h-[96px] p-2 sm:p-2.5 rounded-xl border text-left transition-all duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--brand-500)] ${heatBg} ${
                    isInspecting
                      ? "border-[var(--brand-600)] ring-2 ring-[var(--brand-500)]/30 shadow-md"
                      : cell.isToday
                        ? "border-[var(--brand-500)] ring-1 ring-[var(--brand-500)]/30"
                        : "border-[var(--shell-border)] hover:border-[var(--shell-border-strong)] hover:shadow-xs"
                  }`}
                >
                  {/* Top Bar: Day Number & Today Tag */}
                  <div className="flex items-center justify-between w-full">
                    <span
                      className={`inline-flex items-center justify-center text-xs sm:text-sm font-bold ${
                        cell.isToday
                          ? "h-6 w-6 rounded-full bg-[var(--brand-600)] text-white shadow-xs"
                          : cell.isCurrentMonth
                            ? "text-[var(--text-primary)]"
                            : "text-[var(--text-muted)]"
                      }`}
                    >
                      {cell.dayNumber}
                    </span>

                    {/* Small event counter badge */}
                    {status.count > 0 && cell.isCurrentMonth && (
                      <span className="hidden sm:inline-flex px-1.5 py-0.25 text-[0.625rem] font-bold rounded-md bg-[var(--surface-muted)] text-[var(--text-secondary)] border border-[var(--shell-border)]/60">
                        {status.count}
                      </span>
                    )}
                  </div>

                  {/* Status Indicator Dots Strip */}
                  <div className="flex items-center gap-1 sm:gap-1.5 pt-1.5 flex-wrap">
                    {showGreen && (
                      <span
                        data-testid="dot-adherence"
                        title={dict.dotAdherence}
                        aria-label={dict.dotAdherence}
                        className="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20 shrink-0"
                      />
                    )}
                    {showBlue && (
                      <span
                        data-testid="dot-appointment"
                        title={dict.dotAppointment}
                        aria-label={dict.dotAppointment}
                        className="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-sky-500 ring-2 ring-sky-500/20 shrink-0"
                      />
                    )}
                    {showYellow && (
                      <span
                        data-testid="dot-symptom"
                        title={dict.dotSymptom}
                        aria-label={dict.dotSymptom}
                        className="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-amber-500 ring-2 ring-amber-500/20 shrink-0"
                      />
                    )}
                    {showRed && (
                      <span
                        data-testid="dot-alert"
                        title={dict.dotAlert}
                        aria-label={dict.dotAlert}
                        className="h-2 w-2 sm:h-2.5 sm:w-2.5 rounded-full bg-rose-500 ring-2 ring-rose-500/20 shrink-0 animate-pulse"
                      />
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </SurfaceCard>

      {/* 1-Click Day Inspection Drawer */}
      {inspectingDateStr && (
        <Sheet
          open={Boolean(inspectingDateStr)}
          onClose={() => {
            setInspectingDateStr(null);
            setIsAddingEvent(false);
          }}
          title={dict.drawerTitle.replace("{date}", inspectingDateFormatted)}
          description={dict.drawerSubtitle.replace(
            "{count}",
            String(inspectingEvents.length),
          )}
          size="md"
          data-testid="day-inspection-drawer"
        >
          <div className="space-y-5">
            {/* Quick Day Status Chips */}
            {inspectingDayStatus && (
              <div className="flex flex-wrap items-center gap-2 p-3 rounded-xl bg-[var(--surface-muted)]/50 border border-[var(--shell-border)]">
                {inspectingDayStatus.hasFullAdherence && (
                  <Badge tone="ok" icon="check">
                    {dict.dotAdherence}
                  </Badge>
                )}
                {inspectingDayStatus.hasAppointmentOrLab && (
                  <Badge tone="brand" icon="clinical-notes">
                    {dict.dotAppointment}
                  </Badge>
                )}
                {inspectingDayStatus.hasSymptomFlareUp && (
                  <Badge tone="warn" icon="body">
                    {dict.dotSymptom}
                  </Badge>
                )}
                {inspectingDayStatus.hasAbnormalAlert && (
                  <Badge tone="danger" icon="warning">
                    {dict.dotAlert}
                  </Badge>
                )}
              </div>
            )}

            {/* 1-Click "Thêm sự kiện cho ngày này" Button / Form Toggle */}
            {!readOnly && !isAddingEvent && (
              <Button
                variant="primary"
                icon="add"
                block
                onClick={() => setIsAddingEvent(true)}
                data-testid="btn-open-add-event"
              >
                {dict.addEventBtn}
              </Button>
            )}

            {/* Inline Event Creation Form */}
            {isAddingEvent && (
              <SurfaceCard className="p-4 rounded-xl border-2 border-[var(--brand-500)]/40 bg-[var(--surface-panel)] space-y-4 shadow-sm animate-in fade-in duration-200">
                <div className="flex items-center justify-between border-b border-[var(--shell-border)] pb-2.5">
                  <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Icon name="plus" size={16} className="text-[var(--brand-600)]" />
                    {dict.addEventFormTitle}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setIsAddingEvent(false)}
                    className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  >
                    {dict.cancelBtn}
                  </button>
                </div>

                <form onSubmit={handleSaveNewEvent} className="space-y-3.5">
                  {/* Category Selector */}
                  <div>
                    <label
                      htmlFor="new-event-category"
                      className="block text-xs font-semibold text-[var(--text-secondary)] mb-1"
                    >
                      {dict.categoryLabel}
                    </label>
                    <Select
                      id="new-event-category"
                      value={newCategory}
                      onChange={(e) =>
                        setNewCategory(e.target.value as CalendarEventCategory)
                      }
                      data-testid="select-new-category"
                    >
                      <option value="medication">{dict.catMedication}</option>
                      <option value="appointment">{dict.catAppointment}</option>
                      <option value="lab">{dict.catLab}</option>
                      <option value="symptom">{dict.catSymptom}</option>
                      <option value="alert">{dict.catAlert}</option>
                    </Select>
                  </div>

                  {/* Title */}
                  <div>
                    <Field
                      id="new-event-title"
                      label={dict.titleLabel}
                      placeholder={dict.titlePlaceholder}
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      required
                      autoFocus
                      data-testid="input-new-title"
                    />
                  </div>

                  {/* Time */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Field
                        id="new-event-time"
                        type="time"
                        label={dict.timeLabel}
                        value={newTime}
                        onChange={(e) => setNewTime(e.target.value)}
                        data-testid="input-new-time"
                      />
                    </div>

                    {/* Specific category sub-fields */}
                    {newCategory === "medication" && (
                      <div>
                        <Field
                          id="new-event-dosage"
                          label={dict.dosageLabel}
                          placeholder={dict.dosagePlaceholder}
                          value={newDosage}
                          onChange={(e) => setNewDosage(e.target.value)}
                          data-testid="input-new-dosage"
                        />
                      </div>
                    )}

                    {newCategory === "appointment" && (
                      <div>
                        <Field
                          id="new-event-doctor"
                          label={dict.doctorLabel}
                          placeholder={dict.doctorPlaceholder}
                          value={newDoctor}
                          onChange={(e) => setNewDoctor(e.target.value)}
                          data-testid="input-new-doctor"
                        />
                      </div>
                    )}

                    {newCategory === "symptom" && (
                      <div>
                        <label
                          htmlFor="new-event-severity"
                          className="block text-xs font-semibold text-[var(--text-secondary)] mb-1"
                        >
                          {dict.symptomSeverityLabel}
                        </label>
                        <Select
                          id="new-event-severity"
                          value={newSeverity}
                          onChange={(e) =>
                            setNewSeverity(e.target.value as EventSeverity)
                          }
                          data-testid="select-new-severity"
                        >
                          <option value="mild">{dict.severityMild}</option>
                          <option value="moderate">{dict.severityModerate}</option>
                          <option value="severe">{dict.severitySevere}</option>
                        </Select>
                      </div>
                    )}

                    {(newCategory === "alert" || newCategory === "metric") && (
                      <div>
                        <Field
                          id="new-event-metric"
                          label={dict.metricValueLabel}
                          placeholder={dict.metricValuePlaceholder}
                          value={newMetricValue}
                          onChange={(e) => setNewMetricValue(e.target.value)}
                          data-testid="input-new-metric"
                        />
                      </div>
                    )}
                  </div>

                  {/* Notes */}
                  <div>
                    <Textarea
                      id="new-event-notes"
                      label={dict.notesLabel}
                      placeholder={dict.notesPlaceholder}
                      value={newNotes}
                      onChange={(e) => setNewNotes(e.target.value)}
                      rows={2}
                      data-testid="input-new-notes"
                    />
                  </div>

                  {/* Form Action Buttons */}
                  <div className="flex items-center justify-end gap-2 pt-2 border-t border-[var(--shell-border)]">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => setIsAddingEvent(false)}
                    >
                      {dict.cancelBtn}
                    </Button>
                    <Button
                      type="submit"
                      variant="primary"
                      size="sm"
                      icon="check"
                      loading={isSubmitting}
                      loadingLabel={dict.savingEvent}
                      disabled={!newTitle.trim()}
                      data-testid="btn-submit-new-event"
                    >
                      {dict.saveEventBtn}
                    </Button>
                  </div>
                </form>
              </SurfaceCard>
            )}

            {/* List of Events Recorded for this Day */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                {dict.eventsSectionTitle} ({inspectingEvents.length})
              </h3>

              {inspectingEvents.length === 0 ? (
                <div
                  className="p-6 text-center rounded-xl border border-dashed border-[var(--shell-border)] bg-[var(--surface-muted)]/40 space-y-3"
                  data-testid="day-empty-state"
                >
                  <span
                    className="grid h-10 w-10 mx-auto place-items-center rounded-full bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                    aria-hidden="true"
                  >
                    <Icon name="calendar" size={20} />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-[var(--text-primary)]">
                      {dict.emptyDayTitle}
                    </p>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                      {dict.emptyDayDesc}
                    </p>
                  </div>
                  {!readOnly && (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon="add"
                      onClick={() => setIsAddingEvent(true)}
                    >
                      {dict.firstEventCta}
                    </Button>
                  )}
                </div>
              ) : (
                <div className="space-y-2.5">
                  {inspectingEvents.map((evt) => {
                    const isMed = evt.category === "medication";
                    const isApt = evt.category === "appointment" || evt.category === "lab";
                    const isSym = evt.category === "symptom";
                    const isAlert = evt.category === "alert" || evt.status === "warning";

                    let badgeTone: "ok" | "brand" | "warn" | "danger" | "neutral" = "neutral";
                    let badgeLabel = dict.catMedication;

                    if (isMed) {
                      badgeTone = evt.status === "completed" ? "ok" : "warn";
                      badgeLabel =
                        evt.status === "completed" ? dict.statusCompleted : dict.catMedication;
                    } else if (isApt) {
                      badgeTone = "brand";
                      badgeLabel = evt.category === "lab" ? dict.catLab : dict.catAppointment;
                    } else if (isSym) {
                      badgeTone = "warn";
                      badgeLabel = dict.catSymptom;
                    } else if (isAlert) {
                      badgeTone = "danger";
                      badgeLabel = dict.statusWarning;
                    }

                    return (
                      <div
                        key={evt.id}
                        data-testid={`event-card-${evt.id}`}
                        className={`p-3.5 rounded-xl border transition-all ${
                          isAlert
                            ? "border-rose-500/40 bg-rose-500/5"
                            : isMed && evt.status === "completed"
                              ? "border-emerald-500/30 bg-emerald-500/5"
                              : "border-[var(--shell-border)] bg-[var(--surface-panel)]"
                        }`}
                      >
                        {/* Header: Badge & Time */}
                        <div className="flex items-start justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <Badge tone={badgeTone}>{badgeLabel}</Badge>
                            {evt.time && (
                              <span className="text-xs font-mono text-[var(--text-secondary)]">
                                {evt.time}
                              </span>
                            )}
                          </div>

                          {!readOnly && (
                            <button
                              type="button"
                              onClick={() => handleDeleteEvent(evt.id)}
                              aria-label={`${dict.deleteEventBtn} ${evt.title}`}
                              className="text-xs text-[var(--text-muted)] hover:text-rose-600 transition-colors p-1"
                            >
                              <Icon name="trash" size={13} />
                            </button>
                          )}
                        </div>

                        {/* Event Title */}
                        <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                          {evt.title}
                        </h4>

                        {/* Extra metadata */}
                        {evt.dosage && (
                          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                            <strong className="text-[var(--text-primary)]">Liều dùng:</strong>{" "}
                            {evt.dosage}
                          </p>
                        )}

                        {evt.doctorName && (
                          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                            <strong className="text-[var(--text-primary)]">Bác sĩ:</strong>{" "}
                            {evt.doctorName}
                          </p>
                        )}

                        {evt.location && (
                          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                            <strong className="text-[var(--text-primary)]">Địa điểm:</strong>{" "}
                            {evt.location}
                          </p>
                        )}

                        {evt.metrics && Object.keys(evt.metrics).length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {Object.entries(evt.metrics).map(([k, v]) => (
                              <span
                                key={k}
                                className="px-2 py-0.5 rounded-md text-xs font-mono bg-[var(--surface-muted)] border border-[var(--shell-border)] text-[var(--text-primary)]"
                              >
                                <strong>{k}:</strong> {v}
                              </span>
                            ))}
                          </div>
                        )}

                        {evt.description && (
                          <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-2 p-2 rounded-lg bg-[var(--surface-muted)]/50">
                            {evt.description}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </Sheet>
      )}
    </div>
  );
}

export const LifemapCalendarView = LifeMapCalendarView;
export default LifeMapCalendarView;
