import { useMemo } from "react";
import {
  formatLocaleDate,
  formatLocaleNumber,
  t,
  type UITranslationKey,
} from "@/lib/i18n/catalog";
import {
  ResearchFlowEvent,
  ResearchFlowStage,
  ResearchFlowStageStatus,
} from "@/lib/research";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

type FlowTimelineMode =
  | "idle"
  | "flow-events"
  | "metadata-stages"
  | "local-fallback"
  | "server-await";

type FlowTimelinePanelProps = {
  stages: ResearchFlowStage[];
  events: ResearchFlowEvent[];
  isProcessing: boolean;
  mode: FlowTimelineMode;
};

type TimelineSummary = {
  total: number;
  pending: number;
  inProgress: number;
  completed: number;
  warning: number;
  failed: number;
  skipped: number;
};

const STATUS_META: Record<
  ResearchFlowStageStatus,
  {
    markerClass: string;
    badgeClass: string;
    lineClass: string;
  }
> = {
  pending: {
    markerClass: "border-[color:var(--shell-border)] bg-[var(--surface-panel)]",
    badgeClass: "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
    lineClass: "bg-[var(--shell-border)]",
  },
  in_progress: {
    markerClass: "border-[color:var(--brand-primary)] bg-[var(--brand-primary)]",
    badgeClass: "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
    lineClass: "bg-[var(--brand-primary)]",
  },
  completed: {
    markerClass: "border-[color:var(--brand-primary)] bg-[var(--brand-primary)]",
    badgeClass: "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]",
    lineClass: "bg-[var(--brand-primary)]",
  },
  warning: {
    markerClass: "border-[color:var(--status-warn-border)] bg-[var(--status-warn-text)]",
    badgeClass: "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]",
    lineClass: "bg-[var(--status-warn-text)]",
  },
  failed: {
    markerClass: "border-[color:var(--status-danger-border)] bg-[var(--status-danger-text)]",
    badgeClass: "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]",
    lineClass: "bg-[var(--status-danger-text)]",
  },
  skipped: {
    markerClass: "border-[color:var(--shell-border)] bg-[var(--shell-border)]",
    badgeClass: "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]",
    lineClass: "bg-[var(--shell-border)]",
  },
};

function normalizeStatus(status?: string): ResearchFlowStageStatus {
  const value = (status ?? "").toLowerCase();
  if (value in STATUS_META) return value as ResearchFlowStageStatus;
  return "pending";
}

function statusLabel(
  language: UILanguage,
  status: ResearchFlowStageStatus,
): string {
  return t(
    language,
    `research.workspace.timeline.status.${status}` as UITranslationKey,
  );
}

function resolveModeLabel(
  language: UILanguage,
  mode: FlowTimelineMode,
): string {
  const key: Record<FlowTimelineMode, UITranslationKey> = {
    idle: "research.workspace.timeline.mode.idle",
    "flow-events": "research.workspace.timeline.mode.flowEvents",
    "metadata-stages": "research.workspace.timeline.mode.serverStages",
    "local-fallback": "research.workspace.timeline.mode.localFallback",
    "server-await": "research.workspace.timeline.mode.serverAwait",
  };
  return t(language, key[mode]);
}

function formatEventTime(language: UILanguage, value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return formatLocaleDate(language, date, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(
  language: UILanguage,
  durationMs?: number,
): string | null {
  if (
    durationMs === undefined ||
    !Number.isFinite(durationMs) ||
    durationMs < 0
  )
    return null;
  if (durationMs < 1000)
    return `${formatLocaleNumber(language, Math.round(durationMs))} ms`;
  const seconds = durationMs / 1000;
  if (seconds < 60) return `${formatLocaleNumber(language, seconds)} s`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = Math.round(seconds % 60);
  return `${formatLocaleNumber(language, minutes)} min ${formatLocaleNumber(language, remainSeconds)} s`;
}

function formatPayloadPreview(
  language: UILanguage,
  payload?: Record<string, unknown>,
): string {
  if (!payload) return "";

  const parts: string[] = [];
  if (typeof payload.elapsed_seconds === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.elapsed")}=${formatLocaleNumber(language, payload.elapsed_seconds)} s`,
    );
  }
  if (typeof payload.progress_percent === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.progress")}=${formatLocaleNumber(language, payload.progress_percent)}%`,
    );
  }
  if (typeof payload.heartbeat_seq === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.tick")}=#${formatLocaleNumber(language, payload.heartbeat_seq)}`,
    );
  }
  if (typeof payload.top_k === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.topK")}=${formatLocaleNumber(language, payload.top_k)}`,
    );
  }
  if (typeof payload.source_count === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.sources")}=${formatLocaleNumber(language, payload.source_count)}`,
    );
  }
  if (typeof payload.total_candidates === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.candidates")}=${formatLocaleNumber(language, payload.total_candidates)}`,
    );
  }
  if (typeof payload.selected_count === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.selected")}=${formatLocaleNumber(language, payload.selected_count)}`,
    );
  }
  if (typeof payload.pass_index === "number") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.pass")}=${formatLocaleNumber(language, payload.pass_index)}`,
    );
  }
  if (typeof payload.phase === "string") {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.phase")}=${payload.phase}`,
    );
  }
  if (Array.isArray(payload.top_docs) && payload.top_docs.length > 0) {
    parts.push(
      `${t(language, "research.workspace.timeline.payload.topDocuments")}=${formatLocaleNumber(language, payload.top_docs.length)}`,
    );
  }
  if (parts.length > 0) return parts.join(" · ");

  const keyMap: Record<string, string> = {
    confidence: t(language, "research.workspace.timeline.payload.confidence"),
    severity: t(language, "research.workspace.timeline.payload.severity"),
    supported_claims: t(
      language,
      "research.workspace.timeline.payload.supportedClaims",
    ),
    total_claims: t(
      language,
      "research.workspace.timeline.payload.totalClaims",
    ),
    evidence_count: t(
      language,
      "research.workspace.timeline.payload.evidenceCount",
    ),
  };
  const keys = Object.keys(payload)
    .slice(0, 3)
    .map((item) => keyMap[item] ?? item);
  return keys.join(", ");
}

function isErrorDetail(detail?: string): boolean {
  const text = (detail ?? "").toLowerCase();
  return ["error", "failed", "timeout", "exception", "refused"].some((token) =>
    text.includes(token),
  );
}

function summarizeStages(stages: ResearchFlowStage[]): TimelineSummary {
  const summary: TimelineSummary = {
    total: stages.length,
    pending: 0,
    inProgress: 0,
    completed: 0,
    warning: 0,
    failed: 0,
    skipped: 0,
  };

  for (const stage of stages) {
    const status = normalizeStatus(stage.status);
    if (status === "pending") summary.pending += 1;
    if (status === "in_progress") summary.inProgress += 1;
    if (status === "completed") summary.completed += 1;
    if (status === "warning") summary.warning += 1;
    if (status === "failed") summary.failed += 1;
    if (status === "skipped") summary.skipped += 1;
  }
  return summary;
}

function getProgressPercent(summary: TimelineSummary): number {
  if (summary.total <= 0) return 0;
  const done =
    summary.completed + summary.warning + summary.skipped + summary.failed;
  return Math.max(0, Math.min(100, Math.round((done / summary.total) * 100)));
}

function formatPayloadValue(language: UILanguage, value: unknown): string {
  if (value == null)
    return t(language, "research.workspace.timeline.payload.empty");
  if (typeof value === "string")
    return value.length > 72 ? `${value.slice(0, 72)}...` : value;
  if (typeof value === "number")
    return Number.isFinite(value)
      ? formatLocaleNumber(language, value)
      : t(language, "research.workspace.timeline.payload.notANumber");
  if (typeof value === "boolean") return String(value);
  if (Array.isArray(value))
    return t(language, "research.workspace.timeline.payload.array", {
      count: value.length,
    });
  if (typeof value === "object")
    return t(language, "research.workspace.timeline.payload.object");
  return String(value);
}

function extractPayloadChips(
  language: UILanguage,
  payload?: Record<string, unknown>,
): Array<{ key: string; value: string }> {
  if (!payload) return [];
  const keyMap: Record<string, string> = {
    elapsed_seconds: t(language, "research.workspace.timeline.payload.elapsed"),
    heartbeat_seq: t(language, "research.workspace.timeline.payload.tick"),
    phase: t(language, "research.workspace.timeline.payload.phase"),
    progress_percent: t(
      language,
      "research.workspace.timeline.payload.progress",
    ),
    research_mode: t(language, "research.workspace.timeline.payload.mode"),
    source_mode: t(language, "research.workspace.timeline.payload.sources"),
  };
  return Object.entries(payload)
    .slice(0, 6)
    .map(([key, value]) => {
      if (key === "elapsed_seconds" && typeof value === "number") {
        return {
          key: keyMap[key] ?? key,
          value: `${formatLocaleNumber(language, value)} s`,
        };
      }
      if (key === "progress_percent" && typeof value === "number") {
        return {
          key: keyMap[key] ?? key,
          value: `${formatLocaleNumber(language, value)}%`,
        };
      }
      return {
        key: keyMap[key] ?? key,
        value: formatPayloadValue(language, value),
      };
    });
}

function safeStringifyPayload(payload?: Record<string, unknown>): string {
  if (!payload) return "";
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return "[Payload không thể stringify]";
  }
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(96, Math.max(14, Math.round(value)));
}

export default function FlowTimelinePanel({
  stages,
  events,
  isProcessing,
  mode,
}: FlowTimelinePanelProps) {
  const language = useUILanguage();
  const summary = summarizeStages(stages);
  const progressPercent = getProgressPercent(summary);
  const totalDurationMs = stages.reduce(
    (acc, stage) => acc + (stage.durationMs ?? 0),
    0,
  );
  const durationText =
    totalDurationMs > 0 ? formatDuration(language, totalDurationMs) : null;
  const liveBars = useMemo(() => {
    if (!events.length) {
      const baseline = [
        26 + summary.pending * 2,
        41 + summary.inProgress * 6,
        55 + summary.completed * 3,
        78 + summary.inProgress * 4,
        66 + summary.warning * 6,
        49 + summary.completed * 2,
        33 + summary.failed * 8,
      ];
      return baseline.map((value) => clampPercent(value));
    }

    const recent = events.slice(-7);
    const computed = recent.map((event, index) => {
      const payload = event.payload;
      const status = normalizeStatus(event.status);
      const progress =
        payload && typeof payload.progress_percent === "number"
          ? payload.progress_percent
          : undefined;
      const elapsed =
        payload && typeof payload.elapsed_seconds === "number"
          ? payload.elapsed_seconds
          : undefined;

      let score = progress ?? 34 + index * 7;
      if (elapsed !== undefined) score = Math.max(score, 22 + elapsed * 8);
      if (status === "completed") score += 11;
      if (status === "in_progress") score += 7;
      if (status === "warning") score += 3;
      if (status === "failed") score = Math.max(22, score - 8);
      return clampPercent(score);
    });

    const fallback = [28, 43, 57, 82, 68, 52, 38];
    while (computed.length < 7) {
      computed.unshift(fallback[computed.length] ?? 36);
    }
    return computed.slice(-7);
  }, [
    events,
    summary.completed,
    summary.failed,
    summary.inProgress,
    summary.pending,
    summary.warning,
  ]);

  return (
    <section className="research-panel-modern rounded-[1.35rem] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          {t(language, "research.workspace.timeline.title")}
        </p>
        <span className="research-chip rounded-full px-2 py-0.5 text-[11px]">
          {stages.length}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="research-chip rounded-full px-2.5 py-1 text-[11px] font-medium">
          {resolveModeLabel(language, mode)}
        </span>
        {durationText ? (
          <span className="research-chip rounded-full border-cyan-300/60 bg-cyan-500/10 px-2.5 py-1 text-[11px] font-medium text-cyan-700 dark:text-cyan-200">
            {t(language, "research.workspace.timeline.totalDuration")}:{" "}
            {durationText}
          </span>
        ) : null}
        {isProcessing ? (
          <span className="research-chip-cyan inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
            {t(language, "research.workspace.timeline.processing")}
          </span>
        ) : null}
      </div>

      <div className="research-live-engine mt-3 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[10px] font-bold uppercase tracking-[0.17em] text-cyan-200/95 dark:text-cyan-100">
            {t(language, "research.workspace.timeline.liveEngine")}
          </p>
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-cyan-200 dark:text-cyan-100">
            <span className="research-pulse-dot" />
            {t(language, "research.workspace.timeline.active")}
          </span>
        </div>
        <div className="h-16">
          <div className="research-live-bars">
            {liveBars.map((height, index) => (
              <span
                key={`flow-live-bar-${index}`}
                className="research-live-bar"
                style={{
                  height: `${height}%`,
                  opacity: `${0.42 + index * 0.08}`,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {stages.length ? (
        <div className="mt-3 rounded-xl border border-cyan-200/30 bg-cyan-500/5 p-3 dark:border-cyan-900/60 dark:bg-cyan-950/20">
          <div className="flex items-center justify-between gap-2 text-xs">
            <p className="font-semibold text-[var(--text-primary)]">
              {t(language, "research.workspace.timeline.progress")}
            </p>
            <p className="text-[var(--text-secondary)]">{progressPercent}%</p>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200/80 dark:bg-slate-800/80">
            <div
              className={[
                "h-full transition-all",
                summary.failed
                  ? "bg-rose-500"
                  : summary.warning
                    ? "bg-amber-500"
                    : "bg-emerald-500",
              ].join(" ")}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
            <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
              {t(language, "research.workspace.timeline.count.completed", {
                count: summary.completed,
              })}
            </span>
            <span className="rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-sky-700 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-300">
              {t(language, "research.workspace.timeline.count.inProgress", {
                count: summary.inProgress,
              })}
            </span>
            <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
              {t(language, "research.workspace.timeline.count.warning", {
                count: summary.warning,
              })}
            </span>
            <span className="rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-rose-700 dark:border-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
              {t(language, "research.workspace.timeline.count.failed", {
                count: summary.failed,
              })}
            </span>
            <span className="rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {t(language, "research.workspace.timeline.count.pending", {
                count: summary.pending,
              })}
            </span>
          </div>
        </div>
      ) : null}

      {stages.length ? (
        <ol className="mt-4 space-y-2">
          {stages.map((stage, index) => {
            const status = STATUS_META[normalizeStatus(stage.status)];
            const isLast = index === stages.length - 1;
            return (
              <li
                key={`${stage.id}-${index}`}
                className="relative rounded-2xl border border-cyan-200/30 bg-white/55 p-3 dark:border-cyan-900/40 dark:bg-slate-900/45"
              >
                <div className="flex items-start gap-3">
                  <div className="relative mt-0.5 flex w-4 justify-center">
                    <span
                      className={[
                        "h-3.5 w-3.5 rounded-full border-2",
                        status.markerClass,
                      ].join(" ")}
                    />
                    {!isLast ? (
                      <span
                        className={[
                          "absolute top-4 h-8 w-0.5",
                          status.lineClass,
                        ].join(" ")}
                      />
                    ) : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {stage.label}
                      </p>
                      <span
                        className={[
                          "rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                          status.badgeClass,
                        ].join(" ")}
                      >
                        {statusLabel(language, normalizeStatus(stage.status))}
                      </span>
                    </div>
                    {stage.detail ? (
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">
                        {stage.detail}
                      </p>
                    ) : null}
                    {stage.start ||
                    stage.end ||
                    stage.durationMs !== undefined ||
                    stage.eventCount !== undefined ? (
                      <div className="mt-1 flex flex-wrap gap-1 text-[10px]">
                        {stage.start ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(language, "research.workspace.timeline.started")}
                            : {formatEventTime(language, stage.start)}
                          </span>
                        ) : null}
                        {stage.end ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(language, "research.workspace.timeline.ended")}:{" "}
                            {formatEventTime(language, stage.end)}
                          </span>
                        ) : null}
                        {formatDuration(language, stage.durationMs) ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(
                              language,
                              "research.workspace.timeline.duration",
                            )}
                            : {formatDuration(language, stage.durationMs)}
                          </span>
                        ) : null}
                        {stage.eventCount !== undefined ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(language, "research.workspace.timeline.events")}:{" "}
                            {formatLocaleNumber(language, stage.eventCount)}
                          </span>
                        ) : null}
                        {stage.sourceCount !== undefined ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(language, "research.workspace.timeline.sources")}
                            : {formatLocaleNumber(language, stage.sourceCount)}
                          </span>
                        ) : null}
                        {stage.componentCount !== undefined ? (
                          <span className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                            {t(
                              language,
                              "research.workspace.timeline.components",
                            )}
                            :{" "}
                            {formatLocaleNumber(language, stage.componentCount)}
                          </span>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
          {isProcessing
            ? t(language, "research.workspace.timeline.waiting")
            : t(language, "research.workspace.timeline.empty")}
        </p>
      )}

      {events.length ? (
        <div className="mt-4 rounded-2xl border border-cyan-200/30 bg-cyan-500/5 p-3 dark:border-cyan-900/55 dark:bg-cyan-950/18">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">
            {t(language, "research.workspace.timeline.eventLog")}
          </p>
          <ul className="mt-2 max-h-[22rem] space-y-1.5 overflow-y-auto pr-1">
            {events.slice(-10).map((event) => {
              const status = STATUS_META[normalizeStatus(event.status)];
              const payloadPreview = formatPayloadPreview(
                language,
                event.payload,
              );
              const payloadChips = extractPayloadChips(language, event.payload);
              return (
                <li
                  key={event.id}
                  className="rounded-lg border border-cyan-200/35 bg-white/80 p-2 text-xs text-slate-600 dark:border-cyan-900/45 dark:bg-slate-900/55 dark:text-slate-300"
                >
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="font-semibold text-slate-700 dark:text-slate-200">
                      {event.label}
                    </span>
                    {event.component ? (
                      <span className="rounded-md border border-slate-200 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
                        {event.component}
                      </span>
                    ) : null}
                    <span
                      className={[
                        "rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase",
                        status.badgeClass,
                      ].join(" ")}
                    >
                      {statusLabel(language, normalizeStatus(event.status))}
                    </span>
                    {event.timestamp ? (
                      <span className="text-[11px] opacity-80">
                        {formatEventTime(language, event.timestamp)}
                      </span>
                    ) : null}
                  </div>
                  {event.detail ? (
                    <p
                      className={[
                        "mt-0.5 text-[11px]",
                        isErrorDetail(event.detail)
                          ? "font-medium text-rose-700 dark:text-rose-300"
                          : "text-slate-500 dark:text-slate-400",
                      ].join(" ")}
                    >
                      {event.detail}
                    </p>
                  ) : null}
                  {payloadPreview ? (
                    <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">
                      {payloadPreview}
                    </p>
                  ) : null}
                  {payloadChips.length ? (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {payloadChips.map((chip) => (
                        <span
                          key={`${event.id}-${chip.key}`}
                          className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                        >
                          {chip.key}: {chip.value}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {event.payload ? (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        {t(
                          language,
                          "research.workspace.timeline.payload.details",
                        )}
                      </summary>
                      <pre className="mt-1 overflow-x-auto rounded-md border border-slate-200 bg-slate-50 p-2 text-[10px] text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                        {safeStringifyPayload(event.payload)}
                      </pre>
                    </details>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
