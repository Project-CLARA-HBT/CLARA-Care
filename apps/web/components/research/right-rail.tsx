"use client";

import { DragEvent, FormEvent, useMemo, useState } from "react";
import {
  KnowledgeSource,
  ResearchFlowEvent,
  ResearchFlowStage,
  ResearchTier2Telemetry,
  Tier2Citation,
  UploadedResearchFile
} from "@/lib/research";
import DebugHintsPanel from "@/components/research/debug-hints-panel";
import EvidencePanel from "@/components/research/evidence-panel";
import FlowTimelinePanel from "@/components/research/flow-timeline-panel";
import KnowledgeSourcesPanel from "@/components/research/knowledge-sources-panel";
import TelemetryDetailsPanel from "@/components/research/telemetry-details-panel";
import UploadedFilesPanel from "@/components/research/uploaded-files-panel";

type FlowTimelineMode =
  | "idle"
  | "flow-events"
  | "metadata-stages"
  | "local-fallback"
  | "server-await";
type MobileTab = "flow" | "telemetry" | "evidence" | "sources" | "uploads" | "debug";

type ResearchRightRailProps = {
  citations: Tier2Citation[];
  flowStages: ResearchFlowStage[];
  flowEvents: ResearchFlowEvent[];
  flowMode: FlowTimelineMode;
  telemetry: ResearchTier2Telemetry;
  isSubmitting: boolean;

  knowledgeSources: KnowledgeSource[];
  selectedSourceIds: number[];
  isLoadingSources: boolean;
  isCreatingSource: boolean;
  sourceError: string;
  newSourceName: string;
  onSourceNameChange: (value: string) => void;
  onToggleSource: (sourceId: number) => void;
  onCreateSource: (event: FormEvent<HTMLFormElement>) => void;

  uploadedFiles: UploadedResearchFile[];
  isUploading: boolean;
  isDragActive: boolean;
  uploadError: string;
  onClearUploadedFiles: () => void;
  onRemoveUploadedFile: (fileId: string) => void;
  onDropUpload: (event: DragEvent<HTMLDivElement>) => void;
  onDragOverUpload: (event: DragEvent<HTMLDivElement>) => void;
  onDragEnterUpload: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeaveUpload: (event: DragEvent<HTMLDivElement>) => void;

  showDebugHints: boolean;
  debugHints: {
    roleLabel: string;
    selectedTier: "tier1" | "tier2";
    conversationCount: number;
    selectedSourceCount: number;
    uploadedFileCount: number;
    flowMode: FlowTimelineMode;
    policyAction?: "allow" | "warn";
    fallbackUsed?: boolean;
    verificationVerdict?: string;
    verificationConfidence?: number;
    routingRole?: string;
    routingIntent?: string;
    routingConfidence?: number;
    pipeline?: string;
    telemetryKeywordCount?: number;
    telemetryDocCount?: number;
    telemetrySourceAttemptCount?: number;
    telemetryErrorCount?: number;
    telemetryTopError?: string;
    crawlDomainCount?: number;
  };
};

const TAB_LABELS: Record<MobileTab, string> = {
  flow: "Flow",
  telemetry: "Telemetry",
  evidence: "Evidence",
  sources: "Sources",
  uploads: "Uploads",
  debug: "Debug"
};

export default function ResearchRightRail({
  citations,
  flowStages,
  flowEvents,
  flowMode,
  telemetry,
  isSubmitting,
  knowledgeSources,
  selectedSourceIds,
  isLoadingSources,
  isCreatingSource,
  sourceError,
  newSourceName,
  onSourceNameChange,
  onToggleSource,
  onCreateSource,
  uploadedFiles,
  isUploading,
  isDragActive,
  uploadError,
  onClearUploadedFiles,
  onRemoveUploadedFile,
  onDropUpload,
  onDragOverUpload,
  onDragEnterUpload,
  onDragLeaveUpload,
  showDebugHints,
  debugHints
}: ResearchRightRailProps) {
  const [mobileTab, setMobileTab] = useState<MobileTab>("flow");

  const tabs = useMemo(() => {
    const base: MobileTab[] = ["flow", "telemetry", "evidence", "sources", "uploads"];
    if (showDebugHints) base.push("debug");
    return base;
  }, [showDebugHints]);

  const panelByTab: Record<MobileTab, JSX.Element | null> = {
    flow: (
      <FlowTimelinePanel
        stages={flowStages}
        events={flowEvents}
        mode={flowMode}
        isProcessing={isSubmitting}
      />
    ),
    telemetry: (
      <TelemetryDetailsPanel
        telemetry={telemetry}
        isProcessing={isSubmitting}
      />
    ),
    evidence: <EvidencePanel citations={citations} />,
    sources: (
      <KnowledgeSourcesPanel
        sources={knowledgeSources}
        selectedSourceIds={selectedSourceIds}
        isLoading={isLoadingSources}
        isCreating={isCreatingSource}
        sourceError={sourceError}
        newSourceName={newSourceName}
        onSourceNameChange={onSourceNameChange}
        onToggleSource={onToggleSource}
        onCreateSource={onCreateSource}
      />
    ),
    uploads: (
      <UploadedFilesPanel
        files={uploadedFiles}
        isUploading={isUploading}
        isDragActive={isDragActive}
        uploadError={uploadError}
        onClearAll={onClearUploadedFiles}
        onRemoveFile={onRemoveUploadedFile}
        onDrop={onDropUpload}
        onDragOver={onDragOverUpload}
        onDragEnter={onDragEnterUpload}
        onDragLeave={onDragLeaveUpload}
      />
    ),
    debug: <DebugHintsPanel enabled={showDebugHints} {...debugHints} />
  };

  return (
    <aside className="space-y-4">
      <div className="xl:hidden">
        <div className="rounded-2xl border border-slate-200 bg-white/85 p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900/80">
          <div className="grid grid-cols-4 gap-1 sm:grid-cols-5">
            {tabs.map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setMobileTab(tab)}
                className={[
                  "rounded-xl px-2 py-2 text-xs font-semibold transition",
                  mobileTab === tab
                    ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                    : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
                ].join(" ")}
              >
                {TAB_LABELS[tab]}
              </button>
            ))}
          </div>
        </div>
        {panelByTab[mobileTab]}
      </div>

      <div className="hidden space-y-4 xl:block">
        <FlowTimelinePanel
          stages={flowStages}
          events={flowEvents}
          mode={flowMode}
          isProcessing={isSubmitting}
        />
        <TelemetryDetailsPanel
          telemetry={telemetry}
          isProcessing={isSubmitting}
        />
        <EvidencePanel citations={citations} />
        <KnowledgeSourcesPanel
          sources={knowledgeSources}
          selectedSourceIds={selectedSourceIds}
          isLoading={isLoadingSources}
          isCreating={isCreatingSource}
          sourceError={sourceError}
          newSourceName={newSourceName}
          onSourceNameChange={onSourceNameChange}
          onToggleSource={onToggleSource}
          onCreateSource={onCreateSource}
        />
        <UploadedFilesPanel
          files={uploadedFiles}
          isUploading={isUploading}
          isDragActive={isDragActive}
          uploadError={uploadError}
          onClearAll={onClearUploadedFiles}
          onRemoveFile={onRemoveUploadedFile}
          onDrop={onDropUpload}
          onDragOver={onDragOverUpload}
          onDragEnter={onDragEnterUpload}
          onDragLeave={onDragLeaveUpload}
        />
        <DebugHintsPanel enabled={showDebugHints} {...debugHints} />
      </div>
    </aside>
  );
}
