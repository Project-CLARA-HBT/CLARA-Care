import api from "@/lib/http-client";

export type VisitPrescription = {
  id: string;
  name: string;
  dosage?: string;
  instruction?: string;
  reconciliation_status?: "continued" | "new" | "adjusted" | "discontinued" | string;
};

export type VisitLabOrder = {
  id: string;
  title: string;
  status?: string;
  result_summary?: string;
};

export type DoctorSoapNote = {
  subjective?: string;
  objective?: string;
  assessment?: string;
  plan?: string;
  icd10_codes?: Array<{ code: string; label: string }>;
  clinician_name?: string;
  signed_at?: string;
};

export type VisitFollowUpTask = {
  id: string;
  title: string;
  due_date?: string;
  completed?: boolean;
  priority?: "routine" | "high" | "urgent";
};

export type Visit = {
  id: string;
  title: string;
  goal: string;
  visit_type: string;
  scheduled_at: string | null;
  status: string;
  doctor_name?: string | null;
  specialty?: string | null;
  facility_name?: string | null;
  location?: string | null;
  prep_status?: "not_started" | "in_progress" | "ready" | "completed" | string;
  notes?: string | null;
  clinician_notes?: string | null;
  soap_note?: DoctorSoapNote | null;
  questions?: string[];
  questions_count?: number;
  prescriptions?: VisitPrescription[];
  lab_orders?: VisitLabOrder[];
  documents?: VisitDocument[];
  follow_up_tasks?: VisitFollowUpTask[];
  created_at?: string;
  updated_at?: string;
};

export type VisitPack = {
  id: string;
  version_no: number;
  status: string;
};

export type VisitPackOption = {
  id: string;
  label: string;
  status?: string;
  priority?: string;
  occurred_at?: string;
};

export type VisitPackOptions = {
  concerns: VisitPackOption[];
  episodes: VisitPackOption[];
  events: VisitPackOption[];
  medications: VisitPackOption[];
  instructions: VisitPackOption[];
};

export type VisitShare = {
  id: string;
  token: string;
  expires_at: string;
};

export type VisitIntakeQuestion = {
  key: string;
  text: string;
  reason: string;
};

export type VisitIntakeResult = {
  id: string;
  question_key: string;
  response_state: "answered" | "skipped" | "unknown";
  progress: { answered: number; total: number };
  next_question: VisitIntakeQuestion | null;
  complete: boolean;
};

export type VisitDocument = {
  id: string;
  title: string;
  document_kind: string;
  media_type: string;
  status: string;
  content_digest: string;
  metadata: Record<string, unknown>;
  text_content: string | null;
  provenance: Record<string, unknown>;
  withdrawn_at: string | null;
  deleted_at: string | null;
};

export type VisitPlanCandidate = {
  id: string;
  text?: string;
  source_span?: string;
  source_spans?: Array<{
    page?: number | null;
    region?: number[] | null;
    start: number;
    end: number;
    text: string;
  }>;
  confidence?: number;
  classification?: "clinician_instruction" | "model_interpretation";
  kind?: string;
  [key: string]: unknown;
};

export type VisitPlanDraft = {
  id: string;
  status: string;
  extraction_provider: string;
  candidates: VisitPlanCandidate[];
  safe_unavailable: boolean;
  reason?: string;
};

export type VisitPlanConfirmation = {
  id: string;
  status: string;
  task_ids: string[];
  task_status: string;
  episode_event_ids: string[];
};

export type FamilyGrant = {
  id: string;
  supporter_label?: string;
  profile_id?: string;
  object_type: "episode" | "care_task" | "visit" | string;
  object_id: string;
  allowed_actions: string[];
  purpose: string;
  status?: string;
  expires_at: string;
  grant_version?: number;
  starts_at?: string;
  revoked_at?: string | null;
};

export type FamilyAccessLog = {
  id: string;
  /** Legacy Vietnamese label retained by the API for older clients. */
  actor_label: string;
  /** Stable locale-neutral presentation code; absent only with older APIs. */
  actor_code?: "owner" | "supporter" | "system" | string;
  object_type: string;
  object_id: string;
  /** Legacy append-only audit action retained for compatibility. */
  action: string;
  /** Bounded locale-neutral rendering code. */
  action_code?: string;
  /** Legacy audit outcome retained for compatibility. */
  outcome: string;
  /** Bounded locale-neutral rendering code. */
  outcome_code?: "allowed" | "denied" | "failed" | "unknown" | string;
  purpose: string;
  created_at: string;
};

export type FamilyNotification = {
  id: string;
  kind: "delegated_care_task" | string;
  profile_id: string;
  task_id: string;
  purpose: string;
  expires_at: string;
  action: "complete_task" | string;
  message: string;
};

export async function listVisits(): Promise<Visit[]> {
  return (await api.get<Visit[]>("/visits")).data;
}

export async function getVisit(visitId: string): Promise<Visit> {
  return (await api.get<Visit>(`/visits/${encodeURIComponent(visitId)}`)).data;
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

export async function answerVisitIntake(
  visitId: string,
  input: {
    question_key: string;
    response_state: "answered" | "skipped" | "unknown";
    answer_text?: string;
  },
): Promise<VisitIntakeResult> {
  return (
    await api.post<VisitIntakeResult>(
      `/visits/${encodeURIComponent(visitId)}/intake/answers`,
      input,
    )
  ).data;
}

export async function listVisitDocuments(visitId: string): Promise<VisitDocument[]> {
  return (await api.get<VisitDocument[]>(`/visits/${encodeURIComponent(visitId)}/documents`))
    .data;
}

export async function createVisitDocument(
  visitId: string,
  input: {
    title: string;
    text_content?: string;
    media_type?: string;
    metadata?: Record<string, unknown>;
    scribe_session_id?: number;
  },
): Promise<VisitDocument> {
  return (
    await api.post<VisitDocument>(`/visits/${encodeURIComponent(visitId)}/documents`, {
      ...input,
      media_type: input.media_type ?? "text/plain",
      metadata: input.metadata ?? {},
    })
  ).data;
}

export async function withdrawVisitDocument(
  visitId: string,
  documentId: string,
  reason = "owner_withdrew",
): Promise<VisitDocument> {
  return (
    await api.post<VisitDocument>(
      `/visits/${encodeURIComponent(visitId)}/documents/${encodeURIComponent(documentId)}/withdraw`,
      { reason },
    )
  ).data;
}

export async function deleteVisitDocument(
  visitId: string,
  documentId: string,
  reason = "owner_requested_deletion",
): Promise<VisitDocument> {
  return (
    await api.delete<VisitDocument>(
      `/visits/${encodeURIComponent(visitId)}/documents/${encodeURIComponent(documentId)}`,
      { data: { reason } },
    )
  ).data;
}

export async function extractVisitPlan(
  visitId: string,
  documentId: string,
): Promise<VisitPlanDraft> {
  return (
    await api.post<VisitPlanDraft>(`/visits/${encodeURIComponent(visitId)}/plan/extract`, {
      document_id: documentId,
    })
  ).data;
}

export async function withdrawVisitPlan(
  visitId: string,
  draftId: string,
  reason = "owner_withdrew",
): Promise<{ id: string; status: string; withdrawn_at: string | null }> {
  return (
    await api.post(
      `/visits/${encodeURIComponent(visitId)}/plan/${encodeURIComponent(draftId)}/withdraw`,
      { reason },
    )
  ).data;
}

export async function confirmVisitPlan(
  visitId: string,
  input: {
    draft_id: string;
    candidate_ids: string[];
    task_status?: string;
    episode_id?: string;
  },
): Promise<VisitPlanConfirmation> {
  return (
    await api.post<VisitPlanConfirmation>(
      `/visits/${encodeURIComponent(visitId)}/plan/confirm`,
      input,
    )
  ).data;
}

export async function createVisitPack(
  visitId: string,
  selection: {
    concern_ids: string[];
    episode_ids: string[];
    event_ids: string[];
    medication_course_ids: string[];
    instruction_candidate_ids: string[];
    questions: string[];
  },
): Promise<VisitPack> {
  return (
    await api.post<VisitPack>(`/visits/${encodeURIComponent(visitId)}/pack`, {
      selection,
    })
  ).data;
}

export async function getVisitPackOptions(visitId: string): Promise<VisitPackOptions> {
  return (
    await api.get<VisitPackOptions>(
      `/visits/${encodeURIComponent(visitId)}/pack-options`,
    )
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

export async function revokeVisitShare(packId: string, shareId: string): Promise<void> {
  await api.delete(
    `/visit-packs/${encodeURIComponent(packId)}/shares/${encodeURIComponent(shareId)}`,
  );
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

export async function listFamilyNotifications(): Promise<FamilyNotification[]> {
  return (await api.get<FamilyNotification[]>("/family/notifications")).data;
}

export async function acknowledgeFamilyNotification(
  grantId: string,
  taskId: string,
  purpose: string,
): Promise<void> {
  await api.post(
    `/family/notifications/${encodeURIComponent(grantId)}/${encodeURIComponent(taskId)}/acknowledge`,
    { purpose },
  );
}

export async function listFamilyAccessLog(): Promise<FamilyAccessLog[]> {
  return (await api.get<FamilyAccessLog[]>("/family/access-log")).data;
}

export async function createFamilyInvitation(input: {
  recipient_email: string;
  scope: {
    object_type: "episode" | "care_task" | "visit";
    object_id: string;
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
      "/family/invitations/accept",
      undefined,
      { headers: { "X-Family-Invitation-Token": token } },
    )
  ).data;
}

export type FamilyInvitationPreview = {
  object_type: "episode" | "care_task" | "visit" | string;
  allowed_actions: string[];
  purpose: "care_coordination" | "visit_support" | string;
  expires_at: string;
};

export async function previewFamilyInvitation(token: string): Promise<FamilyInvitationPreview> {
  return (
    await api.post<FamilyInvitationPreview>(
      "/family/invitations/preview",
      undefined,
      { headers: { "X-Family-Invitation-Token": token } },
    )
  ).data;
}

export async function revokeFamilyGrant(grantId: string): Promise<void> {
  await api.delete(`/family/access-grants/${encodeURIComponent(grantId)}`);
}

export type FamilyShareOptions = {
  episodes: Array<{ id: string; label: string }>;
  visits: Array<{ id: string; label: string }>;
  care_tasks: Array<{ id: string; label: string }>;
};

export async function getFamilyShareOptions(): Promise<FamilyShareOptions> {
  return (await api.get<FamilyShareOptions>("/family/share-options")).data;
}

export async function renewFamilyGrant(
  grantId: string,
  expiresAt: string,
): Promise<{ id: string; token: string; expires_at: string }> {
  return (
    await api.post(
      `/family/access-grants/${encodeURIComponent(grantId)}/renewals`,
      { expires_at: expiresAt },
    )
  ).data;
}
