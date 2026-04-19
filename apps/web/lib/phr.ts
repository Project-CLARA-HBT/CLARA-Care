import api from "@/lib/http-client";

export type PhrAllergyItem = {
  id: string;
  name: string;
  reaction: string;
  severity: "mild" | "moderate" | "severe" | "unknown";
  note: string;
};

export type PhrConditionItem = {
  id: string;
  name: string;
  status: "active" | "resolved" | "monitoring" | "unknown";
  diagnosed_on?: string | null;
  note: string;
};

export type PhrMedicationItem = {
  id: string;
  name: string;
  dose: string;
  frequency: string;
  started_on?: string | null;
  is_current: boolean;
  note: string;
};

export type PhrRecord = {
  full_name: string;
  date_of_birth?: string | null;
  gender: string;
  blood_type: string;
  height_cm?: number | null;
  weight_kg?: number | null;
  phone: string;
  address: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  insurance_id: string;
  notes: string;
  allergies: PhrAllergyItem[];
  conditions: PhrConditionItem[];
  medications: PhrMedicationItem[];
  created_at?: string | null;
  updated_at?: string | null;
};

export async function getPhrRecord(): Promise<PhrRecord> {
  const { data } = await api.get<PhrRecord>("/api/v1/phr/record");
  return data;
}

export async function updatePhrRecord(payload: PhrRecord): Promise<PhrRecord> {
  const { data } = await api.put<PhrRecord>("/api/v1/phr/record", payload);
  return data;
}
