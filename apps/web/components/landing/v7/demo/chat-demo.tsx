"use client";

import React, { useState, useId, useEffect } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_SOURCES, type V7DemoSource } from "../landing-data-v7";
import { EvidenceRibbon } from "../artwork/evidence-ribbon";

export interface ChatDemoProps {
  /** Optional custom CSS classes */
  className?: string;
  /** Optional initial selected source ID (defaults to 'dav-national') */
  initialSelectedSourceId?: string;
  /** Whether the advanced pharmacological detail is open by default */
  initialShowAdvanced?: boolean;
}

/**
 * Authority level badge styling configuration
 */
function getAuthorityBadgeConfig(level: V7DemoSource["authorityLevel"]) {
  switch (level) {
    case "National":
      return {
        tag: "National Tier I",
        labelVi: "Dược điển Quốc gia",
        labelEn: "National Pharmacopoeia",
        badgeClasses: "bg-emerald-50 text-emerald-800 border-emerald-200/80",
        dotClasses: "bg-emerald-500",
      };
    case "International":
      return {
        tag: "Global Standard",
        labelVi: "Tiêu chuẩn Quốc tế",
        labelEn: "International Standard",
        badgeClasses: "bg-sky-50 text-sky-800 border-sky-200/80",
        dotClasses: "bg-sky-500",
      };
    case "Regulatory":
      return {
        tag: "Regulatory Alert",
        labelVi: "Cảnh báo Cơ quan Quản lý",
        labelEn: "Regulatory Agency",
        badgeClasses: "bg-amber-50 text-amber-900 border-amber-200/80",
        dotClasses: "bg-amber-500",
      };
    case "Peer-Reviewed":
      return {
        tag: "Peer-Reviewed RCT",
        labelVi: "Nghiên cứu Bình duyệt",
        labelEn: "Peer-Reviewed Literature",
        badgeClasses: "bg-purple-50 text-purple-900 border-purple-200/80",
        dotClasses: "bg-purple-500",
      };
  }
}

/**
 * ChatDemo (Landing v7 Signature Surface)
 *
 * Renders CLARA's signature near-full-width Chat Product Surface demonstrating:
 * 1. Surface Header with FIDES Safe badge and Zero-CoT security lock.
 * 2. User question turn with clinical context chips.
 * 3. 5-Tier Progressive Answer Surface:
 *    - Tier 1: Direct Answer (prominent, high-contrast clinical takeaway)
 *    - Tier 2: Next Action (actionable interactive checklist)
 *    - Tier 3: Uncertainty / Data Gaps (amber warning callout box)
 *    - Tier 4: Referenced Clinical Sources rail with interactive Source Inspector modal/panel
 *    - Tier 5: Advanced Pharmacological Detail (expandable mechanism toggle)
 * 4. Visual connection across clinical claims to verified evidence via EvidenceRibbon artwork.
 * 5. Full WCAG 2.1 AA keyboard accessibility, screen reader semantics, zero TypeScript errors.
 */
export function ChatDemo({
  className = "",
  initialSelectedSourceId = "dav-national",
  initialShowAdvanced = false,
}: ChatDemoProps) {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.chat ?? LANDING_COPY_V7.vi.chat;

  const [selectedSource, setSelectedSource] = useState<V7DemoSource | null>(() => {
    return (
      V7_DEMO_SOURCES.find((s) => s.id === initialSelectedSourceId) ??
      V7_DEMO_SOURCES[0] ??
      null
    );
  });

  const [showAdvanced, setShowAdvanced] = useState<boolean>(initialShowAdvanced);
  const [completedSteps, setCompletedSteps] = useState<Record<number, boolean>>({});

  const regionId = useId();
  const advancedRegionId = `advanced-pharmacology-${regionId}`;
  const inspectorPanelId = `source-inspector-${regionId}`;

  // Keyboard navigation: Escape key closes Source Inspector
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedSource) {
        setSelectedSource(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedSource]);

  // Parse next actions into interactive checklist items
  const actionItems = copy.nextActionBody
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  const toggleStep = (index: number) => {
    setCompletedSteps((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  return (
    <section
      aria-label={lang === "vi" ? "Mô phỏng Giao diện Trò chuyện Lâm sàng CLARA" : "CLARA Clinical Chat Interface Simulation"}
      className={`clara-product-surface relative w-full overflow-hidden p-5 sm:p-7 lg:p-10 shadow-lg ${className}`}
      data-testid="chat-demo"
    >
      {/* ------------------------------------------------------------------------- */}
      {/* 1. SURFACE HEADER: FIDES Safe Badge & Zero-CoT Security                   */}
      {/* ------------------------------------------------------------------------- */}
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div className="flex items-center gap-3.5">
          {/* Avatar Icon */}
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#0B6FD8] to-[#1A86F5] text-white font-bold text-lg shadow-sm"
            aria-hidden="true"
          >
            C
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-base sm:text-lg font-bold text-[#162033] tracking-tight">
                CLARA Clinical Assistant
              </h3>
              {/* FIDES Safe Badge */}
              <span
                data-testid="fides-safe-badge"
                className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-xs"
              >
                <svg
                  viewBox="0 0 16 16"
                  fill="none"
                  className="h-3.5 w-3.5 text-[#14A88D]"
                  aria-hidden="true"
                >
                  <path
                    d="M8 1.5 L13.5 3.5 V7.5 C13.5 11 11 13.8 8 14.8 C5 13.8 2.5 11 2.5 7.5 V3.5 L8 1.5 Z"
                    fill="currentColor"
                    fillOpacity="0.15"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M5.5 8 L7 9.5 L10.5 6"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <span>FIDES Safe</span>
              </span>
            </div>
            <p className="text-xs text-[#6D7A8E] mt-0.5">
              {lang === "vi"
                ? "Phiên tham vấn bối cảnh sức khỏe cá nhân • Bác sĩ giám sát"
                : "Personalized Health Context Consultation • Clinician Supervised"}
            </p>
          </div>
        </div>

        {/* Security & Latency Badges */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Zero-CoT Security badge */}
          <span
            data-testid="zero-cot-badge"
            className="inline-flex items-center gap-2 rounded-xl bg-[#EFF7FF] px-3 py-1.5 text-xs font-semibold text-[#0B6FD8] border border-[#0B6FD8]/20 shadow-xs"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#0B6FD8] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#0B6FD8]" />
            </span>
            <span>Zero-CoT Security Active</span>
          </span>

          <span className="hidden md:inline-flex items-center gap-1.5 rounded-lg bg-[#F1F5F9] px-2.5 py-1 text-[11px] font-mono text-[#48566A] border border-[#E3E8EF]">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#14A88D]" />
            Deterministic RAG • 240ms
          </span>
        </div>
      </header>

      {/* ------------------------------------------------------------------------- */}
      {/* 2. USER QUESTION TURN                                                     */}
      {/* ------------------------------------------------------------------------- */}
      <div className="mt-6 flex justify-end">
        <div className="w-full max-w-2xl rounded-2xl rounded-tr-xs bg-[#EFF7FF]/90 p-4 sm:p-5 border border-[#0B6FD8]/20 text-[#162033] shadow-xs">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#0B6FD8]">
              {lang === "vi" ? "Câu hỏi của bạn" : "Your Question"}
            </span>
            <span className="text-[11px] text-[#6D7A8E]">
              {lang === "vi" ? "Hôm nay, 08:32 • Đơn thuốc Amlodipine" : "Today, 08:32 • Active Rx Amlodipine"}
            </span>
          </div>
          <p className="text-sm sm:text-base font-medium leading-relaxed text-[#162033]">
            {lang === "vi"
              ? "Tôi mới bắt đầu uống Amlodipine 5mg được 3 ngày, gần đây đứng dậy hay thấy hơi chóng mặt nhẹ. Có cần ngừng thuốc ngay không?"
              : "I started taking Amlodipine 5mg 3 days ago and feel mild dizziness when standing up. Should I stop taking it immediately?"}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 pt-2 border-t border-[#0B6FD8]/10 text-xs text-[#48566A]">
            <span className="rounded-md bg-white px-2 py-0.5 text-[11px] font-medium border border-[#E3E8EF]">
              💊 Amlodipine Besylate 5mg (08:00 AM)
            </span>
            <span className="rounded-md bg-white px-2 py-0.5 text-[11px] font-medium border border-[#E3E8EF]">
              ⏱ {lang === "vi" ? "Ngày thứ 3 điều trị" : "Day 3 of regimen"}
            </span>
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------------------- */}
      {/* 3. FIVE-TIER PROGRESSIVE ANSWER SURFACE                                   */}
      {/* ------------------------------------------------------------------------- */}
      <div className="mt-6 flex gap-4">
        {/* Left AI Avatar Badge */}
        <div
          className="hidden sm:flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#EFF7FF] text-[#0B6FD8] font-bold text-sm border border-[#0B6FD8]/25 shadow-xs"
          aria-hidden="true"
        >
          AI
        </div>

        <div className="flex-1 space-y-6">
          {/* ======================================================================= */}
          {/* TIER 1: DIRECT ANSWER (PROMINENT)                                       */}
          {/* ======================================================================= */}
          <article
            data-testid="tier-1-direct-answer"
            className="relative rounded-2xl bg-white p-5 sm:p-6 border-2 border-[#0B6FD8]/30 shadow-sm transition-all duration-200 hover:border-[#0B6FD8]/50"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#0B6FD8] ring-4 ring-[#EFF7FF]" />
                <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#0B6FD8]">
                  Tier 1 • {copy.directAnswerTitle}
                </span>
              </div>
              <span className="rounded-full bg-[#EFF7FF] px-2.5 py-0.5 text-[11px] font-bold text-[#0B6FD8] border border-[#0B6FD8]/20">
                {lang === "vi" ? "Khuyến nghị sơ bộ" : "Primary Takeaway"}
              </span>
            </div>

            <p className="mt-3 text-base sm:text-lg text-[#162033] font-semibold leading-relaxed">
              {copy.directAnswerBody}
            </p>

            <div className="mt-4 flex flex-wrap items-center gap-2 pt-3 border-t border-[#E3E8EF] text-xs text-[#48566A]">
              <span className="inline-flex items-center gap-1.5 font-medium text-[#14A88D]">
                <svg viewBox="0 0 16 16" fill="currentColor" className="h-4 w-4" aria-hidden="true">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                    clipRule="evenodd"
                  />
                </svg>
                {lang === "vi"
                  ? "Không tự ý dừng thuốc đột ngột mà không có chỉ định chuyên môn"
                  : "Do not discontinue antihypertensives abruptly without clinical supervision"}
              </span>
            </div>
          </article>

          {/* ======================================================================= */}
          {/* TIER 2: NEXT ACTION (ACTIONABLE CHECKLIST)                               */}
          {/* ======================================================================= */}
          <article
            data-testid="tier-2-next-action"
            className="rounded-2xl bg-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF]"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#14A88D]" />
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-[#14A88D]">
                  Tier 2 • {copy.nextActionTitle}
                </h4>
              </div>
              <span className="text-[11px] text-[#6D7A8E] font-medium">
                {lang === "vi" ? "Nhấp để đánh dấu hoàn thành" : "Click step to mark completed"}
              </span>
            </div>

            <fieldset className="space-y-2.5">
              <legend className="sr-only">{copy.nextActionTitle}</legend>
              {actionItems.map((item, idx) => {
                const isChecked = !!completedSteps[idx];
                return (
                  <div
                    key={idx}
                    onClick={() => toggleStep(idx)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleStep(idx);
                      }
                    }}
                    role="checkbox"
                    tabIndex={0}
                    aria-checked={isChecked}
                    aria-label={`Step ${idx + 1}: ${item}`}
                    className={`flex items-start gap-3 rounded-xl p-3.5 transition-all duration-200 border cursor-pointer select-none clara-focus-ring ${
                      isChecked
                        ? "bg-[#ECFDF8] border-[#14A88D]/40 text-[#0F766E]"
                        : "bg-white border-[#E3E8EF] hover:border-[#CBD5E1] text-[#162033]"
                    }`}
                  >
                    <div
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                        isChecked
                          ? "bg-[#14A88D] border-[#14A88D] text-white"
                          : "border-[#CBD5E1] bg-white text-transparent"
                      }`}
                      aria-hidden="true"
                    >
                      <svg viewBox="0 0 12 12" fill="none" className="h-3.5 w-3.5 stroke-current stroke-2">
                        <polyline points="2.5 6 4.5 8.5 9.5 3.5" />
                      </svg>
                    </div>

                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-bold ${
                            isChecked ? "text-[#0F766E]" : "text-[#0B6FD8]"
                          }`}
                        >
                          Step {idx + 1}
                        </span>
                        {idx === 2 && (
                          <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200">
                            {lang === "vi" ? "Cảnh báo an toàn" : "Safety Flag"}
                          </span>
                        )}
                      </div>
                      <p
                        className={`text-xs sm:text-sm mt-0.5 leading-relaxed ${
                          isChecked ? "line-through text-[#6D7A8E]" : "font-medium text-[#162033]"
                        }`}
                      >
                        {item.replace(/^\d+\.\s*/, "")}
                      </p>
                    </div>
                  </div>
                );
              })}
            </fieldset>
          </article>

          {/* ======================================================================= */}
          {/* TIER 3: UNCERTAINTY / DATA GAPS (YELLOW WARNING BOX)                     */}
          {/* ======================================================================= */}
          <article
            data-testid="tier-3-uncertainty"
            className="rounded-2xl bg-[#FFFBEB] p-5 border border-[#FDE68A] shadow-xs text-amber-900"
          >
            <div className="flex items-start gap-3">
              <div
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-amber-700 font-bold text-sm border border-amber-300/80"
                aria-hidden="true"
              >
                ⚠
              </div>
              <div className="flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-amber-900">
                    Tier 3 • {copy.uncertaintyTitle}
                  </h4>
                  <span className="rounded-full bg-amber-100/90 px-2 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200">
                    {lang === "vi" ? "Giới hạn bối cảnh" : "Context Boundary"}
                  </span>
                </div>
                <p className="mt-1.5 text-xs sm:text-sm text-amber-950 font-medium leading-relaxed">
                  {copy.uncertaintyBody}
                </p>
                <p className="mt-2 text-[11px] text-amber-800/90 leading-tight">
                  {lang === "vi"
                    ? "Nguyên tắc an toàn: CLARA không suy đoán mức giảm huyết áp khi thiếu chỉ số đo thực nghiệm. Hãy ghi nhận huyết áp để bác sĩ có đủ căn cứ điều chỉnh."
                    : "Safety rule: CLARA does not extrapolate blood pressure drops without empirical logs. Record home vitals to assist your clinician."}
                </p>
              </div>
            </div>
          </article>

          {/* ======================================================================= */}
          {/* TIER 4: REFERENCED CLINICAL SOURCES RAIL & SOURCE INSPECTOR              */}
          {/* ======================================================================= */}
          <article
            data-testid="tier-4-sources"
            className="relative rounded-2xl bg-white p-5 sm:p-6 border border-[#E3E8EF] shadow-xs space-y-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#6D5BD0]" />
                <h4 className="text-xs font-extrabold uppercase tracking-wider text-[#6D5BD0]">
                  Tier 4 • {copy.sourcesTitle}
                </h4>
              </div>
              <span className="text-xs text-[#6D7A8E] font-medium">{copy.sourcesDisclaimer}</span>
            </div>

            {/* Visual Vector Evidence Ribbon connecting Sources */}
            <div className="relative py-1 overflow-hidden rounded-xl bg-slate-50/60 p-2 border border-slate-100">
              <EvidenceRibbon
                variant="horizontal"
                tone="azure"
                active={selectedSource !== null}
                className="w-full h-8 opacity-80"
              />
            </div>

            {/* Sources Rail Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
              {V7_DEMO_SOURCES.map((source) => {
                const isSelected = selectedSource?.id === source.id;
                const badgeConfig = getAuthorityBadgeConfig(source.authorityLevel);

                return (
                  <button
                    key={source.id}
                    type="button"
                    data-testid={`source-btn-${source.id}`}
                    aria-expanded={isSelected}
                    aria-controls={inspectorPanelId}
                    onClick={() => setSelectedSource(isSelected ? null : source)}
                    className={`group relative flex flex-col justify-between rounded-xl p-3.5 text-left transition-all duration-200 border clara-focus-ring cursor-pointer ${
                      isSelected
                        ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-xs ring-1 ring-[#0B6FD8]/30"
                        : "bg-white border-[#E3E8EF] hover:border-[#CBD5E1] hover:bg-[#F8FAFD]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-bold border ${badgeConfig.badgeClasses}`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${badgeConfig.dotClasses}`} />
                        {badgeConfig.tag}
                      </span>
                      <span
                        className={`text-[11px] font-bold transition-transform ${
                          isSelected ? "text-[#0B6FD8] translate-x-0.5" : "text-[#94A3B8]"
                        }`}
                      >
                        {isSelected ? "● Đang tra" : "↗ Tra cứu"}
                      </span>
                    </div>

                    <div>
                      <p className="text-xs font-bold text-[#162033] line-clamp-1 group-hover:text-[#0B6FD8]">
                        {source.name}
                      </p>
                      <p className="text-[11px] text-[#6D7A8E] line-clamp-1 mt-0.5">
                        {source.authority}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Interactive Source Inspector Panel / Modal */}
            {selectedSource && (
              <div
                id={inspectorPanelId}
                data-testid="source-inspector-panel"
                role="region"
                aria-label={`${copy.inspectorTitle}: ${selectedSource.name}`}
                className="relative rounded-2xl bg-gradient-to-br from-[#EFF7FF] via-white to-[#EFF7FF]/50 p-4 sm:p-5 border-2 border-[#0B6FD8]/30 shadow-md animate-fadeIn"
              >
                {/* Inspector Header */}
                <div className="flex items-center justify-between border-b border-[#0B6FD8]/15 pb-3 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#0B6FD8] text-white text-xs font-bold">
                      🔍
                    </span>
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[#0B6FD8]">
                        {copy.inspectorTitle}
                      </span>
                      <h5 className="text-xs sm:text-sm font-bold text-[#162033]">
                        {selectedSource.name}
                      </h5>
                    </div>
                  </div>

                  <button
                    type="button"
                    data-testid="close-source-inspector"
                    aria-label={copy.inspectorClose}
                    onClick={() => setSelectedSource(null)}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold text-[#6D7A8E] hover:bg-[#E3E8EF] hover:text-[#162033] transition-colors clara-focus-ring cursor-pointer"
                  >
                    ✕
                  </button>
                </div>

                {/* Inspector Details Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-xs">
                  {/* Relevance Field */}
                  <div className="rounded-xl bg-white p-3 border border-[#0B6FD8]/15 shadow-xs space-y-1">
                    <span className="font-bold text-[#0B6FD8] block text-[11px] uppercase tracking-wider">
                      {lang === "vi" ? "Lý do đối chiếu & Mức phù hợp" : "Clinical Relevance"}
                    </span>
                    <p className="text-xs text-[#162033] leading-relaxed">
                      {lang === "vi" ? selectedSource.relevanceVi : selectedSource.relevanceEn}
                    </p>
                  </div>

                  {/* Applicability Field */}
                  <div className="rounded-xl bg-white p-3 border border-[#0B6FD8]/15 shadow-xs space-y-1">
                    <span className="font-bold text-[#14A88D] block text-[11px] uppercase tracking-wider">
                      {lang === "vi" ? "Phạm vi áp dụng lâm sàng" : "Clinical Scope & Applicability"}
                    </span>
                    <p className="text-xs text-[#162033] leading-relaxed">
                      {lang === "vi" ? selectedSource.applicabilityVi : selectedSource.applicabilityEn}
                    </p>
                  </div>

                  {/* Limitations Field */}
                  <div className="rounded-xl bg-white p-3 border border-[#0B6FD8]/15 shadow-xs space-y-1">
                    <span className="font-bold text-amber-700 block text-[11px] uppercase tracking-wider">
                      {lang === "vi" ? "Giới hạn & Lưu ý bản địa hóa" : "Nuances & Limitations"}
                    </span>
                    <p className="text-xs text-[#162033] leading-relaxed">
                      {lang === "vi" ? selectedSource.limitationsVi : selectedSource.limitationsEn}
                    </p>
                  </div>

                  {/* Authority & Update Meta */}
                  <div className="rounded-xl bg-white p-3 border border-[#0B6FD8]/15 shadow-xs space-y-1">
                    <span className="font-bold text-[#6D7A8E] block text-[11px] uppercase tracking-wider">
                      {lang === "vi" ? "Cơ quan ban hành & Chu kỳ cập nhật" : "Authority & Release Cycle"}
                    </span>
                    <p className="text-xs text-[#162033] font-semibold">
                      {selectedSource.authority}
                    </p>
                    <span className="inline-block rounded bg-[#F1F5F9] px-2 py-0.5 text-[10px] font-mono text-[#48566A]">
                      {lang === "vi" ? "Đồng bộ:" : "Synced:"} {selectedSource.updated}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </article>

          {/* ======================================================================= */}
          {/* TIER 5: ADVANCED PHARMACOLOGICAL DETAIL (EXPANDABLE MECHANISM TOGGLE)     */}
          {/* ======================================================================= */}
          <article
            data-testid="tier-5-advanced-pharmacology"
            className="rounded-2xl bg-white p-5 border border-[#E3E8EF] shadow-xs"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-[#8B7CF6]" />
                  <h4 className="text-xs font-extrabold uppercase tracking-wider text-[#8B7CF6]">
                    Tier 5 • {copy.advancedDetailTitle}
                  </h4>
                </div>
                <p className="text-xs text-[#6D7A8E] mt-0.5">
                  {lang === "vi"
                    ? "Cơ chế thụ thể phân tử, enzym chuyển hóa gan CYP450 và dược động học"
                    : "Molecular receptor kinetics, hepatic CYP450 metabolism, and pharmacokinetics"}
                </p>
              </div>

              {/* Mechanism Toggle Button */}
              <button
                type="button"
                data-testid="toggle-advanced-pharmacology"
                aria-expanded={showAdvanced}
                aria-controls={advancedRegionId}
                onClick={() => setShowAdvanced((prev) => !prev)}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all duration-200 border clara-focus-ring cursor-pointer ${
                  showAdvanced
                    ? "bg-[#F5F3FF] text-[#6D5BD0] border-[#8B7CF6]/40 shadow-xs"
                    : "bg-white text-[#0B6FD8] border-[#E3E8EF] hover:border-[#0B6FD8]/40 hover:bg-[#EFF7FF]"
                }`}
              >
                <span>{showAdvanced ? "▼ Thu gọn cơ chế" : "▶ Mở rộng cơ chế dược lý"}</span>
              </button>
            </div>

            {/* Expandable Pharmacology Section */}
            {showAdvanced && (
              <div
                id={advancedRegionId}
                data-testid="advanced-pharmacology-content"
                role="region"
                aria-label={copy.advancedDetailTitle}
                className="mt-4 rounded-xl bg-[#F5F3FF]/70 p-4 sm:p-5 border border-[#8B7CF6]/30 text-xs text-[#162033] leading-relaxed space-y-3 animate-fadeIn"
              >
                <div className="flex items-center gap-2 font-bold text-[#6D5BD0]">
                  <span>🧬</span>
                  <span>
                    {lang === "vi"
                      ? "Cơ chế Dược lực học (Pharmacodynamics) & Dược động học (Pharmacokinetics)"
                      : "Pharmacodynamics & Pharmacokinetics Profile"}
                  </span>
                </div>

                <p className="text-xs sm:text-sm text-[#162033] font-medium leading-relaxed">
                  {copy.advancedDetailBody}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 pt-2">
                  <div className="rounded-lg bg-white p-2.5 border border-[#8B7CF6]/20 shadow-xs">
                    <span className="text-[10px] font-bold text-[#6D5BD0] uppercase block">
                      Receptor Pathway
                    </span>
                    <p className="text-[11px] text-[#48566A] mt-0.5">
                      L-type Voltage-gated Ca2+ channels (Vascular smooth muscle)
                    </p>
                  </div>

                  <div className="rounded-lg bg-white p-2.5 border border-[#8B7CF6]/20 shadow-xs">
                    <span className="text-[10px] font-bold text-[#6D5BD0] uppercase block">
                      Metabolism / T1/2
                    </span>
                    <p className="text-[11px] text-[#48566A] mt-0.5">
                      Hepatic CYP3A4 pathway • Half-life: 35–50 hours
                    </p>
                  </div>

                  <div className="rounded-lg bg-white p-2.5 border border-[#8B7CF6]/20 shadow-xs">
                    <span className="text-[10px] font-bold text-[#6D5BD0] uppercase block">
                      Steady State
                    </span>
                    <p className="text-[11px] text-[#48566A] mt-0.5">
                      Peak therapeutic stabilization achieved after 7–8 days
                    </p>
                  </div>
                </div>
              </div>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}

export default ChatDemo;
