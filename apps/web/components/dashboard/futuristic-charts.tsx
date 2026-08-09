"use client";

import { useId, useMemo } from "react";

type ChartFrameProps = {
  title?: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

type NeonSeries = {
  id: string;
  label: string;
  color: string;
  values: number[];
};

type NeonAreaChartProps = {
  title?: string;
  description?: string;
  labels: string[];
  series: NeonSeries[];
  height?: number;
  className?: string;
};

type SegmentRingGaugeProps = {
  label: string;
  value: number;
  max?: number;
  tone?: "cyan" | "emerald" | "amber" | "violet" | "rose";
  note?: string;
  subLabel?: string;
  color?: string;
  size?: number;
};

type RadarAxis = {
  label: string;
  value: number;
  max?: number;
};

type RadarPulseChartProps = {
  title?: string;
  description?: string;
  axes: RadarAxis[];
  size?: number;
};

type MatrixHeatmapMiniProps = {
  title?: string;
  description?: string;
  rows: string[];
  columns: string[];
  values: number[][];
  minLabel?: string;
  maxLabel?: string;
};

type TelemetryBarItem = {
  label: string;
  value: number;
  target?: number;
  tone?: "ok" | "warn" | "danger" | "error" | "neutral";
};

type TelemetryBarsProps = {
  title?: string;
  description?: string;
  items: TelemetryBarItem[];
};

type ConduitStage = {
  label: string;
  status: "ok" | "warn" | "error" | "idle";
  detail?: string;
  note?: string;
};

type ConduitFlowLineProps = {
  title?: string;
  description?: string;
  stages: ConduitStage[];
};

function clamp(value: number, min = 0, max = 100): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
}

function toValueList(series: NeonSeries[]): number[] {
  return series.flatMap((item) => item.values);
}

function formatCompact(value: number): string {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function colorForHeat(value: number): string {
  const alpha = clamp(value, 0, 100) / 100;
  if (alpha > 0.75) return `rgba(255,180,171,${0.24 + alpha * 0.54})`;
  if (alpha > 0.45) return `rgba(250,189,52,${0.2 + alpha * 0.46})`;
  return `rgba(96, 165, 250,${0.18 + alpha * 0.4})`;
}

function toneToColor(tone: TelemetryBarItem["tone"]): string {
  if (tone === "ok") return "#a4c9ff";
  if (tone === "warn") return "#fabd34";
  if (tone === "danger" || tone === "error") return "#ffb4ab";
  return "#a4c9ff";
}

function toneLabel(tone: TelemetryBarItem["tone"]): string {
  if (tone === "ok") return "Healthy";
  if (tone === "warn") return "Warning";
  if (tone === "danger" || tone === "error") return "Critical";
  return "Normal";
}

function stageTone(stage: ConduitStage["status"]): string {
  if (stage === "ok") return "border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]";
  if (stage === "warn") return "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]";
  if (stage === "error") return "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]";
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]";
}

function stageStatusLabel(stage: ConduitStage["status"]): string {
  if (stage === "ok") return "OK";
  if (stage === "warn") return "Warn";
  if (stage === "error") return "Error";
  return "Idle";
}

function stageStatusSymbol(stage: ConduitStage["status"]): string {
  if (stage === "ok") return "O";
  if (stage === "warn") return "!";
  if (stage === "error") return "X";
  return "-";
}

function ChartFrame({ title, description, children, footer }: ChartFrameProps) {
  return (
    <section className="space-y-3" aria-label={title || "chart"}>
      {title ? (
        <div>
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h3>
          {description ? <p className="text-xs text-[var(--text-secondary)]">{description}</p> : null}
        </div>
      ) : null}
      {children}
      {footer ? <div>{footer}</div> : null}
    </section>
  );
}

export function NeonAreaChart({ title, description, labels, series, height = 220, className }: NeonAreaChartProps) {
  const clipId = useId().replace(/:/g, "");

  const prepared = useMemo(() => {
    const width = 760;
    const leftPadding = 46;
    const rightPadding = 18;
    const topPadding = 16;
    const bottomPadding = 36;
    const chartHeight = Math.max(height, 190);
    const values = toValueList(series);
    const rawMax = values.length > 0 ? Math.max(...values, 1) : 1;
    const safeMax = rawMax * 1.08;
    const plotWidth = width - leftPadding - rightPadding;
    const plotHeight = chartHeight - topPadding - bottomPadding;

    const mapped = series.map((item) => {
      const points = item.values.map((value, index) => {
        const x = leftPadding + (index / Math.max(item.values.length - 1, 1)) * plotWidth;
        const y = chartHeight - bottomPadding - (clamp(value, 0, safeMax) / safeMax) * plotHeight;
        return `${x},${y}`;
      });

      const area = [
        `${leftPadding},${chartHeight - bottomPadding}`,
        ...points,
        `${width - rightPadding},${chartHeight - bottomPadding}`
      ].join(" ");

      return {
        ...item,
        points: points.join(" "),
        area,
        latestPoint: points[points.length - 1],
        latest: item.values[item.values.length - 1] ?? 0
      };
    });

    const axisY = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
      const y = chartHeight - bottomPadding - ratio * plotHeight;
      const value = Math.round(ratio * safeMax);
      return { y, value };
    });

    const xLabelStep = labels.length > 10 ? Math.ceil(labels.length / 5) : labels.length > 6 ? 2 : 1;

    return {
      width,
      chartHeight,
      leftPadding,
      rightPadding,
      topPadding,
      bottomPadding,
      mapped,
      axisY,
      xLabelStep
    };
  }, [height, labels, series]);

  if (series.length === 0 || !series.some((item) => item.values.length > 0)) {
    return (
      <ChartFrame title={title} description={description}>
        <div className="flex h-[220px] items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-sm text-[var(--text-muted)]">
          No signal data yet.
        </div>
      </ChartFrame>
    );
  }

  return (
    <div className={className}>
      <ChartFrame
      title={title}
      description={description}
      footer={
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--text-secondary)]">
          {prepared.mapped.map((item) => (
            <span
              key={item.id}
              className="inline-flex items-center gap-1 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5"
            >
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true" />
              {item.label}: {formatCompact(item.latest)}
            </span>
          ))}
        </div>
      }
      >
        <div className="rounded-[var(--radius-lg)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
        <svg
          viewBox={`0 0 ${prepared.width} ${prepared.chartHeight}`}
          className="w-full"
          style={{ height: prepared.chartHeight }}
          role="img"
          aria-label={title || "area chart"}
        >
          <defs>
            <clipPath id={`${clipId}-plot`}>
              <rect
                x={prepared.leftPadding}
                y={prepared.topPadding}
                width={prepared.width - prepared.leftPadding - prepared.rightPadding}
                height={prepared.chartHeight - prepared.topPadding - prepared.bottomPadding}
              />
            </clipPath>
          </defs>

          {prepared.axisY.map((tick) => (
            <g key={`y-${tick.y}`}>
              <line
                x1={prepared.leftPadding}
                y1={tick.y}
                x2={prepared.width - prepared.rightPadding}
                y2={tick.y}
                stroke="var(--shell-border-strong)"
                strokeOpacity="0.58"
                strokeDasharray="4 6"
              />
              <text x={10} y={tick.y + 4} fontSize="10" fill="var(--text-muted)">
                {tick.value}
              </text>
            </g>
          ))}

          <g clipPath={`url(#${clipId}-plot)`}>
            {prepared.mapped.map((item) => (
              <g key={item.id}>
                <polygon points={item.area} fill={item.color} fillOpacity="0.12" />
                <polyline
                  points={item.points}
                  fill="none"
                  stroke={item.color}
                  strokeWidth="2.35"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </g>
            ))}
          </g>

          {prepared.mapped.map((item) => {
            if (!item.latestPoint) return null;
            const [x, y] = item.latestPoint.split(",").map((segment) => Number(segment));
            return (
              <g key={`${item.id}-latest`}>
                <circle cx={x} cy={y} r="5" fill={item.color} fillOpacity="0.22" />
                <circle cx={x} cy={y} r="3" fill={item.color} stroke="var(--on-surface)" strokeOpacity="0.8" strokeWidth="1" />
              </g>
            );
          })}

          {labels.length > 0
            ? labels.map((label, index) => {
                if (index % prepared.xLabelStep !== 0 && index !== labels.length - 1) return null;
                const x =
                  prepared.leftPadding +
                  (index / Math.max(labels.length - 1, 1)) * (prepared.width - prepared.leftPadding - prepared.rightPadding);
                return (
                  <g key={`${label}-${index}`}>
                    <title>{label}</title>
                    <line x1={x} y1={prepared.topPadding} x2={x} y2={prepared.chartHeight - prepared.bottomPadding} stroke="var(--shell-border)" strokeOpacity="0.35" />
                    <text x={x} y={prepared.chartHeight - 8} fontSize="10" textAnchor="middle" fill="var(--text-muted)">
                      {label.length > 10 ? `${label.slice(0, 9)}...` : label}
                    </text>
                  </g>
                );
              })
            : null}
        </svg>
        </div>
      </ChartFrame>
    </div>
  );
}

export function SegmentRingGauge({
  label,
  value,
  max = 100,
  tone = "cyan",
  note,
  subLabel,
  color,
  size = 132
}: SegmentRingGaugeProps) {
  const safeValue = clamp(value, 0, max);
  const ratio = max > 0 ? safeValue / max : 0;
  const radius = size * 0.33;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = `${ratio * circumference} ${circumference}`;

  const toneColor =
    color ??
    (tone === "emerald"
      ? "#a4c9ff"
      : tone === "amber"
        ? "#fabd34"
        : tone === "violet"
          ? "#b4c5ff"
          : tone === "rose"
            ? "#ffb4ab"
            : "#a4c9ff");

  return (
    <div
      className="rounded-[var(--radius-lg)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5"
      role="meter"
      aria-label={`${label} gauge`}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.round(safeValue)}
    >
      <svg viewBox={`0 0 ${size} ${size}`} className="mx-auto h-[110px] w-[110px]">
        <circle cx={center} cy={center} r={radius} stroke="var(--shell-border)" strokeWidth="12" fill="none" />
        <circle cx={center} cy={center} r={radius} stroke="var(--shell-border-strong)" strokeOpacity="0.55" strokeWidth="1.5" strokeDasharray="3 8" fill="none" />
        <circle
          cx={center}
          cy={center}
          r={radius}
          stroke={toneColor}
          strokeWidth="12"
          strokeDasharray={dash}
          strokeLinecap="round"
          fill="none"
          transform={`rotate(-90 ${center} ${center})`}
        />
        <circle cx={center} cy={center} r={size * 0.2} fill="rgba(15,23,42,0.06)" />
      </svg>
      <p className="-mt-16 text-center font-mono text-xl font-semibold text-[var(--text-primary)]">
        {Math.round(safeValue)}
        <span className="text-xs text-[var(--text-muted)]">/{Math.round(max)}</span>
      </p>
      <p className="mt-8 text-center text-xs font-semibold text-[var(--text-secondary)]">{label}</p>
      {subLabel ? <p className="mt-1 text-center text-[11px] text-[var(--text-muted)]">{subLabel}</p> : null}
      {note ? <p className="mt-1 text-center text-[11px] text-[var(--text-muted)]">{note}</p> : null}
    </div>
  );
}

export function RadarPulseChart({ title, description, axes, size = 280 }: RadarPulseChartProps) {
  const canvasPadding = 26;
  const canvas = size + canvasPadding * 2;
  const count = Math.max(axes.length, 3);
  const center = canvas / 2;
  const radius = size * 0.28;

  const points = axes.map((axis, index) => {
    const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
    const max = Math.max(axis.max ?? 100, 1);
    const ratio = clamp(axis.value, 0, max) / max;
    const x = center + Math.cos(angle) * radius * ratio;
    const y = center + Math.sin(angle) * radius * ratio;
    const labelX = center + Math.cos(angle) * (radius + 32);
    const labelY = center + Math.sin(angle) * (radius + 32);
    return { x, y, labelX, labelY, label: axis.label, value: axis.value };
  });

  const polygon = points.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <ChartFrame title={title} description={description}>
      <div className="rounded-[var(--radius-lg)] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
        <svg viewBox={`0 0 ${canvas} ${canvas}`} className="h-[260px] w-full" role="img" aria-label={title || "radar chart"}>
          {[1, 0.75, 0.5, 0.25].map((step) => {
            const ring = axes
              .map((_, index) => {
                const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
                const x = center + Math.cos(angle) * radius * step;
                const y = center + Math.sin(angle) * radius * step;
                return `${x},${y}`;
              })
              .join(" ");
            return <polygon key={step} points={ring} fill="none" stroke="var(--shell-border-strong)" strokeOpacity="0.48" strokeWidth="1" />;
          })}

          {points.map((point, index) => (
            <line key={`axis-${index}`} x1={center} y1={center} x2={point.labelX} y2={point.labelY} stroke="var(--shell-border)" strokeOpacity="0.6" />
          ))}

          <polygon points={polygon} fill="#a4c9ff" fillOpacity="0.18" stroke="#a4c9ff" strokeWidth="2.1" />
          {points.map((point, index) => (
            <g key={`point-${index}`}>
              <circle cx={point.x} cy={point.y} r="4.2" fill="#a4c9ff" />
              <text x={point.labelX} y={point.labelY} textAnchor="middle" fontSize="11" fill="var(--text-secondary)">
                {point.label.length > 11 ? `${point.label.slice(0, 10)}...` : point.label}
                <title>{`${point.label}: ${Math.round(point.value)}`}</title>
              </text>
            </g>
          ))}

          <circle cx={center} cy={center} r="5" fill="#a4c9ff" />
        </svg>
      </div>
    </ChartFrame>
  );
}

export function MatrixHeatmapMini({
  title,
  description,
  rows,
  columns,
  values,
  minLabel = "Lower",
  maxLabel = "Higher"
}: MatrixHeatmapMiniProps) {
  if (rows.length === 0 || columns.length === 0) {
    return (
      <ChartFrame title={title} description={description}>
        <div className="flex h-[220px] items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-sm text-[var(--text-muted)]">
          No matrix data.
        </div>
      </ChartFrame>
    );
  }

  return (
    <ChartFrame
      title={title}
      description={description}
      footer={
        <div className="flex items-center justify-between text-[11px] text-[var(--text-muted)]">
          <span>{minLabel}</span>
          <span>{maxLabel}</span>
        </div>
      }
    >
      <div className="overflow-auto rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
        <table className="w-full border-separate border-spacing-1.5 text-[11px]">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left font-medium text-[var(--text-muted)]" />
              {columns.map((column) => (
                <th key={column} className="px-2 py-1 text-left font-medium text-[var(--text-muted)]">
                  <span className="rounded bg-[var(--surface-muted)] px-1.5 py-0.5">
                    {column}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={row}>
                <th className="whitespace-nowrap px-2 py-1 text-left font-medium text-[var(--text-secondary)]">{row}</th>
                {columns.map((column, columnIndex) => {
                  const value = values[rowIndex]?.[columnIndex] ?? 0;
                  return (
                    <td key={`${row}-${column}`}>
                      <div
                        className="rounded-md border border-[color:var(--shell-border-strong)]/50 px-2 py-1 text-right font-mono text-[var(--text-primary)]"
                        style={{ backgroundColor: colorForHeat(value) }}
                        aria-label={`${row} ${column} ${Math.round(value)}`}
                      >
                        {Math.round(value)}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ChartFrame>
  );
}

export function TelemetryBars({ title, description, items }: TelemetryBarsProps) {
  const max = Math.max(
    ...items.flatMap((item) => [item.value, item.target ?? 0]),
    1
  );

  if (items.length === 0) {
    return (
      <ChartFrame title={title} description={description}>
        <div className="flex h-[220px] items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-sm text-[var(--text-muted)]">
          No telemetry data.
        </div>
      </ChartFrame>
    );
  }

  return (
    <ChartFrame title={title} description={description}>
      <div className="space-y-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
        {items.map((item) => {
          const ratio = clamp(item.value, 0, max) / max;
          const targetRatio = clamp(item.target ?? 0, 0, max) / max;
          const color = toneToColor(item.tone);
          const status = toneLabel(item.tone);
          return (
            <div key={item.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                  {item.label}
                  <span className="rounded border border-[color:var(--shell-border)] px-1.5 py-0 text-[10px] text-[var(--text-muted)]">{status}</span>
                </span>
                <span className="font-mono text-[var(--text-primary)]">
                  {Math.round(item.value)}
                  {item.target !== undefined ? <span className="text-[var(--text-muted)]"> / {Math.round(item.target)}</span> : null}
                </span>
              </div>
              <div className="relative h-2.5 overflow-hidden rounded-full bg-[var(--surface-container-highest)]">
                {item.target !== undefined ? (
                  <span
                    className="absolute inset-y-0 w-px bg-[var(--on-surface)]/75"
                    style={{ left: `${targetRatio * 100}%` }}
                    aria-hidden="true"
                  />
                ) : null}
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${ratio * 100}%`,
                    background: color
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </ChartFrame>
  );
}

export function ConduitFlowLine({ title, description, stages }: ConduitFlowLineProps) {
  if (stages.length === 0) {
    return (
      <ChartFrame title={title} description={description}>
        <div className="flex h-28 items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-sm text-[var(--text-muted)]">
          No pipeline stages.
        </div>
      </ChartFrame>
    );
  }

  return (
    <ChartFrame title={title} description={description}>
      <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
        <div className="flex flex-wrap items-center gap-2">
          {stages.map((stage, index) => (
            <div key={`${stage.label}-${index}`} className="flex items-center gap-2">
              <div className={`rounded-lg border px-2.5 py-1 text-[11px] font-semibold ${stageTone(stage.status)}`} role="status" aria-label={`${stage.label} ${stageStatusLabel(stage.status)}`}>
                <p className="flex items-center gap-1.5">
                  <span aria-hidden="true">{stageStatusSymbol(stage.status)}</span>
                  {stage.label}
                </p>
                <p className="mt-0.5 text-[10px] opacity-90">{stageStatusLabel(stage.status)}</p>
                {stage.note || stage.detail ? <p className="mt-0.5 text-[10px] opacity-85">{stage.note ?? stage.detail}</p> : null}
              </div>
              {index < stages.length - 1 ? (
                <div className="relative h-[2px] w-7 overflow-hidden rounded bg-[var(--surface-brand-soft)]">
                  <span className="absolute inset-y-0 left-0 w-1/2 animate-pulse bg-[var(--brand-primary)]" />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </ChartFrame>
  );
}
