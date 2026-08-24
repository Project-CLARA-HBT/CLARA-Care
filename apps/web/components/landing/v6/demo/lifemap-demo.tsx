"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";

export function LifeMapDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].lifemap;
  const [selectedMilestone, setSelectedMilestone] = useState<number>(3); // Default Today

  return (
    <div className="w-full space-y-8">
      {/* Horizontal / Longitudinal Stage */}
      <div className="clara-product-surface relative overflow-hidden p-6 sm:p-8 lg:p-10">
        <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-4 mb-8">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
              LIFEMAP CHRONOLOGICAL VIEW
            </span>
            <h3 className="text-lg font-bold text-[#162033]">Dòng thời gian sức khỏe liên tục (4 Tháng)</h3>
          </div>
          <span className="rounded-full bg-[#EFF7FF] px-3 py-1 text-xs font-semibold text-[#0B6FD8] border border-[#0B6FD8]/20">
            4 Mốc dữ liệu đồng bộ
          </span>
        </div>

        {/* Timeline Desktop Rail */}
        <div className="relative pt-6 pb-2">
          {/* Central Connecting Spine Line */}
          <div className="absolute top-11 left-6 right-6 hidden md:block h-0.5 bg-[#E3E8EF]" aria-hidden="true" />

          {/* Timeline Nodes Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 relative z-10" role="list">
            {copy.timeline.map((event, idx) => {
              const isSelected = selectedMilestone === idx;
              const isToday = event.emphasis === "today";

              return (
                <button
                  key={event.period}
                  type="button"
                  onClick={() => setSelectedMilestone(idx)}
                  role="listitem"
                  className={`group flex flex-col text-left rounded-2xl p-4 transition-all clara-focus-ring border ${
                    isSelected
                      ? "bg-white border-[#0B6FD8] shadow-md -translate-y-1"
                      : "bg-[#F8FAFD] border-[#E3E8EF] hover:border-[#D5DDE7]"
                  }`}
                >
                  {/* Spine Node Marker */}
                  <div className="flex items-center gap-3 mb-3">
                    <span
                      className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-transform ${
                        isToday
                          ? "bg-[#0B6FD8] text-white ring-4 ring-[#EFF7FF]"
                          : isSelected
                          ? "bg-[#162033] text-white"
                          : "bg-[#E3E8EF] text-[#6D7A8E] group-hover:bg-[#D5DDE7]"
                      }`}
                    >
                      {idx + 1}
                    </span>
                    <span
                      className={`text-xs font-bold uppercase tracking-wider ${
                        isToday ? "text-[#0B6FD8]" : "text-[#6D7A8E]"
                      }`}
                    >
                      {event.period}
                    </span>
                  </div>

                  <span className="text-xs font-semibold rounded-md bg-[#EFF7FF] px-2 py-0.5 text-[#0B6FD8] w-fit mb-2">
                    {event.category}
                  </span>

                  <h4 className="text-sm font-bold text-[#162033] leading-snug line-clamp-1">
                    {event.title}
                  </h4>
                  <p className="mt-1 text-xs text-[#48566A] leading-relaxed line-clamp-2">
                    {event.detail}
                  </p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected Milestone Detail Box */}
        {copy.timeline[selectedMilestone] && (
          <div className="mt-6 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold uppercase tracking-wide text-[#0B6FD8]">
                  Chi tiết mốc {copy.timeline[selectedMilestone].period}
                </span>
                <span className="text-xs text-[#6D7A8E]">• {copy.timeline[selectedMilestone].category}</span>
              </div>
              <p className="text-sm font-semibold text-[#162033]">
                {copy.timeline[selectedMilestone].title}: {copy.timeline[selectedMilestone].detail}
              </p>
            </div>
            <span className="shrink-0 text-xs font-medium text-[#0B6FD8] bg-[#EFF7FF] px-3 py-1.5 rounded-xl border border-[#0B6FD8]/20">
              Đã ghi nhận vào hồ sơ
            </span>
          </div>
        )}
      </div>

      {/* Raised Contextual Insight Callout (Primary WOW moment anchor) */}
      <div className="clara-floating-chrome rounded-3xl p-6 sm:p-8 border border-[#0B6FD8]/25 shadow-xl bg-gradient-to-r from-[#EFF7FF]/90 to-white/90">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-[#0B6FD8] text-white text-xl font-black shadow-md">
              ✦
            </div>
            <div>
              <span className="text-xs font-bold tracking-wider uppercase text-[#0B6FD8]">
                {copy.insightCallout.tag}
              </span>
              <h4 className="text-lg sm:text-xl font-bold text-[#162033] mt-0.5">
                {copy.insightCallout.title}
              </h4>
              <p className="mt-1.5 text-sm sm:text-base text-[#48566A] leading-relaxed max-w-2xl">
                {copy.insightCallout.body}
              </p>
            </div>
          </div>

          <button
            type="button"
            className="inline-flex shrink-0 items-center justify-center rounded-xl bg-[#0B6FD8] px-5 py-3 text-xs sm:text-sm font-bold text-white shadow-sm hover:bg-[#0855A8] transition-all clara-focus-ring"
          >
            {copy.insightCallout.action}
          </button>
        </div>
      </div>
    </div>
  );
}
