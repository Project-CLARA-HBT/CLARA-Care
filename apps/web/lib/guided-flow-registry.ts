export type GuidedFlowLocale = "vi" | "en";

export const WELCOME_STEP_IDS = [
  "start",
  "name",
  "birth",
  "gender",
  "blood-type",
  "body",
  "personalization",
  "review",
] as const;

const WELCOME_LABELS = {
  vi: {
    start: "Bắt đầu",
    name: "Tên",
    birth: "Ngày sinh",
    gender: "Giới tính",
    "blood-type": "Nhóm máu",
    body: "Số đo",
    personalization: "Cá nhân hoá",
    review: "Kiểm tra",
  },
  en: {
    start: "Start",
    name: "Name",
    birth: "Date of birth",
    gender: "Gender",
    "blood-type": "Blood type",
    body: "Measurements",
    personalization: "Personalization",
    review: "Review",
  },
} as const;

export const LIFEMAP_EPISODE_STEP_IDS = [
  "title",
  "goal",
  "priority",
  "review",
] as const;

const LIFEMAP_EPISODE_LABELS = {
  vi: {
    title: "Tên hành trình",
    goal: "Mục tiêu",
    priority: "Ưu tiên",
    review: "Kiểm tra",
  },
  en: {
    title: "Journey name",
    goal: "Goal",
    priority: "Priority",
    review: "Review",
  },
} as const;

export const GUIDED_FLOW_REGISTRY = {
  welcome: {
    id: "welcome",
    routePrefix: "/welcome",
    stepIds: WELCOME_STEP_IDS,
    labels: WELCOME_LABELS,
  },
  lifemapEpisode: {
    id: "lifemapEpisode",
    routePrefix: "/lifemap/new",
    stepIds: LIFEMAP_EPISODE_STEP_IDS,
    labels: LIFEMAP_EPISODE_LABELS,
  },
} as const;

export type GuidedFlowId = keyof typeof GUIDED_FLOW_REGISTRY;
export type GuidedFlowStepId<F extends GuidedFlowId> =
  (typeof GUIDED_FLOW_REGISTRY)[F]["stepIds"][number];

export function isGuidedFlowStep<F extends GuidedFlowId>(
  flowId: F,
  value: string,
): value is GuidedFlowStepId<F> {
  const stepIds = GUIDED_FLOW_REGISTRY[flowId].stepIds as readonly string[];
  return stepIds.includes(value);
}

export function guidedFlowPath<F extends GuidedFlowId>(
  flowId: F,
  stepId: GuidedFlowStepId<F>,
): string {
  return `${GUIDED_FLOW_REGISTRY[flowId].routePrefix}/${stepId}`;
}

export function adjacentGuidedFlowStep<F extends GuidedFlowId>(
  flowId: F,
  current: GuidedFlowStepId<F>,
  direction: "previous" | "next",
): GuidedFlowStepId<F> | null {
  const stepIds = GUIDED_FLOW_REGISTRY[flowId].stepIds;
  const index = (stepIds as readonly string[]).indexOf(current);
  if (index < 0) return null;
  const target = direction === "previous" ? index - 1 : index + 1;
  return (stepIds[target] as GuidedFlowStepId<F> | undefined) ?? null;
}

export function isGuidedFlowStepAhead<F extends GuidedFlowId>(
  flowId: F,
  requested: GuidedFlowStepId<F>,
  current: GuidedFlowStepId<F>,
): boolean {
  const stepIds = GUIDED_FLOW_REGISTRY[flowId].stepIds as readonly string[];
  return stepIds.indexOf(requested) > stepIds.indexOf(current);
}

export function guidedFlowSteps<F extends GuidedFlowId>(
  flowId: F,
  locale: GuidedFlowLocale,
) {
  const flow = GUIDED_FLOW_REGISTRY[flowId];
  const labels = flow.labels[locale] as Record<string, string>;
  return (flow.stepIds as readonly string[]).map((rawId) => {
    const id = rawId as GuidedFlowStepId<F>;
    return { id, label: labels[rawId] };
  });
}

export type GuidedFlowAnalyticsEventName =
  | "flow_started"
  | "step_viewed"
  | "step_completed"
  | "flow_completed"
  | "flow_abandoned";

/**
 * Content-free analytics contract. Callers may emit this shape, but must never
 * attach field values, health text, draft IDs, user IDs, or raw errors.
 */
export type GuidedFlowAnalyticsEvent<F extends GuidedFlowId = GuidedFlowId> = {
  schemaVersion: 1;
  event: GuidedFlowAnalyticsEventName;
  surface: "web";
  flowId: F;
  stepId: GuidedFlowStepId<F>;
  stepIndex: number;
  totalSteps: number;
};

export function makeGuidedFlowAnalyticsEvent<F extends GuidedFlowId>(
  flowId: F,
  stepId: GuidedFlowStepId<F>,
  event: GuidedFlowAnalyticsEventName,
): GuidedFlowAnalyticsEvent<F> {
  const stepIds = GUIDED_FLOW_REGISTRY[flowId].stepIds;
  const stepIndex = (stepIds as readonly string[]).indexOf(stepId);
  if (stepIndex < 0) throw new Error("Unknown guided-flow step");
  return {
    schemaVersion: 1,
    event,
    surface: "web",
    flowId,
    stepId,
    stepIndex,
    totalSteps: stepIds.length,
  };
}
