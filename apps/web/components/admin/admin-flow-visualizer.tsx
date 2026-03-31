"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { ControlTowerRagFlow } from "@/lib/system";

export type FlowToggleKey = Exclude<keyof ControlTowerRagFlow, "low_context_threshold">;

export type FlowNodeId =
  | "input_gateway"
  | "session_guard"
  | "safety_ingress"
  | "legal_guard"
  | "role_router"
  | "intent_router"
  | "planner"
  | "deep_research"
  | "retrieval_internal"
  | "retrieval_scientific"
  | "retrieval_web"
  | "retrieval_file"
  | "evidence_index"
  | "synthesis"
  | "verification"
  | "verification_matrix"
  | "citation_selection"
  | "policy_gate"
  | "deepseek_fallback"
  | "responder";

type FlowNodeStatus = "required" | "on" | "off";

type FlowNodeDef = {
  id: FlowNodeId;
  title: string;
  subtitle: string;
  description: string;
  riskNote: string;
  x: number;
  y: number;
  tone: "sky" | "teal" | "indigo" | "amber" | "rose";
  toggleKey?: FlowToggleKey;
};

export type FlowNodeInfo = Pick<
  FlowNodeDef,
  "id" | "title" | "subtitle" | "description" | "riskNote" | "toggleKey"
>;

type FlowEdgeDef = {
  from: FlowNodeId;
  to: FlowNodeId;
  bend?: number;
  fallback?: boolean;
  label?: string;
};

type AdminFlowVisualizerProps = {
  ragFlow?: ControlTowerRagFlow | null;
  onToggle: (key: FlowToggleKey) => void;
  onSelectNode: (nodeId: FlowNodeId) => void;
  selectedNodeId?: FlowNodeId | null;
};

const SCENE_WIDTH = 2480;
const SCENE_HEIGHT = 1080;
const NODE_CARD_WIDTH = 196;
const EXPORT_SCALE = 3;

const NODES: FlowNodeDef[] = [
  {
    id: "input_gateway",
    title: "Input Gateway",
    subtitle: "Web, mobile, admin trigger",
    description: "Nhận truy vấn đầu vào, gắn trace id, chuẩn hóa payload và phân loại loại phiên.",
    riskNote: "Payload lỏng ngay từ đầu sẽ làm hỏng telemetry và kéo lệch toàn bộ pipeline sau đó.",
    x: 170,
    y: 320,
    tone: "sky",
  },
  {
    id: "session_guard",
    title: "Session Guard",
    subtitle: "Auth, consent, session validity",
    description: "Chặn request chưa đăng nhập, session stale, hoặc chưa qua disclaimer/consent.",
    riskNote: "Thiếu chốt này sẽ làm hở access control và phá vỡ câu chuyện pháp lý của sản phẩm.",
    x: 170,
    y: 500,
    tone: "rose",
  },
  {
    id: "safety_ingress",
    title: "Safety Ingress",
    subtitle: "PII/PHI, triage, payload hygiene",
    description: "Giảm thiểu dữ liệu nhạy cảm, chuẩn hóa ngôn ngữ truy vấn và áp safety prep trước routing.",
    riskNote: "Nếu bỏ qua bước này, câu trả lời có thể chứa dữ liệu nhạy cảm hoặc ngữ cảnh bẩn.",
    x: 170,
    y: 680,
    tone: "teal",
  },
  {
    id: "legal_guard",
    title: "Legal Hard Guard",
    subtitle: "Dosage, kê đơn, chẩn đoán",
    description: "Từ chối tuyệt đối các câu hỏi vượt ranh giới pháp lý như kê đơn, định liều, chẩn đoán.",
    riskNote: "Đây là lớp sống còn để chatbot không tự biến thành AI bác sĩ ngoài phạm vi cho phép.",
    x: 450,
    y: 260,
    tone: "rose",
  },
  {
    id: "role_router",
    title: "Role Router",
    subtitle: "normal / researcher / doctor / admin",
    description: "Chọn nhánh kiểm soát, policy và depth mặc định dựa trên role hiện hành.",
    riskNote: "Router sai role sẽ khiến cùng một truy vấn bị trả lời sai depth hoặc sai policy.",
    x: 450,
    y: 470,
    tone: "indigo",
    toggleKey: "role_router_enabled",
  },
  {
    id: "intent_router",
    title: "Intent Router",
    subtitle: "quick, evidence, deep research",
    description: "Nhận diện ý định để route sang quick guidance, evidence review hoặc deep research.",
    riskNote: "Intent lệch là nguyên nhân phổ biến nhất của retrieval sai nguồn.",
    x: 450,
    y: 680,
    tone: "indigo",
    toggleKey: "intent_router_enabled",
  },
  {
    id: "planner",
    title: "Research Planner",
    subtitle: "Plan steps, source budget, search policy",
    description: "Lập kế hoạch retrieval, search budget, ngưỡng low-context và chiến lược kiểm chứng.",
    riskNote: "Planner yếu làm tăng độ trễ nhưng vẫn không tăng độ chính xác tương ứng.",
    x: 730,
    y: 500,
    tone: "amber",
  },
  {
    id: "deep_research",
    title: "Deep Research Loop",
    subtitle: "Subqueries, multi-pass retrieval",
    description: "Tách subquery, breadth scan, counter-evidence scan và cross-source consistency trong deep mode.",
    riskNote: "Nếu chỉ giả lập bước này bằng client animation, UX sẽ đẹp nhưng pipeline sẽ giả.",
    x: 1010,
    y: 220,
    tone: "amber",
  },
  {
    id: "retrieval_internal",
    title: "Internal Corpus",
    subtitle: "Seed docs, source hub, uploaded files",
    description: "Lấy context từ knowledge source, uploaded documents và internal corpus đang có trong hệ thống.",
    riskNote: "Corpus bẩn hoặc trùng lặp sẽ khiến rerank khó cứu được chất lượng cuối.",
    x: 1010,
    y: 390,
    tone: "sky",
  },
  {
    id: "retrieval_scientific",
    title: "Scientific Retrieval",
    subtitle: "PubMed, Europe PMC, FDA, DailyMed",
    description: "Kéo bằng chứng chuyên môn từ nguồn khoa học và drug-safety connector.",
    riskNote: "Đây là node nhạy với timeout, query rewrite và chất lượng connector nhất.",
    x: 1010,
    y: 560,
    tone: "sky",
    toggleKey: "scientific_retrieval_enabled",
  },
  {
    id: "retrieval_web",
    title: "Web Retrieval",
    subtitle: "SearXNG + controlled crawl",
    description: "Mở rộng recall bằng web retrieval và crawling có allowlist, chỉ dùng khi thật sự cần.",
    riskNote: "Web retrieval mạnh nhưng dễ kéo nhiễu nếu trust/crawl policy không đủ chặt.",
    x: 1010,
    y: 730,
    tone: "sky",
    toggleKey: "web_retrieval_enabled",
  },
  {
    id: "retrieval_file",
    title: "File Retrieval",
    subtitle: "User context grounding",
    description: "Inject ngữ cảnh từ file người dùng tải lên để câu trả lời grounded vào case thực tế.",
    riskNote: "Tắt node này sẽ làm research mất context cá nhân hóa quan trọng.",
    x: 1010,
    y: 900,
    tone: "sky",
    toggleKey: "file_retrieval_enabled",
  },
  {
    id: "evidence_index",
    title: "Evidence Index",
    subtitle: "Dedupe, rerank, lexical gate",
    description: "Dedupe, score blend semantic-lexical, source weighting và loại tài liệu lệch chủ đề.",
    riskNote: "Đây là nơi phải chặn các paper lệch kiểu diet/PCOS trôi vào câu hỏi DDI.",
    x: 1290,
    y: 560,
    tone: "teal",
  },
  {
    id: "synthesis",
    title: "Answer Synthesis",
    subtitle: "DeepSeek generation, Markdown contract",
    description: "Tổng hợp câu trả lời theo contract Markdown, bảng so sánh, mermaid và citation inline.",
    riskNote: "Nếu synthesis không bị ép contract, output sẽ rất khó render nhất quán trên UI.",
    x: 1570,
    y: 560,
    tone: "amber",
  },
  {
    id: "verification",
    title: "FIDES Verification",
    subtitle: "Claim support and contradiction check",
    description: "Đối chiếu claim với retrieved evidence, đo coverage và phát hiện mâu thuẫn.",
    riskNote: "Không có verification thì không biết câu trả lời grounded đến mức nào.",
    x: 1570,
    y: 340,
    tone: "indigo",
    toggleKey: "verification_enabled",
  },
  {
    id: "verification_matrix",
    title: "Verification Matrix",
    subtitle: "Severity, confidence, supported claims",
    description: "Tạo ma trận quyết định hiển thị verdict, severity, confidence và unsupported claims.",
    riskNote: "Matrix yếu sẽ làm warning hiển thị đẹp nhưng không nói đúng vấn đề thật.",
    x: 1570,
    y: 780,
    tone: "indigo",
  },
  {
    id: "citation_selection",
    title: "Citation Selection",
    subtitle: "Top evidence, attribution payload",
    description: "Chọn nguồn được giữ lại cho UI, source attribution và telemetry chi tiết.",
    riskNote: "Citation bị chọn sai sẽ làm người dùng tin vào nguồn không liên quan.",
    x: 1850,
    y: 240,
    tone: "teal",
  },
  {
    id: "policy_gate",
    title: "Policy Gate",
    subtitle: "allow, warn, block, fallback",
    description: "Áp runtime policy để quyết định cho qua, cảnh báo, chặn hay degrade an toàn.",
    riskNote: "Policy gate phải phản ánh đúng trạng thái strict-mode, không được mềm hóa ngầm.",
    x: 1850,
    y: 560,
    tone: "rose",
  },
  {
    id: "deepseek_fallback",
    title: "DeepSeek Fallback",
    subtitle: "Low-context or upstream degraded path",
    description: "Nhánh dự phòng khi low-context hoặc upstream lỗi, chỉ được phép khi runtime cho phép.",
    riskNote: "Lạm dụng fallback sẽ phá toàn bộ lời hứa research grounded của sản phẩm.",
    x: 1850,
    y: 820,
    tone: "rose",
    toggleKey: "deepseek_fallback_enabled",
  },
  {
    id: "responder",
    title: "Responder",
    subtitle: "UI payload, logs, telemetry, DB",
    description: "Trả payload cuối về web/admin, ghi telemetry, attribution, flow events và lưu conversation.",
    riskNote: "Nếu responder thiếu metadata, research trông như đang chạy nhưng không kiểm toán được.",
    x: 2130,
    y: 620,
    tone: "sky",
  },
];

export const FLOW_NODE_INFOS: Record<FlowNodeId, FlowNodeInfo> = NODES.reduce(
  (acc, node) => {
    acc[node.id] = {
      id: node.id,
      title: node.title,
      subtitle: node.subtitle,
      description: node.description,
      riskNote: node.riskNote,
      toggleKey: node.toggleKey,
    };
    return acc;
  },
  {} as Record<FlowNodeId, FlowNodeInfo>,
);

const NODE_BY_ID = NODES.reduce<Record<FlowNodeId, FlowNodeDef>>((acc, node) => {
  acc[node.id] = node;
  return acc;
}, {} as Record<FlowNodeId, FlowNodeDef>);

const EDGES: FlowEdgeDef[] = [
  { from: "input_gateway", to: "session_guard" },
  { from: "session_guard", to: "safety_ingress" },
  { from: "safety_ingress", to: "legal_guard", bend: -132 },
  { from: "safety_ingress", to: "role_router", bend: -24 },
  { from: "safety_ingress", to: "intent_router", bend: 24 },
  { from: "legal_guard", to: "policy_gate", bend: -108, label: "hard refusal" },
  { from: "role_router", to: "planner", bend: 12 },
  { from: "intent_router", to: "planner", bend: 12 },
  { from: "planner", to: "deep_research", bend: -108, label: "deep mode" },
  { from: "planner", to: "retrieval_internal", bend: -22 },
  { from: "planner", to: "retrieval_scientific" },
  { from: "planner", to: "retrieval_web", bend: 24 },
  { from: "planner", to: "retrieval_file", bend: 60 },
  { from: "deep_research", to: "retrieval_scientific", bend: 82 },
  { from: "retrieval_internal", to: "evidence_index", bend: -24 },
  { from: "retrieval_scientific", to: "evidence_index" },
  { from: "retrieval_web", to: "evidence_index", bend: 18 },
  { from: "retrieval_file", to: "evidence_index", bend: 58 },
  { from: "evidence_index", to: "synthesis" },
  { from: "synthesis", to: "verification", bend: -82 },
  { from: "synthesis", to: "verification_matrix", bend: 82 },
  { from: "verification", to: "citation_selection", bend: -40 },
  { from: "verification", to: "policy_gate", bend: 34 },
  { from: "verification_matrix", to: "policy_gate", bend: -34 },
  { from: "citation_selection", to: "responder", bend: 76 },
  { from: "policy_gate", to: "responder", bend: 18 },
  { from: "planner", to: "deepseek_fallback", fallback: true, bend: 178, label: "degraded path" },
  { from: "evidence_index", to: "deepseek_fallback", fallback: true, bend: 156 },
  { from: "policy_gate", to: "deepseek_fallback", fallback: true, bend: 58 },
  { from: "deepseek_fallback", to: "responder", fallback: true, bend: -34, label: "fallback response" },
];

const STATUS_META: Record<
  FlowNodeStatus,
  {
    label: string;
    nodeClass: string;
    badgeClass: string;
  }
> = {
  required: {
    label: "core",
    nodeClass: "border-white/20 bg-white/88 shadow-[0_16px_40px_rgba(15,23,42,0.14)]",
    badgeClass: "border-sky-300/80 bg-sky-100 text-sky-800",
  },
  on: {
    label: "live",
    nodeClass: "border-emerald-300/60 bg-white shadow-[0_20px_48px_rgba(16,185,129,0.16)]",
    badgeClass: "border-emerald-300 bg-emerald-100 text-emerald-800",
  },
  off: {
    label: "off",
    nodeClass: "border-slate-300/70 bg-slate-100/85 opacity-80 shadow-none",
    badgeClass: "border-slate-300 bg-slate-100 text-slate-600",
  },
};

const TONE_META: Record<
  FlowNodeDef["tone"],
  {
    glow: string;
    stripe: string;
    chip: string;
  }
> = {
  sky: {
    glow: "shadow-sky-500/20",
    stripe: "from-sky-500/80 to-cyan-400/70",
    chip: "bg-sky-100 text-sky-700",
  },
  teal: {
    glow: "shadow-teal-500/20",
    stripe: "from-teal-500/80 to-emerald-400/70",
    chip: "bg-teal-100 text-teal-700",
  },
  indigo: {
    glow: "shadow-indigo-500/20",
    stripe: "from-indigo-500/80 to-blue-500/70",
    chip: "bg-indigo-100 text-indigo-700",
  },
  amber: {
    glow: "shadow-amber-500/20",
    stripe: "from-amber-500/80 to-orange-400/70",
    chip: "bg-amber-100 text-amber-700",
  },
  rose: {
    glow: "shadow-rose-500/20",
    stripe: "from-rose-500/80 to-fuchsia-400/70",
    chip: "bg-rose-100 text-rose-700",
  },
};

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function buildPath(from: FlowNodeDef, to: FlowNodeDef, bend = 0): string {
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2 + bend;
  return `M ${from.x} ${from.y} Q ${midX} ${midY} ${to.x} ${to.y}`;
}

function isActive(status: FlowNodeStatus): boolean {
  return status === "required" || status === "on";
}

function resolveNodeStatus(node: FlowNodeDef, ragFlow?: ControlTowerRagFlow | null): FlowNodeStatus {
  if (!node.toggleKey) return "required";
  return ragFlow?.[node.toggleKey] ? "on" : "off";
}

export default function AdminFlowVisualizer({
  ragFlow,
  onToggle,
  onSelectNode,
  selectedNodeId,
}: AdminFlowVisualizerProps) {
  const sceneRef = useRef<HTMLDivElement | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const statusByNode = useMemo(
    () =>
      NODES.reduce<Record<FlowNodeId, FlowNodeStatus>>((acc, node) => {
        acc[node.id] = resolveNodeStatus(node, ragFlow);
        return acc;
      }, {} as Record<FlowNodeId, FlowNodeStatus>),
    [ragFlow],
  );

  const handleExportHighResJpg = useCallback(async () => {
    if (!sceneRef.current || isExporting) {
      return;
    }

    setIsExporting(true);
    try {
      if (typeof document !== "undefined" && "fonts" in document) {
        await document.fonts.ready;
      }
      const { toJpeg } = await import("html-to-image");
      const dataUrl = await toJpeg(sceneRef.current, {
        cacheBust: true,
        pixelRatio: EXPORT_SCALE,
        quality: 0.96,
        canvasWidth: SCENE_WIDTH * EXPORT_SCALE,
        canvasHeight: SCENE_HEIGHT * EXPORT_SCALE,
        backgroundColor: "#f8fafc",
      });
      const anchor = document.createElement("a");
      anchor.href = dataUrl;
      anchor.download = `clara-research-flow-visualizer-${new Date().toISOString().slice(0, 10)}.jpg`;
      anchor.click();
    } catch (error) {
      console.error("Failed to export visualizer JPG", error);
    } finally {
      setIsExporting(false);
    }
  }, [isExporting]);

  const liveNodeCount = NODES.filter((node) => isActive(statusByNode[node.id])).length;
  const optionalNodeCount = NODES.filter((node) => Boolean(node.toggleKey)).length;
  const lowContextThreshold = typeof ragFlow?.low_context_threshold === "number" ? ragFlow.low_context_threshold : 0;

  return (
    <section className="relative overflow-hidden rounded-[28px] border border-slate-200/70 bg-[radial-gradient(circle_at_top_left,_rgba(14,165,233,0.16),_transparent_24%),radial-gradient(circle_at_bottom_right,_rgba(245,158,11,0.14),_transparent_22%),linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(248,250,252,0.94))] p-5 shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(148,163,184,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(148,163,184,0.08)_1px,transparent_1px)] bg-[size:28px_28px]" />

      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Research Control Tower
          </p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight text-slate-950">
            CLARA Research Flow Visualizer
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Canvas này bám sát flow thực tế của Research pipeline: session guard, legal hard guard,
            planner, deep research, retrieval, evidence index, FIDES verification, citation
            selection, policy gate và responder.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-2xl border border-white/70 bg-white/75 px-4 py-3 shadow-[0_12px_32px_rgba(15,23,42,0.08)] backdrop-blur">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Active Nodes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950">{liveNodeCount}</p>
            <p className="mt-1 text-xs text-slate-500">trong tổng {NODES.length} node</p>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/75 px-4 py-3 shadow-[0_12px_32px_rgba(15,23,42,0.08)] backdrop-blur">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Toggle Nodes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950">{optionalNodeCount}</p>
            <p className="mt-1 text-xs text-slate-500">có thể bật/tắt từ runtime</p>
          </div>
          <div className="rounded-2xl border border-white/70 bg-white/75 px-4 py-3 shadow-[0_12px_32px_rgba(15,23,42,0.08)] backdrop-blur">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Low Context Threshold</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950">{lowContextThreshold.toFixed(2)}</p>
            <p className="mt-1 text-xs text-slate-500">điều khiển degraded path</p>
          </div>
        </div>
      </div>

      <div className="relative mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/80 bg-white/70 px-4 py-3 shadow-[0_10px_30px_rgba(15,23,42,0.08)] backdrop-blur">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
            Export
          </p>
          <p className="mt-1 text-sm text-slate-600">
            Xuất trực tiếp flow hiện tại thành ảnh JPG độ phân giải cao để đưa vào proposal hoặc slide pitching.
          </p>
        </div>
        <button
          type="button"
          onClick={handleExportHighResJpg}
          disabled={isExporting}
          className={cx(
            "min-h-11 rounded-full border px-4 py-2 text-sm font-semibold transition",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
            isExporting
              ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400"
              : "border-sky-300 bg-sky-100 text-sky-800 hover:bg-sky-200",
          )}
        >
          {isExporting ? "Đang xuất JPG 3x..." : "Xuất JPG High-Res"}
        </button>
      </div>

      <div className="relative mt-5 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="rounded-full border border-sky-300 bg-sky-100 px-2.5 py-1 font-semibold text-sky-800">
          core
        </span>
        <span className="rounded-full border border-emerald-300 bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-800">
          live
        </span>
        <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">
          off
        </span>
        <span className="rounded-full border border-orange-300 bg-orange-100 px-2.5 py-1 font-semibold text-orange-700">
          degraded branch
        </span>
      </div>

      <div className="relative mt-5 overflow-x-auto rounded-[24px] border border-white/80 bg-slate-950/[0.04] p-3">
        <div
          ref={sceneRef}
          className="relative overflow-hidden rounded-[22px] border border-white/50 bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.45),_transparent_26%),linear-gradient(180deg,_rgba(248,250,252,0.72),_rgba(241,245,249,0.86))]"
          style={{ width: SCENE_WIDTH, height: SCENE_HEIGHT }}
        >
          <svg
            className="pointer-events-none absolute inset-0"
            width={SCENE_WIDTH}
            height={SCENE_HEIGHT}
            viewBox={`0 0 ${SCENE_WIDTH} ${SCENE_HEIGHT}`}
          >
            <defs>
              <marker id="flow-arrow-live" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" fill="#0f766e" />
              </marker>
              <marker id="flow-arrow-muted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
              </marker>
              <marker id="flow-arrow-fallback" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" fill="#ea580c" />
              </marker>
              <filter id="flow-glow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="6" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {EDGES.map((edge) => {
              const from = NODE_BY_ID[edge.from];
              const to = NODE_BY_ID[edge.to];
              const fromStatus = statusByNode[edge.from];
              const toStatus = statusByNode[edge.to];
              const edgeActive = isActive(fromStatus) && isActive(toStatus);
              const fallbackEnabled = edge.fallback ? Boolean(ragFlow?.deepseek_fallback_enabled) : false;
              const path = buildPath(from, to, edge.bend);
              const stroke = edge.fallback
                ? fallbackEnabled
                  ? "#ea580c"
                  : "#cbd5e1"
                : edgeActive
                  ? "#0f766e"
                  : "#94a3b8";
              const marker = edge.fallback
                ? fallbackEnabled
                  ? "url(#flow-arrow-fallback)"
                  : "url(#flow-arrow-muted)"
                : edgeActive
                  ? "url(#flow-arrow-live)"
                  : "url(#flow-arrow-muted)";
              const labelX = (from.x + to.x) / 2;
              const labelY = (from.y + to.y) / 2 + (edge.bend ?? 0) - 12;

              return (
                <g key={`${edge.from}-${edge.to}`}>
                  <path
                    d={path}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={edge.fallback ? 3 : 2.4}
                    strokeDasharray={edge.fallback ? "10 8" : undefined}
                    markerEnd={marker}
                    opacity={edgeActive || fallbackEnabled ? 0.95 : 0.6}
                    filter={edgeActive || fallbackEnabled ? "url(#flow-glow)" : undefined}
                  />
                  {edge.label ? (
                    <text
                      x={labelX}
                      y={labelY}
                      textAnchor="middle"
                      className="fill-slate-600 text-[11px] font-semibold tracking-[0.08em]"
                    >
                      {edge.label}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>

          {NODES.map((node) => {
            const status = statusByNode[node.id];
            const meta = STATUS_META[status];
            const tone = TONE_META[node.tone];
            const isSelected = selectedNodeId === node.id;
            const toggleKey = node.toggleKey;

            return (
              <div
                key={node.id}
                className="absolute"
                style={{ left: node.x, top: node.y, transform: "translate(-50%, -50%)" }}
              >
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectNode(node.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectNode(node.id);
                    }
                  }}
                  className={cx(
                    "group relative cursor-pointer overflow-hidden rounded-[22px] border p-3 text-left transition duration-200",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                    "backdrop-blur-md",
                    meta.nodeClass,
                    tone.glow,
                    isSelected && "border-slate-950/80 ring-2 ring-slate-950/10",
                  )}
                  style={{ width: NODE_CARD_WIDTH }}
                >
                  <div className={cx("absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r", tone.stripe)} />

                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        {node.subtitle}
                      </p>
                      <h4 className="mt-1 text-sm font-semibold leading-5 text-slate-950">{node.title}</h4>
                    </div>
                    <span
                      className={cx(
                        "rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]",
                        meta.badgeClass,
                      )}
                    >
                      {meta.label}
                    </span>
                  </div>

                  <p className="mt-3 text-[12px] leading-5 text-slate-600">{node.description}</p>

                  <div className="mt-3 flex items-center justify-between gap-2">
                    <span className={cx("rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em]", tone.chip)}>
                      {node.tone}
                    </span>

                    {toggleKey ? (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onToggle(toggleKey);
                        }}
                        className={cx(
                          "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition",
                          status === "on"
                            ? "border-emerald-300 bg-emerald-100 text-emerald-800 hover:bg-emerald-200"
                            : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100",
                        )}
                      >
                        {status === "on" ? "disable" : "enable"}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
