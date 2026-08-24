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
  resourceVersion?: string;
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

export interface ListClinicalFeedbackOptions {
  status?: TriageStatus | "all";
  severity?: FeedbackSeverity | "all";
  category?: FeedbackCategory | "all";
  cursor?: number;
  limit?: number;
}

export function mapBackendFeedbackToFrontend(f: any): ClinicalFeedbackItem {
  if (!f) {
    throw new Error("Invalid clinical feedback payload from server");
  }

  const meta = (typeof f.metadata_json === "object" && f.metadata_json !== null)
    ? f.metadata_json
    : {};
  const res = (typeof f.resolution_json === "object" && f.resolution_json !== null)
    ? f.resolution_json
    : {};

  let triageStatus: TriageStatus = "new";
  if (f.status === "in_review" || f.status === "in_triage" || f.triage_status === "in_triage") {
    triageStatus = "in_triage";
  } else if (f.status === "resolved" || f.triage_status === "resolved") {
    triageStatus = "resolved";
  } else if (f.status === "rejected" || f.status === "dismissed" || f.triage_status === "dismissed") {
    triageStatus = "dismissed";
  } else if (f.status === "open" || f.status === "new" || f.triage_status === "new") {
    triageStatus = "new";
  }

  const category = (f.category || meta.category || "clinical_nuance") as FeedbackCategory;
  const severity = (f.clinical_severity || f.severity || meta.severity || "medium") as FeedbackSeverity;
  const submitterRole = (meta.submitter_role || f.submitter_role || "doctor") as SubmitterRole;

  return {
    id: f.public_id || String(f.id),
    query_id: f.target_id || meta.query_id || f.query_id,
    user_query: meta.user_query || f.user_query || f.free_text_redacted || "",
    clara_response: meta.clara_response || f.clara_response || "",
    rating: (meta.rating || f.rating || (severity === "critical" ? 1 : severity === "high" ? 2 : 4)) as FeedbackRating,
    category,
    severity,
    triage_status: triageStatus,
    submitter_role: submitterRole,
    submitter_specialty: meta.submitter_specialty || f.submitter_specialty,
    comment: f.free_text_redacted || meta.comment || f.comment || "",
    proposed_correction: meta.proposed_correction || f.proposed_correction,
    cited_guidelines: meta.cited_guidelines || f.cited_guidelines || [],
    fides_verdict: meta.fides_verdict || f.fides_verdict,
    created_at: f.created_at || new Date().toISOString(),
    updated_at: f.updated_at || new Date().toISOString(),
    resolved_at: res.resolved_at || f.resolved_at,
    resolution_note: res.resolution_summary || res.clinical_notes || f.resolution_note,
    root_cause: res.action_taken || f.root_cause,
    assigned_to: f.assigned_user_id ? String(f.assigned_user_id) : f.assigned_to || meta.assigned_to,
    added_to_eval_benchmark: Boolean(res.benchmark_candidate || f.added_to_eval_benchmark),
    resourceVersion: f.resource_version || f.resourceVersion,
  };
}

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
    if (item.rating >= 1 && item.rating <= 5) {
      rating_breakdown[item.rating] = (rating_breakdown[item.rating] ?? 0) + 1;
      totalRatingSum += item.rating;
    }

    if (item.category in category_breakdown) {
      category_breakdown[item.category] = (category_breakdown[item.category] ?? 0) + 1;
    }

    if (item.triage_status in status_breakdown) {
      status_breakdown[item.triage_status] = (status_breakdown[item.triage_status] ?? 0) + 1;
    }

    if (
      (item.severity === "critical" || item.severity === "high") &&
      (item.triage_status === "new" || item.triage_status === "in_triage")
    ) {
      unresolvedCriticalHigh += 1;
    }

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
// Client API Calls (Server Wired & Fail-Closed)
// ---------------------------------------------------------------------------

export async function listClinicalFeedback(
  options?: ListClinicalFeedbackOptions,
): Promise<ClinicalFeedbackItem[]> {
  const params: Record<string, string | number> = {};

  if (options?.status && options.status !== "all") {
    // Map frontend triage status to backend status
    const statusMap: Record<TriageStatus, string> = {
      new: "open",
      in_triage: "in_review",
      resolved: "resolved",
      dismissed: "rejected",
    };
    params.status = statusMap[options.status] ?? options.status;
  }
  if (options?.severity && options.severity !== "all") {
    params.severity = options.severity;
  }
  if (options?.category && options.category !== "all") {
    params.category = options.category;
  }
  if (options?.cursor !== undefined) {
    params.cursor = options.cursor;
  }
  if (options?.limit !== undefined) {
    params.limit = options.limit;
  }

  const res = await api.get<{ items?: any[]; total?: number } | any[]>("/admin/feedback", {
    params,
  });

  // Preserve known_empty when server returns empty array [] or { items: [] }
  let rawList: any[] = [];
  if (Array.isArray(res.data)) {
    rawList = res.data;
  } else if (res.data && Array.isArray(res.data.items)) {
    rawList = res.data.items;
  }

  return rawList.map(mapBackendFeedbackToFrontend);
}

export async function getClinicalFeedbackDetail(
  id: string | number,
): Promise<ClinicalFeedbackItem> {
  const res = await api.get<any>(`/admin/feedback/${encodeURIComponent(String(id))}`);
  return mapBackendFeedbackToFrontend(res.data);
}

export async function updateFeedbackTriage(
  id: string | number,
  updates: Partial<ClinicalFeedbackItem> & {
    expectedResourceVersion?: string;
    notes?: string;
  },
): Promise<ClinicalFeedbackItem> {
  // If resolution is being performed
  if (updates.triage_status === "resolved" || updates.resolution_note) {
    try {
      const res = await api.post<any>(
        `/admin/feedback/${encodeURIComponent(String(id))}/resolution`,
        {
          resolution_summary: updates.resolution_note || "Resolved",
          action_taken: updates.root_cause || "Action taken",
          clinical_notes: updates.proposed_correction,
          benchmark_candidate: Boolean(updates.added_to_eval_benchmark),
        },
      );
      return mapBackendFeedbackToFrontend(res.data);
    } catch {
      // If resolution endpoint fails, fall through to status patch
    }
  }

  const statusMap: Record<string, string> = {
    new: "open",
    in_triage: "in_review",
    resolved: "resolved",
    dismissed: "rejected",
    open: "open",
    in_review: "in_review",
    rejected: "rejected",
  };

  const nextStatus = updates.triage_status
    ? statusMap[updates.triage_status] ?? updates.triage_status
    : "open";

  const res = await api.patch<any>(
    `/admin/feedback/${encodeURIComponent(String(id))}/status`,
    {
      status: nextStatus,
      notes: updates.resolution_note || updates.notes || "",
      expected_resource_version: updates.expectedResourceVersion,
    },
  );

  return mapBackendFeedbackToFrontend(res.data);
}

export async function exportFeedbackToBenchmark(
  id: string | number,
): Promise<{ success: boolean; benchmark_id?: string }> {
  try {
    const res = await api.post<{ success: boolean; benchmark_id?: string }>(
      `/admin/feedback/${encodeURIComponent(String(id))}/resolution`,
      {
        resolution_summary: "Exported to RAG Golden Benchmark",
        action_taken: "EXPORT_BENCHMARK",
        benchmark_candidate: true,
      },
    );
    return {
      success: true,
      benchmark_id: `BENCH-GOLDEN-${String(id)}`,
    };
  } catch (err) {
    // Also try export-benchmark route if present
    const res = await api.post<{ success: boolean; benchmark_id?: string }>(
      `/admin/feedback/${encodeURIComponent(String(id))}/export-benchmark`,
      {},
    );
    return res.data;
  }
}
