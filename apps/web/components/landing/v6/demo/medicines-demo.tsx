"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { V6_DEMO_MEDICINES, type V6DemoMedicine } from "../landing-data-v6";

export function MedicinesDemo() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].medicines;
  const [activeTab, setActiveTab] = useState<"current" | "needs-confirmation" | "safety" | "cabinet">("current");
  const [selectedMed, setSelectedMed] = useState<V6DemoMedicine>(V6_DEMO_MEDICINES[0]);

  const filteredMeds = V6_DEMO_MEDICINES.filter((med) => {
    if (activeTab === "current") return med.state === "current";
    if (activeTab === "needs-confirmation") return med.state === "needs-confirmation";
    if (activeTab === "cabinet") return med.state === "cabinet";
    return true; // safety checks all
  });

  return (
    <div className="clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10">
      {/* Workspace Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">Bàn làm việc Quản lý Thuốc</h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
              CareGuard Engine
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">
            Phân tầng chính xác trạng thái sử dụng thực tế & kiểm soát tương tác chéo
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1 border border-[#E3E8EF]" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "current"}
            onClick={() => setActiveTab("current")}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all clara-focus-ring ${
              activeTab === "current"
                ? "bg-white text-[#0B6FD8] shadow-sm"
                : "text-[#48566A] hover:text-[#162033]"
            }`}
          >
            {copy.tabs.current}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "needs-confirmation"}
            onClick={() => setActiveTab("needs-confirmation")}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all clara-focus-ring ${
              activeTab === "needs-confirmation"
                ? "bg-white text-amber-700 shadow-sm"
                : "text-[#48566A] hover:text-[#162033]"
            }`}
          >
            {copy.tabs.needsConfirmation}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "safety"}
            onClick={() => setActiveTab("safety")}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all clara-focus-ring ${
              activeTab === "safety"
                ? "bg-white text-[#14A88D] shadow-sm"
                : "text-[#48566A] hover:text-[#162033]"
            }`}
          >
            {copy.tabs.safetyCheck}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "cabinet"}
            onClick={() => setActiveTab("cabinet")}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all clara-focus-ring ${
              activeTab === "cabinet"
                ? "bg-white text-[#162033] shadow-sm"
                : "text-[#48566A] hover:text-[#162033]"
            }`}
          >
            {copy.tabs.cabinet}
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Medication Cards */}
        <div className="lg:col-span-7 space-y-3">
          {filteredMeds.map((med) => {
            const isSelected = selectedMed.id === med.id;
            return (
              <button
                key={med.id}
                type="button"
                onClick={() => setSelectedMed(med)}
                className={`w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring ${
                  isSelected
                    ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-sm"
                    : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7]"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-[#162033]">{med.name}</span>
                    <span className="rounded bg-[#F1F5F9] px-2 py-0.5 text-xs font-medium text-[#48566A]">
                      {med.dosage}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-[#6D7A8E]">{med.category}</p>
                  <p className="mt-1.5 text-xs text-[#48566A] font-medium">{med.schedule}</p>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  {med.state === "current" && (
                    <span className="rounded-full bg-[#ECFDF8] px-2 py-0.5 text-[11px] font-semibold text-[#14A88D]">
                      ✓ Đang dùng
                    </span>
                  )}
                  {med.state === "needs-confirmation" && (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
                      ⚠ Cần duyệt
                    </span>
                  )}
                  {med.state === "cabinet" && (
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                      ☖ Tủ thuốc
                    </span>
                  )}
                  <span className="text-[10px] text-[#6D7A8E]">Nhấp để xem chi tiết</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column: Selected Medication Inspector & Safety Matrix */}
        <div className="lg:col-span-5 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3 mb-4">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                Chi tiết & Thẩm định FIDES
              </span>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-bold text-[#14A88D] border border-[#14A88D]/20 shadow-xs">
                {copy.safetyTag}
              </span>
            </div>

            <h4 className="text-base font-bold text-[#162033]">
              {selectedMed.name} ({selectedMed.dosage})
            </h4>
            <p className="text-xs text-[#6D7A8E] mt-0.5">{selectedMed.category}</p>

            <div className="mt-4 space-y-3">
              <div className="rounded-xl bg-white p-3 border border-[#E3E8EF]">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  Lịch trình sử dụng
                </span>
                <p className="text-xs font-medium text-[#162033] mt-0.5">{selectedMed.schedule}</p>
              </div>

              <div className="rounded-xl bg-white p-3 border border-[#E3E8EF]">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  Khuyến cáo an toàn lâm sàng
                </span>
                <p className="text-xs text-[#48566A] mt-0.5 leading-relaxed">
                  {language === "vi" ? selectedMed.noteVi : selectedMed.noteEn}
                </p>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-[#E3E8EF]">
            <p className="text-[11px] text-[#6D7A8E] italic leading-tight">
              {copy.truthNote}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
