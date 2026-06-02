import api from "@/lib/http-client";

export type ConsentStatus = {
  consent_type: string;
  required_version: string;
  accepted: boolean;
  user_id?: number;
  accepted_version?: string | null;
  accepted_at?: string | null;
};

export type ConsentAcceptPayload = {
  consent_version: string;
  accepted: boolean;
};

export async function getConsentStatus(): Promise<ConsentStatus> {
  const response = await api.get<ConsentStatus>("/auth/consent-status");
  return response.data;
}

export async function acceptConsent(payload: ConsentAcceptPayload): Promise<void> {
  await api.post("/auth/consent", payload);
}
