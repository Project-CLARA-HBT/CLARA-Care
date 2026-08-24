import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdminAnalyticsDashboardPage from "@/app/admin/analytics/page";
import AdminClinicalAnalyticsPage from "@/app/admin/analytics/clinical/page";
import type { ClinicalAnalytics } from "@/lib/analytics-dashboard";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockFetchPlatformAnalytics = vi.fn();
const mockGetClinicalAnalytics = vi.fn();
const trackAdminSurfaceViewed = vi.fn();

const roleState = { role: "admin" as "normal" | "doctor" | "researcher" | "admin" };

const mockPlatformAnalyticsData = {
  generated_at: "2026-08-24T10:00:00Z",
  range: ["2026-07-25", "2026-08-24"] as [string, string],
  has_data: true,
  query_volume: {
    total_queries: 52400,
    safe_completions: 51430,
    total_interventions: 970,
    daily_trend: [
      { date: "2026-08-20", total_queries: 3450, safe_queries: 3390, interventions: 60, active_users: 580 },
      { date: "2026-08-21", total_queries: 3800, safe_queries: 3730, interventions: 70, active_users: 620 },
      { date: "2026-08-22", total_queries: 4100, safe_queries: 4020, interventions: 80, active_users: 690 },
    ],
    surface_usage: [
      { surface: "chat", labelVi: "Hội thoại Y khoa (Chat)", labelEn: "Clinical Chat", count: 22000, active_users: 3940, percentage: 42.0, icon: "chat" },
      { surface: "research", labelVi: "Nghiên cứu & Nguồn dẫn (Research)", labelEn: "Research Hub", count: 11500, active_users: 2060, percentage: 22.0, icon: "folder" },
      { surface: "careguard", labelVi: "Kiểm tra Tương tác Thuốc (CareGuard)", labelEn: "CareGuard Drug Safety", count: 8380, active_users: 1500, percentage: 16.0, icon: "medication" },
      { surface: "council", labelVi: "Hội chẩn Đa chuyên khoa (Council AI)", labelEn: "Council Multi-Specialist", count: 4190, active_users: 750, percentage: 8.0, icon: "contact" },
      { surface: "scribe", labelVi: "Ghi chép Khám bệnh (Medical Scribe)", labelEn: "Medical Scribe", count: 3670, active_users: 655, percentage: 7.0, icon: "clinical-notes" },
      { surface: "selfmed", labelVi: "Tủ thuốc Gia đình (Medicine Cabinet)", labelEn: "Medicine Cabinet", count: 2660, active_users: 475, percentage: 5.0, icon: "medication" },
    ],
    tier_distribution: [
      { tier: "tier1", labelVi: "Tier 1 (Phản hồi Nhanh / Fast Direct)", labelEn: "Tier 1 (Fast Direct)", count: 30392, percentage: 58.0, p50_ms: 180, p90_ms: 330, p99_ms: 710 },
      { tier: "tier2_deep", labelVi: "Tier 2 (Tư duy Lâm sàng / Deep Reasoning)", labelEn: "Tier 2 (Deep Reasoning)", count: 13624, percentage: 26.0, p50_ms: 810, p90_ms: 1420, p99_ms: 2850 },
      { tier: "tier2_deep_beta", labelVi: "Tier 2 Pro (Mở rộng Y văn / High Context)", labelEn: "Tier 2 Pro (High Context)", count: 5240, percentage: 10.0, p50_ms: 1220, p90_ms: 2180, p99_ms: 4050 },
      { tier: "council", labelVi: "Hội chẩn Đa chuyên khoa (Council Multi-Agent)", labelEn: "Council Multi-Agent", count: 3144, percentage: 6.0, p50_ms: 2750, p90_ms: 4500, p99_ms: 8400 },
    ],
  },
  safety_guardrails: {
    total_interventions: 970,
    overall_intervention_rate_pct: 1.85,
    safe_completion_rate_pct: 98.15,
    emergency_fastpath: {
      total_interventions: 174,
      rate_pct: 0.33,
      avg_escalation_ms: 36,
      triggers: [
        { id: "chest_pain", categoryVi: "Đau ngực cấp / Nghi ngờ NMCT", categoryEn: "Acute Chest Pain / Suspected MI", count: 71, pct: 40.8, actionVi: "Kích hoạt chuyển hướng khẩn cấp 115", actionEn: "Immediate 115 emergency dispatch", severity: "critical" as const, protocol: "FAST_EMERGENCY_BYPASS_v2" },
        { id: "stroke_fast", categoryVi: "Dấu hiệu FAST / Đột quỵ cấp", categoryEn: "FAST Signs / Acute Stroke", count: 44, pct: 25.4, actionVi: "Bỏ qua LLM, hướng dẫn sơ cứu đột quỵ", actionEn: "LLM bypassed, direct emergency stroke protocol", severity: "critical" as const, protocol: "FAST_STROKE_TRIAGE_115" },
        { id: "anaphylaxis", categoryVi: "Sốc phản vệ / Dị ứng thuốc cấp", categoryEn: "Acute Anaphylaxis / Drug Reaction", count: 33, pct: 19.0, actionVi: "Cảnh báo ngưng thuốc ngay & gọi 115", actionEn: "Discontinue drug immediately & call 115", severity: "critical" as const, protocol: "ANAPHYLAXIS_GUARD_v1" },
        { id: "severe_dyspnea", categoryVi: "Khó thở cấp tính / Tím tái", categoryEn: "Severe Acute Dyspnea / Cyanosis", count: 26, pct: 14.8, actionVi: "Hướng dẫn tư thế ngồi & gọi trợ giúp", actionEn: "Position guidance & immediate ambulance", severity: "high" as const, protocol: "ACUTE_RESPIRATORY_ESCALATION" },
      ],
    },
    fides_ddi_blocks: {
      total_blocked_claims: 478,
      block_rate_pct: 8.8,
      total_evaluated_claims: 5430,
      verdict_distribution: {
        verified: 4700,
        partially_verified: 502,
        contested: 58,
        unsupported: 18,
        blocked_claims: 478,
      },
      severity_distribution: {
        critical: 478,
        high: 350,
        medium: 780,
        low: 1370,
      },
      top_blocked_patterns: [
        { pattern: "Simvastatin + Clarithromycin (CYP3A4)", riskTypeVi: "Tăng nồng độ statin, nguy cơ tiêu cơ vân cấp", riskTypeEn: "Massive statin elevation, high rhabdomyolysis risk", count: 52, severity: "critical" as const, guidelineAnchor: "DrugBank DB00641 / Dược thư QG 2022" },
        { pattern: "Warfarin + NSAIDs / Aspirin", riskTypeVi: "Hiệp đồng chống đông, xuất huyết nặng", riskTypeEn: "Synergistic anticoagulation, major GI hemorrhage risk", count: 46, severity: "critical" as const, guidelineAnchor: "FDA Black Box / Bộ Y Tế Phác đồ" },
        { pattern: "Sildenafil + Nitroglycerin / Isosorbide", riskTypeVi: "Giãn mạch quá mức, hạ huyết áp tụt dốc nguy hiểm tính mạng", riskTypeEn: "Excessive vasodilation, life-threatening hypotension", count: 29, severity: "critical" as const, guidelineAnchor: "AHA/ACC Heart Guidelines" },
        { pattern: "Methotrexate + Trimethoprim/Sulfamethoxazole", riskTypeVi: "Ức chế chuyển hóa folate tủy xương, suy tủy nghiêm trọng", riskTypeEn: "Bone marrow folate toxicity, severe pancytopenia", count: 23, severity: "critical" as const, guidelineAnchor: "DrugBank DB00563 Safety Bound" },
      ],
    },
    legal_hardguards: {
      total_interventions: 318,
      rate_pct: 0.61,
      intents: [
        { intent: "prescribing_prohibition", labelVi: "Chặn ý định kê đơn & chỉ định thuốc mới", labelEn: "Prescribing Intent Prohibition", count: 180, pct: 56.6, descriptionVi: "Khóa mọi câu trả lời có tính chất kê đơn thuốc kháng sinh.", descriptionEn: "Enforces non-prescribing boundary.", standardRule: "LEGAL_VI_VN_MED_ART_12" },
        { intent: "diagnosis_replacement", labelVi: "Chặn ý định chẩn đoán bệnh xác định thay bác sĩ", labelEn: "Definitive Diagnosis Replacement Block", count: 92, pct: 28.9, descriptionVi: "Ngăn chặn kết luận chẩn đoán xác định.", descriptionEn: "Blocks definitive diagnostic assertions.", standardRule: "LEGAL_MOH_DIAGNOSIS_GUARD" },
        { intent: "personal_dosage_calculation", labelVi: "Chặn tính toán liều lượng cá nhân hóa độc quyền", labelEn: "Personal Dosage Determination Block", count: 46, pct: 14.5, descriptionVi: "Từ chối tự ý điều chỉnh liều thuốc đặc trị.", descriptionEn: "Refuses personalized dosage alterations.", standardRule: "DOSAGE_SAFETY_POLICY_v3" },
      ],
    },
  },
  zero_pii_usage: {
    active_users_peak: 4200,
    total_active_users: 5980,
    role_distribution: [
      { role: "doctor", labelVi: "Bác sĩ & Bác sĩ chuyên khoa", labelEn: "Physicians & Specialists", count: 2240, pct: 37.5 },
      { role: "pharmacist", labelVi: "Dược sĩ Lâm sàng", labelEn: "Clinical Pharmacists", count: 837, pct: 14.0 },
      { role: "researcher", labelVi: "Nhà nghiên cứu Y sinh", labelEn: "Biomedical Researchers", count: 1046, pct: 17.5 },
      { role: "normal", labelVi: "Người dùng Cá nhân / Bệnh nhân", labelEn: "Patients & Family Caregivers", count: 1752, pct: 29.3 },
      { role: "admin", labelVi: "Quản trị viên Hệ thống", labelEn: "System Administrators", count: 105, pct: 1.7 },
    ],
    funnel_stages: [
      { stage: "active_users", labelVi: "1. Người dùng Hoạt động (Active Users)", labelEn: "1. Active Platform Users", count: 5980, conversion_rate_pct: 100 },
      { stage: "ran_query", labelVi: "2. Đặt câu hỏi Y tế / Nghiên cứu (Health Queries)", labelEn: "2. Executed Clinical/Health Query", count: 4830, conversion_rate_pct: 80.8 },
      { stage: "used_clinical_tools", labelVi: "3. Dùng công cụ Chuyên sâu (Council/CareGuard/Scribe)", labelEn: "3. Used Advanced Clinical Tools", count: 2266, conversion_rate_pct: 37.9 },
    ],
    retention_cohorts: [
      { cohort: "2026-05 (May)", cohort_size: 1540, retained: 1170, retention_rate_pct: 76.0 },
      { cohort: "2026-06 (Jun)", cohort_size: 1950, retained: 1500, retention_rate_pct: 77.0 },
      { cohort: "2026-07 (Jul)", cohort_size: 2500, retained: 2025, retention_rate_pct: 81.0 },
      { cohort: "2026-08 (Aug)", cohort_size: 3050, retained: 2562, retention_rate_pct: 84.0 },
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

const mockClinicalAnalyticsData: ClinicalAnalytics = {
  generated_at: "2026-08-24T10:00:00.000Z",
  range: ["2026-07-25", "2026-08-24"],
  verdicts: {
    verified: 350,
    partially_verified: 45,
    contested: 12,
    unsupported: 8,
    blocked_claims: 28,
  },
  ddi_severity: { low: 120, medium: 85, high: 34, critical: 16 },
  router_confidence: { high: 280, medium: 95, low: 22 },
  fallback_rate_pct: 3.8,
  latency: [
    { tier: "tier1", p50_ms: 115, p90_ms: 270, p99_ms: 480 },
    { tier: "tier2_deep", p50_ms: 790, p90_ms: 1380, p99_ms: 2750 },
    { tier: "tier2_deep_beta", p50_ms: 1190, p90_ms: 2100, p99_ms: 3950 },
    { tier: "council", p50_ms: 2680, p90_ms: 4400, p99_ms: 8200 },
  ],
  has_data: true,
};

vi.mock("@/lib/platform-analytics", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/platform-analytics")>();
  return {
    ...actual,
    fetchPlatformAnalytics: () => mockFetchPlatformAnalytics(),
  };
});

vi.mock("@/lib/analytics-dashboard", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/analytics-dashboard")>();
  return {
    ...actual,
    getClinicalAnalytics: () => mockGetClinicalAnalytics(),
  };
});

vi.mock("@/lib/auth-store", () => ({
  getRole: () => roleState.role,
}));

vi.mock("@/lib/analytics/events", () => ({
  trackAdminSurfaceViewed: (props: { view: string }) => trackAdminSurfaceViewed(props),
}));

// ---------------------------------------------------------------------------
// Test Suites
// ---------------------------------------------------------------------------

describe("Spec v8 Section 12.4: Admin Analytics Architecture & Safety Verification", () => {
  beforeEach(() => {
    window.localStorage.setItem("clara_ui_language", "en");
    roleState.role = "admin";
    mockFetchPlatformAnalytics.mockResolvedValue(mockPlatformAnalyticsData);
    mockGetClinicalAnalytics.mockResolvedValue(mockClinicalAnalyticsData);
    trackAdminSurfaceViewed.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  describe("1. AdminCommandStrip Adoption", () => {
    it("renders AdminCommandStrip on Platform Analytics page (/admin/analytics)", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const nav = screen.getByRole("navigation", { name: /Admin command strip/i });
      expect(nav).toBeInTheDocument();
      expect(screen.getByText("Tổng quan")).toBeInTheDocument();
      expect(screen.getByText("Nguồn tri thức")).toBeInTheDocument();
      expect(screen.getByText("Luồng trả lời")).toBeInTheDocument();
      expect(screen.getByText("Giám sát")).toBeInTheDocument();
      expect(screen.getByText("Phân tích")).toBeInTheDocument();
    });

    it("renders AdminCommandStrip on Clinical Analytics page (/admin/analytics/clinical)", async () => {
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      const nav = screen.getByRole("navigation", { name: /Admin command strip/i });
      expect(nav).toBeInTheDocument();
      expect(screen.getByText("Tổng quan")).toBeInTheDocument();
      expect(screen.getByText("Phân tích")).toBeInTheDocument();
    });
  });

  describe("2. Platform Analytics (/admin/analytics - Spec v8 Section 12.4)", () => {
    it("renders with ADMIN_COMMAND shell mode and DENSE density", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      const root = document.querySelector(
        '[data-layout-archetype="Platform Analytics & Safety Dashboard"]'
      );
      expect(root).toBeInTheDocument();
      expect(root).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(root).toHaveAttribute("data-density", "DENSE");
    });

    it("renders query volume trends, daily trend chart, and surface distributions", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Top KPI volume card
      expect(screen.getAllByText(/Aggregated Query Volume/i).length).toBeGreaterThan(0);
      expect(screen.getByText("52.400")).toBeInTheDocument();

      // Trend panel
      expect(screen.getByText(/Daily Query Volume Trend/i)).toBeInTheDocument();

      // Surface usage distribution
      expect(screen.getByText(/Surface Usage Distribution/i)).toBeInTheDocument();
      expect(screen.getByText("Clinical Chat")).toBeInTheDocument();
      expect(screen.getByText("Research Hub")).toBeInTheDocument();
      expect(screen.getByText("CareGuard Drug Safety")).toBeInTheDocument();
      expect(screen.getByText("Council Multi-Specialist")).toBeInTheDocument();
      expect(screen.getByText("Medical Scribe")).toBeInTheDocument();
      expect(screen.getByText("Medicine Cabinet")).toBeInTheDocument();
    });

    it("renders 3-pillar safety guardrail interventions (Emergency 115, FIDES DDI, Legal Hard-guards)", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Pillar 1: Emergency fast-path (115)
      expect(screen.getByText(/1. Emergency Fast-Path \(115\)/i)).toBeInTheDocument();
      expect(screen.getByText("174 events")).toBeInTheDocument();
      expect(screen.getByText(/Acute Chest Pain \/ Suspected MI/i)).toBeInTheDocument();
      expect(screen.getByText(/FAST Signs \/ Acute Stroke/i)).toBeInTheDocument();
      expect(screen.getByText(/Acute Anaphylaxis \/ Drug Reaction/i)).toBeInTheDocument();
      expect(screen.getByText(/36 ms/i)).toBeInTheDocument();

      // Pillar 2: FIDES DDI & Dosage Blocks
      expect(screen.getByText(/2. FIDES DDI & Dosage Blocks/i)).toBeInTheDocument();
      expect(screen.getByText("478 blocks")).toBeInTheDocument();
      expect(screen.getByText("Blocked CRITICAL Claims")).toBeInTheDocument();
      expect(screen.getByText("5.430")).toBeInTheDocument();

      // Pillar 3: Legal Hard-Guards
      expect(screen.getByText(/3. Legal Hard-Guards/i)).toBeInTheDocument();
      expect(screen.getByText("318 guards")).toBeInTheDocument();
      expect(screen.getByText(/Prescribing Intent Prohibition/i)).toBeInTheDocument();
      expect(screen.getByText(/Definitive Diagnosis Replacement Block/i)).toBeInTheDocument();
      expect(screen.getByText(/Personal Dosage Determination Block/i)).toBeInTheDocument();
      expect(screen.getByText(/LEGAL_VI_VN_MED_ART_12/i)).toBeInTheDocument();
    });

    it("renders top blocked hazardous drug-drug interaction pairs table", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      expect(screen.getByText("Simvastatin + Clarithromycin (CYP3A4)")).toBeInTheDocument();
      expect(screen.getByText("Warfarin + NSAIDs / Aspirin")).toBeInTheDocument();
      expect(screen.getByText("Sildenafil + Nitroglycerin / Isosorbide")).toBeInTheDocument();
      expect(screen.getByText("Methotrexate + Trimethoprim/Sulfamethoxazole")).toBeInTheDocument();
      expect(screen.getByText("DrugBank DB00641 / Dược thư QG 2022")).toBeInTheDocument();
    });

    it("renders Zero-PII usage distributions, funnel stages, and retention cohorts", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Zero-PII Invariant Banner
      expect(screen.getByText(/Zero-PII Invariant: 100% Anonymized Aggregates/i)).toBeInTheDocument();
      expect(screen.getByText(/ISO-27701 ENFORCED/i)).toBeInTheDocument();

      // Conversion funnel
      expect(screen.getByText(/1. Active Platform Users/i)).toBeInTheDocument();
      expect(screen.getByText(/2. Executed Clinical\/Health Query/i)).toBeInTheDocument();
      expect(screen.getByText(/3. Used Advanced Clinical Tools/i)).toBeInTheDocument();

      // Roles
      expect(screen.getByText(/Physicians & Specialists/i)).toBeInTheDocument();
      expect(screen.getByText(/Clinical Pharmacists/i)).toBeInTheDocument();

      // Cohorts
      expect(screen.getByText("2026-05 (May)")).toBeInTheDocument();
      expect(screen.getByText("2026-08 (Aug)")).toBeInTheDocument();
    });

    it("opens technical inspector drawer when clicking compliance audit or blocked drug row", async () => {
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(mockFetchPlatformAnalytics).toHaveBeenCalled();
      });

      // Open compliance audit inspector
      const auditBtn = screen.getByRole("button", { name: /View Compliance Audit/i });
      fireEvent.click(auditBtn);

      await waitFor(() => {
        expect(screen.getByText(/Zero-PII & Safety Compliance Audit/i)).toBeInTheDocument();
        expect(screen.getByText(/Scrubbed Data Categories:/i)).toBeInTheDocument();
      });

      // Close inspector
      const closeBtn = screen.getByRole("button", { name: /Close/i });
      fireEvent.click(closeBtn);

      // Click on a blocked drug row
      const drugRow = screen.getByText("Warfarin + NSAIDs / Aspirin");
      fireEvent.click(drugRow);

      await waitFor(() => {
        expect(screen.getByText(/FIDES Block: Warfarin \+ NSAIDs/i)).toBeInTheDocument();
        expect(screen.getByText(/Blocked Interaction Details/i)).toBeInTheDocument();
      });
    });

    it("blocks non-admin users with 403 access denied banner", async () => {
      roleState.role = "doctor";
      render(<AdminAnalyticsDashboardPage />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/Access Denied \(403\)/i)).toBeInTheDocument();
      });

      expect(mockFetchPlatformAnalytics).not.toHaveBeenCalled();
    });
  });

  describe("3. Clinical Analytics (/admin/analytics/clinical - Spec v8 Section 12.4)", () => {
    it("renders with ADMIN_COMMAND shell mode, DENSE density, and Clinical Analytics Drill-down layout archetype", async () => {
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      const root = document.querySelector(
        '[data-layout-archetype="Clinical Analytics Drill-down"]'
      );
      expect(root).toBeInTheDocument();
      expect(root).toHaveAttribute("data-shell-mode", "ADMIN_COMMAND");
      expect(root).toHaveAttribute("data-density", "DENSE");
    });

    it("renders FIDES verdict breakdown, DDI severity distribution, and top hazardous drug pairs", async () => {
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      // KPI cards
      expect(screen.getAllByText(/Blocked CRITICAL Claims/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText("28").length).toBeGreaterThan(0);
      expect(screen.getByText(/Fallback Rate/i)).toBeInTheDocument();
      expect(screen.getByText("3.8%")).toBeInTheDocument();
      expect(screen.getByText(/Critical DDI Hazards/i)).toBeInTheDocument();
      expect(screen.getAllByText("16").length).toBeGreaterThan(0);

      // FIDES Verdict breakdown
      expect(screen.getAllByText(/FIDES Verdict Distribution/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Fully Verified/i)).toBeInTheDocument();
      expect(screen.getByText(/Partially Verified/i)).toBeInTheDocument();
      expect(screen.getByText(/Contested Evidence/i)).toBeInTheDocument();
      expect(screen.getByText(/Unsupported Claims/i)).toBeInTheDocument();

      // DDI Severity Distribution
      expect(screen.getAllByText(/DDI Severity Distribution/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Low Severity/i)).toBeInTheDocument();
      expect(screen.getByText(/Medium Severity/i)).toBeInTheDocument();
      expect(screen.getByText(/High Severity/i)).toBeInTheDocument();
      expect(screen.getByText(/Critical Severity/i)).toBeInTheDocument();

      // Top Hazardous Drug Pairs Table
      expect(screen.getByText(/Top Blocked Dangerous Drug-Drug Interactions/i)).toBeInTheDocument();
      expect(screen.getByText("Simvastatin + Clarithromycin (CYP3A4)")).toBeInTheDocument();
      expect(screen.getByText("Warfarin + NSAIDs / Aspirin")).toBeInTheDocument();
      expect(screen.getByText("Sildenafil + Nitroglycerin / Isosorbide")).toBeInTheDocument();
      expect(screen.getByText("Methotrexate + Trimethoprim/Sulfamethoxazole")).toBeInTheDocument();
    });

    it("renders per-tier latency percentiles and router confidence in role-gated telemetry", async () => {
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      expect(screen.getByTestId("clinical-pipeline-telemetry")).toBeInTheDocument();
      expect(screen.getAllByText(/Per-Tier Latency Percentiles/i).length).toBeGreaterThan(0);
      expect(screen.getByText("115 ms")).toBeInTheDocument();
      expect(screen.getByText("270 ms")).toBeInTheDocument();
      expect(screen.getByText("480 ms")).toBeInTheDocument();
      expect(screen.getByText(/Router Intent & Role Confidence/i)).toBeInTheDocument();
    });

    it("opens technical inspector drawer when clicking a hazardous drug pair row in Clinical Analytics", async () => {
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      const pairRow = screen.getByText("Sildenafil + Nitroglycerin / Isosorbide");
      fireEvent.click(pairRow);

      await waitFor(() => {
        expect(
          screen.getByText(/Drug Interaction Hazard: Sildenafil \+ Nitroglycerin/i)
        ).toBeInTheDocument();
        expect(screen.getByText(/Combination Profile/i)).toBeInTheDocument();
        expect(screen.getByText(/CRITICAL SAFETY/i)).toBeInTheDocument();
        expect(screen.getAllByText(/AHA\/ACC Heart Guidelines/i).length).toBeGreaterThan(0);
      });

      // Close inspector
      const closeBtn = screen.getByRole("button", { name: /Close/i });
      fireEvent.click(closeBtn);
    });

    it("blocks non-admin users from accessing Clinical Analytics page (403 defense-in-depth)", async () => {
      roleState.role = "normal";
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.getByText(/Access Denied \(403\)/i)).toBeInTheDocument();
      });

      expect(mockGetClinicalAnalytics).not.toHaveBeenCalled();
    });

    it("renders Clinical Analytics in Vietnamese when clara_ui_language is vi", async () => {
      window.localStorage.setItem("clara_ui_language", "vi");
      render(<AdminClinicalAnalyticsPage />);

      await waitFor(() => {
        expect(mockGetClinicalAnalytics).toHaveBeenCalled();
      });

      expect(screen.getAllByText(/Phân tích lâm sàng/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/Claim CRITICAL bị chặn/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Phân bố phán quyết FIDES/i).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Phân bố mức độ tương tác \(DDI\)/i).length).toBeGreaterThan(0);
      expect(
        screen.getByText(/Cặp tương tác thuốc nguy hiểm bị FIDES khóa chặn/i)
      ).toBeInTheDocument();
    });
  });
});
