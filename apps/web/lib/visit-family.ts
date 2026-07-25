import api from "@/lib/http-client";

export type Visit = {
  id: string;
  title: string;
  goal: string;
  visit_type: string;
  scheduled_at: string | null;
  status: string;
};

export type VisitPack = {
  id: string;
  version_no: number;
  status: string;
};

export type VisitShare = {
  id: string;
  token: string;
  expires_at: string;
};

export type FamilyGrant = {
  id: string;
  grantee_user_id?: string;
  profile_id?: string;
  object_type: "episode" | "care_task" | "visit" | string;
  object_id: number;
  allowed_actions: string[];
  purpose: string;
  status?: string;
  expires_at: string;
  grant_version?: number;
};

export type FamilyAccessLog = {
  id: string;
  actor_user_id: string | null;
  object_type: string;
  object_id: number;
  action: string;
  outcome: string;
  purpose: string;
  created_at: string;
};

export async function listVisits(): Promise<Visit[]> {
  return (await api.get<Visit[]>("/visits")).data;
}

export async function createVisit(input: {
  title: string;
  goal: string;
  visit_type: string;
  scheduled_at?: string;
}): Promise<Visit> {
  return (await api.post<Visit>("/visits", input)).data;
}

export async function addVisitConcern(
  visitId: string,
  text: string,
  priority: string,
): Promise<void> {
  await api.post(`/visits/${encodeURIComponent(visitId)}/concerns`, { text, priority });
}

export async function createVisitPack(
  visitId: string,
  selection: Record<string, boolean>,
): Promise<VisitPack> {
  return (
    await api.post<VisitPack>(`/visits/${encodeURIComponent(visitId)}/pack`, {
      selection,
    })
  ).data;
}

export async function approveVisitPack(packId: string): Promise<VisitPack> {
  return (await api.post<VisitPack>(`/visit-packs/${encodeURIComponent(packId)}/approve`)).data;
}

export async function shareVisitPack(packId: string, expiresAt: string): Promise<VisitShare> {
  return (
    await api.post<VisitShare>(`/visit-packs/${encodeURIComponent(packId)}/shares`, {
      expires_at: expiresAt,
    })
  ).data;
}

export async function grantVisitScribeConsent(visitId: string): Promise<void> {
  await api.post(`/visits/${encodeURIComponent(visitId)}/scribe-consents`, {
    purpose: "scribe_recording",
    policy_version: "visit-scribe-v1",
  });
}

export async function revokeVisitScribeConsent(visitId: string): Promise<void> {
  await api.delete(
    `/visits/${encodeURIComponent(visitId)}/scribe-consents/scribe_recording`,
  );
}

export async function listFamilyGrants(): Promise<FamilyGrant[]> {
  return (await api.get<FamilyGrant[]>("/family/access-grants")).data;
}

export async function listFamilyRelationships(): Promise<FamilyGrant[]> {
  return (await api.get<FamilyGrant[]>("/family/relationships")).data;
}

export async function listFamilyAccessLog(): Promise<FamilyAccessLog[]> {
  return (await api.get<FamilyAccessLog[]>("/family/access-log")).data;
}

export async function createFamilyInvitation(input: {
  recipient_email: string;
  scope: {
    object_type: "episode" | "care_task" | "visit";
    object_id: number;
    allowed_actions: string[];
  };
  purpose: "care_coordination" | "visit_support";
  expires_at: string;
}): Promise<{ id: string; token: string; expires_at: string }> {
  return (await api.post("/family/invitations", input)).data;
}

export async function acceptFamilyInvitation(token: string): Promise<FamilyGrant> {
  return (
    await api.post<FamilyGrant>(
      `/family/invitations/${encodeURIComponent(token)}/accept`,
    )
  ).data;
}

export async function revokeFamilyGrant(grantId: string): Promise<void> {
  await api.delete(`/family/access-grants/${encodeURIComponent(grantId)}`);
}
