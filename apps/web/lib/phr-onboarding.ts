import api from "@/lib/http-client";
import type {
  PhrAllergyItem,
  PhrConditionItem,
  PhrMedicationItem,
  PhrRecord,
} from "@/lib/phr";

export type PhrOnboardingStatus = "pending" | "completed" | "skipped";

export type PhrOnboarding = {
  status: PhrOnboardingStatus;
  needs_onboarding: boolean;
  version: number;
  completed_at: string | null;
  personalization_consent: boolean;
  optional_fields: string[];
  record: PhrRecord;
};

export type PhrOnboardingPatch = {
  action: "save" | "complete" | "skip";
  confirm_self_declared?: boolean;
  personalization_consent?: boolean | null;
  full_name?: string;
  date_of_birth?: string | null;
  gender?: string;
  blood_type?: string;
  height_cm?: number | null;
  weight_kg?: number | null;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  allergies?: PhrAllergyItem[];
  conditions?: PhrConditionItem[];
  medications?: PhrMedicationItem[];
};

export async function getPhrOnboarding(): Promise<PhrOnboarding> {
  const { data } = await api.get<PhrOnboarding>("/api/v1/phr/onboarding");
  return data;
}

export async function updatePhrOnboarding(
  payload: PhrOnboardingPatch,
): Promise<PhrOnboarding> {
  const { data } = await api.patch<PhrOnboarding>(
    "/api/v1/phr/onboarding",
    payload,
  );
  return data;
}
