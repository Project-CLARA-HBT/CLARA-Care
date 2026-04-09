import { CSSProperties } from "react";

type SparklineProps = {
  points: number[];
  stroke?: string;
};

export function Sparkline({ points, stroke = "#0284c7" }: SparklineProps) {
  if (points.length === 0) {
    return <div className="h-14 rounded-xl border border-dashed border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800" />;
  }

  const width = 220;
  const height = 56;
  const padding = 5;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const line = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * (width - padding * 2) + padding;
      const y = height - padding - ((point - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
  const area = `${padding},${height - padding} ${line} ${width - padding},${height - padding}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-14 w-full rounded-lg border border-slate-200/80 bg-slate-50 dark:border-slate-700/80 dark:bg-slate-800">
      <defs>
        <linearGradient id="sparkArea" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.26" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <line
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        className="text-slate-300 dark:text-slate-700"
        stroke="currentColor"
        strokeDasharray="2 3"
      />
      <polygon points={area} fill="url(#sparkArea)" />
      <polyline points={line} fill="none" stroke={stroke} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type BarBlocksProps = {
  values: number[];
  maxHeight?: number;
  activeColor?: string;
  mutedColor?: string;
};

export function BarBlocks({
  values,
  maxHeight = 62,
  activeColor = "#0ea5e9",
  mutedColor = "#cbd5e1"
}: BarBlocksProps) {
  if (values.length === 0) {
    return <div className="h-16 rounded-xl border border-dashed border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800" />;
  }

  const max = Math.max(...values, 1);

  return (
    <div className="flex h-16 items-end gap-1.5 rounded-xl border border-slate-200 bg-gradient-to-b from-white to-slate-50 px-2 py-1 dark:border-slate-700 dark:from-slate-900 dark:to-slate-800">
      {values.map((value, index) => {
        const ratio = Math.max(0.12, value / max);
        const isPeak = value === max;
        const style: CSSProperties = {
          height: `${Math.round(maxHeight * ratio)}px`,
          background: isPeak
            ? `linear-gradient(180deg, ${activeColor} 0%, #0369a1 100%)`
            : `linear-gradient(180deg, ${mutedColor} 0%, #94a3b8 100%)`
        };
        return (
          <div
            key={`${index}-${value}`}
            style={style}
            className={[
              "w-3 rounded-t-md border border-slate-200/60 dark:border-slate-700/80",
              isPeak ? "shadow-[0_2px_8px_rgba(14,165,233,0.35)]" : ""
            ].join(" ")}
          />
        );
      })}
    </div>
  );
}
