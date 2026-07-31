"use client";

import { DragEvent, FormEvent, useMemo, useState } from "react";
import {
  KnowledgeSource,
  ResearchFlowEvent,
  ResearchFlowStage,
  ResearchTier2PolicyAction,
  ResearchTier2Telemetry,
  Tier2Citation,
  UploadedResearchFile
} from "@/lib/research";
import DebugHintsPanel from "./debug-hints-panel";
import EvidencePanel from "./evidence-panel";
import ConsensusPanel from "./consensus-panel";
import FlowTimelinePanel from "./flow-timeline-panel";
import KnowledgeSourcesPanel from "./knowledge-sources-panel";
import TelemetryDetailsPanel from "./telemetry-details-panel";
import UploadedFilesPanel from "./uploaded-files-panel";
import TelemetryPanel, { isTelemetryVisible } from "@/components/telemetry/telemetry-panel";
import { getRole, type UserRole } from "@/lib/auth-store";

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

  /**
   * Requesting user's role. The detailed Flow Timeline, Telemetry Detail, and
   * Admin Runtime Hints panels are rendered for Admin_Users only; non-admin
   * roles never see them (Requirement 4.3). Defaults to the current stored
   * role when omitted.
   */
  role?: UserRole;

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
    policyAction?: ResearchTier2PolicyAction;
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
  role,
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
  // Detailed telemetry (flow timeline, telemetry detail, debug hints) is
  // Admin_User-only; non-admin roles only get evidence/sources/uploads.
  const viewerRole = role ?? getRole();
  const showTelemetry = isTelemetryVisible(viewerRole);
  const [mobileTab, setMobileTab] = useState<MobileTab>(showTelemetry ? "flow" : "evidence");

  const tabs = useMemo(() => {
    const base: MobileTab[] = showTelemetry
      ? ["flow", "telemetry", "evidence", "sources", "uploads"]
      : ["evidence", "sources", "uploads"];
    if (showTelemetry && showDebugHints) base.push("debug");
    return base;
  }, [showDebugHints, showTelemetry]);

  const panelByTab: Record<MobileTab, JSX.Element | null> = {
    // Detailed telemetry rails (flow timeline, telemetry detail, debug hints)
    // are locked to Admin_Users via the role-gated TelemetryPanel — the same
    // pure role predicate the desktop layout uses (Requirement 11.4). The tab
    // list above already hides these tabs from non-admins; wrapping the panel
    // here is defense-in-depth so the rail can never render to a non-admin even
    // if the active tab desyncs from the role (e.g. role re-hydration), keeping
    // the gate independent of UI tab state.
    flow: (
      <TelemetryPanel role={viewerRole}>
        <FlowTimelinePanel
          stages={flowStages}
          events={flowEvents}
          mode={flowMode}
          isProcessing={isSubmitting}
        />
      </TelemetryPanel>
    ),
    telemetry: (
      <TelemetryPanel role={viewerRole}>
        <TelemetryDetailsPanel
          telemetry={telemetry}
          isProcessing={isSubmitting}
        />
      </TelemetryPanel>
    ),
    evidence: (
      <div className="space-y-4">
        <EvidencePanel citations={citations} />
        <ConsensusPanel consensus={telemetry.consensus} />
      </div>
    ),
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
    debug: (
      <TelemetryPanel role={viewerRole}>
        <DebugHintsPanel enabled={showDebugHints} {...debugHints} />
      </TelemetryPanel>
    )
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
        <TelemetryPanel role={viewerRole} className="space-y-4">
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
        </TelemetryPanel>
        <EvidencePanel citations={citations} />
        <ConsensusPanel consensus={telemetry.consensus} />
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
        <TelemetryPanel role={viewerRole}>
          <DebugHintsPanel enabled={showDebugHints} {...debugHints} />
        </TelemetryPanel>
      </div>
    </aside>
  );
}
