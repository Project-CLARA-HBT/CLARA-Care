import { CSSProperties } from "react";

type SparklineProps = {
  points: number[];
  stroke?: string;
};

export function Sparkline({ points, stroke = "#a4c9ff" }: SparklineProps) {
  if (points.length === 0) {
    return <div className="h-14 rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]" />;
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
    <svg viewBox={`0 0 ${width} ${height}`} className="h-14 w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
      <defs>
      </defs>
      <line
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        stroke="#414751"
        strokeDasharray="2 3"
      />
      <polygon points={area} fill={stroke} fillOpacity="0.12" />
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
  activeColor = "#60a5fa",
  mutedColor = "#414751"
}: BarBlocksProps) {
  if (values.length === 0) {
    return <div className="h-16 rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)]" />;
  }

  const max = Math.max(...values, 1);

  return (
    <div className="flex h-16 items-end gap-1.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1">
      {values.map((value, index) => {
        const ratio = Math.max(0.12, value / max);
        const isPeak = value === max;
        const style: CSSProperties = {
          height: `${Math.round(maxHeight * ratio)}px`,
          background: isPeak ? activeColor : mutedColor
        };
        return (
          <div
            key={`${index}-${value}`}
            style={style}
            className={[
              "w-3 rounded-t-md border border-[color:var(--shell-border)]",
            ].join(" ")}
          />
        );
      })}
    </div>
  );
}
