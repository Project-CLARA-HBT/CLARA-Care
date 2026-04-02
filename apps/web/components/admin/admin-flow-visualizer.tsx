"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ControlTowerRagFlow } from "@/lib/system";

export type FlowToggleKey = Exclude<keyof ControlTowerRagFlow, "low_context_threshold">;

export type FlowNodeId =
  | "input_gateway"
  | "session_guard"
  | "safety_ingress"
  | "legal_guard"
  | "role_router"
  | "intent_router"
  | "query_canonicalizer"
  | "planner"
  | "query_decomposition"
  | "retrieval_orchestrator"
  | "deep_research"
  | "deep_beta_router"
  | "deep_beta_hypothesis"
  | "deep_beta_critic"
  | "deep_beta_consensus"
  | "retrieval_internal"
  | "retrieval_scientific"
  | "retrieval_web"
  | "retrieval_file"
  | "evidence_index"
  | "contradiction_miner"
  | "synthesis"
  | "verification"
  | "verification_matrix"
  | "citation_selection"
  | "policy_gate"
  | "deepseek_fallback"
  | "responder"
  | "evaluation_feedback";

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

const SCENE_WIDTH = 4280;
const SCENE_HEIGHT = 2440;
const NODE_CARD_WIDTH = 252;
const NODE_CARD_HEIGHT = 216;
const NODE_SAFE_GAP_X = 72;
const NODE_SAFE_GAP_Y = 72;
const EXPORT_SCALE = 3;

const NODES: FlowNodeDef[] = [
  {
    id: "input_gateway",
    title: "Input Gateway",
    subtitle: "Web / Mobile / API trigger",
    description: "Nhận query, gắn trace id, correlation id và request budget cho toàn bộ deep research run.",
    riskNote: "Nếu thiếu trace/budget từ đầu thì không tối ưu được timeout, không debug được degraded path.",
    x: 220,
    y: 260,
    tone: "sky",
  },
  {
    id: "session_guard",
    title: "Session Guard",
    subtitle: "Auth, consent, session validity",
    description: "Chặn request chưa đăng nhập, token hết hạn, chưa qua consent/disclaimer và session stale.",
    riskNote: "Bỏ guard này là hở access control và phá vỡ legal chain-of-custody của dữ liệu y tế.",
    x: 220,
    y: 520,
    tone: "rose",
  },
  {
    id: "safety_ingress",
    title: "Safety Ingress",
    subtitle: "PII/PHI, triage, payload hygiene",
    description: "Giảm thiểu PII/PHI, chuẩn hóa query và tiền xử lý safety trước khi vào planner/retrieval.",
    riskNote: "Ngữ cảnh bẩn hoặc chứa PII đi sâu vào pipeline sẽ làm lệch ranking và tăng rủi ro pháp lý.",
    x: 220,
    y: 780,
    tone: "teal",
  },
  {
    id: "legal_guard",
    title: "Legal Hard Guard",
    subtitle: "Dosage, kê đơn, chẩn đoán",
    description: "Từ chối tuyệt đối các câu hỏi vượt ranh giới pháp lý như kê đơn, định liều, chẩn đoán.",
    riskNote: "Đây là lớp sống còn để chatbot không tự biến thành AI bác sĩ ngoài phạm vi cho phép.",
    x: 560,
    y: 240,
    tone: "rose",
  },
  {
    id: "role_router",
    title: "Role Router",
    subtitle: "normal / researcher / doctor / admin",
    description: "Ánh xạ role vào policy, mức explainability và ngân sách suy luận phù hợp.",
    riskNote: "Router sai role sẽ khiến cùng một truy vấn bị trả lời sai depth hoặc sai policy.",
    x: 560,
    y: 500,
    tone: "indigo",
    toggleKey: "role_router_enabled",
  },
  {
    id: "intent_router",
    title: "Intent Router",
    subtitle: "quick / evidence / deep",
    description: "Nhận diện intent và chọn profile retrieval (fast/deep, strict/lenient, branch ưu tiên).",
    riskNote: "Intent lệch là nguyên nhân phổ biến nhất của retrieval sai nguồn.",
    x: 560,
    y: 760,
    tone: "indigo",
    toggleKey: "intent_router_enabled",
  },
  {
    id: "query_canonicalizer",
    title: "Query Canonicalizer",
    subtitle: "normalize + synonym expansion",
    description: "Chuẩn hóa thuật ngữ (VI/EN), map biệt dược-hoạt chất và mở rộng alias trước khi truy xuất.",
    riskNote: "Canonicalization yếu sẽ làm recall thấp dù connector/source tốt.",
    x: 560,
    y: 1020,
    tone: "teal",
  },
  {
    id: "planner",
    title: "Research Planner",
    subtitle: "budget + source policy + pass plan",
    description: "Lập kế hoạch pass, fan-out nguồn, top-k, fallback policy và ngưỡng low-context cho phiên.",
    riskNote: "Planner không kiểm soát budget sẽ gây timeout hoặc chi phí cao nhưng hiệu quả thấp.",
    x: 920,
    y: 520,
    tone: "amber",
  },
  {
    id: "query_decomposition",
    title: "Query Decomposition",
    subtitle: "sub-questions + counter hypotheses",
    description: "Tách câu hỏi thành sub-query, giả thuyết và phản giả thuyết để tránh bias một chiều.",
    riskNote: "Thiếu decomposition dễ bỏ sót bằng chứng phản biện hoặc subgroup rủi ro cao.",
    x: 920,
    y: 780,
    tone: "amber",
  },
  {
    id: "retrieval_orchestrator",
    title: "Retrieval Orchestrator",
    subtitle: "fan-out / retry / timeout / merge",
    description: "Điều phối đa nguồn theo pass, retry có kiểm soát và hợp nhất kết quả theo ưu tiên.",
    riskNote: "Orchestrator kém sẽ làm pipeline thất thường, nguồn tốt vẫn cho output nhiễu.",
    x: 920,
    y: 1040,
    tone: "amber",
  },
  {
    id: "deep_research",
    title: "Deep Research Loop",
    subtitle: "multi-pass + reasoning loop",
    description: "Vòng lặp deep mode: breadth scan, contradiction scan, cross-source consistency và refine query.",
    riskNote: "Nếu chỉ giả lập bước này bằng client animation, UX sẽ đẹp nhưng pipeline sẽ giả.",
    x: 1280,
    y: 220,
    tone: "amber",
  },
  {
    id: "deep_beta_router",
    title: "Deep Beta Router",
    subtitle: "adaptive branch selection",
    description: "Bật nhánh deep_beta cho truy vấn khó: tăng depth budget, chọn critic profile và strategy động.",
    riskNote: "Nếu route nhầm sang deep_beta sẽ đội chi phí; nếu bỏ qua sẽ mất nhánh suy luận nâng cao.",
    x: 1640,
    y: 220,
    tone: "indigo",
  },
  {
    id: "deep_beta_hypothesis",
    title: "Deep Beta Hypothesis Graph",
    subtitle: "claim lattice + uncertainty probes",
    description: "Xây đồ thị giả thuyết, mở rộng phản giả thuyết và đánh dấu vùng bất định cần truy xuất thêm.",
    riskNote: "Không có hypothesis graph thì deep_beta khó vượt chất lượng của deep cũ.",
    x: 1640,
    y: 470,
    tone: "indigo",
  },
  {
    id: "deep_beta_critic",
    title: "Deep Beta Critic Loop",
    subtitle: "cross-source critique passes",
    description: "Chạy critic pass để bẻ gãy lập luận yếu, buộc pipeline thu thập bằng chứng phản biện.",
    riskNote: "Nếu critic loop quá nhẹ, output vẫn có nguy cơ overconfident trên evidence mỏng.",
    x: 2000,
    y: 220,
    tone: "amber",
  },
  {
    id: "deep_beta_consensus",
    title: "Deep Beta Consensus",
    subtitle: "merge verdict + retrieval focus",
    description: "Hợp nhất kết quả critic/hypothesis thành kế hoạch retrieval và verification tập trung hơn.",
    riskNote: "Consensus sai sẽ lan lỗi sang verification và citation selection.",
    x: 2000,
    y: 380,
    tone: "teal",
  },
  {
    id: "retrieval_internal",
    title: "Internal Corpus",
    subtitle: "Seed docs, source hub, uploaded files",
    description: "Lấy context từ kho nội bộ, curated registry và dữ liệu người dùng đã upload.",
    riskNote: "Nếu corpus không versioned/curated, quality drift sẽ tăng nhanh theo thời gian.",
    x: 1280,
    y: 500,
    tone: "sky",
  },
  {
    id: "retrieval_scientific",
    title: "Scientific Retrieval",
    subtitle: "PubMed, Europe PMC, FDA, DailyMed",
    description: "Kéo bằng chứng chuyên môn từ nguồn khoa học và drug-safety connector.",
    riskNote: "Đây là node nhạy với timeout, query rewrite và chất lượng connector nhất.",
    x: 1280,
    y: 760,
    tone: "sky",
    toggleKey: "scientific_retrieval_enabled",
  },
  {
    id: "retrieval_web",
    title: "Web Retrieval",
    subtitle: "SearXNG + controlled crawl",
    description: "Mở rộng recall bằng web retrieval và crawling có allowlist, chỉ dùng khi thật sự cần.",
    riskNote: "Web retrieval mạnh nhưng dễ kéo nhiễu nếu trust/crawl policy không đủ chặt.",
    x: 1280,
    y: 1020,
    tone: "sky",
    toggleKey: "web_retrieval_enabled",
  },
  {
    id: "retrieval_file",
    title: "File Retrieval",
    subtitle: "User context grounding",
    description: "Inject ngữ cảnh từ file người dùng tải lên để câu trả lời grounded vào case thực tế.",
    riskNote: "Tắt node này sẽ làm research mất context cá nhân hóa quan trọng.",
    x: 1280,
    y: 1280,
    tone: "sky",
    toggleKey: "file_retrieval_enabled",
  },
  {
    id: "evidence_index",
    title: "Evidence Index + Rerank",
    subtitle: "dedupe / hybrid score / trust weighting",
    description: "Dedupe, hybrid dense+sparse score, trust-tier weighting và chọn evidence có chất lượng cao.",
    riskNote: "Nếu rerank không có trust/claim signals thì tài liệu nhiễu vẫn lọt vào synthesis.",
    x: 1640,
    y: 700,
    tone: "teal",
  },
  {
    id: "contradiction_miner",
    title: "Contradiction Miner",
    subtitle: "counter-evidence & disagreement map",
    description: "Tìm bằng chứng trái chiều, subgroup conflict và tạo matrix đồng thuận/bất đồng.",
    riskNote: "Không có bước này dễ dẫn đến câu trả lời quá tự tin dù evidence đang mâu thuẫn.",
    x: 1760,
    y: 1000,
    tone: "indigo",
  },
  {
    id: "synthesis",
    title: "Answer Synthesis",
    subtitle: "DeepSeek generation, Markdown contract",
    description: "Tổng hợp câu trả lời theo contract Markdown, bảng so sánh, mermaid và citation inline.",
    riskNote: "Nếu synthesis không bị ép contract, output sẽ rất khó render nhất quán trên UI.",
    x: 2000,
    y: 760,
    tone: "amber",
  },
  {
    id: "verification",
    title: "FIDES Verification",
    subtitle: "Claim support and contradiction check",
    description: "Đối chiếu claim với retrieved evidence, đo coverage và phát hiện mâu thuẫn.",
    riskNote: "Không có verification thì không biết câu trả lời grounded đến mức nào.",
    x: 2000,
    y: 560,
    tone: "indigo",
    toggleKey: "verification_enabled",
  },
  {
    id: "verification_matrix",
    title: "Claim Matrix",
    subtitle: "supported / unsupported / confidence",
    description: "Chuẩn hóa verdict, severity và unsupported claims trước khi policy gate ra quyết định.",
    riskNote: "Claim matrix lệch sẽ tạo warning sai, làm giảm niềm tin vào hệ thống.",
    x: 2140,
    y: 1120,
    tone: "indigo",
  },
  {
    id: "citation_selection",
    title: "Citation Selection",
    subtitle: "Top evidence, attribution payload",
    description: "Chọn nguồn được giữ lại cho UI, source attribution và telemetry chi tiết.",
    riskNote: "Citation bị chọn sai sẽ làm người dùng tin vào nguồn không liên quan.",
    x: 2360,
    y: 500,
    tone: "teal",
  },
  {
    id: "policy_gate",
    title: "Policy Gate",
    subtitle: "allow, warn, block, fallback",
    description: "Áp runtime policy để quyết định cho qua, cảnh báo, chặn hay degrade an toàn.",
    riskNote: "Policy gate phải phản ánh đúng trạng thái strict-mode, không được mềm hóa ngầm.",
    x: 2360,
    y: 760,
    tone: "rose",
  },
  {
    id: "deepseek_fallback",
    title: "DeepSeek Fallback",
    subtitle: "Low-context or upstream degraded path",
    description: "Nhánh dự phòng khi low-context hoặc upstream lỗi, chỉ được phép khi runtime cho phép.",
    riskNote: "Lạm dụng fallback sẽ phá toàn bộ lời hứa research grounded của sản phẩm.",
    x: 2440,
    y: 1240,
    tone: "rose",
    toggleKey: "deepseek_fallback_enabled",
  },
  {
    id: "responder",
    title: "Responder",
    subtitle: "UI payload, logs, telemetry, DB",
    description: "Trả payload cuối về web/admin, ghi telemetry, attribution, flow events và lưu conversation.",
    riskNote: "Nếu responder thiếu metadata, research trông như đang chạy nhưng không kiểm toán được.",
    x: 2720,
    y: 760,
    tone: "sky",
  },
  {
    id: "evaluation_feedback",
    title: "Eval + Feedback Loop",
    subtitle: "online KPIs + hard-negative mining",
    description: "Ghi KPI retrieval/verification, sinh hard negatives và feed ngược về planner/reranker.",
    riskNote: "Không có vòng lặp này thì quality không cải thiện bền vững sau mỗi lần deploy.",
    x: 2860,
    y: 1060,
    tone: "teal",
  },
];

const GRID_ORIGIN_X = 300;
const GRID_ORIGIN_Y = 220;
const GRID_COL_GAP = 520;
const GRID_ROW_GAP = 280;

const NODE_GRID_LAYOUT: Record<FlowNodeId, { col: number; row: number }> = {
  input_gateway: { col: 0, row: 0 },
  session_guard: { col: 0, row: 1 },
  safety_ingress: { col: 0, row: 2 },

  legal_guard: { col: 1, row: 0 },
  role_router: { col: 1, row: 1 },
  intent_router: { col: 1, row: 2 },
  query_canonicalizer: { col: 1, row: 3 },

  planner: { col: 2, row: 1 },
  query_decomposition: { col: 2, row: 2 },
  retrieval_orchestrator: { col: 2, row: 3 },

  deep_research: { col: 3, row: 0 },
  retrieval_internal: { col: 3, row: 2 },
  retrieval_scientific: { col: 3, row: 3 },
  retrieval_web: { col: 3, row: 4 },
  retrieval_file: { col: 3, row: 5 },

  deep_beta_router: { col: 4, row: 0 },
  deep_beta_hypothesis: { col: 4, row: 1 },
  deep_beta_critic: { col: 4, row: 2 },
  deep_beta_consensus: { col: 4, row: 3 },
  evidence_index: { col: 4, row: 4 },
  contradiction_miner: { col: 4, row: 5 },

  citation_selection: { col: 5, row: 3 },
  verification: { col: 5, row: 4 },
  synthesis: { col: 5, row: 5 },
  verification_matrix: { col: 5, row: 6 },

  responder: { col: 6, row: 4 },
  policy_gate: { col: 6, row: 5 },
  deepseek_fallback: { col: 6, row: 6 },
  evaluation_feedback: { col: 6, row: 7 },
};

function intersects(a: FlowNodeDef, b: FlowNodeDef): boolean {
  return (
    Math.abs(a.x - b.x) < NODE_CARD_WIDTH + NODE_SAFE_GAP_X &&
    Math.abs(a.y - b.y) < NODE_CARD_HEIGHT + NODE_SAFE_GAP_Y
  );
}

function clampPosition(node: FlowNodeDef): FlowNodeDef {
  const minX = NODE_CARD_WIDTH / 2 + 32;
  const maxX = SCENE_WIDTH - NODE_CARD_WIDTH / 2 - 32;
  const minY = NODE_CARD_HEIGHT / 2 + 32;
  const maxY = SCENE_HEIGHT - NODE_CARD_HEIGHT / 2 - 32;
  return {
    ...node,
    x: Math.max(minX, Math.min(maxX, node.x)),
    y: Math.max(minY, Math.min(maxY, node.y)),
  };
}

function resolveNonOverlappingNodes(nodes: FlowNodeDef[]): FlowNodeDef[] {
  const seeded = nodes.map((node) => {
    const slot = NODE_GRID_LAYOUT[node.id];
    if (!slot) {
      return clampPosition(node);
    }
    return clampPosition({
      ...node,
      x: GRID_ORIGIN_X + slot.col * GRID_COL_GAP,
      y: GRID_ORIGIN_Y + slot.row * GRID_ROW_GAP,
    });
  });

  const placed: FlowNodeDef[] = [];
  for (const seed of seeded) {
    let candidate = { ...seed };
    let guard = 0;
    while (placed.some((existing) => intersects(candidate, existing)) && guard < 80) {
      candidate = clampPosition({
        ...candidate,
        y: candidate.y + NODE_CARD_HEIGHT + NODE_SAFE_GAP_Y / 2,
      });
      guard += 1;
    }
    placed.push(candidate);
  }
  return placed;
}

const FLOW_NODES = resolveNonOverlappingNodes(NODES);

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

const NODE_BY_ID = FLOW_NODES.reduce<Record<FlowNodeId, FlowNodeDef>>((acc, node) => {
  acc[node.id] = node;
  return acc;
}, {} as Record<FlowNodeId, FlowNodeDef>);

const EDGES: FlowEdgeDef[] = [
  { from: "input_gateway", to: "session_guard" },
  { from: "session_guard", to: "safety_ingress" },
  { from: "safety_ingress", to: "legal_guard", bend: -180 },
  { from: "safety_ingress", to: "role_router", bend: -36 },
  { from: "safety_ingress", to: "intent_router", bend: 14 },
  { from: "safety_ingress", to: "query_canonicalizer", bend: 72 },
  { from: "legal_guard", to: "policy_gate", bend: -160, label: "hard refusal" },
  { from: "role_router", to: "planner", bend: 22 },
  { from: "intent_router", to: "planner", bend: -40 },
  { from: "query_canonicalizer", to: "planner", bend: -64 },
  { from: "planner", to: "query_decomposition", bend: 46, label: "decompose" },
  { from: "planner", to: "deep_research", bend: -170, label: "deep mode" },
  { from: "planner", to: "deep_beta_router", bend: -250, label: "deep_beta mode" },
  { from: "planner", to: "retrieval_orchestrator", bend: 150 },
  { from: "query_decomposition", to: "deep_research", bend: -88 },
  { from: "query_decomposition", to: "deep_beta_router", bend: -160 },
  { from: "query_decomposition", to: "retrieval_orchestrator", bend: 48 },
  { from: "deep_research", to: "deep_beta_router", bend: -118, label: "beta escalation" },
  { from: "deep_beta_router", to: "deep_beta_hypothesis", bend: 48 },
  { from: "deep_beta_hypothesis", to: "deep_beta_critic", bend: -92, label: "critic pass" },
  { from: "deep_beta_critic", to: "deep_beta_consensus", bend: 24, label: "consensus" },
  { from: "deep_beta_consensus", to: "retrieval_scientific", bend: 108, label: "targeted retrieval" },
  { from: "deep_beta_consensus", to: "verification", bend: 24 },
  { from: "deep_beta_consensus", to: "citation_selection", bend: -36 },
  { from: "retrieval_orchestrator", to: "retrieval_internal", bend: -120 },
  { from: "retrieval_orchestrator", to: "retrieval_scientific", bend: -40 },
  { from: "retrieval_orchestrator", to: "retrieval_web", bend: 30 },
  { from: "retrieval_orchestrator", to: "retrieval_file", bend: 80 },
  { from: "deep_research", to: "retrieval_scientific", bend: 82 },
  { from: "retrieval_internal", to: "evidence_index", bend: -54 },
  { from: "retrieval_scientific", to: "evidence_index" },
  { from: "retrieval_web", to: "evidence_index", bend: 28 },
  { from: "retrieval_file", to: "evidence_index", bend: 84 },
  { from: "evidence_index", to: "contradiction_miner", bend: 74, label: "counter evidence" },
  { from: "evidence_index", to: "synthesis", bend: -12 },
  { from: "contradiction_miner", to: "verification_matrix", bend: 68 },
  { from: "synthesis", to: "verification", bend: -100 },
  { from: "synthesis", to: "verification_matrix", bend: 140 },
  { from: "verification", to: "citation_selection", bend: -42 },
  { from: "verification", to: "policy_gate", bend: 20 },
  { from: "verification_matrix", to: "policy_gate", bend: -20 },
  { from: "citation_selection", to: "responder", bend: 66 },
  { from: "policy_gate", to: "responder", bend: 10 },
  { from: "responder", to: "evaluation_feedback", bend: 96, label: "online eval" },
  { from: "evaluation_feedback", to: "planner", bend: -330, label: "offline tuning" },
  { from: "planner", to: "deepseek_fallback", fallback: true, bend: 250, label: "degraded path" },
  { from: "evidence_index", to: "deepseek_fallback", fallback: true, bend: 180 },
  { from: "policy_gate", to: "deepseek_fallback", fallback: true, bend: 86 },
  { from: "deepseek_fallback", to: "responder", fallback: true, bend: -120, label: "fallback response" },
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
    nodeClass:
      "border-cyan-200/70 bg-white/92 shadow-[0_16px_40px_rgba(8,47,73,0.16)] dark:border-cyan-300/55 dark:bg-slate-900/90 dark:shadow-[0_20px_46px_rgba(2,6,23,0.72)]",
    badgeClass:
      "border-cyan-300/80 bg-cyan-100/90 text-cyan-800 dark:border-cyan-400/45 dark:bg-cyan-950/55 dark:text-cyan-200",
  },
  on: {
    label: "live",
    nodeClass:
      "border-emerald-300/70 bg-white/94 shadow-[0_20px_48px_rgba(16,185,129,0.2)] dark:border-emerald-300/55 dark:bg-slate-900/92 dark:shadow-[0_24px_54px_rgba(6,78,59,0.6)]",
    badgeClass:
      "border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-500/45 dark:bg-emerald-950/55 dark:text-emerald-200",
  },
  off: {
    label: "off",
    nodeClass:
      "border-slate-300/75 bg-slate-100/86 opacity-95 shadow-none dark:border-slate-500/75 dark:bg-slate-900/88 dark:opacity-100",
    badgeClass:
      "border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300",
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
    glow: "shadow-[0_0_0_1px_rgba(14,165,233,0.2),0_18px_42px_rgba(14,165,233,0.16)] dark:shadow-[0_0_0_1px_rgba(34,211,238,0.36),0_22px_46px_rgba(8,47,73,0.72)]",
    stripe: "from-cyan-400 via-sky-500 to-blue-500 dark:from-cyan-300 dark:via-sky-400 dark:to-blue-400",
    chip: "border border-cyan-300/70 bg-cyan-100/85 text-cyan-700 dark:border-cyan-500/45 dark:bg-cyan-950/50 dark:text-cyan-200",
  },
  teal: {
    glow: "shadow-[0_0_0_1px_rgba(20,184,166,0.2),0_18px_42px_rgba(20,184,166,0.16)] dark:shadow-[0_0_0_1px_rgba(45,212,191,0.34),0_22px_46px_rgba(6,78,59,0.68)]",
    stripe: "from-teal-400 via-emerald-500 to-lime-400 dark:from-teal-300 dark:via-emerald-400 dark:to-lime-300",
    chip: "border border-teal-300/70 bg-teal-100/85 text-teal-700 dark:border-teal-500/45 dark:bg-teal-950/50 dark:text-teal-200",
  },
  indigo: {
    glow: "shadow-[0_0_0_1px_rgba(99,102,241,0.2),0_18px_42px_rgba(99,102,241,0.16)] dark:shadow-[0_0_0_1px_rgba(129,140,248,0.34),0_22px_46px_rgba(49,46,129,0.68)]",
    stripe: "from-indigo-400 via-blue-500 to-violet-500 dark:from-indigo-300 dark:via-blue-400 dark:to-violet-400",
    chip: "border border-indigo-300/70 bg-indigo-100/85 text-indigo-700 dark:border-indigo-500/45 dark:bg-indigo-950/50 dark:text-indigo-200",
  },
  amber: {
    glow: "shadow-[0_0_0_1px_rgba(245,158,11,0.2),0_18px_42px_rgba(245,158,11,0.16)] dark:shadow-[0_0_0_1px_rgba(251,191,36,0.32),0_22px_46px_rgba(146,64,14,0.66)]",
    stripe: "from-amber-400 via-orange-500 to-yellow-400 dark:from-amber-300 dark:via-orange-400 dark:to-yellow-300",
    chip: "border border-amber-300/70 bg-amber-100/85 text-amber-700 dark:border-amber-500/45 dark:bg-amber-950/50 dark:text-amber-200",
  },
  rose: {
    glow: "shadow-[0_0_0_1px_rgba(244,63,94,0.2),0_18px_42px_rgba(244,63,94,0.16)] dark:shadow-[0_0_0_1px_rgba(251,113,133,0.34),0_22px_46px_rgba(136,19,55,0.68)]",
    stripe: "from-rose-400 via-fuchsia-500 to-pink-500 dark:from-rose-300 dark:via-fuchsia-400 dark:to-pink-400",
    chip: "border border-rose-300/70 bg-rose-100/85 text-rose-700 dark:border-rose-500/45 dark:bg-rose-950/50 dark:text-rose-200",
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
  const [isDarkMode, setIsDarkMode] = useState(false);

  useEffect(() => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    const refresh = () => {
      setIsDarkMode(root.classList.contains("dark") || root.dataset.theme === "dark");
    };
    refresh();
    const observer = new MutationObserver(refresh);
    observer.observe(root, { attributes: true, attributeFilter: ["class", "data-theme"] });
    return () => observer.disconnect();
  }, []);

  const edgePalette = useMemo(
    () =>
      isDarkMode
        ? {
            live: "#22d3ee",
            muted: "#64748b",
            fallback: "#fb923c",
            label: "#a5b4fc",
          }
        : {
            live: "#0891b2",
            muted: "#94a3b8",
            fallback: "#f97316",
            label: "#334155",
          },
    [isDarkMode],
  );

  const statusByNode = useMemo(
    () =>
      FLOW_NODES.reduce<Record<FlowNodeId, FlowNodeStatus>>((acc, node) => {
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
        backgroundColor: isDarkMode ? "#020617" : "#eff6ff",
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
  }, [isDarkMode, isExporting]);

  const liveNodeCount = FLOW_NODES.filter((node) => isActive(statusByNode[node.id])).length;
  const optionalNodeCount = FLOW_NODES.filter((node) => Boolean(node.toggleKey)).length;
  const lowContextThreshold = typeof ragFlow?.low_context_threshold === "number" ? ragFlow.low_context_threshold : 0;

  return (
    <section className="relative overflow-hidden rounded-[32px] border border-cyan-200/45 bg-[radial-gradient(circle_at_8%_4%,rgba(56,189,248,0.28),transparent_33%),radial-gradient(circle_at_86%_18%,rgba(34,211,238,0.18),transparent_36%),radial-gradient(circle_at_88%_92%,rgba(14,165,233,0.24),transparent_42%),linear-gradient(158deg,rgba(255,255,255,0.95),rgba(236,254,255,0.9)_42%,rgba(224,242,254,0.92))] p-5 shadow-[0_34px_96px_rgba(8,47,73,0.2)] dark:border-cyan-500/30 dark:bg-[radial-gradient(circle_at_12%_6%,rgba(34,211,238,0.22),transparent_36%),radial-gradient(circle_at_88%_12%,rgba(56,189,248,0.16),transparent_40%),radial-gradient(circle_at_88%_90%,rgba(59,130,246,0.2),transparent_44%),linear-gradient(160deg,rgba(2,6,23,0.96),rgba(8,47,73,0.86)_46%,rgba(15,23,42,0.94))] dark:shadow-[0_40px_110px_rgba(2,6,23,0.84)]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,rgba(8,145,178,0.14)_1px,transparent_1px),linear-gradient(to_bottom,rgba(8,145,178,0.14)_1px,transparent_1px)] bg-[size:26px_26px] dark:bg-[linear-gradient(to_right,rgba(8,145,178,0.26)_1px,transparent_1px),linear-gradient(to_bottom,rgba(8,145,178,0.26)_1px,transparent_1px)]" />
      <div className="pointer-events-none absolute inset-x-8 top-0 h-36 rounded-b-[40px] bg-gradient-to-b from-cyan-300/30 to-transparent blur-2xl dark:from-cyan-400/25" />

      <div className="relative flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500 dark:text-slate-400">
            CLARA Research Flow Visualizer
          </p>
          <h3 className="mt-2 text-lg font-semibold tracking-tight text-slate-950 dark:text-slate-100">
            Runtime Canvas: Deep + Deep Beta
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
            Canvas mới mô tả pipeline deep research nâng cấp: safety/legal ingress, query canonicalization,
            deep_beta critic loop, retrieval orchestration, contradiction mining, verification và feedback loop.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-2xl border border-cyan-200/60 bg-white/72 px-4 py-3 shadow-[0_16px_36px_rgba(8,145,178,0.16)] backdrop-blur-xl dark:border-cyan-500/35 dark:bg-slate-900/62 dark:shadow-[0_16px_34px_rgba(2,6,23,0.7)]">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Active Nodes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950 dark:text-slate-100">{liveNodeCount}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">trong tổng {FLOW_NODES.length} node</p>
          </div>
          <div className="rounded-2xl border border-cyan-200/60 bg-white/72 px-4 py-3 shadow-[0_16px_36px_rgba(8,145,178,0.16)] backdrop-blur-xl dark:border-cyan-500/35 dark:bg-slate-900/62 dark:shadow-[0_16px_34px_rgba(2,6,23,0.7)]">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Toggle Nodes</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950 dark:text-slate-100">{optionalNodeCount}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">có thể bật/tắt từ runtime</p>
          </div>
          <div className="rounded-2xl border border-cyan-200/60 bg-white/72 px-4 py-3 shadow-[0_16px_36px_rgba(8,145,178,0.16)] backdrop-blur-xl dark:border-cyan-500/35 dark:bg-slate-900/62 dark:shadow-[0_16px_34px_rgba(2,6,23,0.7)]">
            <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Low Context Threshold</p>
            <p className="mt-1 text-2xl font-semibold text-slate-950 dark:text-slate-100">{lowContextThreshold.toFixed(2)}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">điều khiển degraded path</p>
          </div>
        </div>
      </div>

      <div className="relative mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-cyan-200/60 bg-white/70 px-4 py-3 shadow-[0_10px_30px_rgba(8,145,178,0.14)] backdrop-blur-xl dark:border-cyan-500/30 dark:bg-slate-900/58 dark:shadow-[0_16px_38px_rgba(2,6,23,0.72)]">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500 dark:text-slate-400">
            Export
          </p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
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
              ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500"
              : "border-cyan-300 bg-cyan-100/95 text-cyan-800 hover:bg-cyan-200 dark:border-cyan-500/50 dark:bg-cyan-950/50 dark:text-cyan-200 dark:hover:bg-cyan-900/70",
          )}
        >
          {isExporting ? "Đang xuất JPG 3x..." : "Xuất JPG High-Res"}
        </button>
      </div>

      <div className="relative mt-5 flex flex-wrap items-center gap-2 text-[11px]">
        <span className="rounded-full border border-cyan-300/75 bg-cyan-100/92 px-2.5 py-1 font-semibold text-cyan-800 dark:border-cyan-500/45 dark:bg-cyan-950/50 dark:text-cyan-200">
          core
        </span>
        <span className="rounded-full border border-emerald-300/75 bg-emerald-100/92 px-2.5 py-1 font-semibold text-emerald-800 dark:border-emerald-500/45 dark:bg-emerald-950/50 dark:text-emerald-200">
          live
        </span>
        <span className="rounded-full border border-slate-300 bg-slate-100 px-2.5 py-1 font-semibold text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          off
        </span>
        <span className="rounded-full border border-orange-300/75 bg-orange-100/92 px-2.5 py-1 font-semibold text-orange-700 dark:border-orange-500/45 dark:bg-orange-950/50 dark:text-orange-200">
          degraded branch
        </span>
        <span className="rounded-full border border-indigo-300/75 bg-indigo-100/92 px-2.5 py-1 font-semibold text-indigo-700 dark:border-indigo-500/45 dark:bg-indigo-950/50 dark:text-indigo-200">
          tuning feedback
        </span>
      </div>

      <div className="relative mt-5 overflow-x-auto rounded-[24px] border border-cyan-200/50 bg-slate-950/[0.04] p-3 dark:border-cyan-700/30 dark:bg-slate-950/30">
        <div
          ref={sceneRef}
          className="relative overflow-hidden rounded-[22px] border border-cyan-200/50 bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.22),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(59,130,246,0.15),_transparent_34%),linear-gradient(180deg,_rgba(248,250,252,0.78),_rgba(241,245,249,0.88))] dark:border-cyan-700/30 dark:bg-[radial-gradient(circle_at_top,_rgba(34,211,238,0.2),_transparent_36%),radial-gradient(circle_at_bottom_right,_rgba(59,130,246,0.16),_transparent_42%),linear-gradient(180deg,_rgba(2,6,23,0.74),_rgba(15,23,42,0.9))]"
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
                <path d="M0,0 L10,5 L0,10 z" fill={edgePalette.live} />
              </marker>
              <marker id="flow-arrow-muted" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" fill={edgePalette.muted} />
              </marker>
              <marker id="flow-arrow-fallback" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 z" fill={edgePalette.fallback} />
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
                  ? edgePalette.fallback
                  : edgePalette.muted
                : edgeActive
                  ? edgePalette.live
                  : edgePalette.muted;
              const marker = edge.fallback
                ? fallbackEnabled
                  ? "url(#flow-arrow-fallback)"
                  : "url(#flow-arrow-muted)"
                : edgeActive
                  ? "url(#flow-arrow-live)"
                  : "url(#flow-arrow-muted)";
              const labelX = (from.x + to.x) / 2;
              const labelY = (from.y + to.y) / 2 + (edge.bend ?? 0) - 12;

              const showGlow = !isExporting && (edgeActive || fallbackEnabled);
              return (
                <g key={`${edge.from}-${edge.to}`}>
                  <path
                    d={path}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={edge.fallback ? 3 : 2.4}
                    strokeLinecap="round"
                    strokeDasharray={edge.fallback ? "10 8" : undefined}
                    markerEnd={marker}
                    opacity={edgeActive || fallbackEnabled ? 0.95 : 0.6}
                    filter={showGlow ? "url(#flow-glow)" : undefined}
                  />
                  {edge.label ? (
                    <text
                      x={labelX}
                      y={labelY}
                      textAnchor="middle"
                      className="text-[11px] font-semibold tracking-[0.08em]"
                      style={{ fill: edgePalette.label }}
                    >
                      {edge.label}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </svg>

          {FLOW_NODES.map((node) => {
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
                    "backdrop-blur-xl",
                    meta.nodeClass,
                    tone.glow,
                    isSelected && "border-slate-900/80 ring-2 ring-cyan-500/35 dark:border-cyan-200/90 dark:ring-cyan-300/45",
                  )}
                  style={{ width: NODE_CARD_WIDTH }}
                >
                  <div className={cx("absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r", tone.stripe)} />

                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
                        {node.subtitle}
                      </p>
                      <h4 className="mt-1 text-sm font-semibold leading-5 text-slate-950 dark:text-slate-100">{node.title}</h4>
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

                  <p className="mt-3 h-[78px] overflow-hidden text-[12px] leading-5 text-slate-600 dark:text-slate-300">
                    {node.description}
                  </p>

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
                            ? "border-emerald-300 bg-emerald-100 text-emerald-800 hover:bg-emerald-200 dark:border-emerald-500/45 dark:bg-emerald-950/55 dark:text-emerald-200 dark:hover:bg-emerald-900/70"
                            : "border-slate-300 bg-white text-slate-600 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800",
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
