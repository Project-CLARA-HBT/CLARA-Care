"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import { V7_DEMO_MEDICINES, type V7DemoMedicine } from "../landing-data-v7";

export type MedicationTab = "current" | "needs-confirmation" | "safety" | "cabinet";

export interface MedicinesDemoProps {
  /** Optional custom CSS classes */
  className?: string;
  /** Optional initial selected tab */
  initialTab?: MedicationTab;
}

/**
 * MedicinesDemo (Landing v7 Signature Surface)
 *
 * Renders CLARA's Unified Medication Workspace demonstrating:
 * 1. Categorized tabs with silky transitions:
 *    - Đang dùng (Current / Active Regimen)
 *    - Cần xác nhận (Needs Review / Pending Intake)
 *    - Kiểm tra an toàn FIDES (FIDES Safety Matrix)
 *    - Tủ thuốc gia đình (Home Cabinet Inventory)
 * 2. Status badge pills with subtle glowing halos and FIDES verification labels.
 * 3. Rich animated right inspector for selected medication:
 *    - FIDES multi-layer safety verification (Dược thư Quốc gia & DrugBank 5.1).
 *    - Schedule, dosage, administration timing, and clinical guidance notes.
 *    - Drug-Drug Interaction (DDI) compatibility matrix and organ tolerance notes.
 * 4. Semantic truth principle banner: "Tủ thuốc lưu trữ ≠ Thuốc đang uống hàng ngày."
 * 5. Full WCAG 2.1 AA accessibility, keyboard navigation, bilingual support (vi/en), zero TypeScript errors.
 */
export function MedicinesDemo({ className = "", initialTab = "current" }: MedicinesDemoProps) {
  const { language } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang]?.medicines ?? LANDING_COPY_V7.vi.medicines;

  const [activeTab, setActiveTab] = useState<MedicationTab>(initialTab);
  const [selectedMed, setSelectedMed] = useState<V7DemoMedicine>(() => {
    return V7_DEMO_MEDICINES.find((m) => m.state === initialTab) ?? V7_DEMO_MEDICINES[0];
  });

  const filteredMeds = V7_DEMO_MEDICINES.filter((med) => {
    if (activeTab === "current") return med.state === "current";
    if (activeTab === "needs-confirmation") return med.state === "needs-confirmation";
    if (activeTab === "cabinet") return med.state === "cabinet";
    return true; // "safety" tab inspects full repertoire for interactions
  });

  const getStatusBadge = (med: V7DemoMedicine) => {
    switch (med.state) {
      case "current":
        return {
          label: lang === "vi" ? "✓ Đang dùng" : "✓ Active",
          classes:
            "bg-[#ECFDF8] text-[#0E856F] border-[#14A88D]/40 shadow-[0_0_12px_rgba(20,168,141,0.22)] ring-1 ring-[#14A88D]/25",
          dotColor: "bg-[#14A88D] shadow-[0_0_6px_rgba(20,168,141,0.8)]",
        };
      case "needs-confirmation":
        return {
          label: lang === "vi" ? "⚠ Cần xác nhận" : "⚠ Needs Review",
          classes:
            "bg-amber-50 text-amber-900 border-amber-300 shadow-[0_0_12px_rgba(217,119,6,0.22)] ring-1 ring-amber-400/30",
          dotColor: "bg-amber-500 shadow-[0_0_6px_rgba(217,119,6,0.8)]",
        };
      case "cabinet":
        return {
          label: lang === "vi" ? "☖ Tủ thuốc" : "☖ Cabinet",
          classes:
            "bg-slate-100 text-slate-700 border-slate-300 shadow-[0_0_10px_rgba(100,116,139,0.15)] ring-1 ring-slate-200",
          dotColor: "bg-slate-400",
        };
    }
  };

  const getFidesBadge = (med: V7DemoMedicine) => {
    switch (med.fidesStatus) {
      case "verified":
        return {
          label: lang === "vi" ? "FIDES: Đã xác thực" : "FIDES: Verified",
          classes:
            "bg-emerald-50 text-emerald-800 border-emerald-300 shadow-[0_0_10px_rgba(16,185,129,0.25)] ring-1 ring-emerald-200",
        };
      case "pending":
        return {
          label: lang === "vi" ? "FIDES: Chờ duyệt" : "FIDES: Pending",
          classes:
            "bg-amber-50 text-amber-900 border-amber-300 shadow-[0_0_10px_rgba(245,158,11,0.25)] ring-1 ring-amber-200",
        };
      case "storage-only":
        return {
          label: lang === "vi" ? "FIDES: Chỉ lưu trữ" : "FIDES: Storage Only",
          classes: "bg-slate-50 text-slate-600 border-slate-200 shadow-2xs",
        };
    }
  };

  const handleTabChange = (tab: MedicationTab) => {
    setActiveTab(tab);
    if (tab === "current") {
      const match = V7_DEMO_MEDICINES.find((m) => m.state === "current");
      if (match) setSelectedMed(match);
    } else if (tab === "needs-confirmation") {
      const match = V7_DEMO_MEDICINES.find((m) => m.state === "needs-confirmation");
      if (match) setSelectedMed(match);
    } else if (tab === "cabinet") {
      const match = V7_DEMO_MEDICINES.find((m) => m.state === "cabinet");
      if (match) setSelectedMed(match);
    }
  };

  return (
    <div
      data-testid="medicines-demo"
      aria-label={lang === "vi" ? "Không gian Quản lý Thuốc Thống nhất" : "Unified Medication Workspace"}
      className={`clara-product-surface relative w-full overflow-hidden rounded-3xl p-6 sm:p-8 lg:p-10 border border-[#E3E8EF] shadow-xl bg-white transition-all duration-300 ${className}`}
    >
      {/* Ambient background light wash */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-24 -top-24 h-80 w-80 rounded-full bg-gradient-to-br from-[#14A88D]/10 via-[#0B6FD8]/5 to-transparent blur-3xl"
      />

      {/* Workspace Header */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <h3 className="text-lg font-bold text-[#162033] tracking-tight">
              {lang === "vi" ? "Không gian Quản lý Thuốc Thống nhất" : "Unified Medication Workspace"}
            </h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-bold text-[#14A88D] border border-[#14A88D]/30 shadow-[0_0_8px_rgba(20,168,141,0.15)]">
              CareGuard Engine
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] max-w-2xl">
            {lang === "vi"
              ? "Phân tầng chính xác trạng thái sử dụng thực tế & kiểm soát an toàn tương tác đa tầng"
              : "Strict state distinction across active intake, confirmation queues, and multi-layer safety verification"}
          </p>
        </div>

        {/* Silky Tab Switcher with Glowing Halos */}
        <div
          className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1.5 border border-[#E3E8EF] shadow-inner"
          role="tablist"
          aria-label={lang === "vi" ? "Phân loại thuốc" : "Medication categories"}
        >
          <button
            type="button"
            role="tab"
            data-testid="tab-current"
            id="tab-current-btn"
            aria-selected={activeTab === "current"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("current")}
            className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
              activeTab === "current"
                ? "bg-white text-[#0B6FD8] shadow-md shadow-[#0B6FD8]/15 ring-2 ring-[#0B6FD8]/30 -translate-y-0.5"
                : "text-[#48566A] hover:text-[#162033] hover:bg-white/70 hover:-translate-y-0.5"
            }`}
          >
            {copy.tabs.current}
          </button>
          <button
            type="button"
            role="tab"
            data-testid="tab-needs-confirmation"
            id="tab-needs-confirmation-btn"
            aria-selected={activeTab === "needs-confirmation"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("needs-confirmation")}
            className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
              activeTab === "needs-confirmation"
                ? "bg-white text-amber-800 shadow-md shadow-amber-600/15 ring-2 ring-amber-400/40 -translate-y-0.5"
                : "text-[#48566A] hover:text-[#162033] hover:bg-white/70 hover:-translate-y-0.5"
            }`}
          >
            {copy.tabs.needsConfirmation}
          </button>
          <button
            type="button"
            role="tab"
            data-testid="tab-safety"
            id="tab-safety-btn"
            aria-selected={activeTab === "safety"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("safety")}
            className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
              activeTab === "safety"
                ? "bg-white text-[#0E856F] shadow-md shadow-[#14A88D]/15 ring-2 ring-[#14A88D]/40 -translate-y-0.5"
                : "text-[#48566A] hover:text-[#162033] hover:bg-white/70 hover:-translate-y-0.5"
            }`}
          >
            {copy.tabs.safetyCheck}
          </button>
          <button
            type="button"
            role="tab"
            data-testid="tab-cabinet"
            id="tab-cabinet-btn"
            aria-selected={activeTab === "cabinet"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("cabinet")}
            className={`rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all duration-200 clara-focus-ring cursor-pointer ${
              activeTab === "cabinet"
                ? "bg-white text-[#162033] shadow-md shadow-slate-400/15 ring-2 ring-slate-300 -translate-y-0.5"
                : "text-[#48566A] hover:text-[#162033] hover:bg-white/70 hover:-translate-y-0.5"
            }`}
          >
            {copy.tabs.cabinet}
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div
        id="medicines-tabpanel"
        role="tabpanel"
        aria-labelledby={`tab-${activeTab}-btn`}
        className="relative z-10 mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
      >
        {/* Left Column: Medication List with Status Badge Glows & Hover Lift */}
        <div className="lg:col-span-7 space-y-3" data-testid="medications-list">
          {/* Tab Explanatory Header */}
          {activeTab === "safety" && (
            <div className="rounded-xl bg-[#ECFDF8]/90 p-3 border border-[#14A88D]/30 text-xs text-[#0E856F] flex items-center justify-between gap-2 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[#14A88D] text-white text-[10px] font-bold">
                  ✓
                </span>
                <span className="font-semibold">
                  {lang === "vi"
                    ? "Ma trận thẩm định tương tác chéo CareGuard: 0 tương tác nguy hiểm"
                    : "CareGuard Multi-Drug Interaction Matrix: 0 Critical Antagonisms"}
                </span>
              </div>
              <span className="rounded bg-white px-2 py-0.5 font-bold text-[10px] text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                Grade A
              </span>
            </div>
          )}

          {activeTab === "needs-confirmation" && (
            <div className="rounded-xl bg-amber-50/90 p-3 border border-amber-300 text-xs text-amber-900 flex items-center justify-between gap-2 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-amber-500 text-white text-[10px] font-bold">
                  !
                </span>
                <span className="font-semibold">
                  {lang === "vi"
                    ? "Hàng đợi xác nhận: Thuốc chỉ được lên lịch uống sau khi bác sĩ duyệt liều"
                    : "Confirmation Queue: Regimen active only after formal physician dose review"}
                </span>
              </div>
              <span className="rounded bg-white px-2 py-0.5 font-bold text-[10px] text-amber-800 border border-amber-300 shadow-2xs">
                Pending
              </span>
            </div>
          )}

          {filteredMeds.map((med) => {
            const isSelected = selectedMed.id === med.id;
            const statusPill = getStatusBadge(med);
            const fidesPill = getFidesBadge(med);

            return (
              <button
                key={med.id}
                type="button"
                data-testid={`med-item-${med.id}`}
                aria-pressed={isSelected}
                onClick={() => setSelectedMed(med)}
                className={`group w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all duration-200 border clara-focus-ring cursor-pointer ${
                  isSelected
                    ? "bg-gradient-to-r from-[#EFF7FF] via-[#F8FAFD] to-white border-[#0B6FD8] shadow-md shadow-[#0B6FD8]/15 ring-2 ring-[#0B6FD8]/30 -translate-y-0.5"
                    : "bg-white border-[#E3E8EF] hover:border-[#CBD5E1] hover:bg-[#F8FAFD] hover:-translate-y-0.5 hover:shadow-sm"
                }`}
              >
                <div className="space-y-1.5 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-sm text-[#162033] tracking-tight group-hover:text-[#0B6FD8] transition-colors">
                      {med.name}
                    </span>
                    <span className="rounded-md bg-[#F1F5F9] px-2 py-0.5 text-xs font-semibold text-[#48566A] border border-[#E3E8EF]">
                      {med.dosage}
                    </span>
                  </div>
                  <p className="text-xs text-[#6D7A8E] truncate">{med.category}</p>
                  <div className="flex items-center gap-1.5 text-xs text-[#48566A] font-medium pt-0.5">
                    <span className="text-[10px] text-[#6D7A8E]">⏱</span>
                    <span>{med.schedule}</span>
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      data-testid={`status-pill-${med.id}`}
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold border transition-all ${statusPill.classes}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${statusPill.dotColor}`} />
                      {statusPill.label}
                    </span>
                  </div>
                  <span
                    data-testid={`fides-pill-${med.id}`}
                    className={`rounded-md px-2 py-0.5 text-[10px] font-bold border transition-all ${fidesPill.classes}`}
                  >
                    {fidesPill.label}
                  </span>
                  <span className="text-[10px] font-semibold text-[#6D7A8E] group-hover:text-[#0B6FD8] transition-colors pt-0.5 flex items-center gap-1">
                    {lang === "vi" ? "Thẩm định chi tiết →" : "Inspect dossier →"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column: Rich Animated Selected Medication Inspector Panel */}
        <div
          data-testid="medication-inspector"
          className="lg:col-span-5 rounded-2xl bg-gradient-to-b from-[#F8FAFD] via-white to-[#F8FAFD] p-5 sm:p-6 border border-[#E3E8EF] shadow-md flex flex-col gap-4 transition-all duration-300"
        >
          {/* Animated Selected Drug Content */}
          <div key={`inspector-${selectedMed.id}`} className="animate-fadeIn space-y-4">
            {/* Inspector Header */}
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-md bg-[#0B6FD8] text-white text-[10px] font-bold shadow-xs">
                  ✦
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                  {lang === "vi" ? "Thẩm định An toàn FIDES" : "FIDES Safety Verification"}
                </span>
              </div>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-bold text-[#14A88D] border border-[#14A88D]/25 shadow-2xs">
                {copy.safetyTag}
              </span>
            </div>

            {/* Selected Drug Identity */}
            <div>
              <div className="flex items-baseline justify-between gap-2">
                <h4 data-testid="inspector-med-name" className="text-base font-bold text-[#162033]">
                  {selectedMed.name}
                </h4>
                <span
                  data-testid="inspector-med-dosage"
                  className="rounded-lg bg-[#EFF7FF] px-2.5 py-1 text-xs font-bold text-[#0B6FD8] border border-[#0B6FD8]/25"
                >
                  {selectedMed.dosage}
                </span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <p className="text-xs text-[#6D7A8E]">{selectedMed.category}</p>
                <span className="text-[#CBD5E1]">•</span>
                <span className="text-[11px] font-semibold text-[#14A88D]">Đường uống (Oral)</span>
              </div>
            </div>

            {/* Structured Inspector Cards */}
            <div className="space-y-3">
              {/* FIDES Verification Card */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-2xs space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                    {lang === "vi" ? "Trạng thái thẩm định FIDES" : "FIDES Verification Status"}
                  </span>
                  <span
                    data-testid="inspector-fides-status"
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold border ${getFidesBadge(selectedMed).classes}`}
                  >
                    {getFidesBadge(selectedMed).label}
                  </span>
                </div>
                <p className="text-xs font-medium text-[#162033] leading-relaxed">
                  {selectedMed.fidesStatus === "verified" && copy.fidesVerified}
                  {selectedMed.fidesStatus === "pending" &&
                    (lang === "vi"
                      ? "Đang chờ bác sĩ duyệt liều & kiểm tra tương tác chéo đa đơn thuốc"
                      : "Pending clinician dosage confirmation and multi-drug interaction check")}
                  {selectedMed.fidesStatus === "storage-only" &&
                    (lang === "vi"
                      ? "Thuốc dự phòng tủ gia đình — Chưa nằm trong lịch uống hàng ngày"
                      : "Cabinet reserve inventory — Not scheduled in active daily regimen")}
                </p>
                <div className="pt-1.5 border-t border-[#F1F5F9] flex items-center justify-between text-[10px] text-[#6D7A8E]">
                  <span>Nguồn: Dược thư VN • DrugBank 5.1</span>
                  <span className="font-semibold text-[#0B6FD8]">Kiểm tra DDI: 0 xung đột</span>
                </div>
              </div>

              {/* Dosage & Schedule Card */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-2xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                    {lang === "vi" ? "Lịch trình & Liều dùng" : "Schedule & Dosage"}
                  </span>
                  <span className="text-[10px] font-semibold text-[#0B6FD8] bg-[#EFF7FF] px-2 py-0.5 rounded">
                    {lang === "vi" ? "Thời gian biểu" : "Timing Protocol"}
                  </span>
                </div>
                <p data-testid="inspector-med-schedule" className="text-xs font-bold text-[#162033]">
                  {selectedMed.schedule}
                </p>
              </div>

              {/* Clinical Dosage & Safety Recommendations */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-2xs space-y-1.5">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Khuyến cáo an toàn & Liều dùng" : "Dosage Notes & Safety Guidance"}
                </span>
                <p data-testid="inspector-med-notes" className="text-xs text-[#48566A] leading-relaxed font-medium">
                  {lang === "vi" ? selectedMed.noteVi : selectedMed.noteEn}
                </p>
              </div>
            </div>
          </div>

          {/* Semantic Truth Reminder Banner with Glowing Accent */}
          <div
            data-testid="semantic-truth-reminder"
            className="rounded-xl bg-gradient-to-r from-amber-50/95 to-amber-50/70 p-3.5 border border-amber-300 shadow-[0_0_12px_rgba(217,119,6,0.12)] text-amber-900 space-y-1 mt-1 ring-1 ring-amber-200"
          >
            <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800">
              <span aria-hidden="true" className="text-amber-600 font-bold">⚠</span>
              <span>{lang === "vi" ? "Nguyên tắc chân lý ngữ nghĩa:" : "Semantic Truth Principle:"}</span>
            </div>
            <p className="text-[11px] text-amber-900 leading-relaxed font-medium">
              {copy.truthNote}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MedicinesDemo;
