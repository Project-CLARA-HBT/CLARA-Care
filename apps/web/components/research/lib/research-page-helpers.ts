import {
  PersistedResearchConversation,
  ResearchFlowStage,
  ResearchTier2RawResponse,
  UploadedResearchFile,
  normalizeResearchTier2
} from "@/lib/research";
import { ConversationItem, FlowVisibilityMode, ResearchResult, Tier2Result } from "@/components/research/lib/research-page-types";

export function mergeUploadedFiles(current: UploadedResearchFile[], incoming: UploadedResearchFile[]): UploadedResearchFile[] {
  const byId = new Map(current.map((item) => [item.id, item]));

  incoming.forEach((item) => {
    const existing = byId.get(item.id);
    byId.set(item.id, {
      id: item.id,
      name: item.name || existing?.name || `File #${item.id}`,
      size: item.size ?? existing?.size
    });
  });

  return Array.from(byId.values());
}

export function formatHistoryTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function conversationLabel(item: ConversationItem): string {
  const normalized = item.query.replace(/\s+/g, " ").trim();
  return normalized.length > 56 ? `${normalized.slice(0, 56)}...` : normalized;
}

export function resolveFlowModeFromResult(result: Tier2Result): FlowVisibilityMode {
  if (result.flowEvents.length) return "flow-events";
  if (result.flowStages.length) return "metadata-stages";
  return "idle";
}

export function markTimelineFailed(stages: ResearchFlowStage[]): ResearchFlowStage[] {
  if (!stages.length) {
    return [
      {
        id: "server_processing",
        label: "Server processing",
        detail: "Không thể hoàn tất xử lý từ backend cho phiên nghiên cứu này.",
        status: "failed",
        source: "local"
      }
    ];
  }

  const inProgressIndex = stages.findIndex((stage) => stage.status === "in_progress");
  if (inProgressIndex >= 0) {
    return stages.map((stage, index) => (index === inProgressIndex ? { ...stage, status: "failed" } : stage));
  }

  const latestNonCompletedIndex = [...stages].reverse().findIndex((stage) => stage.status !== "completed");
  const failedIndex = latestNonCompletedIndex === -1 ? stages.length - 1 : stages.length - 1 - latestNonCompletedIndex;

  return stages.map((stage, index) => {
    if (index !== failedIndex) return stage;
    return { ...stage, status: "failed" };
  });
}

export function createConversationItem(
  query: string,
  result: ResearchResult,
  options?: { id?: string; createdAt?: number }
): ConversationItem {
  const createdAt = options?.createdAt ?? Date.now();
  return {
    id: options?.id ?? `${createdAt}-${Math.random().toString(36).slice(2, 8)}`,
    query,
    result,
    createdAt
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const next = value.trim();
  return next ? next : undefined;
}

function normalizePersistedTier(value: Record<string, unknown>): "tier1" | "tier2" {
  const raw = asText(value.tier)?.toLowerCase();
  if (raw === "tier2") return "tier2";
  if (raw === "tier1") return "tier1";
  if (value.citations || value.flowEvents || value.flow_events || value.telemetry) return "tier2";
  return "tier1";
}

function parsePersistedResult(value: Record<string, unknown>): ResearchResult {
  const tier = normalizePersistedTier(value);
  if (tier === "tier2") {
    const raw: ResearchTier2RawResponse = {
      ...(value as ResearchTier2RawResponse),
      flow_events: value.flow_events ?? value.flowEvents,
      metadata: asRecord(value.metadata) ?? undefined,
      context_debug: asRecord(value.context_debug) ?? asRecord(value.contextDebug)
    };
    return {
      tier: "tier2",
      ...normalizeResearchTier2(raw)
    };
  }

  return {
    tier: "tier1",
    answer: asText(value.answer) ?? asText(value.summary) ?? "",
    debug: null
  };
}

export function createConversationItemFromPersisted(
  persisted: PersistedResearchConversation
): ConversationItem {
  return createConversationItem(
    persisted.query,
    parsePersistedResult(persisted.result),
    { id: persisted.id, createdAt: persisted.createdAt }
  );
}
