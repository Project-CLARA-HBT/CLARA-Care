"use client";

import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

type CouncilFlowCanvasProps = {
  isEmergency: boolean;
  needsMoreInfo: boolean;
  hasCitations: boolean;
};

type FlowNode = {
  id: string;
  titleKey: UITranslationKey;
  subtitleKey: UITranslationKey;
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
  { id: "input", titleKey: "council.flow.node.input.title", subtitleKey: "council.flow.node.input.subtitle", x: 56, y: 286, kind: "core" },
  { id: "extract", titleKey: "council.flow.node.extract.title", subtitleKey: "council.flow.node.extract.subtitle", x: 270, y: 286, kind: "core" },
  { id: "quality", titleKey: "council.flow.node.quality.title", subtitleKey: "council.flow.node.quality.subtitle", x: 484, y: 286, kind: "core" },
  { id: "orchestrator", titleKey: "council.flow.node.orchestrator.title", subtitleKey: "council.flow.node.orchestrator.subtitle", x: 698, y: 286, kind: "core" },
  { id: "safety", titleKey: "council.flow.node.safety.title", subtitleKey: "council.flow.node.safety.subtitle", x: 912, y: 196, kind: "core" },
  { id: "consensus", titleKey: "council.flow.node.consensus.title", subtitleKey: "council.flow.node.consensus.subtitle", x: 1126, y: 286, kind: "core" },
  { id: "citations", titleKey: "council.flow.node.citations.title", subtitleKey: "council.flow.node.citations.subtitle", x: 912, y: 376, kind: "branch" },
  { id: "followup", titleKey: "council.flow.node.followup.title", subtitleKey: "council.flow.node.followup.subtitle", x: 698, y: 466, kind: "branch" },
  { id: "emergency", titleKey: "council.flow.node.emergency.title", subtitleKey: "council.flow.node.emergency.subtitle", x: 1126, y: 56, kind: "branch" },
  { id: "workspace", titleKey: "council.flow.node.workspace.title", subtitleKey: "council.flow.node.workspace.subtitle", x: 1340, y: 286, kind: "core" },
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
  const language = useUILanguage();
  const reviewState = props.needsMoreInfo
    ? t(language, "council.flow.review.needsMoreInfo")
    : t(language, "council.flow.review.professionalReview");

  return (
    <section className="relative overflow-hidden rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-4 sm:p-5 [--c-node-inactive-fill:#272a30] [--c-node-inactive-stroke:#414751] [--c-node-inactive-title:#c1c7d3] [--c-node-inactive-subtitle:#8b919d] [--c-node-core-fill:#1d2025] [--c-node-core-stroke:#60a5fa] [--c-node-core-title:#e1e2e9] [--c-node-core-subtitle:#a4c9ff] [--c-node-branch-fill:#272a30] [--c-node-branch-stroke:#414751] [--c-node-branch-title:#c1c7d3] [--c-node-branch-subtitle:#8b919d] [--c-node-followup-fill:#4b3500] [--c-node-followup-stroke:#fabd34] [--c-node-followup-title:#ffdea4] [--c-node-followup-subtitle:#fabd34] [--c-node-emergency-fill:#93000a] [--c-node-emergency-stroke:#ffb4ab] [--c-node-emergency-title:#ffdad6] [--c-node-emergency-subtitle:#ffb4ab] [--c-node-citations-fill:#272a30] [--c-node-citations-stroke:#a4c9ff] [--c-node-citations-title:#e1e2e9] [--c-node-citations-subtitle:#a4c9ff] [--c-edge-core:#a4c9ff] [--c-edge-muted:#8b919d] [--c-edge-warning:#fabd34] [--c-edge-danger:#ffb4ab]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(65,71,81,0.28)_1px,transparent_1px),linear-gradient(to_bottom,rgba(65,71,81,0.28)_1px,transparent_1px)] bg-[size:26px_26px]" />

      <div className="relative flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--text-muted)]">{t(language, "council.flow.eyebrow")}</p>
          <h3 className="mt-1 text-lg font-semibold text-[var(--text-primary)] sm:text-xl">{t(language, "council.flow.title")}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
            {t(language, "council.flow.review", { state: reviewState })}
          </span>
          <span
            className={`rounded-full border px-2 py-1 ${
              props.needsMoreInfo
                ? "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            {t(language, "council.flow.needsMoreInfo", { state: t(language, props.needsMoreInfo ? "council.flow.state.on" : "council.flow.state.off") })}
          </span>
          <span
            className={`rounded-full border px-2 py-1 ${
              props.isEmergency
                ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)]"
            }`}
          >
            {t(language, "council.flow.emergency", { state: t(language, props.isEmergency ? "council.flow.state.on" : "council.flow.state.off") })}
          </span>
        </div>
      </div>

      <div className="relative mt-4 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2.5 py-1 font-semibold text-[var(--status-ok-text)]">
          {t(language, "council.flow.legend.core")}
        </span>
        <span className="rounded-full border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-2.5 py-1 font-semibold text-[var(--status-warn-text)]">
          {t(language, "council.flow.legend.needsMoreInfo")}
        </span>
        <span className="rounded-full border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-2.5 py-1 font-semibold text-[var(--status-danger-text)]">
          {t(language, "council.flow.legend.emergency")}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-[color:var(--shell-border)] bg-[var(--bg-elev-1)] p-3">
        <svg
          viewBox={`0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`}
          className="h-[440px] w-[1400px] min-w-[1200px]"
          role="img"
          aria-label={t(language, "council.flow.aria")}
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
                  {t(language, node.titleKey)}
                </text>
                <text x={node.x + 12} y={node.y + 46} fontSize={12} fill={palette.subtitle}>
                  {t(language, node.subtitleKey)}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
