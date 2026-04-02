"use client";

type CouncilFlowCanvasProps = {
  isEmergency: boolean;
  needsMoreInfo: boolean;
  hasCitations: boolean;
  confidenceScore: number | null;
};

type FlowNode = {
  id: string;
  title: string;
  subtitle: string;
  x: number;
  y: number;
  kind: "core" | "branch";
};

type FlowEdge = {
  from: string;
  to: string;
  bend?: number;
  dashed?: boolean;
  branch?: "needs_more_info" | "emergency";
};

const NODE_WIDTH = 188;
const NODE_HEIGHT = 72;
const SCENE_WIDTH = 1560;
const SCENE_HEIGHT = 700;

const NODES: FlowNode[] = [
  { id: "input", title: "Case Intake", subtitle: "Transcript / Audio", x: 56, y: 286, kind: "core" },
  { id: "extract", title: "Intake Extractor", subtitle: "DeepSeek + fallback", x: 270, y: 286, kind: "core" },
  { id: "quality", title: "Quality Gate", subtitle: "Data score + confidence", x: 484, y: 286, kind: "core" },
  { id: "orchestrator", title: "Council Orchestrator", subtitle: "Specialist routing", x: 698, y: 286, kind: "core" },
  { id: "safety", title: "Safety Guard", subtitle: "Red-flag + negation", x: 912, y: 196, kind: "core" },
  { id: "consensus", title: "Consensus Engine", subtitle: "Conflict + triage", x: 1126, y: 286, kind: "core" },
  { id: "citations", title: "Evidence Builder", subtitle: "Citations + trace", x: 912, y: 376, kind: "branch" },
  { id: "followup", title: "Follow-up Branch", subtitle: "Needs more info", x: 698, y: 466, kind: "branch" },
  { id: "emergency", title: "Emergency Branch", subtitle: "Immediate escalation", x: 1126, y: 56, kind: "branch" },
  { id: "workspace", title: "Council Workspace", subtitle: "Analyze / Details / Deepdive", x: 1340, y: 286, kind: "core" },
];

const EDGES: FlowEdge[] = [
  { from: "input", to: "extract" },
  { from: "extract", to: "quality" },
  { from: "quality", to: "orchestrator" },
  { from: "orchestrator", to: "safety", bend: -18 },
  { from: "safety", to: "consensus", bend: 20 },
  { from: "consensus", to: "workspace" },
  { from: "consensus", to: "citations", bend: -26 },
  { from: "citations", to: "workspace", bend: 32 },
  { from: "quality", to: "followup", bend: 44, dashed: true, branch: "needs_more_info" },
  { from: "safety", to: "emergency", bend: -54, dashed: true, branch: "emergency" },
];

function getNodeById(id: string): FlowNode {
  const node = NODES.find((item) => item.id === id);
  if (!node) {
    throw new Error(`Missing node: ${id}`);
  }
  return node;
}

function edgePath(from: FlowNode, to: FlowNode, bend = 0): string {
  const sx = from.x + NODE_WIDTH;
  const sy = from.y + NODE_HEIGHT / 2;
  const ex = to.x;
  const ey = to.y + NODE_HEIGHT / 2;
  const cx = (sx + ex) / 2 + bend;
  return `M ${sx} ${sy} C ${cx} ${sy}, ${cx} ${ey}, ${ex} ${ey}`;
}

function nodePalette(node: FlowNode, props: CouncilFlowCanvasProps): {
  fill: string;
  stroke: string;
  title: string;
  subtitle: string;
} {
  const inactive = {
    fill: "#f1f5f9",
    stroke: "#cbd5e1",
    title: "#334155",
    subtitle: "#64748b",
  };

  if (node.id === "followup") {
    if (!props.needsMoreInfo) return inactive;
    return {
      fill: "#fef3c7",
      stroke: "#f59e0b",
      title: "#92400e",
      subtitle: "#b45309",
    };
  }

  if (node.id === "emergency") {
    if (!props.isEmergency) return inactive;
    return {
      fill: "#fee2e2",
      stroke: "#ef4444",
      title: "#991b1b",
      subtitle: "#b91c1c",
    };
  }

  if (node.id === "citations") {
    if (!props.hasCitations) return inactive;
    return {
      fill: "#dcfce7",
      stroke: "#22c55e",
      title: "#166534",
      subtitle: "#15803d",
    };
  }

  if (node.kind === "branch") {
    return {
      fill: "#e2e8f0",
      stroke: "#94a3b8",
      title: "#334155",
      subtitle: "#64748b",
    };
  }

  return {
    fill: "#e0f2fe",
    stroke: "#0ea5e9",
    title: "#0c4a6e",
    subtitle: "#0369a1",
  };
}

function edgeStroke(edge: FlowEdge, props: CouncilFlowCanvasProps): string {
  if (edge.branch === "emergency") {
    return props.isEmergency ? "#ef4444" : "#94a3b8";
  }
  if (edge.branch === "needs_more_info") {
    return props.needsMoreInfo ? "#f59e0b" : "#94a3b8";
  }
  return "#0ea5e9";
}

export default function CouncilFlowCanvas(props: CouncilFlowCanvasProps) {
  const confidenceLabel =
    typeof props.confidenceScore === "number"
      ? `${Math.round(props.confidenceScore * 100)}%`
      : "n/a";

  return (
    <section className="relative overflow-hidden rounded-[1.7rem] border border-[color:var(--shell-border)] bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.12),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(14,116,144,0.12),_transparent_28%),var(--surface-panel)] p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Council Flow Canvas</p>
          <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)] sm:text-xl">Pipeline hội chẩn từ intake đến workspace đa trang</h3>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">confidence: {confidenceLabel}</span>
          <span
            className={`rounded-full border px-2 py-1 ${
              props.needsMoreInfo
                ? "border-amber-300 bg-amber-100 text-amber-800 dark:border-amber-700/50 dark:bg-amber-950/35 dark:text-amber-200"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            needs_more_info: {props.needsMoreInfo ? "on" : "off"}
          </span>
          <span
            className={`rounded-full border px-2 py-1 ${
              props.isEmergency
                ? "border-red-300 bg-red-100 text-red-800 dark:border-red-700/50 dark:bg-red-950/35 dark:text-red-200"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            emergency: {props.isEmergency ? "on" : "off"}
          </span>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
        <svg
          viewBox={`0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`}
          className="h-[430px] w-[1400px] min-w-[1200px]"
          role="img"
          aria-label="Council consultation flow canvas"
        >
          <defs>
            <marker id="council-flow-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#0284c7" />
            </marker>
            <marker id="council-flow-arrow-muted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
            </marker>
            <marker id="council-flow-arrow-warn" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#f59e0b" />
            </marker>
            <marker id="council-flow-arrow-danger" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#ef4444" />
            </marker>
          </defs>

          {EDGES.map((edge, index) => {
            const from = getNodeById(edge.from);
            const to = getNodeById(edge.to);
            const stroke = edgeStroke(edge, props);
            const marker =
              edge.branch === "emergency"
                ? "url(#council-flow-arrow-danger)"
                : edge.branch === "needs_more_info"
                  ? props.needsMoreInfo
                    ? "url(#council-flow-arrow-warn)"
                    : "url(#council-flow-arrow-muted)"
                  : "url(#council-flow-arrow)";

            return (
              <path
                key={`${edge.from}-${edge.to}-${index}`}
                d={edgePath(from, to, edge.bend)}
                fill="none"
                stroke={stroke}
                strokeWidth={edge.dashed ? 2 : 2.6}
                strokeDasharray={edge.dashed ? "8 7" : undefined}
                markerEnd={marker}
                opacity={edge.dashed ? 0.88 : 1}
              />
            );
          })}

          {NODES.map((node) => {
            const palette = nodePalette(node, props);
            return (
              <g key={node.id}>
                <rect
                  x={node.x}
                  y={node.y}
                  width={NODE_WIDTH}
                  height={NODE_HEIGHT}
                  rx={16}
                  fill={palette.fill}
                  stroke={palette.stroke}
                  strokeWidth={2}
                />
                <text x={node.x + 12} y={node.y + 26} fontSize={14} fontWeight={700} fill={palette.title}>
                  {node.title}
                </text>
                <text x={node.x + 12} y={node.y + 46} fontSize={12} fill={palette.subtitle}>
                  {node.subtitle}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
