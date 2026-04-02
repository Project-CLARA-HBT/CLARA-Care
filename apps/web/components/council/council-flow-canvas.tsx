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
    fill: "var(--c-node-inactive-fill)",
    stroke: "var(--c-node-inactive-stroke)",
    title: "var(--c-node-inactive-title)",
    subtitle: "var(--c-node-inactive-subtitle)",
  };

  if (node.id === "followup") {
    if (!props.needsMoreInfo) return inactive;
    return {
      fill: "var(--c-node-followup-fill)",
      stroke: "var(--c-node-followup-stroke)",
      title: "var(--c-node-followup-title)",
      subtitle: "var(--c-node-followup-subtitle)",
    };
  }

  if (node.id === "emergency") {
    if (!props.isEmergency) return inactive;
    return {
      fill: "var(--c-node-emergency-fill)",
      stroke: "var(--c-node-emergency-stroke)",
      title: "var(--c-node-emergency-title)",
      subtitle: "var(--c-node-emergency-subtitle)",
    };
  }

  if (node.id === "citations") {
    if (!props.hasCitations) return inactive;
    return {
      fill: "var(--c-node-citations-fill)",
      stroke: "var(--c-node-citations-stroke)",
      title: "var(--c-node-citations-title)",
      subtitle: "var(--c-node-citations-subtitle)",
    };
  }

  if (node.kind === "branch") {
    return {
      fill: "var(--c-node-branch-fill)",
      stroke: "var(--c-node-branch-stroke)",
      title: "var(--c-node-branch-title)",
      subtitle: "var(--c-node-branch-subtitle)",
    };
  }

  return {
    fill: "var(--c-node-core-fill)",
    stroke: "var(--c-node-core-stroke)",
    title: "var(--c-node-core-title)",
    subtitle: "var(--c-node-core-subtitle)",
  };
}

function edgeStroke(edge: FlowEdge, props: CouncilFlowCanvasProps): string {
  if (edge.branch === "emergency") {
    return props.isEmergency ? "var(--c-edge-danger)" : "var(--c-edge-muted)";
  }
  if (edge.branch === "needs_more_info") {
    return props.needsMoreInfo ? "var(--c-edge-warning)" : "var(--c-edge-muted)";
  }
  return "var(--c-edge-core)";
}

function isNodeHighlighted(node: FlowNode, props: CouncilFlowCanvasProps): boolean {
  if (node.id === "followup") return props.needsMoreInfo;
  if (node.id === "emergency") return props.isEmergency;
  if (node.id === "citations") return props.hasCitations;
  return node.kind === "core";
}

export default function CouncilFlowCanvas(props: CouncilFlowCanvasProps) {
  const confidenceLabel =
    typeof props.confidenceScore === "number"
      ? `${Math.round(props.confidenceScore * 100)}%`
      : "n/a";

  return (
    <section className="relative overflow-hidden rounded-[1.7rem] border border-[color:var(--shell-border)] bg-[radial-gradient(circle_at_10%_8%,rgba(34,211,238,0.24),transparent_30%),radial-gradient(circle_at_92%_86%,rgba(59,130,246,0.18),transparent_34%),linear-gradient(160deg,rgba(255,255,255,0.92),rgba(241,245,249,0.86))] p-4 shadow-[0_24px_70px_rgba(15,23,42,0.14)] dark:bg-[radial-gradient(circle_at_10%_8%,rgba(34,211,238,0.16),transparent_34%),radial-gradient(circle_at_92%_86%,rgba(59,130,246,0.14),transparent_36%),linear-gradient(160deg,rgba(2,6,23,0.9),rgba(15,23,42,0.88))] dark:shadow-[0_28px_80px_rgba(2,6,23,0.72)] sm:p-5 [--c-node-inactive-fill:#e2e8f0] [--c-node-inactive-stroke:#94a3b8] [--c-node-inactive-title:#334155] [--c-node-inactive-subtitle:#64748b] [--c-node-core-fill:#dff6ff] [--c-node-core-stroke:#0891b2] [--c-node-core-title:#0f172a] [--c-node-core-subtitle:#155e75] [--c-node-branch-fill:#e2e8f0] [--c-node-branch-stroke:#94a3b8] [--c-node-branch-title:#334155] [--c-node-branch-subtitle:#64748b] [--c-node-followup-fill:#fef3c7] [--c-node-followup-stroke:#f59e0b] [--c-node-followup-title:#92400e] [--c-node-followup-subtitle:#b45309] [--c-node-emergency-fill:#fee2e2] [--c-node-emergency-stroke:#ef4444] [--c-node-emergency-title:#991b1b] [--c-node-emergency-subtitle:#b91c1c] [--c-node-citations-fill:#dcfce7] [--c-node-citations-stroke:#22c55e] [--c-node-citations-title:#166534] [--c-node-citations-subtitle:#15803d] [--c-edge-core:#0284c7] [--c-edge-muted:#94a3b8] [--c-edge-warning:#f59e0b] [--c-edge-danger:#ef4444] dark:[--c-node-inactive-fill:#0f172a] dark:[--c-node-inactive-stroke:#475569] dark:[--c-node-inactive-title:#cbd5e1] dark:[--c-node-inactive-subtitle:#94a3b8] dark:[--c-node-core-fill:#082f49] dark:[--c-node-core-stroke:#22d3ee] dark:[--c-node-core-title:#e0f2fe] dark:[--c-node-core-subtitle:#67e8f9] dark:[--c-node-branch-fill:#1e293b] dark:[--c-node-branch-stroke:#64748b] dark:[--c-node-branch-title:#cbd5e1] dark:[--c-node-branch-subtitle:#94a3b8] dark:[--c-node-followup-fill:#451a03] dark:[--c-node-followup-stroke:#fbbf24] dark:[--c-node-followup-title:#fde68a] dark:[--c-node-followup-subtitle:#fcd34d] dark:[--c-node-emergency-fill:#450a0a] dark:[--c-node-emergency-stroke:#f87171] dark:[--c-node-emergency-title:#fecaca] dark:[--c-node-emergency-subtitle:#fca5a5] dark:[--c-node-citations-fill:#052e16] dark:[--c-node-citations-stroke:#4ade80] dark:[--c-node-citations-title:#bbf7d0] dark:[--c-node-citations-subtitle:#86efac] dark:[--c-edge-core:#22d3ee] dark:[--c-edge-muted:#64748b] dark:[--c-edge-warning:#fbbf24] dark:[--c-edge-danger:#f87171]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(148,163,184,0.12)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.12)_1px,transparent_1px)] bg-[size:26px_26px] dark:bg-[linear-gradient(to_right,rgba(71,85,105,0.32)_1px,transparent_1px),linear-gradient(to_bottom,rgba(71,85,105,0.32)_1px,transparent_1px)]" />

      <div className="relative flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">Council Flow Canvas</p>
          <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)] sm:text-xl">Pipeline hội chẩn dạng futuristic, tối ưu dark/light</h3>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
            confidence: {confidenceLabel}
          </span>
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

      <div className="relative mt-4 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="rounded-full border border-cyan-300/70 bg-cyan-100/90 px-2.5 py-1 font-semibold text-cyan-800 dark:border-cyan-500/45 dark:bg-cyan-950/50 dark:text-cyan-200">
          core path
        </span>
        <span className="rounded-full border border-amber-300/70 bg-amber-100/90 px-2.5 py-1 font-semibold text-amber-800 dark:border-amber-500/45 dark:bg-amber-950/50 dark:text-amber-200">
          needs_more_info
        </span>
        <span className="rounded-full border border-rose-300/70 bg-rose-100/90 px-2.5 py-1 font-semibold text-rose-800 dark:border-rose-500/45 dark:bg-rose-950/50 dark:text-rose-200">
          emergency
        </span>
      </div>

      <div className="mt-4 overflow-x-auto rounded-2xl border border-[color:var(--shell-border)] bg-[linear-gradient(180deg,rgba(255,255,255,0.66),rgba(226,232,240,0.56))] p-3 dark:bg-[linear-gradient(180deg,rgba(2,6,23,0.45),rgba(15,23,42,0.62))]">
        <svg
          viewBox={`0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`}
          className="h-[440px] w-[1400px] min-w-[1200px]"
          role="img"
          aria-label="Council consultation flow canvas"
        >
          <defs>
            <marker id="council-flow-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--c-edge-core)" />
            </marker>
            <marker id="council-flow-arrow-muted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--c-edge-muted)" />
            </marker>
            <marker id="council-flow-arrow-warn" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--c-edge-warning)" />
            </marker>
            <marker id="council-flow-arrow-danger" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="var(--c-edge-danger)" />
            </marker>
            <filter id="council-flow-glow" x="-45%" y="-45%" width="190%" height="190%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {EDGES.map((edge, index) => {
            const from = getNodeById(edge.from);
            const to = getNodeById(edge.to);
            const stroke = edgeStroke(edge, props);
            const branchActive =
              edge.branch === "emergency"
                ? props.isEmergency
                : edge.branch === "needs_more_info"
                  ? props.needsMoreInfo
                  : true;
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
                opacity={branchActive ? 1 : 0.54}
                filter={branchActive ? "url(#council-flow-glow)" : undefined}
              />
            );
          })}

          {NODES.map((node) => {
            const palette = nodePalette(node, props);
            const highlighted = isNodeHighlighted(node, props);
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
                  filter={highlighted ? "url(#council-flow-glow)" : undefined}
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
