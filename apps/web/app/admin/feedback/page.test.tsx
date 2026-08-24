import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mockListClinicalFeedback = vi.fn();
const mockUpdateFeedbackTriage = vi.fn();
const mockExportFeedbackToBenchmark = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

vi.mock("@/lib/clinical-feedback", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/clinical-feedback")>();
  return {
    ...actual,
    listClinicalFeedback: () => mockListClinicalFeedback(),
    updateFeedbackTriage: (id: string | number, updates: any) =>
      mockUpdateFeedbackTriage(id, updates),
    exportFeedbackToBenchmark: (id: string | number) =>
      mockExportFeedbackToBenchmark(id),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

import ClinicalFeedbackTriagePage from "@/app/admin/feedback/page";
import type { ClinicalFeedbackItem } from "@/lib/clinical-feedback";

const TEST_CLINICAL_FEEDBACK: ClinicalFeedbackItem[] = [
  {
    id: "FB-801",
    query_id: "Q-10492",
    user_query: "Bệnh nhân suy thận eGFR 28 mL/min có dùng được Metformin 1000mg x 2 lần/ngày không?",
    clara_response: "Metformin có thể sử dụng ở liều 1000mg x 2 lần/ngày, cần theo dõi định kỳ chức năng thận mỗi 3 tháng.",
    rating: 1,
    category: "dosage_ddi",
    severity: "critical",
    triage_status: "new",
    submitter_role: "specialist",
    submitter_specialty: "Nội thận - Lọc máu",
    comment: "Chống chỉ định tuyệt đối Metformin khi eGFR < 30 mL/min/1.73m2 do nguy cơ nhiễm toan acid lactic đe dọa tính mạng theo Dược thư QGVN 2022 và KDIGO 2023.",
    proposed_correction: "Ngừng ngay Metformin. Chuyển sang ức chế DPP-4 (Linagliptin) hoặc Insulin hiệu chỉnh liều theo chức năng thận.",
    cited_guidelines: [
      "Dược thư Quốc gia Việt Nam 2022 - Chuyên luận Metformin",
      "KDIGO 2023 Clinical Practice Guideline for Diabetes Management in CKD",
    ],
    fides_verdict: "BLOCKED_CRITICAL",
    created_at: "2026-08-20T08:15:00Z",
    assigned_to: "Hội đồng An toàn Dược lâm sàng",
    added_to_eval_benchmark: false,
  },
  {
    id: "FB-802",
    query_id: "Q-10488",
    user_query: "Phụ nữ mang thai 3 tháng đầu dùng Isotretinoin bôi ngoài trị mụn được không?",
    clara_response: "Isotretinoin dạng bôi ngoài da có tỷ lệ hấp thu toàn thân thấp, có thể cân nhắc nếu các thuốc bôi khác không hiệu quả.",
    rating: 1,
    category: "contraindication",
    severity: "critical",
    triage_status: "in_triage",
    submitter_role: "pharmacist",
    submitter_specialty: "Dược lâm sàng",
    comment: "Isotretinoin dù dạng bôi hay uống đều xếp Phân loại X thai kỳ (nguy cơ gây quái thai dị tật tim mặt sọ não). Phải cảnh báo đỏ chống chỉ định tuyệt đối.",
    proposed_correction: "Tuyệt đối không sử dụng cho phụ nữ có thai hoặc nghi ngờ có thai. Thay thế an toàn bằng Azelaic acid hoặc Erythromycin bôi.",
    cited_guidelines: [
      "Thông tư 01/2020/TT-BYT Hướng dẫn sử dụng thuốc cho phụ nữ có thai",
      "FDA Pregnancy Category X Isotretinoin Warnings",
    ],
    fides_verdict: "CONTESTED",
    created_at: "2026-08-21T09:30:00Z",
    assigned_to: "Ban An toàn Dược lâm sàng",
    added_to_eval_benchmark: false,
  },
  {
    id: "FB-803",
    query_id: "Q-10475",
    user_query: "Trẻ em 6 tuổi bị sốt xuất huyết Dengue ngày 3 dùng Aspirin để hạ sốt được không?",
    clara_response: "Có thể dùng Aspirin liều thấp 10mg/kg nếu Paracetamol không hạ được sốt cao.",
    rating: 2,
    category: "hallucination",
    severity: "high",
    triage_status: "in_triage",
    submitter_role: "doctor",
    submitter_specialty: "Nhi khoa",
    comment: "Ảo giác nguy hiểm! Chống chỉ định tuyệt đối Aspirin và NSAIDs trong sốt xuất huyết Dengue do nguy cơ xuất huyết tiêu hóa ồ ạt và hội chứng Reye ở trẻ em.",
    proposed_correction: "Chỉ dùng Paracetamol đơn chất 10-15mg/kg/lần (tối đa 60mg/kg/ngày), giãn cách ít nhất 4-6 giờ. Tuyệt đối không dùng Aspirin/Ibuprofen.",
    cited_guidelines: [
      "Bộ Y Tế QĐ 2760/QĐ-BYT Hướng dẫn chẩn đoán, điều trị Sốt xuất huyết Dengue",
      "WHO Dengue Guidelines for Diagnosis, Treatment, Prevention and Control",
    ],
    fides_verdict: "CONTESTED",
    created_at: "2026-08-22T14:10:00Z",
    assigned_to: "Ban An toàn Lâm sàng Nhi",
    added_to_eval_benchmark: true,
  },
  {
    id: "FB-804",
    query_id: "Q-10461",
    user_query: "Phác đồ điều trị tăng huyết áp ở bệnh nhân ĐTĐ theo Hội Tim mạch VN 2024?",
    clara_response: "Khởi đầu bằng ức chế men chuyển (ACEi) hoặc ức chế thụ thể (ARB). Đích huyết áp khuyến cáo chung là < 140/90 mmHg.",
    rating: 3,
    category: "citation_mismatch",
    severity: "medium",
    triage_status: "new",
    submitter_role: "doctor",
    submitter_specialty: "Tim mạch can thiệp",
    comment: "Khuyến cáo VNHA/VSH 2024 và ADA 2024 đã thống nhất siết đích huyết áp cho bệnh nhân ĐTĐ xuống < 130/80 mmHg. Mốc 140/90 mmHg là tài liệu cũ chưa cập nhật.",
    proposed_correction: "Cập nhật đích HA < 130/80 mmHg (nếu dung nạp) theo VNHA 2024 và ADA 2024 Standards of Care.",
    cited_guidelines: [
      "Khuyến cáo chẩn đoán và điều trị Tăng huyết áp - Hội Tim mạch học VN (VNHA 2024)",
      "ADA Standards of Care in Diabetes 2024 - Section 10",
    ],
    fides_verdict: "PARTIALLY_VERIFIED",
    created_at: "2026-08-23T11:05:00Z",
    assigned_to: "Tổ Y văn & Guideline",
    added_to_eval_benchmark: false,
  },
  {
    id: "FB-805",
    query_id: "Q-10450",
    user_query: "Thời điểm uống Levothyroxine tốt nhất trong ngày là khi nào?",
    clara_response: "Nên uống Levothyroxine vào buổi sáng lúc đói, trước bữa ăn sáng 30-60 phút với một cốc nước đầy.",
    rating: 4,
    category: "clinical_nuance",
    severity: "low",
    triage_status: "resolved",
    submitter_role: "doctor",
    submitter_specialty: "Nội tiết",
    comment: "Hướng dẫn thời điểm đúng, nhưng cần nhấn mạnh thêm việc cách xa các chế phẩm bổ sung Canxi, Sắt, Sữa đậu nành ít nhất 4 giờ để tránh cản trở hấp thu.",
    proposed_correction: "Bổ sung lưu ý cách xa Canxi/Sắt/Sữa ít nhất 4 giờ.",
    cited_guidelines: [
      "American Thyroid Association (ATA) Guidelines on Hypothyroidism 2023",
    ],
    fides_verdict: "VERIFIED",
    created_at: "2026-08-23T16:45:00Z",
    resolved_at: "2026-08-24T09:00:00Z",
    resolution_note: "Đã cập nhật prompt rule về tương tác thức ăn/vi chất của Levothyroxine vào knowledge connector.",
    root_cause: "Thiếu rule bổ trợ tương tác vi chất trong hệ thống prompt lâm sàng.",
    assigned_to: "Tổ Y văn & Guideline",
    added_to_eval_benchmark: true,
  },
  {
    id: "FB-806",
    query_id: "Q-10432",
    user_query: "Tương tác giữa Clopidogrel và Omeprazole có làm giảm hiệu quả chống kết tập tiểu cầu không?",
    clara_response: "Omeprazole ức chế enzyme CYP2C19, làm giảm chuyển hóa Clopidogrel thành chất có hoạt tính sinh học, giảm tác dụng chống đông. Khuyến cáo dùng Pantoprazole để thay thế.",
    rating: 5,
    category: "positive_accurate",
    severity: "low",
    triage_status: "resolved",
    submitter_role: "specialist",
    submitter_specialty: "Dược lý lâm sàng",
    comment: "Tư vấn rất chính xác, giải thích rõ cơ chế dược động học qua CYP2C19 và đề xuất thuốc thay thế chuẩn xác theo FDA và Dược thư QG.",
    cited_guidelines: [
      "FDA Drug Safety Communication: Clopidogrel and Omeprazole interaction",
      "Dược thư Quốc gia Việt Nam 2022",
    ],
    fides_verdict: "VERIFIED",
    created_at: "2026-08-24T07:20:00Z",
    resolved_at: "2026-08-24T08:30:00Z",
    resolution_note: "Xác nhận mẫu Q&A chuẩn xác cao, lưu vào golden sample corpus.",
    assigned_to: "Hội đồng Thẩm định Y khoa",
    added_to_eval_benchmark: true,
  },
];

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockListClinicalFeedback.mockResolvedValue([...TEST_CLINICAL_FEEDBACK]);
  mockUpdateFeedbackTriage.mockImplementation(async (id, updates) => {
    const item = TEST_CLINICAL_FEEDBACK.find((i) => String(i.id) === String(id));
    return {
      ...(item ?? TEST_CLINICAL_FEEDBACK[0]),
      ...updates,
      id,
      updated_at: new Date().toISOString(),
    };
  });
  mockExportFeedbackToBenchmark.mockResolvedValue({
    success: true,
    benchmark_id: "BENCH-GOLDEN-FB-801",
  });
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("ClinicalFeedbackTriagePage (Spec v5 Section 6.71)", () => {
  describe("1. Shell and Role-based Access Control", () => {
    it("renders forbidden notice when user role is not admin (Property P7)", async () => {
      roleState.role = "doctor";
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText(/Access Forbidden/i)).toBeInTheDocument();
      });

      expect(mockListClinicalFeedback).not.toHaveBeenCalled();
    });

    it("renders AdminShell, header, and command strip for admin role", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(mockListClinicalFeedback).toHaveBeenCalled();
      });

      expect(
        screen.getByRole("heading", { level: 1, name: /Clinical Feedback Triage Queue/i }),
      ).toBeInTheDocument();
      expect(screen.getByText("TRIAGE-Q")).toBeInTheDocument();
    });
  });

  describe("2. Summary KPIs and Accuracy Rating Breakdown", () => {
    it("renders all 4 summary KPI cards with accurate calculations", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText(/Total Feedback/i)).toBeInTheDocument();
      });

      expect(screen.getByText("Total Feedback")).toBeInTheDocument();
      expect(screen.getByText("Avg Accuracy Rating")).toBeInTheDocument();
      expect(screen.getByText(/Critical Unresolved/i)).toBeInTheDocument();
      expect(screen.getByText("Resolution Rate")).toBeInTheDocument();
    });

    it("renders the Accuracy Rating Breakdown and Clinical Risk Category panels", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("Accuracy Rating Breakdown")).toBeInTheDocument();
      });

      expect(screen.getByText("Accuracy Rating Breakdown")).toBeInTheDocument();
      expect(screen.getByText("Clinical Risk Category Breakdown")).toBeInTheDocument();

      // Check rating rows
      expect(screen.getByText(/5 stars \(Accurate\)/i)).toBeInTheDocument();
      expect(screen.getByText(/1 star \(Critical Hazard\)/i)).toBeInTheDocument();

      // Check category rows
      expect(screen.getAllByText(/Dosage & Drug Interaction/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Contraindication & Red Flag/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Clinical Hallucination/i).length).toBeGreaterThan(0);
    });
  });

  describe("3. Dense Stream Table and Multi-dimensional Filtering", () => {
    it("renders the dense feedback table with all seed items and headers", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      expect(screen.getByText("#FB-801")).toBeInTheDocument();
      expect(screen.getByText("#FB-802")).toBeInTheDocument();
      expect(screen.getByText("#FB-803")).toBeInTheDocument();
      expect(screen.getByText("#FB-804")).toBeInTheDocument();
      expect(screen.getByText("#FB-805")).toBeInTheDocument();
      expect(screen.getByText("#FB-806")).toBeInTheDocument();

      // Check table column headers
      expect(screen.getByText("ID & Date")).toBeInTheDocument();
      expect(screen.getByText("Rating")).toBeInTheDocument();
      expect(screen.getByText("Submitter")).toBeInTheDocument();
      expect(screen.getByText("Category & Risk")).toBeInTheDocument();
      expect(screen.getByText("Status")).toBeInTheDocument();
    });

    it("filters stream items by Triage Status (e.g. Pending, In Triage, Resolved)", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Filter by Resolved
      const resolvedFilterBtn = screen.getByRole("button", { name: /Resolved/i });
      fireEvent.click(resolvedFilterBtn);

      await waitFor(() => {
        expect(screen.queryByText("#FB-801")).not.toBeInTheDocument(); // was "new"
        expect(screen.getByText("#FB-805")).toBeInTheDocument(); // resolved
        expect(screen.getByText("#FB-806")).toBeInTheDocument(); // resolved
      });
    });

    it("filters stream items by search query", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/Search query, notes, ID.../i);
      fireEvent.change(searchInput, { target: { value: "Metformin" } });

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
        expect(screen.queryByText("#FB-802")).not.toBeInTheDocument();
        expect(screen.queryByText("#FB-803")).not.toBeInTheDocument();
      });
    });

    it("filters stream items by Severity dropdown", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const severitySelect = screen.getByLabelText(/Severity:/i);
      fireEvent.change(severitySelect, { target: { value: "low" } });

      await waitFor(() => {
        expect(screen.queryByText("#FB-801")).not.toBeInTheDocument(); // critical
        expect(screen.getByText("#FB-805")).toBeInTheDocument(); // low
        expect(screen.getByText("#FB-806")).toBeInTheDocument(); // low
      });
    });
  });

  describe("4. Resolution Inspector Drawer and Triage Workflow", () => {
    it("opens the Inspector Drawer with clinical context when clicking Inspect", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByText(/1. Feedback & Submitter Metadata/i)).toBeInTheDocument();
        expect(screen.getByText(/2. Clinical Query & CLARA Output/i)).toBeInTheDocument();
        expect(screen.getByText(/3. Clinician Observation & Proposal/i)).toBeInTheDocument();
        expect(screen.getByText(/4. Triage Resolution & Workflow/i)).toBeInTheDocument();
      });

      // Verify clinical query and response are displayed
      expect(screen.getAllByText(/Bệnh nhân suy thận eGFR 28 mL\/min/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Chống chỉ định tuyệt đối Metformin khi eGFR < 30/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Ngừng ngay Metformin/i)).toBeInTheDocument();
    });

    it("allows updating triage status, resolution note, and saves changes", async () => {
      const { container } = render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Open inspector for FB-801
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(container.querySelector("#triage-status-select")).toBeInTheDocument();
      });

      // Change status to in_triage
      const statusSelect = container.querySelector("#triage-status-select") as HTMLSelectElement;
      fireEvent.change(statusSelect, { target: { value: "in_triage" } });

      // Add resolution note
      const notesTextarea = screen.getByLabelText(/Resolution Notes & Corrective Actions/i);
      fireEvent.change(notesTextarea, {
        target: { value: "Escalated to Renal safety committee for prompt constraint update." },
      });

      // Save changes
      const saveBtn = screen.getByRole("button", { name: /Save Changes/i });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(mockUpdateFeedbackTriage).toHaveBeenCalledWith("FB-801", expect.objectContaining({
          triage_status: "in_triage",
          resolution_note: "Escalated to Renal safety committee for prompt constraint update.",
        }));
      });

      // Toast appears
      expect(screen.getByText(/Successfully updated feedback #FB-801 triage status/i)).toBeInTheDocument();
    });

    it("exports clinical feedback item to Golden RAG Benchmark", async () => {
      render(<ClinicalFeedbackTriagePage />);

      await waitFor(() => {
        expect(screen.getByText("#FB-801")).toBeInTheDocument();
      });

      // Open inspector for FB-801
      const inspectBtns = screen.getAllByRole("button", { name: /Inspect/i });
      fireEvent.click(inspectBtns[0]);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /Export RAG Golden/i })).toBeInTheDocument();
      });

      const exportBtn = screen.getByRole("button", { name: /Export RAG Golden/i });
      fireEvent.click(exportBtn);

      await waitFor(() => {
        expect(mockExportFeedbackToBenchmark).toHaveBeenCalledWith("FB-801");
      });

      // Toast appears
      expect(screen.getByText(/Exported feedback #FB-801 to RAG Golden Benchmark/i)).toBeInTheDocument();
    });
  });
});
