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

    // ListDetailLayout adopts PageFrame with workspace="personal"
    expect(document.querySelector('[data-workspace="personal"]')).toBeInTheDocument();

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
    expect(screen.getByTestId("visit-prep-wizard")).toHaveAttribute("data-workspace", "personal");
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

const mockVisitDetail: visitFamilyModule.Visit = {
  id: "visit-123",
  title: "Tái khám Tim mạch & Tăng huyết áp định kỳ",
  goal: "Đánh giá hiệu quả thuốc hạ áp, theo dõi triệu chứng đau ngực và kiểm tra kết quả xét nghiệm sinh hóa máu.",
  visit_type: "Khám chuyên khoa Tim mạch",
  scheduled_at: "2026-08-24T09:00:00.000Z",
  status: "completed",
  doctor_name: "BSCKII. Nguyễn Văn An",
  specialty: "Tim mạch can thiệp",
  facility_name: "Bệnh viện Đại học Y Dược TP.HCM",
  location: "Phòng khám 204 - Khu B",
  prep_status: "completed",
  clinician_notes:
    "Bệnh nhân hợp tác tốt, huyết áp kiểm soát ổn định (130/80 mmHg). Hướng dẫn giảm muối và duy trì tập thể dục 30 phút mỗi ngày.",
  soap_note: {
    subjective:
      "Bệnh nhân 58 tuổi, tái khám tăng huyết áp. Khai có cảm giác hồi hộp thoáng qua khi leo cầu thang 3 tầng tuần trước, không đau ngực dữ dội, không khó thở về đêm. Tuân thủ uống Amlodipine đều đặn mỗi sáng.",
    objective:
      "Sinh hiệu: HA: 130/80 mmHg, Mạch: 74 lần/phút, SpO2: 98%, BMI: 23.4. Khám tim: T1, T2 đều rõ, không âm thổi bệnh lý. Khám phổi: Âm phế bào êm dịu 2 phế trường, không rale. Điện tâm đồ (ECG): Nhịp xoang đều, trục trung gian, không thiếu máu cục bộ cấp.",
    assessment:
      "1. Tăng huyết áp vô căn độ 1 (ICD-10: I10) - Kiểm soát tốt.\n2. Rối loạn lipid máu hỗn hợp (ICD-10: E78.2) - Đang điều trị Statin.\n3. Cơn hồi hộp nhẹ khi gắng sức - Nghi do thể lực chưa thích nghi, loại trừ hội chứng vành cấp.",
    plan:
      "1. Tiếp tục duy trì Amlodipine 5mg: 1 viên uống sáng sau ăn.\n2. Bổ sung Atorvastatin 10mg: 1 viên uống tối trước khi ngủ.\n3. Kê toa 30 ngày và hẹn tái khám định kỳ sau 4 tuần.\n4. Làm xét nghiệm Lipid máu, Men gan (AST/ALT), Creatinine trước lần khám sau 2 ngày.\n5. Dặn dò bệnh nhân đến cấp cứu ngay nếu đau thắt ngực lan ra cánh tay trái hoặc khó thở.",
    icd10_codes: [
      { code: "I10", label: "Tăng huyết áp vô căn (nguyên phát)" },
      { code: "E78.2", label: "Rối loạn lipid máu hỗn hợp" },
    ],
    clinician_name: "BSCKII. Nguyễn Văn An (Mã CCHN: 014829/HCM-CCHN)",
    signed_at: "2026-08-24T09:30:00.000Z",
  },
  prescriptions: [
    {
      id: "rx-1",
      name: "Amlodipine Besylate 5mg",
      dosage: "1 viên/ngày (Sáng)",
      instruction: "Uống sau bữa ăn sáng lúc 7:00",
      reconciliation_status: "continued",
    },
    {
      id: "rx-2",
      name: "Atorvastatin 10mg",
      dosage: "1 viên/ngày (Tối)",
      instruction: "Uống trước khi đi ngủ",
      reconciliation_status: "new",
    },
  ],
  lab_orders: [
    {
      id: "lab-1",
      title: "Bộ mỡ máu toàn phần (Lipid Panel)",
      status: "completed",
      result_summary: "Cholesterol: 4.8 mmol/L",
    },
  ],
  documents: [
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
  ],
  follow_up_tasks: [
    {
      id: "task-1",
      title: "Đo và ghi nhận huyết áp tại nhà 2 lần/ngày (Sáng 7h, Tối 19h)",
      due_date: new Date(Date.now() + 86400000 * 7).toISOString(),
      completed: false,
      priority: "high",
    },
  ],
  questions: [
    "Huyết áp buổi sáng ổn định thì có thể ngưng thuốc được không?",
  ],
};

describe("VisitDetailPage — Visit Detail Reader Archetype (Spec v5 Section 5 & 6.21)", () => {
  it("renders verified visit timeline entry, doctor SOAP notes, prescribed medications with reconciliation, attachments, and follow-up tasks", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("visit-detail-content")).toBeInTheDocument();
    });

    // 1. Shell and Archetype
    expect(screen.getByTestId("visit-detail-reader")).toHaveAttribute("data-shell-mode", "READ");
    expect(screen.getByTestId("visit-detail-reader")).toHaveAttribute("data-layout-archetype", "Visit Detail Reader");
    expect(screen.getByTestId("visit-detail-reader")).toHaveAttribute("data-workspace", "personal");

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

  it("fails closed and renders error alert on 500 server error without fake data", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockRejectedValue(new Error("500 Internal Server Error: Database connection failed"));

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("visit-detail-content")).not.toBeInTheDocument();
    expect(screen.queryByTestId("doctor-soap-notes-section")).not.toBeInTheDocument();
    expect(screen.queryByText(/Hồ sơ khám đã xác thực/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/BSCKII. Nguyễn Văn An/i)).not.toBeInTheDocument();
  });

  it("fails closed on request timeout", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockRejectedValue(new Error("Yêu cầu xử lý quá thời gian chờ. Vui lòng thử lại."));

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText(/quá thời gian chờ/i)).toBeInTheDocument();
    expect(screen.queryByTestId("visit-detail-content")).not.toBeInTheDocument();
  });

  it("does not render verified badges when document is unverified", async () => {
    const unverifiedVisit: visitFamilyModule.Visit = {
      ...mockVisitDetail,
      status: "scheduled",
      documents: [
        {
          id: "doc-draft-1",
          title: "Bản nháp kết quả khám",
          document_kind: "draft",
          media_type: "text/plain",
          status: "pending",
          content_digest: "sha256-draft",
          metadata: {},
          text_content: null,
          provenance: {},
          withdrawn_at: null,
          deleted_at: null,
        },
      ],
    };

    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(unverifiedVisit);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(unverifiedVisit.documents!);

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("visit-detail-content")).toBeInTheDocument();
    });

    expect(screen.queryByText(/Hồ sơ khám đã xác thực/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Verified$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Đã xác thực$/i)).not.toBeInTheDocument();
  });

  it("toggles follow-up task completion state interactively", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

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

  it("commits document creation on 2xx and fails closed on 500 error", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

    const createDocSpy = vi.spyOn(visitFamilyModule, "createVisitDocument").mockResolvedValue({
      id: "doc-created-200",
      title: "Phiếu điện tim gắng sức mới",
      document_kind: "lab_report",
      media_type: "text/plain",
      status: "verified",
      content_digest: "sha256-new",
      metadata: {},
      text_content: "Nhịp xoang bình thường",
      provenance: {},
      withdrawn_at: null,
      deleted_at: null,
    });

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("add-attachment-btn")).toBeInTheDocument();
    });

    // Open Add Document modal
    fireEvent.click(screen.getByTestId("add-attachment-btn"));

    await waitFor(() => {
      expect(screen.getByLabelText(/Tên để bạn dễ nhận ra/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Tên để bạn dễ nhận ra/i), {
      target: { value: "Phiếu điện tim gắng sức mới" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Lưu mục đã chọn/i }));

    await waitFor(() => {
      expect(createDocSpy).toHaveBeenCalledWith("visit-123", expect.objectContaining({
        title: "Phiếu điện tim gắng sức mới",
      }));
      expect(screen.getByText("Phiếu điện tim gắng sức mới")).toBeInTheDocument();
    });
  });

  it("does not mutate document list when createVisitDocument returns 500 error", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

    vi.spyOn(visitFamilyModule, "createVisitDocument").mockRejectedValue(
      new Error("500 Internal Server Error: Upload failed"),
    );

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("add-attachment-btn")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("add-attachment-btn"));

    await waitFor(() => {
      expect(screen.getByLabelText(/Tên để bạn dễ nhận ra/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Tên để bạn dễ nhận ra/i), {
      target: { value: "Tài liệu bị lỗi 500" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Lưu mục đã chọn/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    // Verify document was NOT added into the list (no false-success fallback)
    expect(screen.queryByText("Tài liệu bị lỗi 500")).not.toBeInTheDocument();
  });

  it("does not mutate document list when deleteVisitDocument returns 500 error", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

    vi.spyOn(visitFamilyModule, "deleteVisitDocument").mockRejectedValue(
      new Error("500 Internal Server Error: Deletion forbidden"),
    );

    const VisitDetailPageModule = await import("./[visitId]/page");
    const VisitDetailPage = VisitDetailPageModule.default;

    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("document-item-doc-1")).toBeInTheDocument();
    });

    const removeBtn = screen.getByRole("button", { name: /Gỡ bỏ/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    // Document remains in list because deletion failed closed
    expect(screen.getByTestId("document-item-doc-1")).toBeInTheDocument();
  });

  it("opens share modal and allows copying visit share URL", async () => {
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetail);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetail.documents!);

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
