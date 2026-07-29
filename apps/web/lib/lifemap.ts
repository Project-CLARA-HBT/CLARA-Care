import api from "@/lib/http-client";

export const LIFE_MAP_CLIENT_STATES = [
  "draft",
  "awaiting_review",
  "confirmed",
  "disputed",
  "stale",
  "unavailable",
  "offline",
] as const;

export type LifeMapClientState = (typeof LIFE_MAP_CLIENT_STATES)[number];

export type LifeMapClientContract = {
  version: string;
  states: Record<
    LifeMapClientState,
    {
      truth_authority: boolean;
      can_mutate: boolean;
      vi: string;
      en: string;
    }
  >;
  capabilities: Record<
    string,
    { enabled: boolean; mutation_policy: "online_only" }
  >;
  offline_policy: {
    mutations: "disabled";
    queued_health_mutations_supported: false;
    cached_safety_status_current: false;
    requires_encrypted_cache: true;
    requires_cached_at: true;
    requires_valid_until: true;
  };
};

export type LifeMapTask = {
  id: string;
  title: string;
  due_at: string | null;
};

export type LifeMapEpisode = {
  id: string;
  title: string;
  priority: "routine" | "soon" | "urgent" | string;
};

export type LifeMapToday = {
  generated_at: string;
  tasks: LifeMapTask[];
  episodes: LifeMapEpisode[];
  pending_confirmation_count: number;
};

export type LifeMapReplayEvent = {
  id: string;
  revision_id: string;
  revision: number;
  type: string;
  truth_state: string;
  occurred_at: string;
  provenance: Record<string, unknown>;
  source_reference: string | null;
  policy_version: string;
  why: { code: string; text: string };
};

export type LifeMapReplay = {
  episode: { id: string; title: string; status: string };
  events: LifeMapReplayEvent[];
  tasks: Array<{ id: string; title: string; status: string }>;
  decisions: Array<{
    id: string;
    type: string;
    disposition: string;
    policy_version: string;
    stale: boolean;
    why: { code: string; text: string };
  }>;
};

export type LifeMapDisputeCase = {
  id: string;
  event_id: string;
  event_type: string;
  disputed_revision_id: string;
  revision: number;
  requires_clinical_review: boolean;
  status: "open" | "resolved";
  resolution: {
    action: string;
    resolution_revision_id: string;
    created_at: string;
  } | null;
  created_at: string;
};

export type LifeMapBaseline = {
  id: string;
  signal_key: string;
  status: string;
  personal_median: number | null;
  median_absolute_deviation: number | null;
  unit: string;
  sample_days: number;
  span_days: number;
  minimum_days: number;
  window_days: number;
  rule_version: string;
  computed_at: string;
  stale: boolean;
  explanation: string;
};

export type LifeMapQuestion = {
  episode_id: string;
  ask: boolean;
  question_id?: string | null;
  field_key?: string | null;
  question?: string | null;
  why?: string | null;
  reason_code: string;
  policy_version: string;
};

export type LifeMapAskEvidence = {
  evidence_id: string;
  revision_id: string;
  event_id: string;
  event_type: string;
  occurred_at: string;
  recorded_at: string;
  truth_state: string;
  source_kind: string;
  attribution: string;
  text: string;
};

export type LifeMapAskAnswer = {
  status: "grounded" | "abstained" | "emergency_escalation";
  intent: string;
  answer: string;
  claims: Array<{
    claim_id: string;
    text: string;
    citation_ids: string[];
    truth_state: string;
    attribution: string;
  }>;
  evidence: LifeMapAskEvidence[];
  unknown: string[];
  conflicting: string[];
  stale: string[];
  disputed: string[];
  abstention_code: string;
  disclosure: {
    ai_assisted: boolean;
    mode: string;
    medical_advice: false;
    mutates_lifemap: false;
  };
};

export type LifeMapReviewFinding = {
  id: string;
  kind: "duplicate" | "contradiction" | "missingness" | "model_proposal";
  field_key: string;
  reason_code: string;
  proposal_source: "rule" | "nli" | "llm";
  revision_ids: string[];
  rule_version: string;
  status: "pending" | "resolved" | "dismissed";
  resolution_reason: string;
  requires_human_resolution: boolean;
};

export type CaptureCandidate = {
  id: string;
  type: string;
  field_path: string;
  value: Record<string, unknown>;
  confidence: number | null;
  field_confidence: Record<string, number>;
  source_span:
    | { start: number; end: number }
    | {
        kind: "text_fields";
        fields: Record<string, { start: number; end: number }>;
        text_checksum?: string;
      }
    | null;
  missing_critical_fields: string[];
  security_findings: string[];
  schema_version: string;
  status: string;
  artifact_id?: string | null;
};

export type CaptureArtifact = {
  id: string;
  media_type: string;
  filename: string;
  checksum: string;
  access_token: string;
  access_expires_at: string;
};

export type CaptureSession = {
  id?: string;
  status?: string;
  expires_at?: string;
  candidates?: CaptureCandidate[];
  artifacts?: CaptureArtifact[];
  emergency?: boolean;
  persisted?: boolean;
  message?: string;
};

function idempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `web-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function getLifeMapToday(): Promise<LifeMapToday> {
  return (await api.get<LifeMapToday>("/lifemap/today")).data;
}

export async function getLifeMapClientContract(): Promise<LifeMapClientContract> {
  return (
    await api.get<LifeMapClientContract>("/lifemap/v2/client-contract")
  ).data;
}

export async function completeLifeMapTask(taskId: string): Promise<void> {
  await api.post(
    `/lifemap/tasks/${encodeURIComponent(taskId)}/complete`,
    { evidence: { source: "user" } },
    { headers: { "Idempotency-Key": idempotencyKey() } },
  );
}

export async function createLifeMapEpisode(input: {
  title: string;
  goal: string;
  priority: "routine" | "soon" | "urgent";
}): Promise<{ id: string }> {
  return (
    await api.post<{ id: string }>("/lifemap/episodes", input, {
      headers: { "Idempotency-Key": idempotencyKey() },
    })
  ).data;
}

export async function createLifeMapTask(
  episodeId: string,
  input: { title: string; due_at?: string },
): Promise<{ id: string }> {
  return (
    await api.post<{ id: string }>(
      `/lifemap/episodes/${encodeURIComponent(episodeId)}/tasks`,
      input,
      { headers: { "Idempotency-Key": idempotencyKey() } },
    )
  ).data;
}

export async function acceptLifeMapTask(taskId: string): Promise<void> {
  await api.post(
    `/lifemap/tasks/${encodeURIComponent(taskId)}/accept`,
    {},
    { headers: { "Idempotency-Key": idempotencyKey() } },
  );
}

export async function getLifeMapReplay(
  episodeId: string,
): Promise<LifeMapReplay> {
  return (
    await api.get<LifeMapReplay>(
      `/episodes/${encodeURIComponent(episodeId)}/replay`,
    )
  ).data;
}

export async function correctLifeMapEvent(
  eventId: string,
  revision: number,
  payload: Record<string, unknown>,
  reason: string,
): Promise<void> {
  await api.post(
    `/lifemap/events/${encodeURIComponent(eventId)}/correct`,
    { payload, reason },
    {
      headers: {
        "Idempotency-Key": idempotencyKey(),
        "If-Match": String(revision),
      },
    },
  );
}

export async function disputeLifeMapEvent(
  eventId: string,
  revision: number,
  reason: string,
): Promise<void> {
  await api.post(
    `/lifemap/events/${encodeURIComponent(eventId)}/dispute`,
    { reason },
    {
      headers: {
        "Idempotency-Key": idempotencyKey(),
        "If-Match": String(revision),
      },
    },
  );
}

export async function resolveLifeMapEvent(
  eventId: string,
  revision: number,
  reason: string,
): Promise<void> {
  await api.post(
    `/lifemap/events/${encodeURIComponent(eventId)}/resolve`,
    { reason },
    {
      headers: {
        "Idempotency-Key": idempotencyKey(),
        "If-Match": String(revision),
      },
    },
  );
}

export async function getLifeMapDisputes(): Promise<LifeMapDisputeCase[]> {
  return (await api.get<LifeMapDisputeCase[]>("/lifemap/v2/disputes")).data;
}

export async function disputeLifeMapDecision(
  decisionId: string,
  reason: string,
): Promise<void> {
  await api.post(
    `/decisions/${encodeURIComponent(decisionId)}/dispute`,
    { reason },
  );
}

export async function getLifeMapBaselines(): Promise<LifeMapBaseline[]> {
  return (await api.get<LifeMapBaseline[]>("/lifemap/v2/baselines")).data;
}

export async function getLifeMapNextQuestion(
  episodeId: string,
  locale = "vi",
): Promise<LifeMapQuestion> {
  return (
    await api.get<LifeMapQuestion>(
      `/episodes/${encodeURIComponent(episodeId)}/next-question`,
      { params: { locale } },
    )
  ).data;
}

export async function askLifeMap(
  query: string,
  episodeId?: string,
  locale = "vi",
): Promise<LifeMapAskAnswer> {
  return (
    await api.post<LifeMapAskAnswer>("/lifemap/v2/ask", {
      query,
      episode_id: episodeId || null,
      locale,
    })
  ).data;
}

export async function scanLifeMapReviewFindings(): Promise<
  LifeMapReviewFinding[]
> {
  return (
    await api.post<LifeMapReviewFinding[]>("/lifemap/v2/review-findings/scan")
  ).data;
}

export async function actOnLifeMapReviewFinding(
  findingId: string,
  action: "resolved" | "dismissed",
  reason: string,
): Promise<LifeMapReviewFinding> {
  return (
    await api.post<LifeMapReviewFinding>(
      `/lifemap/v2/review-findings/${encodeURIComponent(findingId)}/actions`,
      { action, reason },
      { headers: { "Idempotency-Key": idempotencyKey() } },
    )
  ).data;
}

export async function recordLifeMapQuestionInteraction(
  episodeId: string,
  questionId: string,
  action: "presented" | "dismissed" | "do_not_ask",
  reason = "",
): Promise<void> {
  await api.post(
    `/episodes/${encodeURIComponent(episodeId)}/questions/${encodeURIComponent(questionId)}/interaction`,
    { action, reason },
    { headers: { "Idempotency-Key": idempotencyKey() } },
  );
}

export async function startLifeMapGuidedAnswer(
  episodeId: string,
  questionId: string,
  answer: Record<string, unknown>,
  locale = "vi",
): Promise<CaptureSession> {
  return (
    await api.post<CaptureSession>("/lifemap/capture/guided-answers", {
      episode_id: episodeId,
      question_id: questionId,
      answer,
      locale,
    })
  ).data;
}

export async function getLifeMapV2Capabilities(
  profileId: string,
): Promise<Record<string, boolean>> {
  const response = await api.get<{
    capabilities?: Record<string, { enabled?: boolean } | boolean>;
  }>(`/profiles/${encodeURIComponent(profileId)}/capabilities`);
  const result: Record<string, boolean> = {};
  for (const [key, value] of Object.entries(response.data.capabilities ?? {})) {
    result[key] =
      typeof value === "boolean" ? value : Boolean(value?.enabled);
  }
  return result;
}

export async function startLifeMapTextCapture(
  text: string,
  locale = "vi",
): Promise<CaptureSession> {
  return (
    await api.post<CaptureSession>("/lifemap/capture/sessions", { text, locale })
  ).data;
}

export async function startLifeMapArtifactCapture(
  inputKind: "medication_label" | "visit_document",
  locale = "vi",
): Promise<CaptureSession> {
  return (
    await api.post<CaptureSession>("/lifemap/capture/artifact-sessions", {
      input_kind: inputKind,
      locale,
    })
  ).data;
}

export async function uploadLifeMapCaptureArtifact(
  sessionId: string,
  file: File,
): Promise<{
  id: string;
  job: { id: string; status: string };
}> {
  const body = new FormData();
  body.append("artifact", file);
  return (
    await api.post(
      `/lifemap/capture/sessions/${encodeURIComponent(sessionId)}/artifacts`,
      body,
    )
  ).data;
}

export async function getLifeMapCaptureSession(
  sessionId: string,
): Promise<CaptureSession> {
  return (
    await api.get<CaptureSession>(
      `/lifemap/capture/sessions/${encodeURIComponent(sessionId)}`,
    )
  ).data;
}

export async function getLifeMapCaptureJob(jobId: string): Promise<{
  id: string;
  status: string;
  error_code: string;
  emergency: boolean;
  message: string;
  candidates: CaptureCandidate[];
}> {
  return (
    await api.get(`/lifemap/capture/jobs/${encodeURIComponent(jobId)}`)
  ).data;
}

export async function abandonLifeMapCaptureSession(
  sessionId: string,
): Promise<void> {
  await api.post(
    `/lifemap/capture/sessions/${encodeURIComponent(sessionId)}/abandon`,
  );
}

export async function getLifeMapCaptureArtifact(
  artifact: CaptureArtifact,
): Promise<Blob> {
  return (
    await api.get(
      `/lifemap/capture/artifacts/${encodeURIComponent(artifact.id)}/content`,
      {
        headers: {
          "X-Capture-Artifact-Token": artifact.access_token,
        },
        responseType: "blob",
      },
    )
  ).data;
}

export async function reviewLifeMapCaptureCandidate(
  candidateId: string,
  action: "edit" | "reject" | "confirm",
  input: { value?: Record<string, unknown>; reason?: string } = {},
): Promise<{
  id: string;
  status: string;
  event_id?: string;
  medication_course_id?: string;
  candidate: CaptureCandidate;
}> {
  return (
    await api.post(
      `/lifemap/capture/candidates/${encodeURIComponent(candidateId)}/review`,
      { action, ...input },
      { headers: { "Idempotency-Key": idempotencyKey() } },
    )
  ).data;
}

export async function getLifeMapCaptureCapability(
  profileId: string,
): Promise<boolean> {
  const response = await api.get<{
    capabilities?: Record<string, { enabled?: boolean } | boolean>;
  }>(`/profiles/${encodeURIComponent(profileId)}/capabilities`);
  const capability = response.data.capabilities?.lifemap_capture;
  return typeof capability === "boolean"
    ? capability
    : Boolean(capability?.enabled);
}
