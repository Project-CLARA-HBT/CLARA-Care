"use client";

import React, { useId, useMemo, useState } from "react";
import { ClaraOrb } from "./clara-orb";

export type ConstellationNodeId =
  | "medications"
  | "recent-changes"
  | "health-record"
  | "prior-questions"
  | "evidence-sources"
  | "clara-core";

export interface ContextConstellationProps {
  /**
   * Convergence progress value from 0 (relaxed spatial orbit) to 1 (tight convergence into CLARA Core).
   * Clamped between 0 and 1. Defaults to 0.5.
   */
  progress?: number;
  /**
   * Optional ID of the currently active or selected node.
   */
  activeNodeId?: string;
  /**
   * Callback invoked when a constellation node or the central CLARA Core is clicked.
   */
  onNodeClick?: (nodeId: string) => void;
  /**
   * UI language for bilingual labels, copy, badges, and clinical context details.
   * Defaults to "vi".
   */
  language?: "vi" | "en";
  /**
   * Additional container CSS classes.
   */
  className?: string;
}

export interface ConstellationNodeItem {
  id: ConstellationNodeId;
  aliases: string[];
  titleVi: string;
  titleEn: string;
  subtitleVi: string;
  subtitleEn: string;
  previewVi: string;
  previewEn: string;
  badgeVi: string;
  badgeEn: string;
  categoryVi: string;
  categoryEn: string;
  tone: "azure" | "amber" | "mint" | "iris" | "sky";
  accentColor: string;
  bgTint: string;
  borderTint: string;
  subtleGlow: string;
  // Spatial positions on 960x580 desktop SVG coordinate plane
  // (x0, y0) = relaxed orbit (progress = 0)
  // (x1, y1) = converged position (progress = 1)
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  // Desktop HTML card placement (relative CSS percentages)
  leftPercent0: number;
  topPercent0: number;
  leftPercent1: number;
  topPercent1: number;
  cardWidthClass: string;
}

const CONSTELLATION_NODES: ConstellationNodeItem[] = [
  {
    id: "medications",
    aliases: ["medications", "activeMedications", "meds", "thuoc"],
    titleVi: "Thuốc đang dùng",
    titleEn: "Active Medications",
    subtitleVi: "Đơn thuốc & Dược động học",
    subtitleEn: "Prescriptions & Pharmacokinetics",
    previewVi: "Metformin 500mg (2x/ngày) • Amlodipine 5mg (sáng)",
    previewEn: "Metformin 500mg (2x/day) • Amlodipine 5mg (morning)",
    badgeVi: "4 hoạt chất",
    badgeEn: "4 active meds",
    categoryVi: "Dược lý",
    categoryEn: "Pharmacology",
    tone: "azure",
    accentColor: "#0B6FD8",
    bgTint: "#EFF7FF",
    borderTint: "rgba(11, 111, 216, 0.28)",
    subtleGlow: "rgba(11, 111, 216, 0.25)",
    x0: 170,
    y0: 130,
    x1: 270,
    y1: 190,
    leftPercent0: 18,
    topPercent0: 22,
    leftPercent1: 28,
    topPercent1: 32,
    cardWidthClass: "w-64 sm:w-72",
  },
  {
    id: "recent-changes",
    aliases: ["recent-changes", "recentChanges", "changes", "thay-doi"],
    titleVi: "Thay đổi gần đây",
    titleEn: "Recent Changes",
    subtitleVi: "Nhật ký biến chuyển sinh hoạt",
    subtitleEn: "Lifestyle & Schedule Shifts",
    previewVi: "Đổi ca làm đêm • Dời cữ uống sáng sang tối (3 ngày trước)",
    previewEn: "Night shift change • Shifted morning dose (3d ago)",
    badgeVi: "Cập nhật mới",
    badgeEn: "Recent shift",
    categoryVi: "Lối sống",
    categoryEn: "Lifestyle",
    tone: "amber",
    accentColor: "#D97706",
    bgTint: "#FEF3C7",
    borderTint: "rgba(217, 119, 6, 0.32)",
    subtleGlow: "rgba(245, 158, 11, 0.25)",
    x0: 480,
    y0: 70,
    x1: 480,
    y1: 140,
    leftPercent0: 50,
    topPercent0: 12,
    leftPercent1: 50,
    topPercent1: 24,
    cardWidthClass: "w-64 sm:w-72",
  },
  {
    id: "health-record",
    aliases: ["health-record", "healthRecord", "record", "phr", "ho-so"],
    titleVi: "Hồ sơ sức khỏe",
    titleEn: "Health Record",
    subtitleVi: "Tiền sử bệnh án & Dị ứng",
    subtitleEn: "Clinical History & Allergies",
    previewVi: "Tăng HA vô căn 10 năm • Dị ứng Penicillin (mề đay)",
    previewEn: "10-yr Essential HTN • Penicillin allergy (urticaria)",
    badgeVi: "Hồ sơ liên thông",
    badgeEn: "Linked PHR",
    categoryVi: "Tiền sử",
    categoryEn: "History",
    tone: "mint",
    accentColor: "#14A88D",
    bgTint: "#ECFDF8",
    borderTint: "rgba(20, 168, 141, 0.32)",
    subtleGlow: "rgba(20, 168, 141, 0.25)",
    x0: 790,
    y0: 130,
    x1: 690,
    y1: 190,
    leftPercent0: 82,
    topPercent0: 22,
    leftPercent1: 72,
    topPercent1: 32,
    cardWidthClass: "w-64 sm:w-72",
  },
  {
    id: "prior-questions",
    aliases: ["prior-questions", "priorQuestions", "pastQuestions", "questions", "cau-hoi"],
    titleVi: "Câu hỏi trước đây",
    titleEn: "Prior Questions",
    subtitleVi: "Lịch sử tương tác & Triệu chứng",
    subtitleEn: "Interaction History & Signals",
    previewVi: "Hồi hộp nhẹ khi uống kèm cà phê sáng (12/08)",
    previewEn: "Mild palpitations with morning coffee (Aug 12)",
    badgeVi: "2 tuần trước",
    badgeEn: "2 weeks ago",
    categoryVi: "Hỏi đáp",
    categoryEn: "Inquiries",
    tone: "iris",
    accentColor: "#8B7CF6",
    bgTint: "#F5F3FF",
    borderTint: "rgba(139, 124, 246, 0.32)",
    subtleGlow: "rgba(139, 124, 246, 0.25)",
    x0: 220,
    y0: 450,
    x1: 310,
    y1: 370,
    leftPercent0: 23,
    topPercent0: 78,
    leftPercent1: 32,
    topPercent1: 64,
    cardWidthClass: "w-64 sm:w-72",
  },
  {
    id: "evidence-sources",
    aliases: ["evidence-sources", "sources", "evidenceSources", "y-van"],
    titleVi: "Nguồn y văn đối chiếu",
    titleEn: "Evidence Sources",
    subtitleVi: "Cơ sở dữ liệu dược & Hướng dẫn",
    subtitleEn: "Clinical Guidelines & Drug Data",
    previewVi: "Dược thư Quốc gia Việt Nam • DrugBank 5.1",
    previewEn: "Vietnam Pharmacopoeia • DrugBank 5.1",
    badgeVi: "5 Nguồn cấp 1",
    badgeEn: "5 Tier-1 Sources",
    categoryVi: "Y văn",
    categoryEn: "Evidence",
    tone: "sky",
    accentColor: "#0284C7",
    bgTint: "#F0F9FF",
    borderTint: "rgba(2, 132, 199, 0.32)",
    subtleGlow: "rgba(2, 132, 199, 0.25)",
    x0: 740,
    y0: 450,
    x1: 650,
    y1: 370,
    leftPercent0: 77,
    topPercent0: 78,
    leftPercent1: 68,
    topPercent1: 64,
    cardWidthClass: "w-64 sm:w-72",
  },
];

const CENTER_NODE = {
  id: "clara-core" as const,
  aliases: ["clara-core", "claraCore", "core", "hub"],
  cx: 480,
  cy: 280,
  titleVi: "CLARA Core",
  titleEn: "CLARA Core",
  subtitleVi: "Hội tụ dữ liệu an toàn",
  subtitleEn: "Safety Convergence Engine",
  descriptionVi: "Hội tụ 5 dòng bối cảnh thời gian thực để đưa ra khuyến nghị an toàn, có căn cứ y văn.",
  descriptionEn: "Synthesizing 5 longitudinal context streams into grounded, verifiable clinical guidance.",
  badgeVi: "FIDES Verified",
  badgeEn: "FIDES Verified",
  statementVi: "Điều gì thực sự đáng chú ý lúc này?",
  statementEn: "What is truly important right now?",
};

function lerp(start: number, end: number, t: number): number {
  return start + (end - start) * t;
}

function renderNodeIcon(nodeId: ConstellationNodeId, color: string) {
  switch (nodeId) {
    case "medications":
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
          <path d="m8.5 8.5 7 7" />
        </svg>
      );
    case "recent-changes":
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case "health-record":
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="M12 8v8" />
          <path d="M8 12h8" />
        </svg>
      );
    case "prior-questions":
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          <path d="M8 10h.01" />
          <path d="M12 10h.01" />
          <path d="M16 10h.01" />
        </svg>
      );
    case "evidence-sources":
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
          <path d="M6 6h10" />
          <path d="M6 10h10" />
          <path d="M6 14h6" />
        </svg>
      );
    case "clara-core":
    default:
      return (
        <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" stroke={color} strokeWidth="2">
          <path d="M12 2L15 9L22 12L15 15L12 22L9 15L2 12L9 9L12 2Z" />
        </svg>
      );
  }
}

/**
 * ContextConstellation Artwork Component
 *
 * Renders a spatial constellation of 5 health context nodes converging toward CLARA Core:
 * - Medications (Thuốc đang dùng)
 * - Recent Changes (Thay đổi gần đây)
 * - Health Record (Hồ sơ sức khỏe)
 * - Prior Questions (Câu hỏi trước đây)
 * - Evidence Sources (Nguồn y văn đối chiếu)
 *
 * Supports continuous scroll-driven convergence (progress: 0 to 1),
 * active node inspection, desktop 3D spatial SVG canvas, and mobile curved stack.
 */
export function ContextConstellation({
  progress = 0.5,
  activeNodeId,
  onNodeClick,
  language = "vi",
  className = "",
}: ContextConstellationProps) {
  const rawId = useId();
  const uid = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Clamp progress strictly between 0 and 1
  const clampedProgress = Math.max(0, Math.min(1, Number.isFinite(progress) ? progress : 0.5));
  const isVI = language === "vi";

  // Match active or hovered node
  const effectiveActiveId = (activeNodeId || hoveredNodeId || "").toLowerCase();

  const isNodeActive = React.useCallback(
    (node: ConstellationNodeItem | typeof CENTER_NODE) => {
      if (!effectiveActiveId) return false;
      return (
        effectiveActiveId === node.id ||
        node.aliases.some((alias) => alias.toLowerCase() === effectiveActiveId)
      );
    },
    [effectiveActiveId]
  );

  const isCoreActive =
    effectiveActiveId === "clara-core" ||
    CENTER_NODE.aliases.some((alias) => alias.toLowerCase() === effectiveActiveId);

  // Calculate dynamic node positions based on clampedProgress
  const dynamicNodes = useMemo(() => {
    return CONSTELLATION_NODES.map((node) => {
      const curX = lerp(node.x0, node.x1, clampedProgress);
      const curY = lerp(node.y0, node.y1, clampedProgress);
      const curLeft = lerp(node.leftPercent0, node.leftPercent1, clampedProgress);
      const curTop = lerp(node.topPercent0, node.topPercent1, clampedProgress);
      const active = isNodeActive(node);

      // SVG Bezier path to center
      // Cubic bezier from (curX, curY) to (480, 280) with smooth tension control
      const midX = (curX + CENTER_NODE.cx) / 2;
      const midY = (curY + CENTER_NODE.cy) / 2;
      const dx = CENTER_NODE.cx - curX;
      const dy = CENTER_NODE.cy - curY;
      const ctrl1X = curX + dx * 0.25 - dy * 0.12;
      const ctrl1Y = curY + dy * 0.25 + dx * 0.12;
      const ctrl2X = CENTER_NODE.cx - dx * 0.25 + dy * 0.08;
      const ctrl2Y = CENTER_NODE.cy - dy * 0.25 - dx * 0.08;

      const pathD = `M ${curX.toFixed(1)} ${curY.toFixed(1)} C ${ctrl1X.toFixed(1)} ${ctrl1Y.toFixed(1)}, ${ctrl2X.toFixed(1)} ${ctrl2Y.toFixed(1)}, ${CENTER_NODE.cx} ${CENTER_NODE.cy}`;

      return {
        ...node,
        curX,
        curY,
        curLeft,
        curTop,
        active,
        pathD,
        midX,
        midY,
      };
    });
  }, [clampedProgress, isNodeActive]);

  const handleNodeSelect = (id: string) => {
    onNodeClick?.(id);
  };

  // Unique SVG element IDs
  const gradCoreAuraId = `constell-core-aura-${uid}`;
  const gradLineAzureId = `constell-line-azure-${uid}`;
  const filterGlowId = `constell-glow-${uid}`;

  return (
    <div
      data-testid="context-constellation"
      data-artwork="context-constellation"
      data-progress={clampedProgress.toFixed(2)}
      data-active-node={activeNodeId ?? ""}
      data-language={language}
      role="region"
      aria-label={isVI ? "Bản đồ bối cảnh hội tụ CLARA Core" : "CLARA Context Constellation"}
      className={`relative w-full select-none overflow-hidden rounded-3xl border border-[#E3E8EF] bg-gradient-to-b from-[#FFFFFF] via-[#F8FAFD] to-[#F1F5F9] p-4 sm:p-6 lg:p-8 shadow-xl transition-all duration-300 ${className}`}
    >
      {/* Top Header Rail / Constellation Stage Status */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#0B6FD8] text-white shadow-xs">
            <span className="text-sm font-black">✦</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                {isVI ? "Bản Đồ Bối Cảnh Hội Tụ" : "Longitudinal Context Constellation"}
              </span>
              <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/25">
                5 {isVI ? "Dòng Bối Cảnh" : "Context Streams"}
              </span>
            </div>
            <p className="text-[11px] text-[#6D7A8E]">
              {isVI
                ? "Các dòng dữ liệu độc lập hội tụ thành bức tranh sức khỏe hoàn chỉnh"
                : "Independent context streams converging into a unified clinical picture"}
            </p>
          </div>
        </div>

        {/* Convergence Progress Indicator */}
        <div className="flex items-center gap-2.5 rounded-2xl bg-white px-3.5 py-1.5 border border-[#E3E8EF] shadow-xs">
          <span className="text-[11px] font-bold text-[#6D7A8E]">
            {isVI ? "Độ hội tụ" : "Convergence"}:
          </span>
          <div className="h-2 w-20 sm:w-28 rounded-full bg-[#F1F5F9] overflow-hidden border border-[#E3E8EF]/60">
            <div
              className="h-full bg-gradient-to-r from-[#0B6FD8] to-[#14A88D] transition-all duration-300"
              style={{ width: `${Math.round(clampedProgress * 100)}%` }}
            />
          </div>
          <span className="text-[11px] font-black text-[#0B6FD8] tabular-nums">
            {Math.round(clampedProgress * 100)}%
          </span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 1. DESKTOP SPATIAL CANVAS (md:block hidden)                                */}
      {/* ========================================================================= */}
      <div className="relative hidden md:block w-full h-[540px] lg:h-[580px] overflow-hidden rounded-2xl bg-[#F8FAFD]/60 border border-[#E3E8EF]/60">
        {/* Ambient background glows */}
        <div
          className="absolute inset-0 pointer-events-none opacity-40"
          style={{
            background:
              "radial-gradient(circle 420px at 50% 50%, rgba(11, 111, 216, 0.08), rgba(20, 168, 141, 0.04), transparent 75%)",
          }}
        />

        {/* SVG Connector & Orbit Canvas */}
        <svg
          aria-hidden="true"
          viewBox="0 0 960 560"
          className="absolute inset-0 h-full w-full pointer-events-none"
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Filter Glow */}
            <filter id={filterGlowId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Core Radial Aura Gradient */}
            <radialGradient id={gradCoreAuraId} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.25" />
              <stop offset="60%" stopColor="#14A88D" stopOpacity="0.1" />
              <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0" />
            </radialGradient>

            {/* General Azure Line Gradient */}
            <linearGradient id={gradLineAzureId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#0B6FD8" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#14A88D" stopOpacity="0.9" />
            </linearGradient>

            {/* Per-Node Custom Gradients */}
            {dynamicNodes.map((node) => {
              const gradId = `constell-node-grad-${node.id}-${uid}`;
              return (
                <linearGradient
                  key={gradId}
                  id={gradId}
                  x1={node.curX > CENTER_NODE.cx ? "100%" : "0%"}
                  y1={node.curY > CENTER_NODE.cy ? "100%" : "0%"}
                  x2={node.curX > CENTER_NODE.cx ? "0%" : "100%"}
                  y2={node.curY > CENTER_NODE.cy ? "0%" : "100%"}
                >
                  <stop offset="0%" stopColor={node.accentColor} stopOpacity="0.85" />
                  <stop offset="100%" stopColor="#0B6FD8" stopOpacity="0.95" />
                </linearGradient>
              );
            })}
          </defs>

          {/* Concentric Orbital Guidance Rings */}
          <circle
            cx={CENTER_NODE.cx}
            cy={CENTER_NODE.cy}
            r={lerp(280, 210, clampedProgress)}
            fill="none"
            stroke="#E3E8EF"
            strokeWidth="1"
            strokeDasharray="4 6"
            className="opacity-70 motion-safe:animate-[spin_90s_linear_infinite] motion-reduce:animate-none"
            style={{ transformOrigin: "480px 280px" }}
          />
          <circle
            cx={CENTER_NODE.cx}
            cy={CENTER_NODE.cy}
            r={lerp(180, 130, clampedProgress)}
            fill="none"
            stroke="#CBD5E1"
            strokeWidth="1.25"
            strokeDasharray="6 8"
            className="opacity-60 motion-safe:animate-[spin_60s_linear_infinite_reverse] motion-reduce:animate-none"
            style={{ transformOrigin: "480px 280px" }}
          />

          {/* Central Convergence Ambient Disc */}
          <circle
            cx={CENTER_NODE.cx}
            cy={CENTER_NODE.cy}
            r={lerp(90, 130, clampedProgress)}
            fill={`url(#${gradCoreAuraId})`}
            className="transition-all duration-500"
          />

          {/* Connector Splines & Particle Pulses from each Node */}
          {dynamicNodes.map((node) => {
            const isHighlighted = node.active || isCoreActive;
            const gradId = `constell-node-grad-${node.id}-${uid}`;
            const strokeWidth = isHighlighted ? 2.5 : lerp(1.2, 2.0, clampedProgress);

            return (
              <g key={`spline-group-${node.id}`} className="transition-all duration-300">
                {/* Background Shadow / Glow Spline */}
                {isHighlighted && (
                  <path
                    d={node.pathD}
                    fill="none"
                    stroke={node.accentColor}
                    strokeWidth="6"
                    strokeOpacity="0.3"
                    filter={`url(#${filterGlowId})`}
                  />
                )}

                {/* Primary Connector Path */}
                <path
                  id={`path-${node.id}-${uid}`}
                  d={node.pathD}
                  fill="none"
                  stroke={`url(#${gradId})`}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isHighlighted ? "none" : "6 6"}
                  strokeOpacity={isHighlighted ? 0.95 : lerp(0.45, 0.85, clampedProgress)}
                  className={isHighlighted ? "" : "clara-constellation-line"}
                />

                {/* Animated Particle Stream toward Center */}
                <circle r={isHighlighted ? "4.5" : "3.5"} fill={node.accentColor}>
                  <animateMotion
                    dur={isHighlighted ? "2.2s" : "3.8s"}
                    repeatCount="indefinite"
                    path={node.pathD}
                  />
                </circle>

                {/* Inward Convergence Arrow / Flow Indicator */}
                <circle
                  cx={node.midX}
                  cy={node.midY}
                  r="2.5"
                  fill="#FFFFFF"
                  stroke={node.accentColor}
                  strokeWidth="1.5"
                />

                {/* Node Anchor Point Dot on Canvas */}
                <circle
                  cx={node.curX}
                  cy={node.curY}
                  r={isHighlighted ? "6" : "4.5"}
                  fill="#FFFFFF"
                  stroke={node.accentColor}
                  strokeWidth={isHighlighted ? "3" : "2"}
                  className="transition-all duration-200"
                />
              </g>
            );
          })}

          {/* Center Hub Outer Ring Anchor */}
          <circle
            cx={CENTER_NODE.cx}
            cy={CENTER_NODE.cy}
            r="44"
            fill="#FFFFFF"
            stroke="#0B6FD8"
            strokeWidth="2"
            className="shadow-sm"
          />
        </svg>

        {/* 5 Outer HTML Context Node Cards (Desktop Spatial Overlays) */}
        {dynamicNodes.map((node) => {
          const isHighlighted = node.active || isCoreActive;

          return (
            <div
              key={`desktop-card-${node.id}`}
              style={{
                left: `${node.curLeft}%`,
                top: `${node.curTop}%`,
                transform: "translate(-50%, -50%)",
              }}
              className={`absolute z-20 transition-all duration-300 ease-out ${node.cardWidthClass}`}
            >
              <button
                type="button"
                role="button"
                aria-label={`${isVI ? node.titleVi : node.titleEn}: ${isVI ? node.subtitleVi : node.subtitleEn}`}
                aria-pressed={isHighlighted}
                onClick={() => handleNodeSelect(node.id)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                className={`w-full group text-left rounded-2xl p-3.5 sm:p-4 transition-all duration-200 backdrop-blur-md border clara-focus-ring ${
                  isHighlighted
                    ? "bg-white shadow-xl -translate-y-1 scale-102 ring-2 ring-offset-1"
                    : "bg-white/95 hover:bg-white shadow-md hover:shadow-lg hover:-translate-y-0.5"
                }`}
                style={{
                  borderColor: isHighlighted ? node.accentColor : node.borderTint,
                  boxShadow: isHighlighted
                    ? `0 12px 28px -6px ${node.subtleGlow}, 0 0 1px ${node.accentColor}`
                    : undefined,
                }}
              >
                {/* Card Header: Category & Badge */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="flex h-6 w-6 items-center justify-center rounded-lg shadow-xs"
                      style={{ backgroundColor: node.bgTint }}
                    >
                      {renderNodeIcon(node.id, node.accentColor)}
                    </span>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                      {isVI ? node.categoryVi : node.categoryEn}
                    </span>
                  </div>
                  <span
                    className="rounded-md px-2 py-0.5 text-[10px] font-bold border transition-colors"
                    style={{
                      color: node.accentColor,
                      backgroundColor: node.bgTint,
                      borderColor: node.borderTint,
                    }}
                  >
                    {isVI ? node.badgeVi : node.badgeEn}
                  </span>
                </div>

                {/* Main Title & Subtitle */}
                <h4 className="text-xs sm:text-sm font-bold text-[#162033] group-hover:text-[#0B6FD8] transition-colors leading-tight">
                  {isVI ? node.titleVi : node.titleEn}
                </h4>
                <p className="text-[11px] font-medium text-[#6D7A8E] mt-0.5 line-clamp-1">
                  {isVI ? node.subtitleVi : node.subtitleEn}
                </p>

                {/* Clinical Context Detail Pill */}
                <div className="mt-2 pt-2 border-t border-[#E3E8EF]/80 flex items-center justify-between gap-2">
                  <span className="text-[10px] text-[#48566A] font-medium truncate">
                    {isVI ? node.previewVi : node.previewEn}
                  </span>
                  <span
                    className="text-[11px] font-bold shrink-0 transition-transform group-hover:translate-x-0.5"
                    style={{ color: node.accentColor }}
                  >
                    ➔
                  </span>
                </div>
              </button>
            </div>
          );
        })}

        {/* Central Convergence Hub: CLARA CORE (Desktop Focal Point) */}
        <div
          style={{
            left: "50%",
            top: "50%",
            transform: "translate(-50%, -50%)",
          }}
          className="absolute z-30 w-72 sm:w-80 text-center"
        >
          <button
            type="button"
            role="button"
            aria-label={`${CENTER_NODE.titleVi} - ${isVI ? CENTER_NODE.subtitleVi : CENTER_NODE.subtitleEn}`}
            aria-pressed={isCoreActive}
            onClick={() => handleNodeSelect(CENTER_NODE.id)}
            onMouseEnter={() => setHoveredNodeId(CENTER_NODE.id)}
            onMouseLeave={() => setHoveredNodeId(null)}
            className={`w-full group rounded-3xl p-5 sm:p-6 transition-all duration-300 backdrop-blur-xl border-2 clara-focus-ring ${
              isCoreActive
                ? "bg-white shadow-2xl scale-105 border-[#0B6FD8] ring-4 ring-[#0B6FD8]/20"
                : "bg-white/95 hover:bg-white shadow-xl hover:shadow-2xl hover:scale-102 border-[#0B6FD8]"
            }`}
            style={{
              boxShadow: isCoreActive
                ? "0 20px 48px -12px rgba(11, 111, 216, 0.35), 0 0 1px #0B6FD8"
                : "0 16px 40px -12px rgba(22, 32, 51, 0.12)",
            }}
          >
            {/* Center Brand Orb Anchor */}
            <div className="flex justify-center mb-3">
              <ClaraOrb size="md" tone="azure" pulse={true} />
            </div>

            {/* Center Node Title & Subtitle */}
            <div className="inline-flex items-center gap-1.5 rounded-full bg-[#EFF7FF] px-3 py-1 border border-[#0B6FD8]/25 mb-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#0B6FD8] animate-pulse" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                {isVI ? CENTER_NODE.badgeVi : CENTER_NODE.badgeEn}
              </span>
            </div>

            <h3 className="text-base sm:text-lg font-black text-[#162033] tracking-tight">
              {CENTER_NODE.titleVi}
            </h3>
            <p className="text-xs font-semibold text-[#0B6FD8] mt-0.5">
              {isVI ? CENTER_NODE.subtitleVi : CENTER_NODE.subtitleEn}
            </p>

            <p className="text-[11px] text-[#6D7A8E] mt-2 leading-relaxed px-2 line-clamp-2">
              {isVI ? CENTER_NODE.descriptionVi : CENTER_NODE.descriptionEn}
            </p>

            {/* Resolving Synthesis Statement Banner */}
            <div className="mt-3.5 pt-3 border-t border-[#E3E8EF] flex items-center justify-center gap-2">
              <span className="text-[11px] font-bold text-[#0B6FD8] group-hover:text-[#0855A8] transition-colors">
                ➔ {isVI ? CENTER_NODE.statementVi : CENTER_NODE.statementEn}
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* 2. MOBILE RESPONSIVE STACKED & CURVED CONSTELLATION (< md:block)          */}
      {/* ========================================================================= */}
      <div className="block md:hidden space-y-4">
        {/* Mobile Central Focal Beacon */}
        <button
          type="button"
          role="button"
          aria-label={`${CENTER_NODE.titleVi} - ${isVI ? CENTER_NODE.subtitleVi : CENTER_NODE.subtitleEn}`}
          aria-pressed={isCoreActive}
          onClick={() => handleNodeSelect(CENTER_NODE.id)}
          className={`w-full text-left rounded-2xl p-4 sm:p-5 border-2 transition-all duration-200 clara-focus-ring ${
            isCoreActive
              ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-lg"
              : "bg-white border-[#0B6FD8] shadow-md hover:shadow-lg"
          }`}
        >
          <div className="flex items-center gap-3.5">
            <div className="shrink-0">
              <ClaraOrb size="sm" tone="azure" pulse={true} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-black text-[#162033]">{CENTER_NODE.titleVi}</h3>
                <span className="rounded-full bg-[#EFF7FF] px-2 py-0.5 text-[10px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/25">
                  {isVI ? CENTER_NODE.badgeVi : CENTER_NODE.badgeEn}
                </span>
              </div>
              <p className="text-xs font-bold text-[#0B6FD8] mt-0.5">
                {isVI ? CENTER_NODE.subtitleVi : CENTER_NODE.subtitleEn}
              </p>
              <p className="text-[11px] text-[#6D7A8E] mt-1 leading-relaxed">
                {isVI ? CENTER_NODE.descriptionVi : CENTER_NODE.descriptionEn}
              </p>
            </div>
          </div>
          <div className="mt-3 pt-2.5 border-t border-[#E3E8EF] flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#0B6FD8]">
              {isVI ? CENTER_NODE.statementVi : CENTER_NODE.statementEn}
            </span>
            <span className="text-xs font-bold text-[#0B6FD8]">➔</span>
          </div>
        </button>

        {/* Mobile Curved Ribbon Stream of 5 Context Nodes */}
        <div className="relative pl-6 sm:pl-8 space-y-3">
          {/* Left Vertical Constellation Curved Spine */}
          <div
            aria-hidden="true"
            className="absolute left-2.5 sm:left-3.5 top-3 bottom-3 w-0.5 bg-gradient-to-b from-[#0B6FD8] via-[#14A88D] to-[#8B7CF6] rounded-full opacity-60"
          />

          {CONSTELLATION_NODES.map((node, index) => {
            const isHighlighted = isNodeActive(node) || isCoreActive;

            return (
              <div key={`mobile-node-${node.id}`} className="relative">
                {/* Branch Node Pin on Spine */}
                <div
                  aria-hidden="true"
                  className="absolute -left-6 sm:-left-8 top-4 flex items-center justify-center"
                >
                  <span
                    className={`h-3 w-3 rounded-full border-2 bg-white transition-all duration-200 ${
                      isHighlighted ? "scale-125 ring-2 ring-offset-1" : ""
                    }`}
                    style={{
                      borderColor: node.accentColor,
                      backgroundColor: isHighlighted ? node.accentColor : "#FFFFFF",
                    }}
                  />
                </div>

                {/* Mobile Card */}
                <button
                  type="button"
                  role="button"
                  aria-label={`${isVI ? node.titleVi : node.titleEn}`}
                  aria-pressed={isHighlighted}
                  onClick={() => handleNodeSelect(node.id)}
                  className={`w-full text-left rounded-2xl p-3.5 transition-all duration-200 border clara-focus-ring ${
                    isHighlighted
                      ? "bg-white shadow-md border-current ring-1 ring-offset-1"
                      : "bg-white/90 shadow-xs border-[#E3E8EF] hover:border-[#CBD5E1]"
                  }`}
                  style={{
                    borderColor: isHighlighted ? node.accentColor : undefined,
                  }}
                >
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2">
                      <span
                        className="flex h-5 w-5 items-center justify-center rounded-md text-[10px]"
                        style={{ backgroundColor: node.bgTint }}
                      >
                        {renderNodeIcon(node.id, node.accentColor)}
                      </span>
                      <span className="text-xs font-bold text-[#162033]">
                        {isVI ? node.titleVi : node.titleEn}
                      </span>
                    </div>
                    <span
                      className="rounded px-1.5 py-0.5 text-[9px] font-bold border"
                      style={{
                        color: node.accentColor,
                        backgroundColor: node.bgTint,
                        borderColor: node.borderTint,
                      }}
                    >
                      {isVI ? node.badgeVi : node.badgeEn}
                    </span>
                  </div>

                  <p className="text-[11px] font-medium text-[#6D7A8E]">
                    {isVI ? node.subtitleVi : node.subtitleEn}
                  </p>

                  <div className="mt-2 pt-2 border-t border-[#E3E8EF]/60 flex items-center justify-between text-[10px] text-[#48566A]">
                    <span className="truncate">{isVI ? node.previewVi : node.previewEn}</span>
                    <span className="font-bold text-[#0B6FD8] shrink-0 ml-2">
                      #{index + 1} ➔
                    </span>
                  </div>
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Footer Meta: Safety & Convergence Note */}
      <div className="mt-4 pt-3.5 border-t border-[#E3E8EF]/80 flex flex-wrap items-center justify-between gap-3 text-xs text-[#6D7A8E]">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-[#14A88D]" />
          <span>
            {isVI
              ? "Dữ liệu được xử lý tại vùng biên an toàn theo nguyên tắc Zero-CoT"
              : "Context verified within privacy-preserving Zero-CoT enclave"}
          </span>
        </div>
        <div className="flex items-center gap-1 font-semibold text-[#0B6FD8]">
          <span>{isVI ? "FIDES Safety Engine v7.4" : "FIDES Safety Engine v7.4"}</span>
          <span>✦</span>
        </div>
      </div>
    </div>
  );
}

export default ContextConstellation;
