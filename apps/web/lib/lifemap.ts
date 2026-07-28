import api from "@/lib/http-client";

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

export type CaptureCandidate = {
  id: string;
  type: string;
  field_path: string;
  value: Record<string, unknown>;
  confidence: number | null;
  source_span: { start: number; end: number } | null;
  missing_critical_fields: string[];
  security_findings: string[];
  schema_version: string;
  status: string;
};

export type CaptureSession = {
  id?: string;
  status?: string;
  expires_at?: string;
  candidates?: CaptureCandidate[];
  emergency: boolean;
  persisted: boolean;
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

export async function startLifeMapTextCapture(
  text: string,
  locale = "vi",
): Promise<CaptureSession> {
  return (
    await api.post<CaptureSession>("/lifemap/capture/sessions", { text, locale })
  ).data;
}

export async function reviewLifeMapCaptureCandidate(
  candidateId: string,
  action: "edit" | "reject" | "confirm",
  input: { value?: Record<string, unknown>; reason?: string } = {},
): Promise<{ id: string; status: string; event_id?: string }> {
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
