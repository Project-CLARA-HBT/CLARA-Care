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
  resourceVersion?: string;
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

export interface CreateExperimentPayload {
  key: string;
  name: string;
  nameVi?: string;
  description?: string;
  descriptionVi?: string;
  category?: ExperimentCategory;
  rolloutPercentage?: number;
  targetRoles?: UserRole[];
  targetCohorts?: string[];
  safetyOwner?: string;
  isSafetyInvariant?: boolean;
}

export const AVAILABLE_COHORTS = [
  { id: "beta_testers", labelVi: "Nhóm Beta Testers", labelEn: "Beta Testers" },
  { id: "internal_clinicians", labelVi: "Bác sĩ Nội bộ CLARA", labelEn: "Internal Clinicians" },
  { id: "vietnam_hospitals", labelVi: "Bệnh viện đối tác VN", labelEn: "Vietnam Partner Hospitals" },
  { id: "mobile_canary", labelVi: "Người dùng Canary Di động", labelEn: "Mobile Canary Users" },
  { id: "general_users", labelVi: "Người dùng Toàn bộ", labelEn: "General Users" },
  { id: "canary_nodes", labelVi: "Hạ tầng Node Thử nghiệm", labelEn: "Canary Nodes" },
];

export function mapBackendExperimentToFrontend(e: any): FeatureFlagExperiment {
  if (!e) {
    throw new Error("Invalid experiment payload from server");
  }

  const rules = (typeof e.target_rules_json === "object" && e.target_rules_json !== null)
    ? e.target_rules_json
    : {};

  const rolloutPercentage = typeof e.rollout_basis_points === "number"
    ? Math.round(e.rollout_basis_points / 100)
    : (e.rolloutPercentage ?? 0);

  const isSafetyInvariant = Boolean(
    e.isSafetyInvariant ??
      rules.is_safety_invariant ??
      rules.isSafetyInvariant ??
      (
        (typeof e.key === "string" && (e.key === "fides_critical_ddi_blocking" || e.key === "emergency_115_fast_path")) ||
        rules.category === "safety_invariant" ||
        e.category === "safety_invariant"
      )
  );

  let status: ExperimentStatus = "inactive";
  if (e.status === "killed") {
    status = "killed";
  } else if (e.status === "running") {
    status = rolloutPercentage === 100 ? "active" : "gradual_rollout";
  } else if (e.status === "paused" || e.status === "draft") {
    status = rolloutPercentage > 0 ? "gradual_rollout" : "inactive";
  } else if (e.status === "active" || e.status === "gradual_rollout" || e.status === "inactive") {
    status = e.status;
  } else {
    status = rolloutPercentage === 100 ? "active" : rolloutPercentage > 0 ? "gradual_rollout" : "inactive";
  }

  return {
    id: String(e.id ?? e.key),
    key: e.key,
    name: e.name || e.key,
    nameVi: rules.name_vi || rules.nameVi || e.nameVi || e.name || e.key,
    description: e.description || "",
    descriptionVi: rules.description_vi || rules.descriptionVi || e.descriptionVi || e.description || "",
    category: (rules.category || e.category || (isSafetyInvariant ? "safety_invariant" : "ai_systems")) as ExperimentCategory,
    status,
    rolloutPercentage,
    targetRoles: rules.target_roles || rules.targetRoles || e.targetRoles || ["normal", "doctor", "researcher", "admin"],
    targetCohorts: rules.target_cohorts || rules.targetCohorts || e.targetCohorts || ["general_users"],
    matchMode: rules.match_mode || rules.matchMode || e.matchMode || "any",
    killSwitchActive: e.status === "killed" || Boolean(e.killSwitchActive),
    killSwitchReason: rules.kill_switch_reason || e.killSwitchReason,
    killSwitchedAt: rules.kill_switched_at || e.killSwitchedAt,
    killSwitchedBy: rules.kill_switched_by || e.killSwitchedBy,
    isSafetyInvariant,
    variants: rules.variants || e.variants,
    metrics: rules.metrics || e.metrics,
    resourceVersion: e.resource_version || e.resourceVersion,
    createdAt: e.created_at || e.createdAt || new Date().toISOString(),
    updatedAt: e.updated_at || e.updatedAt || new Date().toISOString(),
    updatedBy: e.safety_owner || e.updatedBy || "clara-safety",
  };
}

export async function listExperiments(statusFilter?: string): Promise<FeatureFlagExperiment[]> {
  const params: Record<string, string> = {};
  if (statusFilter && statusFilter !== "all") {
    params.status = statusFilter;
  }

  const response = await api.get<any[]>("/admin/experiments", { params });
  const rawList = Array.isArray(response.data) ? response.data : [];
  return rawList.map(mapBackendExperimentToFrontend);
}

export async function createExperiment(
  payload: CreateExperimentPayload,
): Promise<FeatureFlagExperiment> {
  const rolloutBasisPoints = Math.round((payload.rolloutPercentage ?? 0) * 100);

  const response = await api.post<any>("/admin/experiments", {
    key: payload.key,
    name: payload.name,
    description: payload.description || "",
    rollout_basis_points: rolloutBasisPoints,
    safety_owner: payload.safetyOwner || "clara-safety",
    target_rules_json: {
      name_vi: payload.nameVi,
      description_vi: payload.descriptionVi,
      category: payload.category,
      target_roles: payload.targetRoles,
      target_cohorts: payload.targetCohorts,
      is_safety_invariant: payload.isSafetyInvariant,
    },
  });

  return mapBackendExperimentToFrontend(response.data);
}

export async function updateExperiment(
  id: string | number,
  updates: Partial<FeatureFlagExperiment> & {
    expectedResourceVersion?: string;
    reasonCode?: string;
  },
): Promise<FeatureFlagExperiment> {
  if (updates.isSafetyInvariant && (updates.rolloutPercentage !== undefined && updates.rolloutPercentage < 100)) {
    throw new Error("Safety invariant flags cannot have rollout reduced below 100% (ANA-005).");
  }
  if (updates.isSafetyInvariant && updates.killSwitchActive === true) {
    throw new Error("Safety invariants cannot be kill-switched (ANA-005).");
  }

  const rolloutBasisPoints =
    updates.rolloutPercentage !== undefined
      ? Math.round(updates.rolloutPercentage * 100)
      : undefined;

  const response = await api.patch<any>(
    `/admin/experiments/${encodeURIComponent(String(id))}/rollout`,
    {
      rollout_basis_points: rolloutBasisPoints ?? 0,
      expected_resource_version: updates.expectedResourceVersion,
      reason_code: updates.reasonCode || "ADMIN_ROLLOUT_CHANGE",
    },
  );

  return mapBackendExperimentToFrontend(response.data);
}

export async function overrideKillSwitch(
  id: string | number,
  kill: boolean,
  reason?: string,
  expectedResourceVersion?: string,
): Promise<FeatureFlagExperiment> {
  if (kill) {
    const response = await api.post<any>(
      `/admin/experiments/${encodeURIComponent(String(id))}/kill`,
      {
        reason: reason || "EMERGENCY_KILL_SWITCH",
        expected_resource_version: expectedResourceVersion,
      },
    );
    return mapBackendExperimentToFrontend(response.data);
  }

  const response = await api.patch<any>(
    `/admin/experiments/${encodeURIComponent(String(id))}/rollout`,
    {
      rollout_basis_points: 0,
      expected_resource_version: expectedResourceVersion,
      reason_code: reason || "RESTORE_FROM_KILL_SWITCH",
    },
  );
  return mapBackendExperimentToFrontend(response.data);
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
    if (exp.killSwitchActive || exp.status === "killed") {
      killSwitched++;
    } else if (exp.rolloutPercentage === 100 || exp.status === "active") {
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
