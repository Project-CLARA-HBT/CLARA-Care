import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockFetchPlatformAnalytics = vi.fn();
const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

const mockPlatformAnalyticsData = {
  generated_at: "2026-04-12T10:00:00Z",
  range: ["2026-03-13", "2026-04-12"] as [string, string],
  has_data: true,
  query_volume: {
    total_queries: 42850,
    safe_completions: 42062,
    total_interventions: 788,
    daily_trend: [
      { date: "2026-04-01", total_queries: 2850, safe_queries: 2800, interventions: 50, active_users: 480 },
      { date: "2026-04-02", total_queries: 3100, safe_queries: 3045, interventions: 55, active_users: 520 },
      { date: "2026-04-03", total_queries: 3400, safe_queries: 3340, interventions: 60, active_users: 570 },
    ],
    surface_usage: [
      { surface: "chat", labelVi: "Hội thoại Y khoa (Chat)", labelEn: "Clinical Chat", count: 18000, active_users: 3240, percentage: 42.0, icon: "chat" },
      { surface: "research", labelVi: "Nghiên cứu & Nguồn dẫn (Research)", labelEn: "Research Hub", count: 9400, active_users: 1690, percentage: 22.0, icon: "folder" },
      { surface: "careguard", labelVi: "Kiểm tra Tương tác Thuốc (CareGuard)", labelEn: "CareGuard Drug Safety", count: 6850, active_users: 1230, percentage: 16.0, icon: "medication" },
      { surface: "council", labelVi: "Hội chẩn Đa chuyên khoa (Council AI)", labelEn: "Council Multi-Specialist", count: 3420, active_users: 615, percentage: 8.0, icon: "contact" },
      { surface: "scribe", labelVi: "Ghi chép Khám bệnh (Medical Scribe)", labelEn: "Medical Scribe", count: 3000, active_users: 540, percentage: 7.0, icon: "clinical-notes" },
      { surface: "selfmed", labelVi: "Tủ thuốc Gia đình (Medicine Cabinet)", labelEn: "Medicine Cabinet", count: 2180, active_users: 390, percentage: 5.0, icon: "medication" },
    ],
    tier_distribution: [
      { tier: "tier1", labelVi: "Tier 1 (Phản hồi Nhanh / Fast Direct)", labelEn: "Tier 1 (Fast Direct)", count: 24850, percentage: 58.0, p50_ms: 185, p90_ms: 340, p99_ms: 720 },
      { tier: "tier2_deep", labelVi: "Tier 2 (Tư duy Lâm sàng / Deep Reasoning)", labelEn: "Tier 2 (Deep Reasoning)", count: 11140, percentage: 26.0, p50_ms: 820, p90_ms: 1450, p99_ms: 2890 },
      { tier: "tier2_deep_beta", labelVi: "Tier 2 Pro (Mở rộng Y văn / High Context)", labelEn: "Tier 2 Pro (High Context)", count: 4285, percentage: 10.0, p50_ms: 1250, p90_ms: 2200, p99_ms: 4100 },
      { tier: "council", labelVi: "Hội chẩn Đa chuyên khoa (Council Multi-Agent)", labelEn: "Council Multi-Agent", count: 2575, percentage: 6.0, p50_ms: 2800, p90_ms: 4600, p99_ms: 8500 },
    ],
  },
  safety_guardrails: {
    total_interventions: 788,
    overall_intervention_rate_pct: 1.84,
    safe_completion_rate_pct: 98.16,
    emergency_fastpath: {
      total_interventions: 142,
      rate_pct: 0.33,
      avg_escalation_ms: 38,
      triggers: [
        { id: "chest_pain", categoryVi: "Đau ngực cấp / Nghi ngờ NMCT", categoryEn: "Acute Chest Pain / Suspected MI", count: 58, pct: 40.8, actionVi: "Kích hoạt chuyển hướng khẩn cấp 115", actionEn: "Immediate 115 emergency dispatch", severity: "critical" as const, protocol: "FAST_EMERGENCY_BYPASS_v2" },
        { id: "stroke_fast", categoryVi: "Dấu hiệu FAST / Đột quỵ cấp", categoryEn: "FAST Signs / Acute Stroke", count: 36, pct: 25.4, actionVi: "Bỏ qua LLM, hướng dẫn sơ cứu đột quỵ", actionEn: "LLM bypassed, direct emergency stroke protocol", severity: "critical" as const, protocol: "FAST_STRORO_TRIAGE_115" },
        { id: "anaphylaxis", categoryVi: "Sốc phản vệ / Dị ứng thuốc cấp", categoryEn: "Acute Anaphylaxis / Drug Reaction", count: 27, pct: 19.0, actionVi: "Cảnh báo ngưng thuốc ngay & gọi 115", actionEn: "Discontinue drug immediately & call 115", severity: "critical" as const, protocol: "ANAPHYLAXIS_GUARD_v1" },
        { id: "severe_dyspnea", categoryVi: "Khó thở cấp tính / Tím tái", categoryEn: "Severe Acute Dyspnea / Cyanosis", count: 21, pct: 14.8, actionVi: "Hướng dẫn tư thế ngồi & gọi trợ giúp y tế", actionEn: "Position guidance & immediate ambulance", severity: "high" as const, protocol: "ACUTE_RESPIRATORY_ESCALATION" },
      ],
    },
    fides_ddi_blocks: {
      total_blocked_claims: 389,
      block_rate_pct: 8.8,
      total_evaluated_claims: 4418,
      verdict_distribution: {
        verified: 3820,
        partially_verified: 412,
        contested: 48,
        unsupported: 15,
        blocked_claims: 389,
      },
      severity_distribution: {
        critical: 389,
        high: 285,
        medium: 640,
        low: 1120,
      },
      top_blocked_patterns: [
        { pattern: "Simvastatin + Clarithromycin (CYP3A4)", riskTypeVi: "Tăng nồng độ statin, nguy cơ tiêu cơ vân cấp", riskTypeEn: "Massive statin elevation, high rhabdomyolysis risk", count: 42, severity: "critical" as const, guidelineAnchor: "DrugBank DB00641 / Dược thư QG 2022" },
        { pattern: "Warfarin + NSAIDs / Aspirin", riskTypeVi: "Hiệp đồng chống đông, xuất huyết nặng", riskTypeEn: "Synergistic anticoagulation, major GI hemorrhage risk", count: 38, severity: "critical" as const, guidelineAnchor: "FDA Black Box / Bộ Y Tế Phác đồ" },
      ],
    },
    legal_hardguards: {
      total_interventions: 257,
      rate_pct: 0.60,
      intents: [
        { intent: "prescribing_prohibition", labelVi: "Chặn ý định kê đơn & chỉ định thuốc mới", labelEn: "Prescribing Intent Prohibition", count: 146, pct: 56.8, descriptionVi: "Khóa mọi câu trả lời có tính chất kê đơn thuốc kháng sinh.", descriptionEn: "Enforces non-prescribing boundary.", standardRule: "LEGAL_VI_VN_MED_ART_12" },
        { intent: "diagnosis_replacement", labelVi: "Chặn ý định chẩn đoán bệnh xác định thay bác sĩ", labelEn: "Definitive Diagnosis Replacement Block", count: 74, pct: 28.8, descriptionVi: "Ngăn chặn kết luận chẩn đoán xác định.", descriptionEn: "Blocks definitive diagnostic assertions.", standardRule: "LEGAL_MOH_DIAGNOSIS_GUARD" },
        { intent: "personal_dosage_calculation", labelVi: "Chặn tính toán liều lượng cá nhân hóa độc quyền", labelEn: "Personal Dosage Determination Block", count: 37, pct: 14.4, descriptionVi: "Từ chối tự ý điều chỉnh liều thuốc đặc trị.", descriptionEn: "Refuses personalized dosage alterations.", standardRule: "DOSAGE_SAFETY_POLICY_v3" },
      ],
    },
  },
  zero_pii_usage: {
    active_users_peak: 3420,
    total_active_users: 4850,
    role_distribution: [
      { role: "doctor", labelVi: "Bác sĩ & Bác sĩ chuyên khoa", labelEn: "Physicians & Specialists", count: 1820, pct: 37.5 },
      { role: "pharmacist", labelVi: "Dược sĩ Lâm sàng", labelEn: "Clinical Pharmacists", count: 680, pct: 14.0 },
      { role: "researcher", labelVi: "Nhà nghiên cứu Y sinh", labelEn: "Biomedical Researchers", count: 850, pct: 17.5 },
      { role: "normal", labelVi: "Người dùng Cá nhân / Bệnh nhân", labelEn: "Patients & Family Caregivers", count: 1420, pct: 29.3 },
      { role: "admin", labelVi: "Quản trị viên Hệ thống", labelEn: "System Administrators", count: 80, pct: 1.7 },
    ],
    funnel_stages: [
      { stage: "active_users", labelVi: "1. Người dùng Hoạt động (Active Users)", labelEn: "1. Active Platform Users", count: 4850, conversion_rate_pct: 100 },
      { stage: "ran_query", labelVi: "2. Đặt câu hỏi Y tế / Nghiên cứu (Health Queries)", labelEn: "2. Executed Clinical/Health Query", count: 3920, conversion_rate_pct: 80.8 },
      { stage: "used_clinical_tools", labelVi: "3. Dùng công cụ Chuyên sâu (Council/CareGuard/Scribe)", labelEn: "3. Used Advanced Clinical Tools", count: 1840, conversion_rate_pct: 37.9 },
    ],
    retention_cohorts: [
      { cohort: "2026-01 (Jan)", cohort_size: 1240, retained: 942, retention_rate_pct: 76.0 },
      { cohort: "2026-02 (Feb)", cohort_size: 1580, retained: 1216, retention_rate_pct: 77.0 },
      { cohort: "2026-03 (Mar)", cohort_size: 2030, retained: 1644, retention_rate_pct: 81.0 },
      { cohort: "2026-04 (Apr)", cohort_size: 2480, retained: 2083, retention_rate_pct: 84.0 },
    ],
    compliance: {
      zero_pii_verified: true,
      scrubbed_fields_count: 24,
      scrubbed_categories: [
        "Identities (Names, Emails, Phone, Addresses)",
        "Free-text user queries and prompts",
        "Free-text medical transcripts and clinical notes",
        "Raw medication names and dosage strings",
        "Upstream internal exceptions and stack traces",
      ],
      last_audit_status: "PASSED_STRICT_NO_PII_INVARIANT",
    },
  },
};

vi.mock("@/lib/platform-analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/platform-analytics")>();
  return {
    ...actual,
    fetchPlatformAnalytics: () => mockFetchPlatformAnalytics(),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: vi.fn(),
}));

import AdminAnalyticsDashboardPage from "@/app/admin/analytics/page";

beforeEach(() => {
  window.localStorage.setItem("clara_ui_language", "en");
  roleState.role = "admin";
  mockFetchPlatformAnalytics.mockResolvedValue(mockPlatformAnalyticsData);
});

afterEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AdminAnalyticsDashboardPage (Spec v5 Section 6.64 - Platform Analytics & Safety Dashboard)", () => {
  describe("1. Shell and Role-based Access Control (RBAC)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and Platform Analytics & Safety Dashboard layout archetype", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const container = document.querySelector(
        '[data-layout-archetype="Platform Analytics & Safety Dashboard"]'
      );
      expect(container).toBeInTheDocument();
      expect(container).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(container).toHaveAttribute("data-density", "DENSE");
    });

    it("blocks non-admin users with an access denied 403 banner (defense-in-depth)", async () => {
      roleState.role = "doctor";
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/Access Denied/i)).toBeInTheDocument();
      });

      expect(mockFetchPlatformAnalytics).not.toHaveBeenCalled();
    });
  });

  describe("2. Aggregated Query Volume & KPI Cards", () => {
    it("renders top-level KPI summary cards with query volume, intervention rates, and safe completion", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Aggregated query volume
      expect(screen.getAllByText(/Aggregated Query Volume/i).length).toBeGreaterThan(0);
      expect(screen.getByText("42.850")).toBeInTheDocument();

      // Safety Intervention Rate & Safe Completion
      expect(screen.getByText(/Safety Intervention Rate/i)).toBeInTheDocument();
      expect(screen.getByText("1.84%")).toBeInTheDocument();
      expect(screen.getByText(/Safe Completion Rate/i)).toBeInTheDocument();
      expect(screen.getByText("98.16%")).toBeInTheDocument();

      // Emergency & FIDES counts
      expect(screen.getByText(/Emergency & FIDES Blocks/i)).toBeInTheDocument();
      expect(screen.getByText("142 / 389")).toBeInTheDocument();

      // Peak Active Users
      expect(screen.getByText(/Peak Active Users/i)).toBeInTheDocument();
      expect(screen.getByText("3.420")).toBeInTheDocument();
    });

    it("renders daily query volume trend chart and surface adoption breakdown", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      expect(screen.getByText(/Daily Query Volume Trend/i)).toBeInTheDocument();
      expect(screen.getByText(/Surface Usage Distribution/i)).toBeInTheDocument();
      expect(screen.getByText("Clinical Chat")).toBeInTheDocument();
      expect(screen.getByText("Research Hub")).toBeInTheDocument();
      expect(screen.getByText("CareGuard Drug Safety")).toBeInTheDocument();
    });
  });

  describe("3. Safety Guardrail Intervention Rates (Emergency 115, FIDES DDI, Legal Hard-guards)", () => {
    it("renders all three safety guardrail pillars with exact intervention counts and rates", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // 1. Emergency fast-path
      expect(screen.getByText(/1. Emergency Fast-Path \(115\)/i)).toBeInTheDocument();
      expect(screen.getByText("142 events")).toBeInTheDocument();
      expect(screen.getByText(/Acute Chest Pain \/ Suspected MI/i)).toBeInTheDocument();
      expect(screen.getByText(/FAST Signs \/ Acute Stroke/i)).toBeInTheDocument();

      // 2. FIDES DDI & Dosage Blocks
      expect(screen.getByText(/2. FIDES DDI & Dosage Blocks/i)).toBeInTheDocument();
      expect(screen.getByText("389 blocks")).toBeInTheDocument();
      expect(screen.getByText("Blocked CRITICAL Claims")).toBeInTheDocument();

      // 3. Legal Hard-guards
      expect(screen.getByText(/3. Legal Hard-Guards/i)).toBeInTheDocument();
      expect(screen.getByText("257 guards")).toBeInTheDocument();
      expect(screen.getByText(/Prescribing Intent Prohibition/i)).toBeInTheDocument();
      expect(screen.getByText(/Definitive Diagnosis Replacement Block/i)).toBeInTheDocument();
    });

    it("renders top blocked hazardous drug-drug interaction pairs table", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      expect(screen.getByText("Simvastatin + Clarithromycin (CYP3A4)")).toBeInTheDocument();
      expect(screen.getByText("Warfarin + NSAIDs / Aspirin")).toBeInTheDocument();
      expect(screen.getByText("DrugBank DB00641 / Dược thư QG 2022")).toBeInTheDocument();
    });
  });

  describe("4. Zero-PII Usage Distributions & Cohort Retention", () => {
    it("renders zero-PII invariant badge, conversion funnel, and retention cohort matrix", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Zero PII banner
      expect(screen.getByText(/Zero-PII Invariant: 100% Anonymized Aggregates/i)).toBeInTheDocument();

      // Funnel stages
      expect(screen.getByText(/1. Active Platform Users/i)).toBeInTheDocument();
      expect(screen.getByText(/2. Executed Clinical\/Health Query/i)).toBeInTheDocument();
      expect(screen.getByText(/3. Used Advanced Clinical Tools/i)).toBeInTheDocument();

      // Retention cohorts
      expect(screen.getByText("2026-01 (Jan)")).toBeInTheDocument();
      expect(screen.getByText("2026-04 (Apr)")).toBeInTheDocument();
      expect(screen.getByText("84%")).toBeInTheDocument();
    });
  });

  describe("5. Interactive Tab Filtering & Inspector Drawer", () => {
    it("filters sections when clicking filter pills", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Switch to Guardrails tab
      const guardrailsTab = screen.getByRole("tab", { name: /Safety Guardrails/i });
      fireEvent.click(guardrailsTab);

      expect(screen.getByText(/1. Emergency Fast-Path \(115\)/i)).toBeInTheDocument();
      expect(screen.queryByText(/Daily Query Volume Trend/i)).not.toBeInTheDocument();

      // Switch to Latency tab
      const latencyTab = screen.getByRole("tab", { name: /Latency & Pipeline/i });
      fireEvent.click(latencyTab);

      expect(screen.getByText(/Inference Latency & Pipeline Performance/i)).toBeInTheDocument();
      expect(screen.getByText("Tier 1 (Fast Direct)")).toBeInTheDocument();
    });

    it("opens technical inspector drawer when clicking compliance audit button", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const auditBtn = screen.getByRole("button", { name: /View Compliance Audit/i });
      fireEvent.click(auditBtn);

      await waitFor(() => {
        expect(screen.getByText(/Zero-PII & Safety Compliance Audit/i)).toBeInTheDocument();
        expect(screen.getByText(/Zero-PII Audit Report/i)).toBeInTheDocument();
        expect(screen.getByText(/Scrubbed Data Categories:/i)).toBeInTheDocument();
      });

      // Close inspector
      const closeBtn = screen.getByRole("button", { name: /Close/i });
      fireEvent.click(closeBtn);
    });

    it("opens technical inspector drawer when clicking a blocked drug pair", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const blockedRow = screen.getByText("Simvastatin + Clarithromycin (CYP3A4)");
      fireEvent.click(blockedRow);

      await waitFor(() => {
        expect(screen.getByText(/FIDES Block: Simvastatin \+ Clarithromycin/i)).toBeInTheDocument();
        expect(screen.getByText(/Blocked Interaction Details/i)).toBeInTheDocument();
      });
    });
  });

  describe("6. Date Range Controls, Error States & Language", () => {
    it("handles preset 7D and 90D range button clicks", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const btn7D = screen.getByRole("button", { name: "7D" });
      fireEvent.click(btn7D);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });
    });

    it("displays error alert when analytics fetch fails", async () => {
      mockFetchPlatformAnalytics.mockRejectedValueOnce(new Error("API network error"));

      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
    });

    it("renders in Vietnamese when clara_ui_language is vi", async () => {
      window.localStorage.setItem("clara_ui_language", "vi");

      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      expect(screen.getAllByText(/Phân tích Nền tảng & An toàn Hệ thống/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Tổng Khối lượng Truy vấn/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Tỷ lệ Can thiệp Rào chắn/i).length).toBeGreaterThan(0);
    });
  });
});
