import api from "@/lib/http-client";
import type { UserRole } from "@/lib/auth-store";

export type ExperimentCategory =
  | "ai_systems"
  | "clinical"
  | "platform"
  | "consumer"
  | "safety_invariant";

export type ExperimentStatus =
  | "active"
  | "gradual_rollout"
  | "paused"
  | "inactive"
  | "killed";

export interface ExperimentVariant {
  id: string;
  name: string;
  weight: number; // percentage 0-100
  description: string;
}

export interface ExperimentMetrics {
  totalEvaluations: number;
  treatmentImpressions: number;
  controlImpressions: number;
  errorRate: number; // 0.0 - 1.0
  latencyP95Ms: number;
  sampleSize?: number;
}

export interface FeatureFlagExperiment {
  id: string;
  key: string;
  name: string;
  nameVi: string;
  description: string;
  descriptionVi: string;
  category: ExperimentCategory;
  status: ExperimentStatus;
  rolloutPercentage: number; // 0 to 100
  targetRoles: UserRole[];
  targetCohorts: string[];
  matchMode?: "any" | "all";
  killSwitchActive: boolean;
  killSwitchReason?: string;
  killSwitchedAt?: string;
  killSwitchedBy?: string;
  isSafetyInvariant?: boolean; // Under ANA-005: locked, cannot be disabled
  variants?: ExperimentVariant[];
  metrics?: ExperimentMetrics;
  createdAt: string;
  updatedAt: string;
  updatedBy: string;
}

export interface ExperimentStats {
  totalFlags: number;
  activeRollouts: number;
  fullyEnabled: number;
  killSwitched: number;
  safetyInvariants: number;
}

export const AVAILABLE_COHORTS = [
  { id: "beta_testers", labelVi: "Nhóm Beta Testers", labelEn: "Beta Testers" },
  { id: "internal_clinicians", labelVi: "Bác sĩ Nội bộ CLARA", labelEn: "Internal Clinicians" },
  { id: "vietnam_hospitals", labelVi: "Bệnh viện đối tác VN", labelEn: "Vietnam Partner Hospitals" },
  { id: "mobile_canary", labelVi: "Người dùng Canary Di động", labelEn: "Mobile Canary Users" },
  { id: "general_users", labelVi: "Người dùng Toàn bộ", labelEn: "General Users" },
  { id: "canary_nodes", labelVi: "Hạ tầng Node Thử nghiệm", labelEn: "Canary Nodes" },
];

export const DEFAULT_EXPERIMENTS: FeatureFlagExperiment[] = [
  {
    id: "exp-graphrag",
    key: "rag_graphrag_pipeline",
    name: "GraphRAG Multi-Hop Knowledge Retrieval",
    nameVi: "Truy xuất Đồ thị Tri thức Đa bước GraphRAG",
    description: "Multi-hop knowledge graph expansion for complex clinical inquiries across medical literature.",
    descriptionVi: "Mở rộng đồ thị tri thức đa bước cho các câu hỏi lâm sàng phức tạp dựa trên y văn.",
    category: "ai_systems",
    status: "gradual_rollout",
    rolloutPercentage: 35,
    targetRoles: ["admin", "doctor", "researcher"],
    targetCohorts: ["beta_testers", "vietnam_hospitals"],
    matchMode: "any",
    killSwitchActive: false,
    variants: [
      { id: "treatment-a", name: "Multi-Hop Triplet Graph", weight: 35, description: "Full entity relation extraction" },
      { id: "control", name: "Standard Dense Vector", weight: 65, description: "Standard dense embedding retrieval" },
    ],
    metrics: {
      totalEvaluations: 14250,
      treatmentImpressions: 4980,
      controlImpressions: 9270,
      errorRate: 0.008,
      latencyP95Ms: 412,
    },
    createdAt: "2026-03-01T08:00:00Z",
    updatedAt: "2026-04-10T14:30:00Z",
    updatedBy: "lead-engineer@clara.vn",
  },
  {
    id: "exp-nli-v2",
    key: "nli_deep_verifier_v2",
    name: "NLI Deep Claim Verification v2",
    nameVi: "Kiểm chứng Luận điểm NLI Chuyên sâu v2",
    description: "Secondary NLI cross-encoder model scoring fine-grained claim-evidence contradiction.",
    descriptionVi: "Mô hình NLI cross-encoder tầng 2 chấm điểm mâu thuẫn giữa luận điểm và bằng chứng.",
    category: "ai_systems",
    status: "active",
    rolloutPercentage: 100,
    targetRoles: ["admin", "doctor", "researcher", "normal"],
    targetCohorts: ["general_users"],
    matchMode: "any",
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 48920,
      treatmentImpressions: 48920,
      controlImpressions: 0,
      errorRate: 0.002,
      latencyP95Ms: 185,
    },
    createdAt: "2026-02-15T09:00:00Z",
    updatedAt: "2026-04-05T11:20:00Z",
    updatedBy: "ai-safety@clara.vn",
  },
  {
    id: "exp-scribe-filter",
    key: "scribe_ambient_noise_filter",
    name: "Scribe Ambient Clinical Noise Filter",
    nameVi: "Bộ lọc Tiếng ồn Môi trường Lâm sàng Scribe",
    description: "Neural acoustic noise suppression for hospital ambient recording environments.",
    descriptionVi: "Khử nhiễu âm học thần kinh cho môi trường ghi âm hội chẩn tại bệnh viện.",
    category: "clinical",
    status: "gradual_rollout",
    rolloutPercentage: 50,
    targetRoles: ["doctor", "admin"],
    targetCohorts: ["internal_clinicians", "vietnam_hospitals"],
    matchMode: "all",
    killSwitchActive: false,
    variants: [
      { id: "treatment", name: "Spectral Gate + RNN", weight: 50, description: "Real-time acoustic gating" },
      { id: "control", name: "Raw Audio Pass", weight: 50, description: "Direct Whisper ASR input" },
    ],
    metrics: {
      totalEvaluations: 3840,
      treatmentImpressions: 1920,
      controlImpressions: 1920,
      errorRate: 0.012,
      latencyP95Ms: 290,
    },
    createdAt: "2026-03-20T10:00:00Z",
    updatedAt: "2026-04-12T16:45:00Z",
    updatedBy: "scribe-team@clara.vn",
  },
  {
    id: "exp-council-consensus",
    key: "council_multi_agent_consensus",
    name: "Council Multi-Agent Consensus Protocol",
    nameVi: "Giao thức Đồng thuận Hội đồng Đa Chuyên gia",
    description: "Parallel multi-specialist debate loop for high-complexity diagnostic synthesis.",
    descriptionVi: "Vòng tranh biện song song giữa nhiều chuyên gia cho ca bệnh phức tạp.",
    category: "clinical",
    status: "paused",
    rolloutPercentage: 10,
    targetRoles: ["doctor", "admin"],
    targetCohorts: ["internal_clinicians"],
    matchMode: "all",
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 820,
      treatmentImpressions: 82,
      controlImpressions: 738,
      errorRate: 0.024,
      latencyP95Ms: 1450,
    },
    createdAt: "2026-03-10T12:00:00Z",
    updatedAt: "2026-04-08T09:15:00Z",
    updatedBy: "council-lead@clara.vn",
  },
  {
    id: "exp-lifemap-reminders",
    key: "lifemap_predictive_adherence",
    name: "LifeMap Predictive Adherence Engine",
    nameVi: "Động cơ Dự đoán Tuân thủ Liệu trình LifeMap",
    description: "Adaptive notification scheduler predicting medication refill and dosage adherence.",
    descriptionVi: "Bộ lập lịch nhắc nhở thích ứng dự đoán thời điểm uống thuốc và mua thêm thuốc.",
    category: "consumer",
    status: "gradual_rollout",
    rolloutPercentage: 25,
    targetRoles: ["normal", "admin"],
    targetCohorts: ["beta_testers", "mobile_canary"],
    matchMode: "any",
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 8900,
      treatmentImpressions: 2225,
      controlImpressions: 6675,
      errorRate: 0.005,
      latencyP95Ms: 85,
    },
    createdAt: "2026-03-25T14:00:00Z",
    updatedAt: "2026-04-14T10:00:00Z",
    updatedBy: "phr-platform@clara.vn",
  },
  {
    id: "exp-ocr-normalization",
    key: "phr_smart_ocr_normalization",
    name: "PHR Smart Drug Label OCR Normalization",
    nameVi: "Chuẩn hóa Nhãn thuốc OCR Thông minh PHR",
    description: "Vietnamese pharmacist shorthand extraction and dosage frequency parser.",
    descriptionVi: "Trích xuất chữ viết tắt toa thuốc tiếng Việt và phân tích tần suất liều dùng.",
    category: "consumer",
    status: "active",
    rolloutPercentage: 80,
    targetRoles: ["normal", "doctor", "admin"],
    targetCohorts: ["general_users"],
    matchMode: "any",
    killSwitchActive: false,
    metrics: {
      totalEvaluations: 16400,
      treatmentImpressions: 13120,
      controlImpressions: 3280,
      errorRate: 0.015,
      latencyP95Ms: 560,
    },
    createdAt: "2026-02-28T11:00:00Z",
    updatedAt: "2026-04-11T13:20:00Z",
    updatedBy: "vision-team@clara.vn",
  },
  {
    id: "exp-db-pool",
    key: "platform_dynamic_connection_pool",
    name: "Platform Dynamic Async DB Pool",
    nameVi: "Bộ gom Kết nối Cơ sở Dữ liệu Động",
    description: "Adaptive connection burst allocation for PostgreSQL during peak clinical hours.",
    descriptionVi: "Phân bổ kết nối PostgreSQL linh hoạt theo tải giờ cao điểm lâm sàng.",
    category: "platform",
    status: "inactive",
    rolloutPercentage: 0,
    targetRoles: ["admin"],
    targetCohorts: ["canary_nodes"],
    matchMode: "all",
    killSwitchActive: false,
    createdAt: "2026-04-01T09:00:00Z",
    updatedAt: "2026-04-01T09:00:00Z",
    updatedBy: "infra@clara.vn",
  },
  {
    id: "exp-fides-gate",
    key: "fides_critical_ddi_blocking",
    name: "FIDES Critical Drug-DDI Blocking (Safety Invariant)",
    nameVi: "Khóa Chặn Tương tác Thuốc Nguy hiểm FIDES (Bất biến An toàn)",
    description: "Regression-locked invariant blocking critical contraindicated drug-drug interactions (ANA-005).",
    descriptionVi: "Bất biến khóa hồi quy tự động chặn các tương tác thuốc chống chỉ định nghiêm trọng (ANA-005).",
    category: "safety_invariant",
    status: "active",
    rolloutPercentage: 100,
    targetRoles: ["admin", "doctor", "researcher", "normal"],
    targetCohorts: ["general_users"],
    matchMode: "any",
    killSwitchActive: false,
    isSafetyInvariant: true,
    metrics: {
      totalEvaluations: 65400,
      treatmentImpressions: 65400,
      controlImpressions: 0,
      errorRate: 0.000,
      latencyP95Ms: 45,
    },
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    updatedBy: "safety-board@clara.vn",
  },
  {
    id: "exp-emergency-115",
    key: "emergency_115_fast_path",
    name: "Emergency 115 Fast-Path Triage (Safety Invariant)",
    nameVi: "Điều hướng Cấp cứu 115 Tức thì (Bất biến An toàn)",
    description: "Deterministic bypass directly presenting 115 escalation for acute medical symptoms (ANA-005).",
    descriptionVi: "Nhánh điều hướng tất định chuyển thẳng số cấp cứu 115 khi phát hiện triệu chứng nguy kịch.",
    category: "safety_invariant",
    status: "active",
    rolloutPercentage: 100,
    targetRoles: ["admin", "doctor", "researcher", "normal"],
    targetCohorts: ["general_users"],
    matchMode: "any",
    killSwitchActive: false,
    isSafetyInvariant: true,
    metrics: {
      totalEvaluations: 24300,
      treatmentImpressions: 24300,
      controlImpressions: 0,
      errorRate: 0.000,
      latencyP95Ms: 12,
    },
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    updatedBy: "safety-board@clara.vn",
  },
];

let inMemoryExperiments: FeatureFlagExperiment[] = JSON.parse(JSON.stringify(DEFAULT_EXPERIMENTS));

export async function listExperiments(): Promise<FeatureFlagExperiment[]> {
  try {
    const response = await api.get<FeatureFlagExperiment[]>("/admin/experiments");
    if (response.data && Array.isArray(response.data)) {
      inMemoryExperiments = response.data;
      return response.data;
    }
  } catch {
    // Fall back to in-memory store for offline/isolated runtime
  }
  return [...inMemoryExperiments];
}

export async function updateExperiment(
  id: string,
  updates: Partial<FeatureFlagExperiment>
): Promise<FeatureFlagExperiment> {
  const index = inMemoryExperiments.findIndex((e) => e.id === id);
  if (index === -1) {
    throw new Error(`Experiment ${id} not found`);
  }

  const existing = inMemoryExperiments[index];
  if (existing.isSafetyInvariant && (updates.rolloutPercentage !== undefined && updates.rolloutPercentage < 100)) {
    throw new Error("Safety invariant flags cannot have rollout reduced below 100% (ANA-005).");
  }
  if (existing.isSafetyInvariant && updates.killSwitchActive === true) {
    throw new Error("Safety invariants cannot be kill-switched (ANA-005).");
  }

  const updated: FeatureFlagExperiment = {
    ...existing,
    ...updates,
    updatedAt: new Date().toISOString(),
  };

  // Adjust status according to rollout percentage & kill switch
  if (updated.killSwitchActive) {
    updated.status = "killed";
  } else if (updated.rolloutPercentage === 0) {
    updated.status = "inactive";
  } else if (updated.rolloutPercentage === 100) {
    updated.status = "active";
  } else {
    updated.status = "gradual_rollout";
  }

  inMemoryExperiments[index] = updated;

  try {
    const response = await api.put<FeatureFlagExperiment>(`/admin/experiments/${encodeURIComponent(id)}`, updated);
    if (response.data) {
      inMemoryExperiments[index] = response.data;
      return response.data;
    }
  } catch {
    // Fall back to local memory store
  }

  return updated;
}

export async function overrideKillSwitch(
  id: string,
  kill: boolean,
  reason?: string
): Promise<FeatureFlagExperiment> {
  const index = inMemoryExperiments.findIndex((e) => e.id === id);
  if (index === -1) {
    throw new Error(`Experiment ${id} not found`);
  }

  const existing = inMemoryExperiments[index];
  if (existing.isSafetyInvariant) {
    throw new Error("Cannot override kill switch on locked safety invariant (ANA-005).");
  }

  const updated: FeatureFlagExperiment = {
    ...existing,
    killSwitchActive: kill,
    killSwitchReason: kill ? reason || "Manual Admin Emergency Kill" : undefined,
    killSwitchedAt: kill ? new Date().toISOString() : undefined,
    killSwitchedBy: kill ? "admin@clara.vn" : undefined,
    status: kill ? "killed" : existing.rolloutPercentage === 100 ? "active" : existing.rolloutPercentage > 0 ? "gradual_rollout" : "inactive",
    updatedAt: new Date().toISOString(),
  };

  inMemoryExperiments[index] = updated;

  try {
    const response = await api.post<FeatureFlagExperiment>(
      `/admin/experiments/${encodeURIComponent(id)}/kill`,
      { kill, reason }
    );
    if (response.data) {
      inMemoryExperiments[index] = response.data;
      return response.data;
    }
  } catch {
    // Fall back to local memory store
  }

  return updated;
}

export function calculateExperimentStats(experiments: FeatureFlagExperiment[]): ExperimentStats {
  let activeRollouts = 0;
  let fullyEnabled = 0;
  let killSwitched = 0;
  let safetyInvariants = 0;

  for (const exp of experiments) {
    if (exp.isSafetyInvariant) {
      safetyInvariants++;
    }
    if (exp.killSwitchActive) {
      killSwitched++;
    } else if (exp.rolloutPercentage === 100) {
      fullyEnabled++;
    } else if (exp.rolloutPercentage > 0) {
      activeRollouts++;
    }
  }

  return {
    totalFlags: experiments.length,
    activeRollouts,
    fullyEnabled,
    killSwitched,
    safetyInvariants,
  };
}

export function resetInMemoryExperiments(): void {
  inMemoryExperiments = JSON.parse(JSON.stringify(DEFAULT_EXPERIMENTS));
}
