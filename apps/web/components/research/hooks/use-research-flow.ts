"use client";

import { useCallback, useState } from "react";
import { markTimelineFailed, resolveFlowModeFromResult } from "@/components/research/lib/research-page-helpers";
import { FlowVisibilityMode, Tier2Result } from "@/components/research/lib/research-page-types";
import { ResearchFlowEvent, ResearchFlowStage } from "@/lib/research";

type ResolvedFlowPayload = {
  mode: FlowVisibilityMode;
  stages: ResearchFlowStage[];
  events: ResearchFlowEvent[];
};

export function useResearchFlow() {
  const [liveFlowStages, setLiveFlowStages] = useState<ResearchFlowStage[]>([]);
  const [liveFlowEvents, setLiveFlowEvents] = useState<ResearchFlowEvent[]>([]);
  const [flowMode, setFlowMode] = useState<FlowVisibilityMode>("idle");

  const stopServerProcessing = useCallback(() => {
    // No-op by design. `isSubmitting` from page controls active processing UI.
  }, []);

  const resetFlow = useCallback(() => {
    setFlowMode("idle");
    setLiveFlowStages([]);
    setLiveFlowEvents([]);
  }, []);

  const startServerProcessing = useCallback(() => {
    // Honest waiting state: do not fabricate completed timeline steps.
    setFlowMode("idle");
    setLiveFlowEvents([]);
    setLiveFlowStages([]);
  }, []);

  const setResolvedFlow = useCallback(({ mode, stages, events }: ResolvedFlowPayload) => {
    setFlowMode(mode);
    setLiveFlowStages(stages);
    setLiveFlowEvents(events);
  }, []);

  const markFlowFailed = useCallback(() => {
    setLiveFlowStages((prev) => markTimelineFailed(prev));
    setFlowMode("metadata-stages");
  }, []);

  const hydrateFlowFromTier2Result = useCallback((result: Tier2Result) => {
    setLiveFlowStages(result.flowStages);
    setLiveFlowEvents(result.flowEvents);
    setFlowMode(resolveFlowModeFromResult(result));
  }, []);

  return {
    liveFlowStages,
    liveFlowEvents,
    flowMode,
    resetFlow,
    startServerProcessing,
    stopServerProcessing,
    setResolvedFlow,
    markFlowFailed,
    hydrateFlowFromTier2Result
  };
}
