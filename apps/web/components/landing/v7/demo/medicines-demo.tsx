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
 * 1. Categorized tabs: Đang dùng (Current), Cần xác nhận (Needs review), Kiểm tra an toàn FIDES (Safety), Tủ thuốc (Cabinet).
 * 2. List of medications with visual status pills & FIDES verification labels.
 * 3. Right inspector for selected medication with FIDES safety verification, schedule & dosage notes.
 * 4. Semantic truth reminder: "Tủ thuốc lưu trữ ≠ Thuốc đang uống hàng ngày." (Cabinet != Active intake).
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
          classes: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20",
        };
      case "needs-confirmation":
        return {
          label: lang === "vi" ? "⚠ Cần xác nhận" : "⚠ Needs Review",
          classes: "bg-amber-50 text-amber-700 border-amber-200",
        };
      case "cabinet":
        return {
          label: lang === "vi" ? "☖ Tủ thuốc" : "☖ Cabinet",
          classes: "bg-slate-100 text-slate-600 border-slate-200",
        };
    }
  };

  const getFidesBadge = (med: V7DemoMedicine) => {
    switch (med.fidesStatus) {
      case "verified":
        return {
          label: lang === "vi" ? "FIDES: Đã xác thực" : "FIDES: Verified",
          classes: "bg-emerald-50 text-emerald-700 border-emerald-200",
        };
      case "pending":
        return {
          label: lang === "vi" ? "FIDES: Chờ duyệt" : "FIDES: Pending",
          classes: "bg-amber-50 text-amber-700 border-amber-200",
        };
      case "storage-only":
        return {
          label: lang === "vi" ? "FIDES: Chỉ lưu trữ" : "FIDES: Storage Only",
          classes: "bg-slate-50 text-slate-500 border-slate-200",
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
      className={`clara-product-surface relative w-full overflow-hidden p-6 sm:p-8 lg:p-10 ${className}`}
    >
      {/* Workspace Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E3E8EF] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-[#162033]">
              {lang === "vi" ? "Không gian Quản lý Thuốc Thống nhất" : "Unified Medication Workspace"}
            </h3>
            <span className="rounded-full bg-[#ECFDF8] px-2.5 py-0.5 text-xs font-semibold text-[#14A88D] border border-[#14A88D]/20">
              CareGuard Engine
            </span>
          </div>
          <p className="text-xs text-[#6D7A8E] mt-0.5">
            {lang === "vi"
              ? "Phân tầng chính xác trạng thái sử dụng thực tế & kiểm soát an toàn đa tầng"
              : "Strict state distinction across active intake, confirmation queues, and safety verification"}
          </p>
        </div>

        {/* Tab Switcher */}
        <div
          className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-[#F1F5F9] p-1 border border-[#E3E8EF]"
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
            data-testid="tab-needs-confirmation"
            id="tab-needs-confirmation-btn"
            aria-selected={activeTab === "needs-confirmation"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("needs-confirmation")}
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
            data-testid="tab-safety"
            id="tab-safety-btn"
            aria-selected={activeTab === "safety"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("safety")}
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
            data-testid="tab-cabinet"
            id="tab-cabinet-btn"
            aria-selected={activeTab === "cabinet"}
            aria-controls="medicines-tabpanel"
            onClick={() => handleTabChange("cabinet")}
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
      <div
        id="medicines-tabpanel"
        role="tabpanel"
        aria-labelledby={`tab-${activeTab}-btn`}
        className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start"
      >
        {/* Left Column: Medication List with Status Pills */}
        <div className="lg:col-span-7 space-y-3" data-testid="medications-list">
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
                className={`w-full flex items-start justify-between gap-4 rounded-2xl p-4 text-left transition-all border clara-focus-ring ${
                  isSelected
                    ? "bg-[#EFF7FF] border-[#0B6FD8] shadow-sm ring-1 ring-[#0B6FD8]/20"
                    : "bg-white border-[#E3E8EF] hover:border-[#D5DDE7] hover:bg-[#F8FAFD]"
                }`}
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-sm text-[#162033] tracking-tight">{med.name}</span>
                    <span className="rounded-md bg-[#F1F5F9] px-2 py-0.5 text-xs font-semibold text-[#48566A]">
                      {med.dosage}
                    </span>
                  </div>
                  <p className="text-xs text-[#6D7A8E] truncate">{med.category}</p>
                  <p className="text-xs text-[#48566A] font-medium pt-0.5">{med.schedule}</p>
                </div>

                <div className="flex flex-col items-end gap-1.5 shrink-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      data-testid={`status-pill-${med.id}`}
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold border ${statusPill.classes}`}
                    >
                      {statusPill.label}
                    </span>
                  </div>
                  <span
                    data-testid={`fides-pill-${med.id}`}
                    className={`rounded-md px-2 py-0.5 text-[10px] font-medium border ${fidesPill.classes}`}
                  >
                    {fidesPill.label}
                  </span>
                  <span className="text-[10px] text-[#6D7A8E] pt-0.5">
                    {lang === "vi" ? "Nhấp để thẩm định →" : "Click to inspect →"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Right Column: Selected Medication Inspector & Safety Matrix */}
        <div
          data-testid="medication-inspector"
          className="lg:col-span-5 rounded-2xl bg-[#F8FAFD] p-5 border border-[#E3E8EF] flex flex-col gap-4"
        >
          <div>
            {/* Inspector Header */}
            <div className="flex items-center justify-between border-b border-[#E3E8EF] pb-3 mb-4">
              <span className="text-xs font-bold uppercase tracking-wider text-[#0B6FD8]">
                {lang === "vi" ? "Thẩm định An toàn FIDES" : "FIDES Safety Verification"}
              </span>
              <span className="rounded-full bg-white px-2.5 py-0.5 text-[11px] font-bold text-[#14A88D] border border-[#14A88D]/20 shadow-xs">
                {copy.safetyTag}
              </span>
            </div>

            {/* Selected Drug Identity */}
            <div className="mb-4">
              <div className="flex items-baseline justify-between gap-2">
                <h4 data-testid="inspector-med-name" className="text-base font-bold text-[#162033]">
                  {selectedMed.name}
                </h4>
                <span data-testid="inspector-med-dosage" className="text-sm font-semibold text-[#0B6FD8]">
                  {selectedMed.dosage}
                </span>
              </div>
              <p className="text-xs text-[#6D7A8E] mt-0.5">{selectedMed.category}</p>
            </div>

            {/* Structured Inspector Cards */}
            <div className="space-y-3">
              {/* FIDES Verification Card */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                    {lang === "vi" ? "Trạng thái thẩm định FIDES" : "FIDES Verification Status"}
                  </span>
                  <span
                    data-testid="inspector-fides-status"
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold border ${getFidesBadge(selectedMed).classes}`}
                  >
                    {getFidesBadge(selectedMed).label}
                  </span>
                </div>
                <p className="text-xs font-medium text-[#162033]">
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
              </div>

              {/* Dosage & Schedule Card */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Lịch trình & Liều dùng" : "Schedule & Dosage"}
                </span>
                <p data-testid="inspector-med-schedule" className="text-xs font-semibold text-[#162033]">
                  {selectedMed.schedule}
                </p>
              </div>

              {/* Clinical Dosage & Safety Recommendations */}
              <div className="rounded-xl bg-white p-3.5 border border-[#E3E8EF] shadow-xs space-y-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
                  {lang === "vi" ? "Khuyến cáo an toàn & Liều dùng" : "Dosage Notes & Safety Guidance"}
                </span>
                <p data-testid="inspector-med-notes" className="text-xs text-[#48566A] leading-relaxed">
                  {lang === "vi" ? selectedMed.noteVi : selectedMed.noteEn}
                </p>
              </div>
            </div>
          </div>

          {/* Semantic Truth Reminder Banner */}
          <div
            data-testid="semantic-truth-reminder"
            className="rounded-xl bg-amber-50/80 p-3 border border-amber-200/80 text-amber-900 space-y-1 mt-1"
          >
            <div className="flex items-center gap-1.5 font-bold text-xs text-amber-800">
              <span aria-hidden="true">⚠</span>
              <span>{lang === "vi" ? "Nguyên tắc chân lý ngữ nghĩa:" : "Semantic Truth Principle:"}</span>
            </div>
            <p className="text-[11px] text-amber-900/90 leading-tight">
              {copy.truthNote}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MedicinesDemo;
