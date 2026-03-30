import { ResearchFlowEvent, ResearchFlowStage, ResearchFlowStageStatus } from "@/lib/research";

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

const STATUS_META: Record<
  ResearchFlowStageStatus,
  {
    label: string;
    markerClass: string;
    badgeClass: string;
    lineClass: string;
  }
> = {
  pending: {
    label: "pending",
    markerClass: "border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-900",
    badgeClass: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300",
    lineClass: "bg-slate-200 dark:bg-slate-700"
  },
  in_progress: {
    label: "in progress",
    markerClass: "border-sky-500 bg-sky-500",
    badgeClass: "border-sky-300 bg-sky-100 text-sky-700 dark:border-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
    lineClass: "bg-sky-400 dark:bg-sky-600"
  },
  completed: {
    label: "completed",
    markerClass: "border-emerald-500 bg-emerald-500",
    badgeClass: "border-emerald-300 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
    lineClass: "bg-emerald-400 dark:bg-emerald-600"
  },
  warning: {
    label: "warning",
    markerClass: "border-amber-500 bg-amber-500",
    badgeClass: "border-amber-300 bg-amber-100 text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    lineClass: "bg-amber-400 dark:bg-amber-600"
  },
  failed: {
    label: "failed",
    markerClass: "border-rose-500 bg-rose-500",
    badgeClass: "border-rose-300 bg-rose-100 text-rose-700 dark:border-rose-700 dark:bg-rose-950/40 dark:text-rose-300",
    lineClass: "bg-rose-400 dark:bg-rose-600"
  },
  skipped: {
    label: "skipped",
    markerClass: "border-slate-400 bg-slate-400",
    badgeClass: "border-slate-300 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300",
    lineClass: "bg-slate-200 dark:bg-slate-700"
  }
};

function normalizeStatus(status?: string): ResearchFlowStageStatus {
  const value = (status ?? "").toLowerCase();
  if (value in STATUS_META) return value as ResearchFlowStageStatus;
  return "pending";
}

function resolveModeLabel(mode: FlowTimelineMode): string {
  if (mode === "flow-events") return "Realtime flow events";
  if (mode === "metadata-stages") return "Server stage summary";
  if (mode === "local-fallback") return "Legacy local fallback";
  if (mode === "server-await") return "Server reasoning in progress";
  return "Waiting";
}

function formatEventTime(value?: string): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatPayloadPreview(payload?: Record<string, unknown>): string {
  if (!payload) return "";

  const parts: string[] = [];
  if (typeof payload.top_k === "number") {
    parts.push(`top_k=${payload.top_k}`);
  }
  if (typeof payload.source_count === "number") {
    parts.push(`source_count=${payload.source_count}`);
  }
  if (typeof payload.total_candidates === "number") {
    parts.push(`candidates=${payload.total_candidates}`);
  }
  if (typeof payload.selected_count === "number") {
    parts.push(`selected=${payload.selected_count}`);
  }
  if (typeof payload.pass_index === "number") {
    parts.push(`pass=${payload.pass_index}`);
  }
  if (typeof payload.phase === "string") {
    parts.push(`phase=${payload.phase}`);
  }
  if (Array.isArray(payload.top_docs) && payload.top_docs.length > 0) {
    parts.push(`top_docs=${payload.top_docs.length}`);
  }
  if (typeof payload.error === "string" && payload.error.trim()) {
    parts.push(`error=${payload.error}`);
  }
  if (parts.length > 0) return parts.join(" · ");

  const keys = Object.keys(payload).slice(0, 3);
  return keys.join(", ");
}

function isErrorDetail(detail?: string): boolean {
  const text = (detail ?? "").toLowerCase();
  return ["error", "failed", "timeout", "exception", "refused"].some((token) =>
    text.includes(token)
  );
}

export default function FlowTimelinePanel({
  stages,
  events,
  isProcessing,
  mode
}: FlowTimelinePanelProps) {
  return (
    <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Flow Timeline</p>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {stages.length}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {resolveModeLabel(mode)}
        </span>
        {isProcessing ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-300 bg-sky-100 px-2.5 py-1 text-[11px] font-semibold text-sky-700 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
            Đang xử lý
          </span>
        ) : null}
      </div>

      {stages.length ? (
        <ol className="mt-4 space-y-2">
          {stages.map((stage, index) => {
            const status = STATUS_META[normalizeStatus(stage.status)];
            const isLast = index === stages.length - 1;
            return (
              <li key={`${stage.id}-${index}`} className="relative rounded-2xl border border-slate-200 bg-slate-50/80 p-3 dark:border-slate-700 dark:bg-slate-800/70">
                <div className="flex items-start gap-3">
                  <div className="relative mt-0.5 flex w-4 justify-center">
                    <span className={["h-3.5 w-3.5 rounded-full border-2", status.markerClass].join(" ")} />
                    {!isLast ? <span className={["absolute top-4 h-8 w-0.5", status.lineClass].join(" ")} /> : null}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{stage.label}</p>
                      <span className={["rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", status.badgeClass].join(" ")}>
                        {status.label}
                      </span>
                    </div>
                    {stage.detail ? (
                      <p className="mt-1 text-xs text-slate-600 dark:text-slate-300">{stage.detail}</p>
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
            ? "Server đang xử lý. Timeline sẽ hiển thị khi backend trả flow events/stages thật."
            : "Backend chưa trả telemetry flow cho phiên này, nên không hiển thị stage giả lập sau khi hoàn tất."}
        </p>
      )}

      {events.length ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-3 dark:border-slate-700 dark:bg-slate-800/70">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Event Log</p>
          <ul className="mt-2 space-y-1.5">
            {events.slice(-6).map((event) => {
              const status = STATUS_META[normalizeStatus(event.status)];
              const payloadPreview = formatPayloadPreview(event.payload);
              return (
                <li key={event.id} className="text-xs text-slate-600 dark:text-slate-300">
                  <div className="flex flex-wrap items-center gap-1">
                    <span className="font-semibold text-slate-700 dark:text-slate-200">{event.label}</span>
                    {event.component ? (
                      <span className="rounded-md border border-slate-200 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
                        {event.component}
                      </span>
                    ) : null}
                    <span className={["rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase", status.badgeClass].join(" ")}>
                      {status.label}
                    </span>
                    {event.timestamp ? <span className="text-[11px] opacity-80">{formatEventTime(event.timestamp)}</span> : null}
                  </div>
                  {event.detail ? (
                    <p
                      className={[
                        "mt-0.5 text-[11px]",
                        isErrorDetail(event.detail)
                          ? "font-medium text-rose-700 dark:text-rose-300"
                          : "text-slate-500 dark:text-slate-400"
                      ].join(" ")}
                    >
                      {event.detail}
                    </p>
                  ) : null}
                  {payloadPreview ? (
                    <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{payloadPreview}</p>
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
