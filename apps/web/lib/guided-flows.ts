import api from "@/lib/http-client";

export type LifeMapEpisodeStep = "title" | "goal" | "priority" | "review";
export type LifeMapPriority = "routine" | "soon" | "urgent";

export type LifeMapEpisodeDraftPayload = {
  title?: string;
  goal?: string;
  priority?: LifeMapPriority;
};

export type GuidedFlowDraft = {
  id: string;
  flow_type: "lifemap_episode";
  current_step: LifeMapEpisodeStep;
  payload: LifeMapEpisodeDraftPayload;
  status: "active" | "committed" | "abandoned";
  revision: number;
  expires_at: string;
  committed_resource: { type: "lifemap_episode"; id: string } | null;
};

type DraftList = { items: GuidedFlowDraft[] };

export async function listLifeMapEpisodeDrafts(): Promise<GuidedFlowDraft[]> {
  const { data } = await api.get<DraftList>("/api/v1/guided-flows", {
    params: { flow_type: "lifemap_episode" },
  });
  return data.items;
}
export async function createLifeMapEpisodeDraft(
  idempotencyKey: string,
): Promise<GuidedFlowDraft> {
  const { data } = await api.post<GuidedFlowDraft>(
    "/api/v1/guided-flows",
    {
      flow_type: "lifemap_episode",
      current_step: "title",
      payload: {},
    },
    { headers: { "Idempotency-Key": idempotencyKey } },
  );
  return data;
}

export async function getGuidedFlowDraft(
  draftId: string,
): Promise<GuidedFlowDraft> {
  const { data } = await api.get<GuidedFlowDraft>(
    `/api/v1/guided-flows/${encodeURIComponent(draftId)}`,
  );
  return data;
}

export async function updateLifeMapEpisodeDraft(
  draftId: string,
  revision: number,
  currentStep: LifeMapEpisodeStep,
  payload: LifeMapEpisodeDraftPayload,
): Promise<GuidedFlowDraft> {
  const { data } = await api.patch<GuidedFlowDraft>(
    `/api/v1/guided-flows/${encodeURIComponent(draftId)}`,
    { current_step: currentStep, payload },
    { headers: { "If-Match": `"${revision}"` } },
  );
  return data;
}

export async function commitLifeMapEpisodeDraft(
  draftId: string,
  revision: number,
  idempotencyKey: string,
): Promise<GuidedFlowDraft> {
  const { data } = await api.post<GuidedFlowDraft>(
    `/api/v1/guided-flows/${encodeURIComponent(draftId)}/commit`,
    {},
    {
      headers: {
        "Idempotency-Key": idempotencyKey,
        "If-Match": `"${revision}"`,
      },
    },
  );
  return data;
}
