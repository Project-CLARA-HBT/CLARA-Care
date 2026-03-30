"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import HistoryPanel from "@/components/research/history-panel";
import { useResearchFlow } from "@/components/research/hooks/use-research-flow";
import { useResearchKnowledgeSources } from "@/components/research/hooks/use-research-knowledge-sources";
import { useResearchUploads } from "@/components/research/hooks/use-research-uploads";
import { ROLE_LABELS, SUGGESTED_QUERIES } from "@/components/research/lib/research-page-constants";
import {
  conversationLabel,
  createConversationItem,
  formatHistoryTime,
  resolveFlowModeFromResult
} from "@/components/research/lib/research-page-helpers";
import { ResearchMainCard, ResearchWorkspaceHeader } from "@/components/research/lib/research-page-sections";
import { ConversationItem, FlowVisibilityMode, ResearchResult } from "@/components/research/lib/research-page-types";
import ResearchRightRail from "@/components/research/right-rail";
import PageShell from "@/components/ui/page-shell";
import { UserRole, getRole } from "@/lib/auth-store";
import { ChatResponse, getChatIntentDebug, getChatReply } from "@/lib/chat";
import api from "@/lib/http-client";
import {
  ResearchExecutionMode,
  ResearchFlowEvent,
  ResearchFlowStage,
  ResearchTier,
  Tier2Citation,
  Tier2Step,
  normalizeResearchTier2,
  runResearchTier2
} from "@/lib/research";

export default function ResearchPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [selectedTier, setSelectedTier] = useState<ResearchTier>("tier1");
  const [selectedResearchMode, setSelectedResearchMode] = useState<ResearchExecutionMode>("fast");
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [history, setHistory] = useState<ConversationItem[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const flow = useResearchFlow();
  const uploads = useResearchUploads({
    onBeforeUpload: () => {
      setError("");
    }
  });
  const sources = useResearchKnowledgeSources();

  const isDev = process.env.NODE_ENV !== "production";
  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? ROLE_LABELS.normal, [role]);

  const activeConversation = useMemo(
    () => history.find((item) => item.id === activeConversationId) ?? null,
    [history, activeConversationId]
  );

  const activeTier2Result = useMemo(() => {
    if (activeConversation?.result.tier === "tier2") return activeConversation.result;
    if (result?.tier === "tier2") return result;
    return null;
  }, [activeConversation, result]);

  const evidenceCitations = useMemo<Tier2Citation[]>(() => activeTier2Result?.citations ?? [], [activeTier2Result]);
  const evidenceSteps = useMemo<Tier2Step[]>(() => activeTier2Result?.steps ?? [], [activeTier2Result]);
  const activeTelemetry = useMemo(
    () =>
      activeTier2Result?.telemetry ?? {
        keywords: [],
        searchPlan: {
          keywords: [],
          subqueries: [],
          connectors: []
        },
        sourceAttempts: [],
        indexSummary: {},
        crawlSummary: {
          domains: []
        },
        docs: [],
        scores: [],
        sourceReasoning: [],
        errors: []
      },
    [activeTier2Result]
  );

  const persistedFlowStages = useMemo<ResearchFlowStage[]>(() => activeTier2Result?.flowStages ?? [], [activeTier2Result]);
  const persistedFlowEvents = useMemo<ResearchFlowEvent[]>(() => activeTier2Result?.flowEvents ?? [], [activeTier2Result]);
  const persistedFlowMode = useMemo<FlowVisibilityMode>(() => {
    if (!activeTier2Result) return "idle";
    return resolveFlowModeFromResult(activeTier2Result);
  }, [activeTier2Result]);

  const timelineStages = isSubmitting
    ? flow.liveFlowStages
    : persistedFlowStages.length
      ? persistedFlowStages
      : flow.liveFlowStages;
  const timelineEvents = isSubmitting
    ? flow.liveFlowEvents
    : persistedFlowEvents.length
      ? persistedFlowEvents
      : flow.liveFlowEvents;
  const timelineMode = isSubmitting ? flow.flowMode : persistedFlowMode !== "idle" ? persistedFlowMode : flow.flowMode;

  const historyItems = useMemo(
    () =>
      history.map((item) => ({
        id: item.id,
        label: conversationLabel(item),
        timestamp: formatHistoryTime(item.createdAt),
        tier: item.result.tier,
        active: item.id === activeConversationId
      })),
    [history, activeConversationId]
  );

  useEffect(() => {
    setRole(getRole());
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isSubmitting) return;

    setError("");
    setIsSubmitting(true);
    setLastQuery(message);

    try {
      let nextResult: ResearchResult;

      if (selectedTier === "tier1") {
        flow.resetFlow();

        const response = await api.post<ChatResponse>("/chat", { message });
        const answer = getChatReply(response.data);
        if (!answer) throw new Error("Chưa có nội dung trả lời hợp lệ.");

        nextResult = { tier: "tier1", answer, debug: getChatIntentDebug(response.data) };
      } else {
        flow.startServerProcessing();

        const response = await runResearchTier2(message, {
          uploadedFileIds: uploads.uploadedFileIds,
          sourceIds: sources.selectedSourceIds,
          researchMode: selectedResearchMode
        });
        const normalized = normalizeResearchTier2(response);
        if (!normalized.answer && !normalized.citations.length) {
          throw new Error("Chưa có phản hồi chuyên sâu hợp lệ.");
        }

        const resolvedMode: FlowVisibilityMode =
          normalized.flowEvents.length > 0
            ? "flow-events"
            : normalized.flowStages.length > 0
              ? "metadata-stages"
              : "idle";

        const resolvedStages = normalized.flowStages.length > 0 ? normalized.flowStages : [];

        flow.setResolvedFlow({
          mode: resolvedMode,
          events: normalized.flowEvents,
          stages: resolvedStages
        });

        nextResult = {
          tier: "tier2",
          ...normalized
        };
      }

      setResult(nextResult);

      const conversation = createConversationItem(message, nextResult);

      setHistory((prev) => [conversation, ...prev]);
      setActiveConversationId(conversation.id);
      setQuery("");
    } catch (submitError) {
      if (selectedTier === "tier2") {
        flow.markFlowFailed();
      }
      setError(submitError instanceof Error ? submitError.message : "Không thể gửi câu hỏi.");
    } finally {
      flow.stopServerProcessing();
      setIsSubmitting(false);
    }
  };

  const onOpenConversation = (conversationId: string) => {
    const item = history.find((entry) => entry.id === conversationId);
    if (!item) return;

    setActiveConversationId(item.id);
    setLastQuery(item.query);
    setResult(item.result);
    setSelectedTier(item.result.tier);
    setError("");

    if (item.result.tier === "tier2") {
      flow.hydrateFlowFromTier2Result(item.result);
    } else {
      flow.resetFlow();
    }
  };

  const showDebugHints = role === "admin" || isDev;

  return (
    <PageShell title="Hỏi đáp y tế" variant="plain">
      <div className="grid gap-4 xl:grid-cols-[minmax(16rem,19rem)_minmax(0,1fr)_minmax(20rem,24rem)] 2xl:grid-cols-[18rem_minmax(0,1fr)_24rem] 2xl:gap-5">
        <aside className="order-2 space-y-4 xl:order-1 xl:sticky xl:top-24 xl:max-h-[calc(100dvh-7.5rem)] xl:overflow-y-auto xl:pr-1">
          <HistoryPanel
            items={historyItems}
            suggestions={SUGGESTED_QUERIES}
            onOpenConversation={onOpenConversation}
            onPickSuggestion={setQuery}
          />
        </aside>

        <section className="order-1 space-y-4 xl:order-2">
          <ResearchWorkspaceHeader
            roleLabel={roleLabel}
            selectedSourceCount={sources.selectedSourceIds.length}
            uploadedFileCount={uploads.uploadedFiles.length}
          />

          <ResearchMainCard
            query={query}
            selectedTier={selectedTier}
            isSubmitting={isSubmitting}
            isUploading={uploads.isUploading}
            fileInputRef={fileInputRef}
            onSubmit={onSubmit}
            onUploadInputChange={uploads.onUploadInputChange}
            onQueryChange={setQuery}
            onSelectTier={setSelectedTier}
            selectedResearchMode={selectedResearchMode}
            onSelectResearchMode={setSelectedResearchMode}
            lastQuery={lastQuery}
            result={result}
            showDebugHints={showDebugHints}
            evidenceSteps={evidenceSteps}
          />

          {error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
              {error}
            </div>
          ) : null}
        </section>

        <aside className="order-3 space-y-4 xl:sticky xl:top-24 xl:max-h-[calc(100dvh-7.5rem)] xl:overflow-y-auto xl:pl-1">
          <ResearchRightRail
            citations={evidenceCitations}
            flowStages={timelineStages}
            flowEvents={timelineEvents}
            flowMode={timelineMode}
            telemetry={activeTelemetry}
            isSubmitting={isSubmitting}
            knowledgeSources={sources.knowledgeSources}
            selectedSourceIds={sources.selectedSourceIds}
            isLoadingSources={sources.isLoadingSources}
            isCreatingSource={sources.isCreatingSource}
            sourceError={sources.sourceError}
            newSourceName={sources.newSourceName}
            onSourceNameChange={sources.setNewSourceName}
            onToggleSource={sources.onToggleSource}
            onCreateSource={sources.onCreateSource}
            uploadedFiles={uploads.uploadedFiles}
            isUploading={uploads.isUploading}
            isDragActive={uploads.isDragActive}
            uploadError={uploads.uploadError}
            onClearUploadedFiles={uploads.onClearUploadedFiles}
            onRemoveUploadedFile={uploads.onRemoveUploadedFile}
            onDropUpload={uploads.onDropUpload}
            onDragOverUpload={uploads.onDragOverUpload}
            onDragEnterUpload={uploads.onDragEnterUpload}
            onDragLeaveUpload={uploads.onDragLeaveUpload}
            showDebugHints={showDebugHints}
            debugHints={{
              roleLabel,
              selectedTier,
              conversationCount: history.length,
              selectedSourceCount: sources.selectedSourceIds.length,
              uploadedFileCount: uploads.uploadedFiles.length,
              flowMode: timelineMode,
              policyAction: activeTier2Result?.policyAction,
              fallbackUsed: activeTier2Result?.fallbackUsed,
              verificationVerdict: activeTier2Result?.verificationStatus?.verdict,
              verificationConfidence: activeTier2Result?.verificationStatus?.confidence,
              routingRole: activeTier2Result?.debug.routing?.role,
              routingIntent: activeTier2Result?.debug.routing?.intent,
              routingConfidence: activeTier2Result?.debug.routing?.confidence,
              pipeline: activeTier2Result?.debug.pipeline,
              telemetryKeywordCount: activeTier2Result?.debug.telemetryKeywordCount ?? activeTelemetry.keywords.length,
              telemetryDocCount: activeTier2Result?.debug.telemetryDocCount ?? activeTelemetry.docs.length,
              telemetrySourceAttemptCount: activeTelemetry.sourceAttempts.length,
              telemetryErrorCount: activeTier2Result?.debug.telemetryErrorCount ?? activeTelemetry.errors.length,
              telemetryTopError: activeTelemetry.errors[0],
              crawlDomainCount: activeTelemetry.crawlSummary.domains.length
            }}
          />
        </aside>
      </div>
    </PageShell>
  );
}
