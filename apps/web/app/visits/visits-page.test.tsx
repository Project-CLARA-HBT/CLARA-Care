import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import VisitsPage from "./page";
import * as visitFamilyModule from "@/lib/visit-family";

const mockPush = vi.fn();
const mockReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useParams: () => ({ visitId: "visit-123" }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

const mockVisits: visitFamilyModule.Visit[] = [
  {
    id: "visit-upcoming-1",
    title: "Tái khám Tim mạch định kỳ",
    goal: "Kiểm tra huyết áp và đánh giá tác dụng phụ của thuốc",
    visit_type: "Khám chuyên khoa",
    scheduled_at: new Date(Date.now() + 86400000 * 3).toISOString(), // 3 days in future
    status: "scheduled",
    doctor_name: "BSCKII Nguyễn Văn An",
    specialty: "Tim mạch can thiệp",
    facility_name: "Bệnh viện Đại học Y Dược",
    location: "Phòng 102, Khu A",
    prep_status: "ready",
    questions: [
      "Huyết áp buổi sáng có cần đo trước khi uống thuốc không?",
      "Cơn đau ngực nhẹ khi leo cầu thang có đáng lo ngại?",
    ],
    questions_count: 2,
  },
  {
    id: "visit-past-1",
    title: "Khám Nội tiết & Đường huyết",
    goal: "Đánh giá chỉ số HbA1c và điều chỉnh liều",
    visit_type: "Khám định kỳ",
    scheduled_at: new Date(Date.now() - 86400000 * 30).toISOString(), // 30 days ago
    status: "completed",
    doctor_name: "TS.BS Lê Thị Mai",
    specialty: "Nội tiết",
    facility_name: "Bệnh viện Chợ Rẫy",
    clinician_notes: "Chỉ số HbA1c kiểm soát tốt (6.8%). Tiếp tục duy trì chế độ ăn giảm tinh bột.",
    prescriptions: [
      {
        id: "rx-1",
        name: "Metformin 500mg",
        dosage: "1 viên x 2 lần/ngày",
        instruction: "Uống sau ăn sáng và tối",
      },
    ],
    lab_orders: [
      {
        id: "lab-1",
        title: "Xét nghiệm Glucose & HbA1c",
        result_summary: "6.8%",
      },
    ],
  },
];

const mockDocuments: visitFamilyModule.VisitDocument[] = [
  {
    id: "doc-1",
    title: "Phiếu kết quả xét nghiệm sinh hóa máu",
    document_kind: "lab_report",
    media_type: "application/pdf",
    status: "verified",
    content_digest: "sha256-abc",
    metadata: {},
    text_content: "Glucose: 6.8 mmol/L",
    provenance: {},
    withdrawn_at: null,
    deleted_at: null,
  },
];

afterEach(cleanup);

beforeEach(() => {
  mockPush.mockReset();
  mockReplace.mockReset();
  vi.restoreAllMocks();
});

describe("VisitsPage — Visit Timeline Archetype (Spec v5 Section 6.20)", () => {
  it("renders header and 'Chuẩn bị lần khám mới' CTA button linking to /visits/new", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue(mockVisits);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockDocuments);

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("prepare-new-visit-cta")).toBeInTheDocument();
    });

    const ctaButton = screen.getByTestId("prepare-new-visit-cta");
    expect(ctaButton).toHaveAttribute("href", "/visits/new");
    expect(ctaButton).toHaveTextContent(/Chuẩn bị lần khám mới/i);
  });

  it("renders upcoming visit HeroObject with doctor, specialty, time, prep status, and questions ready", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue(mockVisits);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockDocuments);

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("upcoming-visit-section")).toBeInTheDocument();
    });

    expect(screen.getByText("Tái khám Tim mạch định kỳ")).toBeInTheDocument();
    expect(screen.getByText(/BSCKII Nguyễn Văn An/)).toBeInTheDocument();
    expect(screen.getByText(/Tim mạch can thiệp/)).toBeInTheDocument();
    expect(screen.getByText(/Bệnh viện Đại học Y Dược/)).toBeInTheDocument();
    expect(screen.getByText(/Kiểm tra huyết áp và đánh giá tác dụng phụ/)).toBeInTheDocument();
    expect(screen.getByText(/2 câu hỏi đã sẵn sàng/i)).toBeInTheDocument();
  });

  it("renders chronological past visit timeline stream with clinician notes, prescriptions, and lab order attachments", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue(mockVisits);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockDocuments);

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("past-visits-timeline-stream")).toBeInTheDocument();
    });

    // Clinician notes
    expect(screen.getByText("Khám Nội tiết & Đường huyết")).toBeInTheDocument();
    expect(screen.getByText(/Chỉ số HbA1c kiểm soát tốt/)).toBeInTheDocument();

    // Prescriptions
    expect(screen.getByText("Metformin 500mg")).toBeInTheDocument();
    expect(screen.getByText("1 viên x 2 lần/ngày")).toBeInTheDocument();
    expect(screen.getByText("Uống sau ăn sáng và tối")).toBeInTheDocument();

    // Lab orders & document attachments
    expect(screen.getByText("Xét nghiệm Glucose & HbA1c")).toBeInTheDocument();
    expect(screen.getByText("(6.8%)")).toBeInTheDocument();
    expect(screen.getByText("Phiếu kết quả xét nghiệm sinh hóa máu")).toBeInTheDocument();
  });

  it("renders empty state with guidance on how visit preparation works when no visits exist", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue([]);

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("visits-empty-state")).toBeInTheDocument();
    });

    expect(screen.getByText(/Cách thức chuẩn bị buổi khám/i)).toBeInTheDocument();
    expect(screen.getByText(/1\. Lên lịch và xác định mục tiêu trọng tâm/i)).toBeInTheDocument();
    expect(screen.getByText(/2\. Tự chọn hồ sơ, toa thuốc/i)).toBeInTheDocument();
    expect(screen.getByText(/3\. Tạo Visit Pack bảo mật/i)).toBeInTheDocument();
    expect(screen.getByText(/4\. Cập nhật kết luận, chỉ định xét nghiệm/i)).toBeInTheDocument();
  });

  it("handles fetch failure gracefully and renders retry affordance", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockRejectedValue(new Error("Network connection lost"));

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText(/Network connection lost/i)).toBeInTheDocument();
    const retryBtn = screen.getByRole("button", { name: /Thử lại/i });
    expect(retryBtn).toBeInTheDocument();
  });

  it("toggles Scribe recording consent on upcoming visit", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue(mockVisits);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockDocuments);
    const grantSpy = vi.spyOn(visitFamilyModule, "grantVisitScribeConsent").mockResolvedValue(undefined);

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("upcoming-visit-section")).toBeInTheDocument();
    });

    const consentBtn = screen.getByRole("button", { name: /Đồng ý ghi âm buổi này/i });
    expect(consentBtn).toBeInTheDocument();

    fireEvent.click(consentBtn);

    await waitFor(() => {
      expect(grantSpy).toHaveBeenCalledWith("visit-upcoming-1");
    });
  });
});

describe("NewVisitPage — Visit Preparation Wizard Archetype (Spec v5 Section 6.21)", () => {
  it("steps through all 4 guided prep stages: Reason -> Symptoms -> Medications -> Summary/Questions and saves", async () => {
    const createSpy = vi.spyOn(visitFamilyModule, "createVisit").mockResolvedValue({
      id: "visit-created-99",
      title: "Tái khám Tim mạch & Đánh giá huyết áp",
      goal: "Kiểm tra triệu chứng đau ngực",
      visit_type: "Tim mạch",
      scheduled_at: new Date().toISOString(),
      status: "scheduled",
    });
    const addConcernSpy = vi.spyOn(visitFamilyModule, "addVisitConcern").mockResolvedValue(undefined);

    const NewVisitPageModule = await import("./new/page");
    const NewVisitPage = NewVisitPageModule.default;

    render(<NewVisitPage />);

    // Step 1: Reason for visit
    expect(screen.getByTestId("visit-prep-wizard")).toHaveAttribute("data-shell-mode", "FOCUS");
    expect(screen.getByTestId("visit-prep-wizard")).toHaveAttribute("data-layout-archetype", "Visit Prep Wizard");
    expect(screen.getByTestId("wizard-step-reason")).toBeInTheDocument();

    const titleInput = screen.getByLabelText(/Tiêu đề buổi khám/i);
    fireEvent.change(titleInput, { target: { value: "Tái khám Tim mạch & Đánh giá huyết áp" } });

    const goalInput = screen.getByLabelText(/Mục tiêu trọng tâm/i);
    fireEvent.change(goalInput, { target: { value: "Kiểm tra triệu chứng đau ngực" } });

    const specialtyInput = screen.getByLabelText(/Chuyên khoa khám/i);
    fireEvent.change(specialtyInput, { target: { value: "Tim mạch" } });

    // Advance to Step 2
    fireEvent.click(screen.getByRole("button", { name: /Tiếp tục/i }));

    // Step 2: Symptoms & Timeline
    await waitFor(() => {
      expect(screen.getByTestId("wizard-step-symptoms")).toBeInTheDocument();
    });
    expect(screen.getByText(/Triệu chứng & Diễn tiến theo thời gian/i)).toBeInTheDocument();

    // Select symptom chip
    const symptomChip = screen.getByTestId("symptom-chip-Đau tức ngực");
    fireEvent.click(symptomChip);

    const timelineInput = screen.getByLabelText(/Thời gian & Diễn tiến/i);
    fireEvent.change(timelineInput, { target: { value: "Bắt đầu 3 ngày trước khi gắng sức" } });

    // Advance to Step 3
    fireEvent.click(screen.getByRole("button", { name: /Tiếp tục/i }));

    // Step 3: Current Medications & Allergies
    await waitFor(() => {
      expect(screen.getByTestId("wizard-step-medications")).toBeInTheDocument();
    });
    expect(screen.getByText(/Thuốc đang sử dụng & Tiền sử dị ứng/i)).toBeInTheDocument();
    expect(screen.getByText("Amlodipine 5mg")).toBeInTheDocument();

    // Select allergy chip
    const allergyChip = screen.getByTestId("allergy-chip-Penicillin / Beta-lactam");
    fireEvent.click(allergyChip);

    // Advance to Step 4
    fireEvent.click(screen.getByRole("button", { name: /Tiếp tục/i }));

    // Step 4: Generated Visit Summary & Questions pack
    await waitFor(() => {
      expect(screen.getByTestId("wizard-step-summary")).toBeInTheDocument();
    });
    expect(screen.getByTestId("handoff-pack-preview")).toBeInTheDocument();
    expect(screen.getByText(/Bản xem trước Visit Handoff Pack/i)).toBeInTheDocument();
    expect(screen.getByTestId("questions-pack-section")).toBeInTheDocument();

    // Copy summary action
    const copyBtn = screen.getByRole("button", { name: /Sao chép tóm tắt/i });
    expect(copyBtn).toBeInTheDocument();

    // Save and Complete
    const saveBtn = screen.getByRole("button", { name: /Lưu và hoàn tất chuẩn bị/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Tái khám Tim mạch & Đánh giá huyết áp",
        }),
      );
      expect(mockReplace).toHaveBeenCalledWith("/visits/visit-created-99");
    });
  });

  it("validates required title on step 1 before advancing", async () => {
    const NewVisitPageModule = await import("./new/page");
    const NewVisitPage = NewVisitPageModule.default;

    render(<NewVisitPage />);

    expect(screen.getByTestId("wizard-step-reason")).toBeInTheDocument();

    // Click next without title
    fireEvent.click(screen.getByRole("button", { name: /Tiếp tục/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/Vui lòng nhập ít nhất 2 ký tự/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryByTestId("wizard-step-symptoms")).not.toBeInTheDocument();
  });
});

describe("VisitDetailPage — Visit Detail Reader Archetype (Spec v5 Section 5 & 6.21)", () => {
  it("renders verified visit timeline entry, doctor SOAP notes, prescribed medications with reconciliation, attachments, and follow-up tasks", async () => {
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue([
      {
        id: "doc-1",
        title: "Toa thuốc điện tử #RX-202608-019",
        document_kind: "prescription",
        media_type: "application/pdf",
        status: "verified",
        content_digest: "sha256-abc",
        metadata: {},
        text_content: "Amlodipine 5mg",
        provenance: {},
        withdrawn_at: null,
        deleted_at: null,
      },
    ]);

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("visit-detail-content")).toBeInTheDocument();
    });

    // 1. Shell and Archetype
    expect(screen.getByTestId("visit-detail-reader")).toHaveAttribute("data-shell-mode", "READ");
    expect(screen.getByTestId("visit-detail-reader")).toHaveAttribute("data-layout-archetype", "Visit Detail Reader");

    // Back link to /visits
    const backLink = screen.getByTestId("back-to-visits-link");
    expect(backLink).toHaveAttribute("href", "/visits");

    // 2. Verified Timeline Entry Header
    expect(screen.getByTestId("visit-timeline-entry")).toBeInTheDocument();
    expect(screen.getByText("Tái khám Tim mạch & Tăng huyết áp định kỳ")).toBeInTheDocument();
    expect(screen.getAllByText(/BSCKII. Nguyễn Văn An/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Bệnh viện Đại học Y Dược TP.HCM/)).toBeInTheDocument();
    expect(screen.getByText(/Hồ sơ khám đã xác thực/i)).toBeInTheDocument();

    // 3. Doctor SOAP notes
    expect(screen.getByTestId("doctor-soap-notes-section")).toBeInTheDocument();
    expect(screen.getByTestId("soap-subjective")).toBeInTheDocument();
    expect(screen.getByTestId("soap-objective")).toBeInTheDocument();
    expect(screen.getByTestId("soap-assessment")).toBeInTheDocument();
    expect(screen.getByTestId("soap-plan")).toBeInTheDocument();
    expect(screen.getByText(/HA: 130\/80 mmHg/)).toBeInTheDocument();
    expect(screen.getByText(/I10: Tăng huyết áp vô căn/)).toBeInTheDocument();

    // 4. Prescribed medications with reconciliation status
    expect(screen.getByTestId("medication-reconciliation-section")).toBeInTheDocument();
    expect(screen.getByText("Amlodipine Besylate 5mg")).toBeInTheDocument();
    expect(screen.getByText("Atorvastatin 10mg")).toBeInTheDocument();
    expect(screen.getByText("Đang tiếp tục")).toBeInTheDocument();
    expect(screen.getByText("Mới kê toa")).toBeInTheDocument();
    expect(screen.getByText(/Đối soát an toàn thuốc DrugBank/i)).toBeInTheDocument();

    // 5. Attachments & Lab orders
    expect(screen.getByTestId("attachments-lab-orders-section")).toBeInTheDocument();
    expect(screen.getByText("Bộ mỡ máu toàn phần (Lipid Panel)")).toBeInTheDocument();
    expect(screen.getByText(/Cholesterol: 4.8 mmol\/L/)).toBeInTheDocument();
    expect(screen.getByText(/Toa thuốc điện tử/)).toBeInTheDocument();

    // 6. Follow-up tasks & action items
    expect(screen.getByTestId("follow-up-tasks-section")).toBeInTheDocument();
  });

  it("toggles follow-up task completion state interactively", async () => {
    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("follow-up-tasks-section")).toBeInTheDocument();
    });

    const taskRow = screen.getByTestId("task-row-task-1");
    expect(taskRow).toBeInTheDocument();

    const checkbox = taskRow.querySelector("input[type='checkbox']") as HTMLInputElement;
    expect(checkbox.checked).toBe(false);

    // Toggle completion
    fireEvent.click(taskRow);

    await waitFor(() => {
      expect(checkbox.checked).toBe(true);
    });
  });

  it("opens share modal and allows copying visit share URL", async () => {
    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("share-visit-action")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("share-visit-action"));

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: /Chia sẻ Visit Pack/i })).toBeInTheDocument();
    });

    const copyShareBtn = screen.getByRole("button", { name: /Sao chép liên kết/i });
    expect(copyShareBtn).toBeInTheDocument();
  });
});
