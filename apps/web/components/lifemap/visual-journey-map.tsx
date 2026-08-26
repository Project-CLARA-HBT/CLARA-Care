"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Icon, type IconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type JourneyNodeCategory =
  | "goal"
  | "milestone"
  | "treatment"
  | "assessment"
  | "encounter"
  | "lifestyle";

export type JourneyNodeStatus =
  | "completed"
  | "in_progress"
  | "pending"
  | "disputed";

export interface JourneyNode {
  id: string;
  title: string;
  category: JourneyNodeCategory;
  status: JourneyNodeStatus;
  date?: string;
  description?: string;
  metrics?: Record<string, string | number>;
  tags?: string[];
}

export interface JourneyPhase {
  id: string;
  title: string;
  description?: string;
  nodes: JourneyNode[];
}

export interface VisualJourneyMapProps {
  episodes?: Array<{ id: string; title: string; priority?: string; status?: string }>;
  selectedEpisodeId?: string;
  onSelectEpisode?: (id: string) => void;
  phases?: JourneyPhase[];
  onSelectNode?: (node: JourneyNode) => void;
  onAddNode?: (phaseId?: string) => void;
  readOnly?: boolean;
  className?: string;
}

const DEFAULT_PHASES: JourneyPhase[] = [
  {
    id: "phase-init",
    title: "1. Khởi động & Đánh giá ban đầu",
    description: "Khám tổng quát, đo chỉ số nền và thiết lập mục tiêu",
    nodes: [
      {
        id: "node-1",
        title: "Thiết lập mục tiêu kiểm soát huyết áp",
        category: "goal",
        status: "completed",
        date: "2026-08-01",
        description: "Duy trì huyết áp < 130/80 mmHg và nhịp tim ổn định 65-75 bpm.",
        metrics: { "Mục tiêu": "< 130/80 mmHg" },
      },
      {
        id: "node-2",
        title: "Khám chuyên khoa Tim mạch",
        category: "encounter",
        status: "completed",
        date: "2026-08-03",
        description: "BS. Trần Văn Hoàng khám tim mạch, tư vấn phác đồ và dinh dưỡng.",
      },
      {
        id: "node-3",
        title: "Xét nghiệm máu & Mỡ máu nền",
        category: "assessment",
        status: "completed",
        date: "2026-08-05",
        description: "Cholesterol toàn phần: 4.8 mmol/L, HbA1c: 5.6%.",
        metrics: { Cholesterol: "4.8 mmol/L", HbA1c: "5.6%" },
      },
    ],
  },
  {
    id: "phase-active",
    title: "2. Giai đoạn Can thiệp & Theo dõi đều đặn",
    description: "Uống thuốc đúng giờ, đo huyết áp 2 lần/ngày và vận động nhẹ",
    nodes: [
      {
        id: "node-4",
        title: "Dùng thuốc Amlodipine 5mg mỗi sáng",
        category: "treatment",
        status: "in_progress",
        date: "2026-08-03",
        description: "Uống 1 viên vào 07:00 sau ăn sáng.",
        tags: ["Thuốc hàng ngày"],
      },
      {
        id: "node-5",
        title: "Ghi nhật ký huyết áp 7 ngày liên tục",
        category: "milestone",
        status: "in_progress",
        date: "2026-08-10",
        description: "Đã đạt 6/7 ngày theo dõi sáng tối.",
        metrics: { "Tiến độ": "6/7 ngày", "Trung bình": "126/81 mmHg" },
      },
      {
        id: "node-6",
        title: "Đi bộ 30 phút/ngày vào buổi chiều",
        category: "lifestyle",
        status: "pending",
        description: "Vận động nhẹ nhàng nhằm cải thiện lưu thông máu.",
      },
    ],
  },
  {
    id: "phase-review",
    title: "3. Tái khám & Tối ưu hóa phác đồ",
    description: "Đánh giá hiệu quả sau 30 ngày và thảo luận cùng bác sĩ",
    nodes: [
      {
        id: "node-7",
        title: "Tái khám đánh giá hiệu quả thuốc",
        category: "encounter",
        status: "pending",
        date: "2026-09-03",
        description: "Mang báo cáo tóm tắt 30 ngày LifeMap cho bác sĩ xem xét.",
      },
      {
        id: "node-8",
        title: "Đạt mốc huyết áp ổn định 1 tháng",
        category: "goal",
        status: "pending",
        description: "90% các lần đo duy trì trong ngưỡng mục tiêu an toàn.",
      },
    ],
  },
];

export function VisualJourneyMap({
  episodes = [],
  selectedEpisodeId,
  onSelectEpisode,
  phases = DEFAULT_PHASES,
  onSelectNode,
  onAddNode,
  readOnly = false,
  className = "",
}: VisualJourneyMapProps) {
  const language = useUILanguage();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const allNodes = useMemo(
    () => phases.flatMap((phase) => phase.nodes),
    [phases],
  );

  const completedCount = useMemo(
    () => allNodes.filter((n) => n.status === "completed").length,
    [allNodes],
  );

  const progressPercent = allNodes.length
    ? Math.round((completedCount / allNodes.length) * 100)
    : 0;

  const activeNode = useMemo(
    () => allNodes.find((n) => n.id === selectedNodeId) ?? allNodes[0] ?? null,
    [allNodes, selectedNodeId],
  );

  const handleNodeClick = (node: JourneyNode) => {
    setSelectedNodeId(node.id);
    onSelectNode?.(node);
  };

  const getStatusTone = (status: JourneyNodeStatus): "ok" | "brand" | "neutral" | "warn" => {
    switch (status) {
      case "completed":
        return "ok";
      case "in_progress":
        return "brand";
      case "disputed":
        return "warn";
      default:
        return "neutral";
    }
  };

  const getStatusLabel = (status: JourneyNodeStatus): string => {
    switch (status) {
      case "completed":
        return "Đã hoàn thành";
      case "in_progress":
        return "Đang thực hiện";
      case "disputed":
        return "Đang khiếu nại";
      default:
        return "Dự kiến";
    }
  };

  const getCategoryIcon = (category: JourneyNodeCategory): IconName => {
    switch (category) {
      case "goal":
        return "check";
      case "milestone":
        return "progress";
      case "treatment":
        return "medication";
      case "assessment":
        return "clinical-notes";
      case "encounter":
        return "contact";
      case "lifestyle":
        return "body";
      default:
        return "progress";
    }
  };

  return (
    <div className={`space-y-6 ${className}`} data-testid="visual-journey-map">
      {/* Top Header & Episode Selector Bar */}
      <SurfaceCard className="p-4 rounded-xl border border-[var(--shell-border)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
              <Icon name="progress" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                  Bản đồ hành trình
                </span>
                <span className="text-xs text-[var(--text-muted)]">•</span>
                <span className="text-xs font-medium text-[var(--text-brand)]">
                  Tiến độ: {progressPercent}% ({completedCount}/{allNodes.length} mốc)
                </span>
              </div>
              <h2 className="text-base font-semibold text-[var(--text-primary)]">
                Lộ trình mục tiêu sức khỏe trực quan
              </h2>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {episodes.length > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-[var(--text-secondary)]">Hành trình:</span>
                <select
                  aria-label="Chọn hành trình"
                  value={selectedEpisodeId ?? episodes[0]?.id ?? ""}
                  onChange={(e) => onSelectEpisode?.(e.target.value)}
                  className="rounded-lg border border-[var(--shell-border)] bg-[var(--surface-panel)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-primary)] focus:border-[var(--brand-primary)]"
                >
                  {episodes.map((ep) => (
                    <option key={ep.id} value={ep.id}>
                      {ep.title}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {!readOnly && (
              <Button
                size="sm"
                variant="secondary"
                icon="add"
                onClick={() => onAddNode?.()}
              >
                Thêm mốc mới
              </Button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="mt-4">
          <div
            className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]"
            role="progressbar"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Tiến độ hành trình"
          >
            <div
              className="h-full bg-[var(--brand-500)] transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </SurfaceCard>

      {/* Map Nodes Lanes */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {phases.map((phase, pIdx) => (
          <div
            key={phase.id}
            className="flex flex-col rounded-xl border border-[var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm"
          >
            <div className="mb-3 border-b border-[var(--shell-border)] pb-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-[var(--text-brand)]">
                  Chặng {pIdx + 1}
                </span>
                <span className="text-xs text-[var(--text-muted)]">
                  {phase.nodes.length} nút
                </span>
              </div>
              <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                {phase.title}
              </h3>
              {phase.description && (
                <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
                  {phase.description}
                </p>
              )}
            </div>

            <div className="flex-1 space-y-3">
              {phase.nodes.map((node) => {
                const isSelected = activeNode?.id === node.id;
                return (
                  <button
                    key={node.id}
                    type="button"
                    role="button"
                    aria-label={node.title}
                    aria-pressed={isSelected}
                    onClick={() => handleNodeClick(node)}
                    className={`w-full rounded-xl border p-3.5 text-left transition-all ${
                      isSelected
                        ? "border-[var(--brand-500)] bg-[var(--surface-brand-soft,rgba(164,201,255,0.12))] shadow-xs"
                        : "border-[var(--shell-border)] bg-[var(--surface-container)] hover:border-[var(--brand-300)] hover:bg-[var(--surface-container-high)]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-[var(--surface-muted)] text-[var(--text-brand)]">
                          <Icon name={getCategoryIcon(node.category)} size={14} />
                        </span>
                        <span className="text-xs font-semibold text-[var(--text-primary)] line-clamp-1">
                          {node.title}
                        </span>
                      </div>
                      <Badge tone={getStatusTone(node.status)}>
                        {getStatusLabel(node.status)}
                      </Badge>
                    </div>

                    {node.description && (
                      <p className="mt-2 text-xs text-[var(--text-secondary)] line-clamp-2">
                        {node.description}
                      </p>
                    )}

                    {node.metrics && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5">
                        {Object.entries(node.metrics).map(([k, v]) => (
                          <span
                            key={k}
                            className="rounded-md bg-[var(--surface-muted)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-primary)] border border-[var(--shell-border)]"
                          >
                            <strong>{k}:</strong> {v}
                          </span>
                        ))}
                      </div>
                    )}

                    {node.date && (
                      <div className="mt-2 text-[11px] text-[var(--text-muted)]">
                        {formatLocaleDate(language, node.date, { dateStyle: "medium" })}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Selected Node Detail Inspector */}
      {activeNode && (
        <SurfaceCard className="p-5 rounded-xl border border-[var(--brand-subtle,var(--shell-border))] bg-[var(--surface-raised)]" aria-live="polite">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[var(--shell-border)] pb-3">
            <div>
              <div className="flex items-center gap-2">
                <Badge tone={getStatusTone(activeNode.status)}>
                  {getStatusLabel(activeNode.status)}
                </Badge>
                <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                  {activeNode.category}
                </span>
              </div>
              <h3 className="mt-1 text-base font-bold text-[var(--text-primary)]">
                {activeNode.title}
              </h3>
            </div>
            {activeNode.date && (
              <span className="text-xs font-mono text-[var(--text-secondary)]">
                {formatLocaleDate(language, activeNode.date, { dateStyle: "long" })}
              </span>
            )}
          </div>

          <div className="mt-4 space-y-3 text-sm">
            {activeNode.description && (
              <p className="text-[var(--text-secondary)] leading-relaxed">
                {activeNode.description}
              </p>
            )}

            {activeNode.metrics && Object.keys(activeNode.metrics).length > 0 && (
              <div className="rounded-lg bg-[var(--surface-muted)] p-3 border border-[var(--shell-border)]">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] mb-2">
                  Chỉ số liên quan
                </h4>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(activeNode.metrics).map(([key, val]) => (
                    <div key={key} className="flex justify-between py-1 border-b border-[var(--shell-border)]/50 last:border-0">
                      <span className="text-[var(--text-secondary)]">{key}:</span>
                      <span className="font-semibold text-[var(--text-primary)]">{val}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </SurfaceCard>
      )}
    </div>
  );
}

export default VisualJourneyMap;
