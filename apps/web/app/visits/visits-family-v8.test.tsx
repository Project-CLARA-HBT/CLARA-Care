import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import VisitsPage from "./page";
import VisitDetailPage from "./[visitId]/page";
import FamilyPage from "../family/page";
import * as visitFamilyModule from "@/lib/visit-family";

const mockPush = vi.fn();
const mockReplace = vi.fn();
const mockPrefetch = vi.fn();
const mockBack = vi.fn();
const mockRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    prefetch: mockPrefetch,
    back: mockBack,
    refresh: mockRefresh,
  }),
  useParams: () => ({ visitId: "visit-123" }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/visits",
}));

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

// ============================================================================
// Mock Data Fixtures according to Spec v8 Section 7.13 & 7.14
// ============================================================================

const mockVisitsList: visitFamilyModule.Visit[] = [
  {
    id: "visit-upcoming-v8",
    title: "Tái khám Tim mạch can thiệp & Tăng huyết áp",
    goal: "Đánh giá khả năng dung nạp thuốc hạ áp và kiểm tra huyết áp định kỳ",
    visit_type: "Khám chuyên khoa",
    scheduled_at: new Date(Date.now() + 86400000 * 2).toISOString(), // 2 days in future
    status: "scheduled",
    doctor_name: "BSCKII. Nguyễn Văn An",
    specialty: "Tim mạch can thiệp",
    facility_name: "Bệnh viện Đại học Y Dược TP.HCM",
    location: "Phòng khám 204 - Khu B",
    prep_status: "ready",
    questions: [
      "Huyết áp sáng đo 135/85 mmHg có cần tăng liều không?",
      "Có thể duy trì đi bộ nhanh 30 phút mỗi ngày được không?",
    ],
    questions_count: 2,
  },
  {
    id: "visit-past-v8",
    title: "Khám Nội tiết & Kiểm soát Đái tháo đường",
    goal: "Đánh giá chỉ số HbA1c và điều chỉnh phác đồ Metformin",
    visit_type: "Khám định kỳ",
    scheduled_at: new Date(Date.now() - 86400000 * 45).toISOString(), // 45 days ago
    status: "completed",
    doctor_name: "TS.BS. Lê Thị Mai",
    specialty: "Nội tiết",
    facility_name: "Bệnh viện Chợ Rẫy",
    location: "Phòng 12, Tầng 3",
    clinician_notes: "Chỉ số HbA1c đạt mục tiêu (6.7%). Tiếp tục duy trì chế độ ăn và vận động.",
    soap_note: {
      subjective: "Bệnh nhân không ghi nhận cơn hạ đường huyết, ăn uống điều độ.",
      objective: "HbA1c: 6.7%, Glucose đói: 5.8 mmol/L.",
      assessment: "Đái tháo đường type 2 kiểm soát tốt.",
      plan: "Duy trì Metformin 500mg và hẹn tái khám sau 3 tháng.",
      clinician_name: "TS.BS. Lê Thị Mai",
      signed_at: new Date(Date.now() - 86400000 * 45).toISOString(),
    },
    prescriptions: [
      {
        id: "rx-metformin",
        name: "Metformin 500mg",
        dosage: "1 viên x 2 lần/ngày",
        instruction: "Uống ngay sau bữa ăn sáng và tối",
        reconciliation_status: "continued",
      },
    ],
    lab_orders: [
      {
        id: "lab-hba1c",
        title: "Xét nghiệm HbA1c & Sinh hóa máu",
        status: "completed",
        result_summary: "6.7% - Đạt mục tiêu",
      },
    ],
  },
];

const mockVisitDetailV8: visitFamilyModule.Visit = {
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
      "Bệnh nhân 58 tuổi, tái khám tăng huyết áp. Khai có cảm giác hồi hộp nhẹ khi leo cầu thang, không đau ngực dữ dội, không khó thở về đêm.",
    objective:
      "Sinh hiệu: HA: 130/80 mmHg, Mạch: 74 lần/phút, SpO2: 98%, BMI: 23.4. ECG: Nhịp xoang đều, không thiếu máu cơ tim cấp.",
    assessment:
      "1. Tăng huyết áp vô căn độ 1 (ICD-10: I10) - Kiểm soát tốt.\n2. Rối loạn lipid máu hỗn hợp (ICD-10: E78.2) - Đang điều trị Statin.",
    plan:
      "1. Tiếp tục duy trì Amlodipine 5mg: 1 viên uống sáng sau ăn.\n2. Bổ sung Atorvastatin 10mg: 1 viên uống tối trước khi ngủ.\n3. Hẹn tái khám sau 4 tuần kèm xét nghiệm Lipid máu và Men gan.",
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
      content_digest: "sha256-verified-doc",
      metadata: {},
      text_content: "Amlodipine 5mg, Atorvastatin 10mg",
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
    "Huyết áp buổi sáng ổn định thì có thể giảm liều Amlodipine được không?",
  ],
};

const mockFamilyGrantsV8: visitFamilyModule.FamilyGrant[] = [
  {
    id: "grant-active-1",
    supporter_label: "Nguyễn Thị Bình (Con gái)",
    object_type: "medications",
    object_id: "obj-meds-1",
    allowed_actions: ["view", "add_observation"],
    purpose: "care_coordination",
    expires_at: new Date(Date.now() + 25 * 24 * 60 * 60 * 1000).toISOString(),
    status: "active",
  },
  {
    id: "grant-expired-2",
    supporter_label: "BS. Lê Văn Cường",
    object_type: "visit",
    object_id: "obj-visit-2",
    allowed_actions: ["view"],
    purpose: "visit_support",
    expires_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    status: "expired",
  },
  {
    id: "grant-revoked-3",
    supporter_label: "Trần Minh Đức",
    object_type: "episode",
    object_id: "obj-ep-3",
    allowed_actions: ["view"],
    purpose: "care_coordination",
    expires_at: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
    status: "revoked",
    revoked_at: new Date().toISOString(),
  },
];

const mockFamilyRelationshipsV8: visitFamilyModule.FamilyGrant[] = [
  {
    id: "rel-received-1",
    supporter_label: "Trần Văn Em (Bố)",
    object_type: "care_task",
    object_id: "obj-task-4",
    allowed_actions: ["view", "complete_task"],
    purpose: "care_coordination",
    expires_at: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString(),
    status: "active",
  },
];

const mockFamilyNotificationsV8: visitFamilyModule.FamilyNotification[] = [
  {
    id: "notif-task-1",
    kind: "delegated_care_task",
    profile_id: "prof-parent-1",
    task_id: "task-med-reminder-99",
    purpose: "care_coordination",
    expires_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
    action: "complete_task",
    message: "Nhắc bố đo huyết áp và uống thuốc Amlodipine sau bữa ăn sáng",
  },
];

const mockFamilyLogsV8: visitFamilyModule.FamilyAccessLog[] = [
  {
    id: "log-1",
    actor_label: "Nguyễn Thị Bình (Con gái)",
    actor_code: "supporter",
    object_type: "medications",
    object_id: "obj-meds-1",
    action: "view",
    action_code: "view",
    outcome: "success",
    outcome_code: "allowed",
    purpose: "care_coordination",
    created_at: new Date(Date.now() - 1800 * 1000).toISOString(),
  },
  {
    id: "log-2",
    actor_label: "BS. Lê Văn Cường",
    actor_code: "supporter",
    object_type: "visit",
    object_id: "obj-visit-2",
    action: "view",
    action_code: "view",
    outcome: "denied",
    outcome_code: "denied",
    purpose: "visit_support",
    created_at: new Date(Date.now() - 7200 * 1000).toISOString(),
  },
];

describe("Spec v8 Section 7.13 — /visits: Upcoming Visit Card & Past Visit Timeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(visitFamilyModule, "listVisits").mockResolvedValue(mockVisitsList);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue([]);
    vi.spyOn(visitFamilyModule, "grantVisitScribeConsent").mockResolvedValue(undefined);
    vi.spyOn(visitFamilyModule, "revokeVisitScribeConsent").mockResolvedValue(undefined);
  });

  afterEach(cleanup);

  it("renders '+ Chuẩn bị lần khám mới' CTA button pointing to /visits/new", async () => {
    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("prepare-new-visit-cta")).toBeInTheDocument();
    });

    const cta = screen.getByTestId("prepare-new-visit-cta");
    expect(cta).toHaveAttribute("href", "/visits/new");
    expect(cta).toHaveTextContent(/Chuẩn bị lần khám mới/i);
  });

  it("renders upcoming visit card with physician, scheduled datetime, question pack readiness, and Scribe consent", async () => {
    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("upcoming-visit-section")).toBeInTheDocument();
    });

    // Physician & Facility information
    expect(screen.getByText("Tái khám Tim mạch can thiệp & Tăng huyết áp")).toBeInTheDocument();
    expect(screen.getByText(/BSCKII. Nguyễn Văn An/)).toBeInTheDocument();
    expect(screen.getAllByText(/Tim mạch can thiệp/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Bệnh viện Đại học Y Dược TP.HCM/)).toBeInTheDocument();
    expect(screen.getByText(/Phòng khám 204 - Khu B/)).toBeInTheDocument();

    // Goal and Question pack readiness
    expect(screen.getByText(/Đánh giá khả năng dung nạp thuốc hạ áp/)).toBeInTheDocument();
    expect(screen.getByText(/2 câu hỏi đã sẵn sàng/i)).toBeInTheDocument();
    expect(screen.getByText(/Huyết áp sáng đo 135\/85 mmHg có cần tăng liều không\?/)).toBeInTheDocument();

    // Scribe recording consent switch
    const scribeConsentBtn = screen.getByRole("button", { name: /Đồng ý ghi âm buổi này/i });
    expect(scribeConsentBtn).toBeInTheDocument();

    fireEvent.click(scribeConsentBtn);

    await waitFor(() => {
      expect(visitFamilyModule.grantVisitScribeConsent).toHaveBeenCalledWith("visit-upcoming-v8");
    });
  });

  it("renders chronological past visit timeline rows with SOAP summary and attachments", async () => {
    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("past-visits-timeline-stream")).toBeInTheDocument();
    });

    // Past visit title & doctor
    expect(screen.getByText("Khám Nội tiết & Kiểm soát Đái tháo đường")).toBeInTheDocument();
    expect(screen.getByText(/TS.BS. Lê Thị Mai/)).toBeInTheDocument();
    expect(screen.getByText(/Bệnh viện Chợ Rẫy/)).toBeInTheDocument();

    // SOAP notes / clinician notes
    expect(screen.getByText(/Chỉ số HbA1c đạt mục tiêu \(6.7%\)/)).toBeInTheDocument();

    // Prescriptions
    expect(screen.getByText("Metformin 500mg")).toBeInTheDocument();
    expect(screen.getByText("1 viên x 2 lần/ngày")).toBeInTheDocument();

    // Lab orders & attachments
    expect(screen.getByText("Xét nghiệm HbA1c & Sinh hóa máu")).toBeInTheDocument();
    expect(screen.getByText("(6.7% - Đạt mục tiêu)")).toBeInTheDocument();
  });

  it("selects a past visit and displays its clinical dossier in the side inspector panel", async () => {
    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByTestId("past-visit-item-visit-past-v8")).toBeInTheDocument();
    });

    // Click past visit timeline item
    fireEvent.click(screen.getByTestId("past-visit-item-visit-past-v8"));

    await waitFor(() => {
      expect(screen.getByTestId("visit-inspector-panel")).toBeInTheDocument();
    });

    const inspector = screen.getByTestId("visit-inspector-panel");
    expect(inspector).toHaveTextContent("Khám Nội tiết & Kiểm soát Đái tháo đường");
    expect(inspector).toHaveTextContent("TS.BS. Lê Thị Mai");
    expect(inspector).toHaveTextContent("Metformin 500mg");
  });

  it("renders empty state with guidance on visit preparation when no visits exist", async () => {
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

  it("renders safe user-facing error state and retry button when visit list fails to load", async () => {
    vi.spyOn(visitFamilyModule, "listVisits").mockRejectedValue(new Error("500 Internal Server Error"));

    render(<VisitsPage />);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(screen.getByText(/Chưa thể tải lịch khám/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Thử lại/i })).toBeInTheDocument();
  });
});

describe("Spec v8 Section 7.13 — /visits/[visitId]: Visit Detail Reader Dossier", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(visitFamilyModule, "getVisit").mockResolvedValue(mockVisitDetailV8);
    vi.spyOn(visitFamilyModule, "listVisitDocuments").mockResolvedValue(mockVisitDetailV8.documents!);
    vi.spyOn(visitFamilyModule, "grantVisitScribeConsent").mockResolvedValue(undefined);
    vi.spyOn(visitFamilyModule, "createVisitDocument").mockResolvedValue({
      id: "doc-new-v8",
      title: "Phiếu siêu âm Doppler tim mới",
      document_kind: "lab_report",
      media_type: "text/plain",
      status: "verified",
      content_digest: "sha256-new-doc",
      metadata: {},
      text_content: "EF 62%, không hẹp hở van tim nặng",
      provenance: {},
      withdrawn_at: null,
      deleted_at: null,
    });
    vi.spyOn(visitFamilyModule, "deleteVisitDocument").mockResolvedValue({
      id: "doc-1",
      title: "Toa thuốc điện tử #RX-202608-019",
      document_kind: "prescription",
      media_type: "application/pdf",
      status: "verified",
      content_digest: "sha256-verified-doc",
      metadata: {},
      text_content: null,
      provenance: {},
      withdrawn_at: null,
      deleted_at: new Date().toISOString(),
    });
  });

  afterEach(cleanup);

  it("renders verified visit header with attending physician, scheduled time, and Scribe toggle", async () => {
    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("visit-detail-content")).toBeInTheDocument();
    });

    expect(screen.getByTestId("visit-timeline-entry")).toBeInTheDocument();
    expect(screen.getByText("Tái khám Tim mạch & Tăng huyết áp định kỳ")).toBeInTheDocument();
    expect(screen.getAllByText(/BSCKII. Nguyễn Văn An/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Bệnh viện Đại học Y Dược TP.HCM/)).toBeInTheDocument();
    expect(screen.getByText(/Hồ sơ khám đã xác thực/i)).toBeInTheDocument();

    const scribeToggle = screen.getByTestId("scribe-consent-toggle");
    fireEvent.click(scribeToggle);

    await waitFor(() => {
      expect(visitFamilyModule.grantVisitScribeConsent).toHaveBeenCalledWith("visit-123");
    });
  });

  it("renders structured SOAP notes (S, O, A, P) with ICD-10 coding and clinician signature", async () => {
    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("doctor-soap-notes-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("soap-subjective")).toHaveTextContent(/Bệnh nhân 58 tuổi, tái khám tăng huyết áp/);
    expect(screen.getByTestId("soap-objective")).toHaveTextContent(/HA: 130\/80 mmHg, Mạch: 74 lần\/phút/);
    expect(screen.getByTestId("soap-assessment")).toHaveTextContent(/Tăng huyết áp vô căn độ 1/);
    expect(screen.getByTestId("soap-assessment")).toHaveTextContent(/I10: Tăng huyết áp vô căn/);
    expect(screen.getByTestId("soap-plan")).toHaveTextContent(/Amlodipine 5mg: 1 viên uống sáng/);
    expect(screen.getByText(/BSCKII. Nguyễn Văn An \(Mã CCHN: 014829\/HCM-CCHN\)/)).toBeInTheDocument();
  });

  it("renders prescribed medications with DrugBank verification and reconciliation status badges", async () => {
    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("medication-reconciliation-section")).toBeInTheDocument();
    });

    expect(screen.getByText(/Đối soát an toàn thuốc DrugBank/i)).toBeInTheDocument();
    expect(screen.getByText("Amlodipine Besylate 5mg")).toBeInTheDocument();
    expect(screen.getByText("Atorvastatin 10mg")).toBeInTheDocument();
    expect(screen.getByText("Đang tiếp tục")).toBeInTheDocument();
    expect(screen.getByText("Mới kê toa")).toBeInTheDocument();
  });

  it("supports document addition via modal and attachment deletion", async () => {
    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("attachments-lab-orders-section")).toBeInTheDocument();
    });

    // Add document
    fireEvent.click(screen.getByTestId("add-attachment-btn"));
    await waitFor(() => {
      expect(screen.getByLabelText(/Tên để bạn dễ nhận ra/i)).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Tên để bạn dễ nhận ra/i), {
      target: { value: "Phiếu siêu âm Doppler tim mới" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Lưu mục đã chọn/i }));

    await waitFor(() => {
      expect(visitFamilyModule.createVisitDocument).toHaveBeenCalledWith("visit-123", expect.objectContaining({
        title: "Phiếu siêu âm Doppler tim mới",
      }));
    });

    // Delete document
    const removeButtons = screen.getAllByRole("button", { name: /Gỡ bỏ/i });
    expect(removeButtons.length).toBeGreaterThan(0);
    fireEvent.click(removeButtons[0]);

    await waitFor(() => {
      expect(visitFamilyModule.deleteVisitDocument).toHaveBeenCalledWith("visit-123", "doc-new-v8", "owner_requested");
    });
  });

  it("allows toggling follow-up task completion state", async () => {
    render(<VisitDetailPage />);

    await waitFor(() => {
      expect(screen.getByTestId("follow-up-tasks-section")).toBeInTheDocument();
    });

    const taskRow = screen.getByTestId("task-row-task-1");
    const checkbox = taskRow.querySelector("input[type='checkbox']") as HTMLInputElement;
    expect(checkbox.checked).toBe(false);

    fireEvent.click(taskRow);
    await waitFor(() => {
      expect(checkbox.checked).toBe(true);
    });
  });
});

describe("Spec v8 Section 7.14 — /family: Scope Disclosure, Sharing Grants, Care Tasks & Audit Log", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(visitFamilyModule, "listFamilyGrants").mockResolvedValue(mockFamilyGrantsV8);
    vi.spyOn(visitFamilyModule, "listFamilyRelationships").mockResolvedValue(mockFamilyRelationshipsV8);
    vi.spyOn(visitFamilyModule, "listFamilyNotifications").mockResolvedValue(mockFamilyNotificationsV8);
    vi.spyOn(visitFamilyModule, "listFamilyAccessLog").mockResolvedValue(mockFamilyLogsV8);
    vi.spyOn(visitFamilyModule, "revokeFamilyGrant").mockResolvedValue(undefined);
    vi.spyOn(visitFamilyModule, "renewFamilyGrant").mockResolvedValue({
      id: "grant-active-1",
      token: "tok-renew-v8-abc-123",
      expires_at: new Date(Date.now() + 30 * 86400000).toISOString(),
    });
    vi.spyOn(visitFamilyModule, "acknowledgeFamilyNotification").mockResolvedValue(undefined);
  });

  afterEach(cleanup);

  it("renders Explicit Category Scope Disclosure Banner with 4 security pillars", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("scope-disclosure-banner")).toBeInTheDocument();
    });

    const banner = screen.getByTestId("scope-disclosure-banner");
    expect(banner).toHaveTextContent("Bảo vệ quyền riêng tư & Minh bạch phạm vi chia sẻ");
    expect(banner).toHaveTextContent("Phân quyền tường minh");
    expect(banner).toHaveTextContent("Bảo mật suy luận AI");
    expect(banner).toHaveTextContent("Thu hồi tức thì 1 chạm");
    expect(banner).toHaveTextContent("Nhật ký kiểm toán");
  });

  it("renders active sharing grants list rows with 1-click revoke dialog and renew flow", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("grants-list")).toBeInTheDocument();
    });

    // Grantee & scope details
    expect(screen.getByText("Nguyễn Thị Bình (Con gái)")).toBeInTheDocument();
    expect(screen.getByText("Đơn thuốc & Tủ thuốc")).toBeInTheDocument();
    expect(screen.getAllByText(/Phối hợp chăm sóc/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("xem").length).toBeGreaterThan(0);
    expect(screen.getByText("thêm ghi nhận")).toBeInTheDocument();

    // 1-Click Revoke confirmation dialog flow
    const revokeBtn = screen.getByTestId("revoke-grant-btn-grant-active-1");
    fireEvent.click(revokeBtn);

    expect(screen.getByTestId("revoke-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText("Thu hồi quyền chia sẻ?")).toBeInTheDocument();
    expect(screen.getByText(/Bạn có chắc chắn muốn thu hồi quyền của Nguyễn Thị Bình/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("confirm-revoke-btn"));

    await waitFor(() => {
      expect(visitFamilyModule.revokeFamilyGrant).toHaveBeenCalledWith("grant-active-1");
    });

    // Renew grant action
    const renewBtn = screen.getByTestId("renew-grant-btn-grant-active-1");
    fireEvent.click(renewBtn);

    await waitFor(() => {
      expect(visitFamilyModule.renewFamilyGrant).toHaveBeenCalledWith("grant-active-1", expect.any(String));
      expect(screen.getByTestId("grant-created-notice")).toBeInTheDocument();
      expect(screen.getByText("tok-renew-v8-abc-123")).toBeInTheDocument();
    });
  });

  it("renders delegated care tasks tab with 1-click acknowledge task completion", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("family-sharing-hub")).toBeInTheDocument();
    });

    // Switch to received tab
    const receivedTab = screen.getByRole("tab", { name: /Được chia sẻ với tôi/i });
    fireEvent.click(receivedTab);

    expect(screen.getByTestId("delegated-tasks-section")).toBeInTheDocument();
    expect(screen.getByText("Nhắc bố đo huyết áp và uống thuốc Amlodipine sau bữa ăn sáng")).toBeInTheDocument();

    const ackBtn = screen.getByTestId("acknowledge-task-btn-notif-task-1");
    fireEvent.click(ackBtn);

    await waitFor(() => {
      expect(visitFamilyModule.acknowledgeFamilyNotification).toHaveBeenCalledWith(
        "notif-task-1",
        "task-med-reminder-99",
        "care_coordination",
      );
    });
  });

  it("renders append-only audit log ledger with timestamp, actor, category, action, and outcome badge", async () => {
    render(<FamilyPage />);

    await waitFor(() => {
      expect(screen.getByTestId("family-sharing-hub")).toBeInTheDocument();
    });

    // Switch to log tab
    const logTab = screen.getByRole("tab", { name: /Nhật ký truy cập/i });
    fireEvent.click(logTab);

    expect(screen.getByTestId("access-history-section")).toBeInTheDocument();
    expect(screen.getByTestId("access-logs-table")).toBeInTheDocument();
    expect(screen.getAllByText("Người hỗ trợ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Đơn thuốc & Tủ thuốc").length).toBeGreaterThan(0);
    expect(screen.getByText("được cho phép")).toBeInTheDocument();
    expect(screen.getByText("bị từ chối")).toBeInTheDocument();
  });
});
