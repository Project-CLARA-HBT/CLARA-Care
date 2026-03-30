type DebugHintsPanelProps = {
  enabled: boolean;
  roleLabel: string;
  selectedTier: "tier1" | "tier2";
  conversationCount: number;
  selectedSourceCount: number;
  uploadedFileCount: number;
  flowMode: "idle" | "flow-events" | "metadata-stages" | "local-fallback" | "server-await";
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
  researchMode?: string;
  deepPassCount?: number;
};

function formatConfidence(value?: number): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "n/a";
  return value.toFixed(2);
}

export default function DebugHintsPanel({
  enabled,
  roleLabel,
  selectedTier,
  conversationCount,
  selectedSourceCount,
  uploadedFileCount,
  flowMode,
  policyAction,
  fallbackUsed,
  verificationVerdict,
  verificationConfidence,
  routingRole,
  routingIntent,
  routingConfidence,
  pipeline,
  telemetryKeywordCount,
  telemetryDocCount,
  telemetrySourceAttemptCount,
  telemetryErrorCount,
  telemetryTopError,
  crawlDomainCount,
  researchMode,
  deepPassCount
}: DebugHintsPanelProps) {
  if (!enabled) return null;

  return (
    <section className="rounded-3xl border border-dashed border-slate-300 bg-white/90 p-4 shadow-sm dark:border-slate-600 dark:bg-slate-900/85">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Admin Runtime Hints</p>
      <div className="mt-2 grid gap-2 text-xs text-slate-700 dark:text-slate-300">
        <p>role_label: {roleLabel}</p>
        <p>tier_mode: {selectedTier}</p>
        <p>history_count: {conversationCount}</p>
        <p>source_selected: {selectedSourceCount}</p>
        <p>uploaded_files: {uploadedFileCount}</p>
        <p>flow_mode: {flowMode}</p>
        <p>policy_action: {policyAction ?? "n/a"}</p>
        <p>fallback_used: {typeof fallbackUsed === "boolean" ? String(fallbackUsed) : "n/a"}</p>
        <p>verification: {verificationVerdict ?? "n/a"}</p>
        <p>verification_confidence: {formatConfidence(verificationConfidence)}</p>
        <p>routing_role: {routingRole ?? "n/a"}</p>
        <p>routing_intent: {routingIntent ?? "n/a"}</p>
        <p>routing_confidence: {formatConfidence(routingConfidence)}</p>
        <p>pipeline: {pipeline ?? "n/a"}</p>
        <p>research_mode: {researchMode ?? "n/a"}</p>
        <p>deep_pass_count: {deepPassCount ?? 0}</p>
        <p>telemetry_keywords: {telemetryKeywordCount ?? 0}</p>
        <p>telemetry_docs: {telemetryDocCount ?? 0}</p>
        <p>telemetry_source_attempts: {telemetrySourceAttemptCount ?? 0}</p>
        <p>telemetry_errors: {telemetryErrorCount ?? 0}</p>
        <p>crawl_domains: {crawlDomainCount ?? 0}</p>
        <p>telemetry_top_error: {telemetryTopError ?? "n/a"}</p>
      </div>
    </section>
  );
}
