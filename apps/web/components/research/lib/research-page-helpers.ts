import { ResearchFlowStage, UploadedResearchFile } from "@/lib/research";
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

export function createConversationItem(query: string, result: ResearchResult): ConversationItem {
  const createdAt = Date.now();
  return {
    id: `${createdAt}-${Math.random().toString(36).slice(2, 8)}`,
    query,
    result,
    createdAt
  };
}
