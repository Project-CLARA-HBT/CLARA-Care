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
