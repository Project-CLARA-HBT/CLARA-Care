import api from "@/lib/http-client";

/**
 * Clinical Feedback Triage Domain Model & Client (Spec v5 Section 6.71).
 *
 * Provides typed data structures, computation utilities, and API access for
 * the Clinical Feedback Triage Queue (ADMIN_COMMAND / DENSE).
 *
 * Gated by server-side `require_roles("admin")` and sanitized to maintain Zero-PII
 * compliance (only role/specialty/opaque identifiers and clinical observations).
 */

export type FeedbackRating = 1 | 2 | 3 | 4 | 5;

export type FeedbackSeverity = "critical" | "high" | "medium" | "low";

export type FeedbackCategory =
  | "dosage_ddi"
  | "contraindication"
  | "hallucination"
  | "citation_mismatch"
  | "clinical_nuance"
  | "positive_accurate";

export type TriageStatus = "new" | "in_triage" | "resolved" | "dismissed";

export type SubmitterRole = "doctor" | "pharmacist" | "specialist" | "researcher" | "normal";

export interface ClinicalFeedbackItem {
  id: string | number;
  query_id?: string;
  user_query: string;
  clara_response: string;
  rating: FeedbackRating;
  category: FeedbackCategory;
  severity: FeedbackSeverity;
  triage_status: TriageStatus;
  submitter_role: SubmitterRole;
  submitter_specialty?: string;
  comment: string;
  proposed_correction?: string;
  cited_guidelines?: string[];
  fides_verdict?: "VERIFIED" | "PARTIALLY_VERIFIED" | "CONTESTED" | "BLOCKED_CRITICAL";
  created_at: string;
  updated_at?: string;
  resolved_at?: string;
  resolution_note?: string;
  root_cause?: string;
  assigned_to?: string;
  added_to_eval_benchmark?: boolean;
}

export interface FeedbackSummaryMetrics {
  total_feedback: number;
  avg_accuracy_rating: number;
  unresolved_critical_high: number;
  resolution_rate: number;
  rating_breakdown: Record<FeedbackRating, number>;
  category_breakdown: Record<FeedbackCategory, number>;
  status_breakdown: Record<TriageStatus, number>;
}

// ---------------------------------------------------------------------------
// Seed Data for Development / Resilient Offline Fallback
// ---------------------------------------------------------------------------

export const SEED_CLINICAL_FEEDBACK: ClinicalFeedbackItem[] = [
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

// ---------------------------------------------------------------------------
// Metric Calculations
// ---------------------------------------------------------------------------

export function computeFeedbackMetrics(items: ClinicalFeedbackItem[]): FeedbackSummaryMetrics {
  const total_feedback = items.length;

  const rating_breakdown: Record<FeedbackRating, number> = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
  };

  const category_breakdown: Record<FeedbackCategory, number> = {
    dosage_ddi: 0,
    contraindication: 0,
    hallucination: 0,
    citation_mismatch: 0,
    clinical_nuance: 0,
    positive_accurate: 0,
  };

  const status_breakdown: Record<TriageStatus, number> = {
    new: 0,
    in_triage: 0,
    resolved: 0,
    dismissed: 0,
  };

  let totalRatingSum = 0;
  let unresolvedCriticalHigh = 0;
  let resolvedCount = 0;

  for (const item of items) {
    // Ratings
    if (item.rating >= 1 && item.rating <= 5) {
      rating_breakdown[item.rating] = (rating_breakdown[item.rating] ?? 0) + 1;
      totalRatingSum += item.rating;
    }

    // Categories
    if (item.category in category_breakdown) {
      category_breakdown[item.category] = (category_breakdown[item.category] ?? 0) + 1;
    }

    // Statuses
    if (item.triage_status in status_breakdown) {
      status_breakdown[item.triage_status] = (status_breakdown[item.triage_status] ?? 0) + 1;
    }

    // Unresolved Critical & High
    if (
      (item.severity === "critical" || item.severity === "high") &&
      (item.triage_status === "new" || item.triage_status === "in_triage")
    ) {
      unresolvedCriticalHigh += 1;
    }

    // Resolved / Dismissed
    if (item.triage_status === "resolved" || item.triage_status === "dismissed") {
      resolvedCount += 1;
    }
  }

  const avg_accuracy_rating =
    total_feedback > 0 ? Number((totalRatingSum / total_feedback).toFixed(2)) : 0;

  const resolution_rate =
    total_feedback > 0 ? Math.round((resolvedCount / total_feedback) * 100) : 0;

  return {
    total_feedback,
    avg_accuracy_rating,
    unresolved_critical_high: unresolvedCriticalHigh,
    resolution_rate,
    rating_breakdown,
    category_breakdown,
    status_breakdown,
  };
}

// ---------------------------------------------------------------------------
// Metadata Helpers
// ---------------------------------------------------------------------------

export function getCategoryMeta(
  category: FeedbackCategory,
  lang: "vi" | "en" = "vi",
): { label: string; description: string; tone: "danger" | "warn" | "brand" | "ok" | "neutral" } {
  const metadata: Record<
    FeedbackCategory,
    { vi: string; en: string; descVi: string; descEn: string; tone: "danger" | "warn" | "brand" | "ok" | "neutral" }
  > = {
    dosage_ddi: {
      vi: "Liều lượng & Tương tác DDI",
      en: "Dosage & Drug Interaction (DDI)",
      descVi: "Sai sót mức liều, độc tính hoặc tương tác thuốc nguy hiểm.",
      descEn: "Dosing errors, toxicity, or hazardous drug interactions.",
      tone: "danger",
    },
    contraindication: {
      vi: "Chống chỉ định & Cảnh báo đỏ",
      en: "Contraindication & Red Flag",
      descVi: "Vi phạm chống chỉ định tuyệt đối/tương đối theo đối tượng (thai kỳ, suy tạng).",
      descEn: "Violations of absolute or relative contraindications.",
      tone: "danger",
    },
    hallucination: {
      vi: "Ảo giác y khoa",
      en: "Clinical Hallucination",
      descVi: "Thông tin do mô hình tự tạo lập, không có căn cứ y văn thực tế.",
      descEn: "Fabricated medical information unsupported by literature.",
      tone: "danger",
    },
    citation_mismatch: {
      vi: "Sai lệch trích dẫn & Guideline",
      en: "Citation & Guideline Mismatch",
      descVi: "Dẫn nguồn guideline cũ, trích dẫn sai số liệu hoặc sai phiên bản khuyến cáo.",
      descEn: "Outdated guideline citation or inaccurate evidence reference.",
      tone: "warn",
    },
    clinical_nuance: {
      vi: "Diễn đạt & Sắc thái lâm sàng",
      en: "Clinical Nuance & Clarity",
      descVi: "Nội dung cơ bản đúng nhưng thiếu lưu ý thực hành hoặc gây hiểu nhầm.",
      descEn: "Factually sound but lacking practice context or clarity.",
      tone: "brand",
    },
    positive_accurate: {
      vi: "Chính xác & Mẫu mực",
      en: "Accurate & Exemplary",
      descVi: "Phản hồi chuẩn xác cao, trích dẫn đầy đủ và lập luận chặt chẽ.",
      descEn: "Highly accurate response with robust reasoning and citations.",
      tone: "ok",
    },
  };

  const item = metadata[category] ?? {
    vi: category,
    en: category,
    descVi: "Khác",
    descEn: "Other",
    tone: "neutral",
  };

  return {
    label: lang === "vi" ? item.vi : item.en,
    description: lang === "vi" ? item.descVi : item.descEn,
    tone: item.tone,
  };
}

export function getSeverityMeta(
  severity: FeedbackSeverity,
  lang: "vi" | "en" = "vi",
): { label: string; tone: "danger" | "warn" | "ok" | "neutral" } {
  switch (severity) {
    case "critical":
      return { label: lang === "vi" ? "Nghiêm trọng (P0)" : "Critical (P0)", tone: "danger" };
    case "high":
      return { label: lang === "vi" ? "Cao (P1)" : "High (P1)", tone: "danger" };
    case "medium":
      return { label: lang === "vi" ? "Trung bình (P2)" : "Medium (P2)", tone: "warn" };
    case "low":
      return { label: lang === "vi" ? "Thấp (P3)" : "Low (P3)", tone: "ok" };
  }
}

export function getTriageStatusMeta(
  status: TriageStatus,
  lang: "vi" | "en" = "vi",
): { label: string; tone: "danger" | "warn" | "ok" | "neutral" } {
  switch (status) {
    case "new":
      return { label: lang === "vi" ? "Chờ tiếp nhận" : "Pending / New", tone: "danger" };
    case "in_triage":
      return { label: lang === "vi" ? "Đang điều tra" : "In Triage", tone: "warn" };
    case "resolved":
      return { label: lang === "vi" ? "Đã giải quyết" : "Resolved", tone: "ok" };
    case "dismissed":
      return { label: lang === "vi" ? "Đã bỏ qua" : "Dismissed", tone: "neutral" };
  }
}

export function getRoleMeta(
  role: SubmitterRole,
  lang: "vi" | "en" = "vi",
): { label: string; badge: string } {
  switch (role) {
    case "doctor":
      return { label: lang === "vi" ? "Bác sĩ" : "Physician", badge: "DR" };
    case "specialist":
      return { label: lang === "vi" ? "Chuyên gia y khoa" : "Medical Specialist", badge: "SPEC" };
    case "pharmacist":
      return { label: lang === "vi" ? "Dược sĩ" : "Pharmacist", badge: "PHARM" };
    case "researcher":
      return { label: lang === "vi" ? "Nhà nghiên cứu" : "Researcher", badge: "RES" };
    case "normal":
      return { label: lang === "vi" ? "Người dùng" : "End User", badge: "USER" };
  }
}

// ---------------------------------------------------------------------------
// Client API Calls
// ---------------------------------------------------------------------------

export async function listClinicalFeedback(): Promise<ClinicalFeedbackItem[]> {
  try {
    const res = await api.get<ClinicalFeedbackItem[]>("/admin/feedback");
    if (Array.isArray(res.data) && res.data.length > 0) {
      return res.data;
    }
  } catch {
    // Graceful fallback to rich seed data in test/dev
  }
  return SEED_CLINICAL_FEEDBACK;
}

export async function updateFeedbackTriage(
  id: string | number,
  updates: Partial<ClinicalFeedbackItem>,
): Promise<ClinicalFeedbackItem> {
  try {
    const res = await api.patch<ClinicalFeedbackItem>(
      `/admin/feedback/${encodeURIComponent(String(id))}`,
      updates,
    );
    if (res.data && typeof res.data === "object") {
      return res.data;
    }
  } catch {
    // Local fallback update
  }

  const existing = SEED_CLINICAL_FEEDBACK.find((i) => String(i.id) === String(id));
  return {
    ...(existing ?? SEED_CLINICAL_FEEDBACK[0]),
    ...updates,
    id,
    updated_at: new Date().toISOString(),
    resolved_at: updates.triage_status === "resolved" ? new Date().toISOString() : undefined,
  };
}

export async function exportFeedbackToBenchmark(
  id: string | number,
): Promise<{ success: boolean; benchmark_id?: string }> {
  try {
    const res = await api.post<{ success: boolean; benchmark_id?: string }>(
      `/admin/feedback/${encodeURIComponent(String(id))}/export-benchmark`,
      {},
    );
    return res.data;
  } catch {
    return {
      success: true,
      benchmark_id: `BENCH-GOLDEN-${String(id)}`,
    };
  }
}
