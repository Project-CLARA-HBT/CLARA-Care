import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ConsumerCarePage from "./page";
import ConsumerCareVisitsPage from "./visits/page";
import VisitPreparePage from "./prepare/page";
import SymptomCheckerPage from "./check-symptoms/page";
import { v2Client } from "@/lib/api/v2-client";

const mockRouter = {
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/care",
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const mockCareSummary = {
  profile: { id: "p-1", display_name: "Nguyễn Văn A" },
  upcoming_visits: [
    {
      id: "v-1",
      title: "Tái khám Tim mạch",
      doctor_name: "BSCKII Nguyễn Văn An",
      specialty: "Tim mạch",
      facility_name: "Bệnh viện ĐHYD",
      scheduled_at: "2026-08-25T09:00:00Z",
      status: "scheduled",
      prep_status: "not_started",
      document_count: 2,
    },
  ],
  prep_prompts: [
    {
      id: "prompt-1",
      visit_id: "v-1",
      title: "Chuẩn bị cho buổi khám Tim mạch sắp tới",
      description: "Hãy hoàn thành tóm tắt triệu chứng và soạn câu hỏi.",
      action_label: "Chuẩn bị ngay",
      action_href: "/care/prepare?visitId=v-1",
      urgency: "high",
    },
  ],
  active_tasks: [
    {
      id: "task-1",
      title: "Đo huyết áp sáng trước khám",
      due_date: "2026-08-25T08:00:00Z",
      status: "pending",
      priority: "high",
      description: "Ghi nhận 3 lần đo liên tiếp",
    },
  ],
};

const mockVisitsList = [
  {
    id: "v-1",
    title: "Tái khám Tim mạch",
    doctor_name: "BSCKII Nguyễn Văn An",
    specialty: "Tim mạch",
    facility_name: "Bệnh viện ĐHYD",
    scheduled_at: "2026-08-25T09:00:00Z",
    status: "scheduled",
    prep_status: "not_started",
    reason_for_visit: "Kiểm tra huyết áp mục tiêu",
    document_count: 1,
    documents: [
      {
        id: "d-1",
        title: "Điện tâm đồ ECG",
        mime_type: "application/pdf",
        recorded_at: "2026-08-01T08:00:00Z",
        summary: "Nhịp xoang 72 l/p",
      },
    ],
  },
  {
    id: "v-old",
    title: "Khám Tai Mũi Họng cũ",
    doctor_name: "BS Trần Văn B",
    specialty: "Tai Mũi Họng",
    facility_name: "Phòng khám Đa khoa",
    scheduled_at: "2026-07-01T09:00:00Z",
    status: "completed",
    prep_status: "completed",
    reason_for_visit: "Viêm họng cấp",
    document_count: 0,
    documents: [],
  },
];

describe("Care Overview & Sub-route Pages", () => {
  describe("Care Overview Page (/care)", () => {
    it("renders header, symptom checker banner, upcoming visits, prep prompts, and care tasks", async () => {
      vi.spyOn(v2Client, "getCareSummary").mockResolvedValueOnce(mockCareSummary as any);

      render(<ConsumerCarePage />);

      await waitFor(() => {
        expect(screen.getByTestId("care-overview-page")).toBeInTheDocument();
      });

      expect(screen.getByText("Chăm sóc & Khám bệnh")).toBeInTheDocument();
      expect(screen.getByTestId("symptom-checker-banner")).toBeInTheDocument();
      expect(screen.getByText("Kiểm tra triệu chứng & Định hướng chăm sóc")).toBeInTheDocument();
      expect(screen.getByTestId("launch-symptom-checker-btn")).toHaveAttribute("href", "/care/check-symptoms");

      // Prep Prompts
      expect(screen.getByText("Chuẩn bị cho buổi khám Tim mạch sắp tới")).toBeInTheDocument();

      // Upcoming Visits
      expect(screen.getByText("Tái khám Tim mạch")).toBeInTheDocument();
      expect(screen.getByText(/BSCKII Nguyễn Văn An/)).toBeInTheDocument();

      // Active Tasks
      expect(screen.getByText("Đo huyết áp sáng trước khám")).toBeInTheDocument();
    });

    it("allows checking and completing an active care task", async () => {
      vi.spyOn(v2Client, "getCareSummary").mockResolvedValueOnce(mockCareSummary as any);

      render(<ConsumerCarePage />);

      await waitFor(() => {
        expect(screen.getByTestId("care-task-task-1")).toBeInTheDocument();
      });

      const taskCheckbox = screen.getByLabelText(/Mark "Đo huyết áp sáng trước khám" as completed/i);
      expect(taskCheckbox).not.toBeChecked();

      fireEvent.click(taskCheckbox);
      expect(taskCheckbox).toBeChecked();
    });
  });

  describe("Care Visits Page (/care/visits)", () => {
    it("renders visits list, filter tabs, search, and visit details with documents", async () => {
      vi.spyOn(v2Client, "getVisits").mockResolvedValueOnce(mockVisitsList as any);

      render(<ConsumerCareVisitsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("care-visits-page")).toBeInTheDocument();
      });

      expect(screen.getByText("Lịch khám & Hồ sơ buổi khám")).toBeInTheDocument();
      expect(screen.getByTestId("tab-all-visits")).toBeInTheDocument();
      expect(screen.getByTestId("tab-upcoming-visits")).toBeInTheDocument();
      expect(screen.getByTestId("tab-past-visits")).toBeInTheDocument();

      // Detail pane
      expect(screen.getByTestId("visit-detail-pane")).toBeInTheDocument();
      expect(screen.getByText("Điện tâm đồ ECG")).toBeInTheDocument();
    });

    it("filters visits by search query", async () => {
      vi.spyOn(v2Client, "getVisits").mockResolvedValueOnce(mockVisitsList as any);

      render(<ConsumerCareVisitsPage />);

      await waitFor(() => {
        expect(screen.getByTestId("visits-search-input")).toBeInTheDocument();
      });

      const searchInput = screen.getByTestId("visits-search-input");
      fireEvent.change(searchInput, { target: { value: "Tai Mũi Họng" } });

      await waitFor(() => {
        expect(screen.getAllByText("Khám Tai Mũi Họng cũ").length).toBeGreaterThan(0);
        expect(screen.queryByTestId("visit-item-v-1")).not.toBeInTheDocument();
      });
    });
  });

  describe("Visit Preparation Wizard (/care/prepare)", () => {
    it("walks through all 4 steps: purpose, longitudinal changes, questions & goals, handoff preview", async () => {
      vi.spyOn(v2Client, "getVisits").mockResolvedValueOnce(mockVisitsList as any);
      vi.spyOn(v2Client, "prepareVisit").mockResolvedValueOnce({
        visit_id: "v-1",
        purpose: "Tái khám Tim mạch",
        summary: "Ready",
        what_changed: ["Huyết áp ổn định"],
        patient_questions: ["Có giảm thuốc được không?"],
        patient_goals: ["Kiểm tra tim mạch"],
        created_at: new Date().toISOString(),
      });

      render(<VisitPreparePage />);

      // Step 1: Select visit or purpose
      await waitFor(() => {
        expect(screen.getByTestId("prep-step-1-card")).toBeInTheDocument();
      });
      expect(screen.getByText(/Chọn buổi khám hoặc nhập lý do đi khám/i)).toBeInTheDocument();

      // Proceed to Step 2
      fireEvent.click(screen.getByText(/Tiếp theo: Diễn tiến thay đổi/i));

      // Step 2: Longitudinal changes
      expect(screen.getByTestId("prep-step-2-card")).toBeInTheDocument();
      expect(screen.getByText(/Diễn tiến & Thay đổi kể từ lần khám trước/i)).toBeInTheDocument();

      // Proceed to Step 3
      fireEvent.click(screen.getByText(/Tiếp theo: Soạn câu hỏi/i));

      // Step 3: Questions & Goals
      expect(screen.getByTestId("prep-step-3-card")).toBeInTheDocument();
      expect(screen.getByText(/Soạn câu hỏi & Mục tiêu cho buổi khám/i)).toBeInTheDocument();

      // Proceed to Step 4
      fireEvent.click(screen.getByText(/Tiếp theo: Xem bản tóm tắt/i));

      // Step 4: Handoff Preview
      expect(screen.getByTestId("prep-step-4-card")).toBeInTheDocument();
      expect(screen.getByTestId("handoff-pack-preview")).toBeInTheDocument();
      expect(screen.getByText("CLARA CLINICIAN HANDOFF PACK")).toBeInTheDocument();

      // Save & Complete
      fireEvent.click(screen.getByText(/Lưu & Hoàn tất chuẩn bị/i));
      await waitFor(() => {
        expect(screen.getByText(/Đã lưu bản chuẩn bị thành công/i)).toBeInTheDocument();
      });
    });
  });

  describe("Symptom Checker & Care Navigation Flow (/care/check-symptoms)", () => {
    it("triggers immediate deterministic red-flag emergency alert override when red flag selected", async () => {
      render(<SymptomCheckerPage />);

      expect(screen.getByTestId("symptom-step-1")).toBeInTheDocument();
      expect(screen.getByTestId("red-flag-section")).toBeInTheDocument();

      // Click on chest pain red-flag checkbox
      const chestPainCheckbox = screen.getByTestId("redflag-checkbox-chest_pain").querySelector("input")!;
      fireEvent.click(chestPainCheckbox);

      // Emergency alertdialog modal should appear immediately
      await waitFor(() => {
        expect(screen.getByTestId("emergency-modal-content")).toBeInTheDocument();
      });
      expect(screen.getByText("CẢNH BÁO CẤP CỨU KHẨN CẤP")).toBeInTheDocument();
      expect(screen.getByText(/Gọi 115 ngay/i)).toBeInTheDocument();
    });

    it("steps through bounded symptom questions and presents urgency result card with handoff summary", async () => {
      vi.spyOn(v2Client, "checkSymptoms").mockResolvedValueOnce({
        urgency: "routine",
        is_red_flag_emergency: false,
        title: "Khám thông thường / Hẹn khám chuyên khoa",
        explanation: "Triệu chứng cần được bác sĩ đánh giá nhưng không có dấu hiệu khẩn cấp.",
        care_navigation_guidance: "Đặt lịch hẹn khám chuyên khoa trong 1-3 ngày tới.",
        recommended_actions: ["Nghỉ ngơi và theo dõi nhiệt độ"],
        clinician_handoff_summary: "Bệnh nhân có triệu chứng đau đầu nhẹ kéo dài 2 ngày.",
        questions_for_doctor: ["Nguyên nhân đau đầu do đâu?"],
        when_to_seek_immediate_care: ["Đau đầu dữ dội đột ngột"],
      });

      render(<SymptomCheckerPage />);

      // Step 1: Select symptom chip
      const symptomChip = screen.getByTestId("symptom-chip-Đau đầu");
      fireEvent.click(symptomChip);

      fireEvent.click(screen.getByText(/Tiếp theo: Mức độ & Thời gian/i));

      // Step 2: Duration & Severity
      expect(screen.getByTestId("symptom-step-2")).toBeInTheDocument();
      fireEvent.click(screen.getByText(/Tiếp theo: Tiền sử & An toàn/i));

      // Step 3: Safety & Context
      expect(screen.getByTestId("symptom-step-3")).toBeInTheDocument();
      fireEvent.click(screen.getByText(/Xem kết quả đánh giá/i));

      // Step 4: Urgency Result Card & Clinician Handoff
      await waitFor(() => {
        expect(screen.getByTestId("symptom-check-result")).toBeInTheDocument();
      });

      expect(screen.getByText("Khám thông thường / Hẹn khám chuyên khoa")).toBeInTheDocument();
      expect(screen.getByText("Tóm tắt bàn giao cho Bác sĩ")).toBeInTheDocument();
      expect(screen.getByText("Bệnh nhân có triệu chứng đau đầu nhẹ kéo dài 2 ngày.")).toBeInTheDocument();
      expect(screen.getByText("Nguyên nhân đau đầu do đâu?")).toBeInTheDocument();
    });
  });
});
