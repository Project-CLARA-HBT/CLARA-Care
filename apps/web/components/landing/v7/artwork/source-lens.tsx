"use client";

import React, { useId, useMemo } from "react";

export type AuthorityTier = "National" | "International" | "Regulatory" | "Peer-Reviewed";

export interface SourceLensProps {
  /**
   * Authority Tier to focus the lens upon:
   * - "National": National Pharmacopoeia (DAV - Dược thư Quốc gia Việt Nam)
   * - "International": DrugBank 5.1 & WHO Guidelines
   * - "Regulatory": FDA Drug Safety Communications
   * - "Peer-Reviewed": PubMed / MEDLINE Clinical Queries
   */
  tier?: AuthorityTier;
  /**
   * Whether the optical aperture lens is actively focusing and illuminated (defaults to true)
   */
  active?: boolean;
  /**
   * Additional CSS class names
   */
  className?: string;
  /**
   * Optional callback when an authority tier or source is selected interactively
   */
  onSelectTier?: (tier: AuthorityTier) => void;
  /**
   * Optional custom accessible label
   */
  ariaLabel?: string;
}

interface ClinicalAuthoritySource {
  id: string;
  shortName: string;
  fullName: string;
  authority: string;
  tier: AuthorityTier;
  tierRank: string;
  scopeVi: string;
  scopeEn: string;
  badgeAccent: string;
  badgeBg: string;
  badgeBorder: string;
  angleDeg: number;
  cx: number;
  cy: number;
  citationCount: string;
  verificationLevel: string;
}

const CLINICAL_SOURCES: ClinicalAuthoritySource[] = [
  {
    id: "dav",
    shortName: "DAV",
    fullName: "Dược thư Quốc gia Việt Nam",
    authority: "Bộ Y tế Việt Nam / Cục Quản lý Dược",
    tier: "National",
    tierRank: "Tier I",
    scopeVi: "Quy chuẩn liều lượng, chỉ định và chống chỉ định quốc gia",
    scopeEn: "National official standard for dosage & indications",
    badgeAccent: "#0B6FD8",
    badgeBg: "rgba(11, 111, 216, 0.08)",
    badgeBorder: "rgba(11, 111, 216, 0.25)",
    angleDeg: -90,
    cx: 360,
    cy: 70,
    citationCount: "100% Đơn vị Y tế",
    verificationLevel: "Pháp lý & Bắt buộc",
  },
  {
    id: "drugbank",
    shortName: "DrugBank",
    fullName: "DrugBank 5.1 Comprehensive",
    authority: "OMx Technologies / University of Alberta",
    tier: "International",
    tierRank: "Tier II",
    scopeVi: "Ma trận tương tác DDI, dược động học và chuyển hóa CYP450",
    scopeEn: "Molecular DDI matrices, PK pathways & CYP450 metabolism",
    badgeAccent: "#8B7CF6",
    badgeBg: "rgba(139, 124, 246, 0.08)",
    badgeBorder: "rgba(139, 124, 246, 0.25)",
    angleDeg: -18,
    cx: 580,
    cy: 165,
    citationCount: "1.4M+ Tương tác",
    verificationLevel: "Dược lý Phân tử",
  },
  {
    id: "who",
    shortName: "WHO",
    fullName: "WHO Guidelines for Essential Medicines",
    authority: "Tổ chức Y tế Thế giới (WHO)",
    tier: "International",
    tierRank: "Tier II",
    scopeVi: "Phác đồ điều trị chuẩn toàn cầu cho bệnh lý mạn tính",
    scopeEn: "Global guideline protocols for non-communicable diseases",
    badgeAccent: "#14A88D",
    badgeBg: "rgba(20, 168, 141, 0.08)",
    badgeBorder: "rgba(20, 168, 141, 0.25)",
    angleDeg: 54,
    cx: 500,
    cy: 350,
    citationCount: "194 Quốc gia",
    verificationLevel: "Đồng thuận Toàn cầu",
  },
  {
    id: "fda",
    shortName: "FDA",
    fullName: "FDA Drug Safety Communications",
    authority: "US Food and Drug Administration",
    tier: "Regulatory",
    tierRank: "Tier III",
    scopeVi: "Cảnh báo an toàn khẩn cấp, độc tính mới và thay đổi nhãn",
    scopeEn: "Real-time safety alerts, toxicities & black-box revisions",
    badgeAccent: "#F59E0B",
    badgeBg: "rgba(245, 158, 11, 0.08)",
    badgeBorder: "rgba(245, 158, 11, 0.25)",
    angleDeg: 126,
    cx: 220,
    cy: 350,
    citationCount: "Cập nhật liên tục",
    verificationLevel: "Giám sát An toàn",
  },
  {
    id: "pubmed",
    shortName: "PubMed",
    fullName: "PubMed / MEDLINE Clinical Queries",
    authority: "National Library of Medicine (NLM)",
    tier: "Peer-Reviewed",
    tierRank: "Tier IV",
    scopeVi: "Thử nghiệm lâm sàng ngẫu nhiên RCT và phân tích gộp",
    scopeEn: "Randomized controlled trials (RCT) & meta-analyses",
    badgeAccent: "#0284C7",
    badgeBg: "rgba(2, 132, 199, 0.08)",
    badgeBorder: "rgba(2, 132, 199, 0.25)",
    angleDeg: 198,
    cx: 140,
    cy: 165,
    citationCount: "36M+ Y văn",
    verificationLevel: "Bằng chứng Đối chứng",
  },
];

const TIER_META: Record<
  AuthorityTier,
  {
    badgeLabel: string;
    descriptionVi: string;
    descriptionEn: string;
    primaryColor: string;
    accentColor: string;
    secondaryColor: string;
    focalIndex: string;
    reticleRadius: number;
    apertureBladesAngle: number;
  }
> = {
  National: {
    badgeLabel: "Tier I: Quy chuẩn Dược thư Quốc gia",
    descriptionVi: "Quy chuẩn bắt buộc cho mọi chỉ định và liều dùng tại Việt Nam",
    descriptionEn: "Mandatory regulatory standard for clinical prescriptions in Vietnam",
    primaryColor: "#0B6FD8",
    accentColor: "#1A86F5",
    secondaryColor: "#EFF7FF",
    focalIndex: "1.000 α (Độ chính xác Tuyệt đối)",
    reticleRadius: 72,
    apertureBladesAngle: 0,
  },
  International: {
    badgeLabel: "Tier II: Dữ liệu Dược lý & Hướng dẫn Quốc tế",
    descriptionVi: "Ma trận tương tác phân tử DrugBank và phác đồ đồng thuận WHO",
    descriptionEn: "Molecular PK/PD matrix from DrugBank & global consensus from WHO",
    primaryColor: "#8B7CF6",
    accentColor: "#A78BFA",
    secondaryColor: "#F5F3FF",
    focalIndex: "0.985 β (Đa trung tâm Toàn cầu)",
    reticleRadius: 84,
    apertureBladesAngle: 24,
  },
  Regulatory: {
    badgeLabel: "Tier III: Cơ quan Quản lý Dược Quốc tế",
    descriptionVi: "Giám sát cảnh báo an toàn độc tính và cập nhật nhãn khẩn cấp FDA",
    descriptionEn: "Sentinel adverse drug event alerts & black-box warning revisions",
    primaryColor: "#D97706",
    accentColor: "#F59E0B",
    secondaryColor: "#FEF3C7",
    focalIndex: "0.992 γ (Giám sát Thời gian thực)",
    reticleRadius: 92,
    apertureBladesAngle: 48,
  },
  "Peer-Reviewed": {
    badgeLabel: "Tier IV: Y văn Lâm sàng Bình duyệt",
    descriptionVi: "Bằng chứng RCT thử nghiệm mù đôi và phân tích gộp MEDLINE / PubMed",
    descriptionEn: "Double-blind RCTs, systematic reviews & peer-reviewed meta-analyses",
    primaryColor: "#0284C7",
    accentColor: "#38BDF8",
    secondaryColor: "#E0F2FE",
    focalIndex: "0.978 δ (Bằng chứng Đối chứng)",
    reticleRadius: 104,
    apertureBladesAngle: 72,
  },
};

/**
 * SourceLens Artwork Component
 *
 * Renders the high-precision Evidence Source Lens artwork highlighting verified clinical
 * authority across 5 foundational tiers: National Pharmacopoeia (DAV), DrugBank 5.1,
 * WHO Guidelines, FDA Safety Alerts, and PubMed RCT Evidence.
 */
export function SourceLens({
  tier = "National",
  active = true,
  className = "",
  onSelectTier,
  ariaLabel,
}: SourceLensProps) {
  const rawId = useId();
  const uid = rawId.replace(/[^a-zA-Z0-9-_]/g, "");

  const activeMeta = useMemo(() => TIER_META[tier] ?? TIER_META.National, [tier]);
  const activeSources = useMemo(
    () => CLINICAL_SOURCES.filter((s) => s.tier === tier),
    [tier]
  );
  const primaryActiveSource = activeSources[0] ?? CLINICAL_SOURCES[0];

  const lensCenterX = 360;
  const lensCenterY = 240;

  // Aperture blade geometries (6 interlocking logarithmic spiral blades)
  const apertureBlades = useMemo(() => {
    const blades = [];
    const bladeCount = 6;
    const innerR = active ? 46 : 58;
    const outerR = 120;
    const baseAngle = activeMeta.apertureBladesAngle;

    for (let i = 0; i < bladeCount; i++) {
      const angle = (i * (360 / bladeCount) + baseAngle) * (Math.PI / 180);
      const nextAngle = ((i + 1) * (360 / bladeCount) + baseAngle) * (Math.PI / 180);

      const x1 = lensCenterX + Math.cos(angle) * innerR;
      const y1 = lensCenterY + Math.sin(angle) * innerR;
      const x2 = lensCenterX + Math.cos(nextAngle) * outerR;
      const y2 = lensCenterY + Math.sin(nextAngle) * outerR;
      const x3 = lensCenterX + Math.cos(angle + 0.4) * outerR;
      const y3 = lensCenterY + Math.sin(angle + 0.4) * outerR;

      blades.push({
        d: `M ${x1} ${y1} Q ${lensCenterX + Math.cos(angle + 0.2) * (innerR + 35)} ${
          lensCenterY + Math.sin(angle + 0.2) * (innerR + 35)
        } ${x2} ${y2} L ${x3} ${y3} Z`,
        index: i,
      });
    }
    return blades;
  }, [active, activeMeta.apertureBladesAngle]);

  // Calibration tick marks along the 360-degree compass perimeter
  const calibrationTicks = useMemo(() => {
    const ticks = [];
    const radius = 142;
    for (let deg = 0; deg < 360; deg += 10) {
      const isMajor = deg % 30 === 0;
      const isCard = deg % 90 === 0;
      const length = isCard ? 9 : isMajor ? 6 : 3;
      const rad = (deg * Math.PI) / 180;
      const x1 = lensCenterX + Math.cos(rad) * radius;
      const y1 = lensCenterY + Math.sin(rad) * radius;
      const x2 = lensCenterX + Math.cos(rad) * (radius - length);
      const y2 = lensCenterY + Math.sin(rad) * (radius - length);

      ticks.push({
        x1,
        y1,
        x2,
        y2,
        isMajor,
        isCard,
        deg,
      });
    }
    return ticks;
  }, []);

  const accessibleText =
    ariaLabel ||
    `Evidence Source Lens: ${tier} Authority focused (${primaryActiveSource.fullName}). Highlighted sources: Dược thư Quốc gia Việt Nam, DrugBank, WHO, FDA, PubMed.`;

  return (
    <div
      className={`relative w-full overflow-hidden rounded-3xl border border-[#E3E8EF] bg-gradient-to-b from-[#FFFFFF] via-[#F8FAFD] to-[#F1F5F9] p-4 sm:p-6 lg:p-8 shadow-xl ${className}`}
      data-testid="source-lens"
      data-active-tier={tier}
      data-active={active}
      role="region"
      aria-label={accessibleText}
    >
      {/* Top Header Rail: Lens Status & Tier Quick Selector */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EF]/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-xl font-bold text-white shadow-xs transition-colors duration-300"
            style={{ backgroundColor: activeMeta.primaryColor }}
          >
            <svg
              className="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="22" y1="12" x2="18" y2="12" />
              <line x1="6" y1="12" x2="2" y2="12" />
              <line x1="12" y1="6" x2="12" y2="2" />
              <line x1="12" y1="22" x2="12" y2="18" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                Evidence Source Lens
              </span>
              <span
                className="rounded-full px-2 py-0.5 text-[10px] font-bold transition-colors duration-300"
                style={{
                  backgroundColor: activeMeta.secondaryColor,
                  color: activeMeta.primaryColor,
                  borderColor: activeMeta.accentColor,
                  borderWidth: "1px",
                }}
              >
                {tier} Mode
              </span>
            </div>
            <p className="text-[11px] text-[#6D7A8E]">
              Hệ thống ống kính phân giải và đối chiếu 5 tầng cơ quan thẩm quyền lâm sàng
            </p>
          </div>
        </div>

        {/* Tier Interactive Filter Tabs */}
        <div
          className="flex flex-wrap items-center gap-1 rounded-xl bg-[#EFF4FA] p-1 border border-[#E3E8EF]"
          role="tablist"
          aria-label="Clinical Authority Tiers"
        >
          {(["National", "International", "Regulatory", "Peer-Reviewed"] as const).map((t) => {
            const isSelected = tier === t;
            const meta = TIER_META[t];
            return (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={isSelected}
                onClick={() => onSelectTier?.(t)}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all ${
                  isSelected
                    ? "bg-white text-[#162033] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
              >
                <span
                  className="h-2 w-2 rounded-full transition-all duration-300"
                  style={{
                    backgroundColor: isSelected ? meta.primaryColor : "#CBD5E1",
                    transform: isSelected ? "scale(1.2)" : "scale(1)",
                  }}
                />
                <span>{t}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main SVG Lens Artwork Viewport */}
      <div className="relative w-full aspect-[16/10] sm:aspect-[16/9] max-h-[460px] flex items-center justify-center">
        <svg
          viewBox="0 0 720 440"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full overflow-visible select-none"
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          <defs>
            {/* Ambient Refraction Glow */}
            <radialGradient
              id={`lens-glow-${uid}`}
              cx="50%"
              cy="50%"
              r="50%"
              fx="50%"
              fy="50%"
            >
              <stop offset="0%" stopColor={activeMeta.accentColor} stopOpacity={active ? "0.22" : "0.08"} />
              <stop offset="45%" stopColor={activeMeta.primaryColor} stopOpacity={active ? "0.10" : "0.03"} />
              <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0" />
            </radialGradient>

            {/* Lens Core Glass Radial Gradient */}
            <radialGradient
              id={`lens-glass-${uid}`}
              cx="38%"
              cy="34%"
              r="60%"
              fx="38%"
              fy="34%"
            >
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
              <stop offset="25%" stopColor={activeMeta.secondaryColor} stopOpacity="0.8" />
              <stop offset="65%" stopColor="#E2E8F0" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#CBD5E1" stopOpacity="0.75" />
            </radialGradient>

            {/* Aperture Ring Linear Stroke */}
            <linearGradient
              id={`aperture-ring-grad-${uid}`}
              x1="0%"
              y1="0%"
              x2="100%"
              y2="100%"
            >
              <stop offset="0%" stopColor={activeMeta.accentColor} stopOpacity="0.8" />
              <stop offset="50%" stopColor="#94A3B8" stopOpacity="0.4" />
              <stop offset="100%" stopColor={activeMeta.primaryColor} stopOpacity="0.85" />
            </linearGradient>

            {/* Laser Line Gradient from Sources to Center */}
            <linearGradient
              id={`laser-beam-${uid}`}
              x1="0%"
              y1="0%"
              x2="100%"
              y2="100%"
            >
              <stop offset="0%" stopColor={activeMeta.primaryColor} stopOpacity="0.7" />
              <stop offset="100%" stopColor={activeMeta.accentColor} stopOpacity="0.15" />
            </linearGradient>

            {/* Glow Filter */}
            <filter id={`filter-glow-${uid}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Soft Shadow for Nodes */}
            <filter id={`node-shadow-${uid}`} x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#0F172A" floodOpacity="0.1" />
            </filter>
          </defs>

          {/* 1. Background Ambient Radial Glow */}
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r="190"
            fill={`url(#lens-glow-${uid})`}
            className="transition-all duration-700"
          />

          {/* 2. Concentric Precision Optics Rings */}
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r="170"
            stroke="#E2E8F0"
            strokeWidth="1"
            strokeDasharray="4 4"
            className="opacity-70"
          />
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r="152"
            stroke="#CBD5E1"
            strokeWidth="1.5"
            className="opacity-80"
          />
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r="142"
            stroke={`url(#aperture-ring-grad-${uid})`}
            strokeWidth="2"
          />
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r="128"
            stroke="#E2E8F0"
            strokeWidth="1"
          />

          {/* 3. Perimeter Degree Calibration Ticks */}
          <g className="opacity-75">
            {calibrationTicks.map((tick) => (
              <line
                key={`tick-${tick.deg}`}
                x1={tick.x1}
                y1={tick.y1}
                x2={tick.x2}
                y2={tick.y2}
                stroke={
                  tick.isCard
                    ? activeMeta.primaryColor
                    : tick.isMajor
                    ? "#64748B"
                    : "#94A3B8"
                }
                strokeWidth={tick.isCard ? 2 : tick.isMajor ? 1.5 : 1}
                strokeLinecap="round"
              />
            ))}
          </g>

          {/* 4. Radial Ray Connectors from Sources to Lens Center */}
          <g className="transition-all duration-500">
            {CLINICAL_SOURCES.map((source) => {
              const isSourceInTier = source.tier === tier;
              return (
                <g key={`ray-${source.id}`}>
                  {/* Outer connector line */}
                  <line
                    x1={source.cx}
                    y1={source.cy}
                    x2={lensCenterX}
                    y2={lensCenterY}
                    stroke={isSourceInTier ? source.badgeAccent : "#E2E8F0"}
                    strokeWidth={isSourceInTier ? 2 : 1}
                    strokeDasharray={isSourceInTier ? "none" : "3 3"}
                    strokeOpacity={isSourceInTier ? 0.8 : 0.35}
                    className="transition-all duration-500"
                  />
                  {/* In-flight laser pulse dot for active tier */}
                  {isSourceInTier && active && (
                    <circle
                      cx={(source.cx + lensCenterX) / 2}
                      cy={(source.cy + lensCenterY) / 2}
                      r="3.5"
                      fill={source.badgeAccent}
                      filter={`url(#filter-glow-${uid})`}
                    />
                  )}
                </g>
              );
            })}
          </g>

          {/* 5. Aperture Iris Diaphragm (Optical Blades) */}
          <g className="transition-transform duration-700 ease-out">
            {apertureBlades.map((blade) => (
              <path
                key={`blade-${blade.index}`}
                d={blade.d}
                fill="#F8FAFC"
                fillOpacity="0.88"
                stroke="#CBD5E1"
                strokeWidth="1.2"
                className="transition-all duration-500"
              />
            ))}
          </g>

          {/* 6. Central Optical Lens Core Surface */}
          <circle
            cx={lensCenterX}
            cy={lensCenterY}
            r={activeMeta.reticleRadius}
            fill={`url(#lens-glass-${uid})`}
            stroke={activeMeta.primaryColor}
            strokeWidth="2.5"
            className="transition-all duration-500"
            filter={`url(#node-shadow-${uid})`}
          />

          {/* 7. Inner Reticle & Crosshair Optics */}
          <g className="transition-all duration-500">
            {/* Horizontal & Vertical Crosshairs */}
            <line
              x1={lensCenterX - 48}
              y1={lensCenterY}
              x2={lensCenterX - 14}
              y2={lensCenterY}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <line
              x1={lensCenterX + 14}
              y1={lensCenterY}
              x2={lensCenterX + 48}
              y2={lensCenterY}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <line
              x1={lensCenterX}
              y1={lensCenterY - 48}
              x2={lensCenterX}
              y2={lensCenterY - 14}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <line
              x1={lensCenterX}
              y1={lensCenterY + 14}
              x2={lensCenterX}
              y2={lensCenterY + 48}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              strokeLinecap="round"
            />

            {/* Target Alignment Corner Brackets */}
            <path
              d={`M ${lensCenterX - 28} ${lensCenterY - 18} L ${lensCenterX - 28} ${lensCenterY - 28} L ${lensCenterX - 18} ${lensCenterY - 28}`}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d={`M ${lensCenterX + 28} ${lensCenterY - 18} L ${lensCenterX + 28} ${lensCenterY - 28} L ${lensCenterX + 18} ${lensCenterY - 28}`}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d={`M ${lensCenterX - 28} ${lensCenterY + 18} L ${lensCenterX - 28} ${lensCenterY + 28} L ${lensCenterX - 18} ${lensCenterY + 28}`}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />
            <path
              d={`M ${lensCenterX + 28} ${lensCenterY + 18} L ${lensCenterX + 28} ${lensCenterY + 28} L ${lensCenterX + 18} ${lensCenterY + 28}`}
              stroke={activeMeta.primaryColor}
              strokeWidth="1.5"
              fill="none"
              strokeLinecap="round"
            />

            {/* Focal Point Indicator */}
            <circle
              cx={lensCenterX}
              cy={lensCenterY}
              r="6.5"
              fill={activeMeta.primaryColor}
              filter={active ? `url(#filter-glow-${uid})` : undefined}
            />
            <circle
              cx={lensCenterX}
              cy={lensCenterY}
              r="2.5"
              fill="#FFFFFF"
            />

            {/* Optical Refraction Arc */}
            <path
              d={`M ${lensCenterX - 35} ${lensCenterY - 35} A 50 50 0 0 1 ${lensCenterX + 35} ${lensCenterY - 35}`}
              stroke="#FFFFFF"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeOpacity="0.8"
            />
          </g>

          {/* 8. 5 Verified Clinical Authority Source Nodes */}
          {CLINICAL_SOURCES.map((source) => {
            const isSourceInTier = source.tier === tier;
            const isSelected = isSourceInTier && active;

            return (
              <g
                key={`node-${source.id}`}
                className="cursor-pointer transition-all duration-300 group"
                onClick={() => onSelectTier?.(source.tier)}
                filter={`url(#node-shadow-${uid})`}
              >
                {/* Active Outer Pulsing Halo */}
                {isSelected && (
                  <circle
                    cx={source.cx}
                    cy={source.cy}
                    r="32"
                    fill={source.badgeAccent}
                    fillOpacity="0.12"
                    stroke={source.badgeAccent}
                    strokeWidth="1.5"
                    strokeOpacity="0.4"
                    strokeDasharray="4 3"
                  />
                )}

                {/* Node Pill Surface */}
                <rect
                  x={source.cx - 55}
                  y={source.cy - 22}
                  width="110"
                  height="44"
                  rx="14"
                  fill="#FFFFFF"
                  stroke={isSelected ? source.badgeAccent : "#E2E8F0"}
                  strokeWidth={isSelected ? 2.5 : 1.2}
                  className="transition-all duration-300 group-hover:stroke-[#94A3B8]"
                />

                {/* Authority Icon Dot */}
                <circle
                  cx={source.cx - 38}
                  cy={source.cy}
                  r="7"
                  fill={isSelected ? source.badgeAccent : "#94A3B8"}
                  className="transition-colors duration-300"
                />
                <circle
                  cx={source.cx - 38}
                  cy={source.cy}
                  r="3"
                  fill="#FFFFFF"
                />

                {/* Node Text Label */}
                <text
                  x={source.cx - 24}
                  y={source.cy - 3}
                  fontSize="12"
                  fontWeight="bold"
                  fill={isSelected ? "#162033" : "#48566A"}
                  letterSpacing="-0.2px"
                >
                  {source.shortName}
                </text>
                <text
                  x={source.cx - 24}
                  y={source.cy + 12}
                  fontSize="9.5"
                  fontWeight="600"
                  fill={isSelected ? source.badgeAccent : "#94A3B8"}
                >
                  {source.tierRank}
                </text>

                {/* Verified Authority Checkmark Tag */}
                {isSelected && (
                  <g transform={`translate(${source.cx + 38}, ${source.cy - 12})`}>
                    <circle cx="0" cy="0" r="7" fill={source.badgeAccent} />
                    <path
                      d="M -3.2 -0.2 L -1 2.2 L 3.2 -2.2"
                      stroke="#FFFFFF"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </g>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Bottom Qualitative Authority Badge Banner */}
      <div
        className="mt-4 rounded-2xl p-4 sm:p-5 border transition-all duration-500"
        style={{
          backgroundColor: activeMeta.secondaryColor,
          borderColor: activeMeta.accentColor + "40",
        }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold text-white shadow-xs"
                style={{ backgroundColor: activeMeta.primaryColor }}
              >
                <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2L4 5V11.09C4 16.14 7.41 20.85 12 22C16.59 20.85 20 16.14 20 11.09V5L12 2ZM10 15.5L6.5 12L7.91 10.59L10 12.67L16.09 6.59L17.5 8L10 15.5Z" />
                </svg>
                <span>{activeMeta.badgeLabel}</span>
              </span>

              <span className="text-xs font-semibold text-[#48566A]">
                {primaryActiveSource.fullName}
              </span>
            </div>

            <p className="text-xs text-[#162033] font-medium leading-relaxed">
              {primaryActiveSource.scopeVi}
            </p>
          </div>

          {/* Qualitative Authority Index Box */}
          <div className="shrink-0 flex items-center gap-3 border-t sm:border-t-0 sm:border-l border-[#E3E8EF] pt-2.5 sm:pt-0 sm:pl-4">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#6D7A8E] block">
                Thẩm quyền xác thực
              </span>
              <span
                className="text-xs font-bold"
                style={{ color: activeMeta.primaryColor }}
              >
                {primaryActiveSource.verificationLevel}
              </span>
            </div>

            <div className="rounded-xl bg-white px-2.5 py-1.5 border border-[#E3E8EF] shadow-xs text-right">
              <span className="text-[10px] text-[#6D7A8E] block">Quy mô bảo chứng</span>
              <span className="text-xs font-bold text-[#162033]">
                {primaryActiveSource.citationCount}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default SourceLens;
