"use client";

import { useMemo, useRef } from "react";
import type { ControlTowerRagFlow } from "@/lib/system";

type NeuralNode = {
  id: string;
  label: string;
  layer: number;
  row: number;
  kind: "required" | "toggle";
  toggleKey?: keyof ControlTowerRagFlow;
};

type NeuralEdge = {
  from: string;
  to: string;
};

type AdminNeuralNetworkVisualizerProps = {
  ragFlow?: ControlTowerRagFlow | null;
};

const LAYER_X = [90, 340, 600, 860, 1110];
const ROW_Y = [80, 200, 320];
const NODE_W = 190;
const NODE_H = 74;
const SCENE_W = 1320;
const SCENE_H = 420;

const NODES: NeuralNode[] = [
  { id: "q", label: "Query Encoder", layer: 0, row: 0, kind: "required" },
  { id: "ctx", label: "Context Gate", layer: 0, row: 1, kind: "required" },
  { id: "policy", label: "Policy Guard", layer: 0, row: 2, kind: "required" },

  { id: "internal", label: "Internal Retrieval", layer: 1, row: 0, kind: "required" },
  { id: "sci", label: "Scientific Retrieval", layer: 1, row: 1, kind: "toggle", toggleKey: "scientific_retrieval_enabled" },
  { id: "web", label: "Web Retrieval", layer: 1, row: 2, kind: "toggle", toggleKey: "web_retrieval_enabled" },

  { id: "rank", label: "Neural Reranker", layer: 2, row: 0, kind: "toggle", toggleKey: "rag_reranker_enabled" },
  { id: "index", label: "Evidence Index", layer: 2, row: 1, kind: "required" },
  { id: "verify", label: "NLI Verifier", layer: 2, row: 2, kind: "toggle", toggleKey: "rag_nli_enabled" },

  { id: "matrix", label: "Claim Matrix", layer: 3, row: 0, kind: "toggle", toggleKey: "rule_verification_enabled" },
  { id: "cite", label: "Citation Selector", layer: 3, row: 1, kind: "required" },

  { id: "answer", label: "Answer Synthesizer", layer: 4, row: 0, kind: "required" },
  { id: "telemetry", label: "Telemetry Stream", layer: 4, row: 1, kind: "required" },
  { id: "store", label: "Conversation Store", layer: 4, row: 2, kind: "required" },
];

const EDGES: NeuralEdge[] = [
  { from: "q", to: "internal" },
  { from: "ctx", to: "sci" },
  { from: "ctx", to: "web" },
  { from: "policy", to: "rank" },
  { from: "internal", to: "rank" },
  { from: "sci", to: "index" },
  { from: "web", to: "index" },
  { from: "rank", to: "index" },
  { from: "index", to: "verify" },
  { from: "verify", to: "matrix" },
  { from: "index", to: "cite" },
  { from: "matrix", to: "answer" },
  { from: "cite", to: "answer" },
  { from: "answer", to: "telemetry" },
  { from: "telemetry", to: "store" },
];

function nodePosition(node: NeuralNode): { x: number; y: number } {
  return {
    x: LAYER_X[node.layer] ?? 0,
    y: ROW_Y[node.row] ?? 0,
  };
}

function edgePath(from: NeuralNode, to: NeuralNode): string {
  const p1 = nodePosition(from);
  const p2 = nodePosition(to);
  const x1 = p1.x + NODE_W;
  const y1 = p1.y + NODE_H / 2;
  const x2 = p2.x;
  const y2 = p2.y + NODE_H / 2;
  const mid = x1 + (x2 - x1) * 0.48;
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
}

export function AdminNeuralNetworkVisualizer({
  ragFlow,
}: AdminNeuralNetworkVisualizerProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);

  const statusMap = useMemo(() => {
    const map = new Map<string, "on" | "off" | "required">();
    for (const node of NODES) {
      if (node.kind === "required" || !node.toggleKey) {
        map.set(node.id, "required");
        continue;
      }
      map.set(node.id, ragFlow ? (ragFlow[node.toggleKey] ? "on" : "off") : "off");
    }
    return map;
  }, [ragFlow]);

  const exportSvg = () => {
    const svg = svgRef.current;
    if (!svg) return;
    const xml = new XMLSerializer().serializeToString(svg);
    const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "clara-neural-network-flow.svg";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const exportJpg = async () => {
    const svg = svgRef.current;
    if (!svg) return;
    const xml = new XMLSerializer().serializeToString(svg);
    const encoded = btoa(unescape(encodeURIComponent(xml)));
    const src = `data:image/svg+xml;base64,${encoded}`;
    const img = new Image();
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("svg_to_image_failed"));
      img.src = src;
    });
    const scale = 2.2;
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(SCENE_W * scale);
    canvas.height = Math.round(SCENE_H * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#0b0e13";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const anchor = document.createElement("a");
    anchor.href = canvas.toDataURL("image/jpeg", 0.96);
    anchor.download = "clara-neural-network-flow.jpg";
    anchor.click();
  };

  return (
    <section className="rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
            Neural Network Flow
          </p>
          <h4 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
            Runtime Graph: Retrieval → Rerank → NLI → Answer
          </h4>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={exportSvg}
            className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] hover:border-[color:var(--brand-primary)]"
          >
            Export SVG
          </button>
          <button
            type="button"
            onClick={() => void exportJpg()}
            className="rounded-lg border border-[color:var(--brand-600)] bg-[var(--brand-600)] px-3 py-1.5 text-xs font-medium text-[#cdd7ff] hover:bg-[var(--brand-700)]"
          >
            Export JPG
          </button>
        </div>
      </div>

      <div className="mt-3 overflow-x-auto rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${SCENE_W} ${SCENE_H}`}
          className="h-[430px] min-w-[1220px] w-full"
          role="img"
          aria-label="CLARA neural network admin flow"
        >
          {EDGES.map((edge) => {
            const from = NODES.find((item) => item.id === edge.from);
            const to = NODES.find((item) => item.id === edge.to);
            if (!from || !to) return null;
            const fromState = statusMap.get(from.id) ?? "off";
            const toState = statusMap.get(to.id) ?? "off";
            const active = fromState !== "off" && toState !== "off";
            return (
              <path
                key={`${edge.from}-${edge.to}`}
                d={edgePath(from, to)}
                fill="none"
                stroke={active ? "#60a5fa" : "#414751"}
                strokeOpacity={active ? 0.9 : 0.42}
                strokeWidth={active ? 2.6 : 1.9}
                strokeDasharray={active ? "0" : "5 5"}
              />
            );
          })}

          {NODES.map((node) => {
            const pos = nodePosition(node);
            const status = statusMap.get(node.id) ?? "off";
            const active = status !== "off";
            const fill = status === "required" ? "#1d2025" : active ? "#272a30" : "#191c21";
            const border = status === "required" || active ? "#a4c9ff" : "#414751";
            const label = status === "required" ? "CORE" : active ? "LIVE" : "OFF";
            return (
              <g key={node.id}>
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={16}
                  fill={fill}
                  stroke={border}
                  strokeWidth={1.6}
                  opacity={0.96}
                />
                <text x={pos.x + 14} y={pos.y + 30} fill="#e1e2e9" fontSize="13" fontWeight="700">
                  {node.label}
                </text>
                <text x={pos.x + 14} y={pos.y + 52} fill="#a4c9ff" fontSize="11" fontWeight="600">
                  {label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
        <span className="rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2 py-1 text-[var(--text-brand)]">
          CORE
        </span>
        <span className="rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2 py-1 text-[var(--text-brand)]">
          LIVE (toggle bật)
        </span>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[var(--text-secondary)]">
          OFF (toggle tắt)
        </span>
      </div>
    </section>
  );
}

export default AdminNeuralNetworkVisualizer;
