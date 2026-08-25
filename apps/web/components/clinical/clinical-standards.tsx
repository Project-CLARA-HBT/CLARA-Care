"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import Icon, { type IconName } from "@/components/ui/icon";
import { Badge } from "@/components/ui/badge";
import { StatusChip } from "@/components/ui/status-chip";
import Button from "@/components/ui/button";
import { useUILanguage } from "@/lib/use-ui-language";
import { formatLocaleDate } from "@/lib/i18n/catalog";

interface StandardSectionMeta {
  id: string;
  titleVi: string;
  titleEn: string;
  badgeVi: string;
  badgeEn: string;
  icon: IconName;
}

const STANDARD_SECTIONS: StandardSectionMeta[] = [
  {
    id: "cdss-overview",
    titleVi: "1. Kiến trúc Hệ thống Hỗ trợ Quyết định Lâm sàng (CDSS)",
    titleEn: "1. Clinical Decision Support System (CDSS) Architecture",
    badgeVi: "CDSS Cốt lõi",
    badgeEn: "Core CDSS",
    icon: "clinical-notes",
  },
  {
    id: "ai-council",
    titleVi: "2. Điều phối Hội đồng Chuyên khoa AI (5 Chuyên khoa)",
    titleEn: "2. Multi-Specialist AI Council Orchestration (5 Specialties)",
    badgeVi: "Hội đồng AI",
    badgeEn: "AI Council",
    icon: "progress",
  },
  {
    id: "ambient-scribe",
    titleVi: "3. Trợ lý Ghi chép Ambient Scribe, SOAP & Ký số Điện tử",
    titleEn: "3. Ambient Clinical Scribe, SOAP Structuring & Electronic Signature",
    badgeVi: "SOAP & Ký số",
    badgeEn: "SOAP & E-Sign",
    icon: "clinical-notes",
  },
  {
    id: "glhs-evidence",
    titleVi: "4. Đồ thị Tri thức GLHS & Tích hợp Living Evidence",
    titleEn: "4. GLHS Knowledge Graph & Living Evidence Pipeline",
    badgeVi: "GLHS & Y văn",
    badgeEn: "GLHS & Evidence",
    icon: "progress",
  },
  {
    id: "ddi-renal-safety",
    titleVi: "5. Kiểm tra Tương tác thuốc (DDI) & Chỉnh liều Thận eGFR",
    titleEn: "5. Drug-Drug Interactions (DDI) & Renal Clearance eGFR Protocols",
    badgeVi: "Dược lý & eGFR",
    badgeEn: "Rx & Renal",
    icon: "medication",
  },
  {
    id: "legal-guardrails",
    titleVi: "6. Ranh giới Pháp lý theo Luật Khám bệnh, chữa bệnh 2023",
    titleEn: "6. Legal Boundaries & Vietnam Medical Law 2023 Compliance",
    badgeVi: "Luật KBCB 2023",
    badgeEn: "Law Compliance",
    icon: "warning",
  },
  {
    id: "fides-verification",
    titleVi: "7. Giao thức Xác thực Y khoa FIDES & Quy tắc Hard-Veto",
    titleEn: "7. FIDES Medical Verification Protocols & Hard-Veto Rule",
    badgeVi: "FIDES Hard-Veto",
    badgeEn: "FIDES Hard-Veto",
    icon: "check",
  },
  {
    id: "zero-cot-privacy",
    titleVi: "8. Bảo mật Dòng Suy luận Zero-CoT & Chuẩn Zero-PII",
    titleEn: "8. Zero-CoT Reasoning Stream Privacy & Zero-PII Guarantees",
    badgeVi: "Zero-CoT & PII",
    badgeEn: "Zero-CoT Privacy",
    icon: "warning",
  },
];

export function ClinicalStandards({ className = "" }: { className?: string }) {
  const uiLanguage = useUILanguage();
  const [activeSection, setActiveSection] = useState<string>("cdss-overview");
  const [manualLang, setManualLang] = useState<"vi" | "en" | null>(null);

  const lang = manualLang ?? uiLanguage;
  const isVi = lang === "vi";

  const copy = useCallback(
    (viText: string, enText: string) => (isVi ? viText : enText),
    [isVi],
  );

  const scrollToSection = (id: string) => {
    setActiveSection(id);
    const element = document.getElementById(id);
    if (element) {
      const yOffset = -90;
      const y = element.getBoundingClientRect().top + window.pageYOffset + yOffset;
      window.scrollTo({ top: y, behavior: "smooth" });
    }
  };

  return (
    <div className={`space-y-8 ${className}`.trim()} data-testid="clinical-standards-view">
      {/* Top Banner & Header */}
      <header className="rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2 max-w-4xl">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--brand-primary)]/30 bg-[color:var(--surface-brand-soft)] px-3 py-1 text-xs font-bold uppercase tracking-wider text-[color:var(--text-brand)]">
                <Icon name="clinical-notes" size={13} />
                {copy("ĐẶC TẢ TIÊU CHUẨN LÂM SÀNG", "CLINICAL STANDARDS SPECIFICATION")}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-semibold text-emerald-400">
                <Icon name="check" size={12} />
                {copy("Luật KBCB 15/2023/QH15", "Vietnam Medical Law 2023")}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-0.5 text-xs font-semibold text-purple-300">
                {copy("FIDES Lite v1.2 Hard-Veto", "FIDES Lite v1.2 Hard-Veto")}
              </span>
              <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 text-xs font-semibold text-sky-300">
                {copy("Zero-CoT Privacy", "Zero-CoT Privacy")}
              </span>
            </div>

            <h1 className="text-2xl font-black tracking-tight text-[var(--text-primary)] sm:text-3xl lg:text-4xl">
              {copy(
                "Tiêu chuẩn Lâm sàng & Giao thức An toàn Y tế CLARA",
                "CLARA Clinical Standards & Medical Safety Protocols",
              )}
            </h1>

            <p className="text-sm leading-relaxed text-[var(--text-secondary)] sm:text-base">
              {copy(
                "Tài liệu quy chuẩn y khoa và kiến trúc kỹ thuật dành cho Bác sĩ, Dược sĩ lâm sàng, Hội đồng Chuyên môn và Nhà nghiên cứu y sinh. Xác lập ranh giới an toàn tuyệt đối, quy trình hội đồng AI đa chuyên khoa, cơ chế ghi chép SOAP ký số, kiểm chứng DDI/eGFR và nguyên tắc phủ quyết Hard-Veto.",
                "Authoritative clinical standards and technical architecture specification for Physicians, Clinical Pharmacists, Medical Boards, and Biomedical Researchers. Establishes absolute safety invariants, multi-specialty AI council protocols, SOAP e-signatures, DDI/eGFR checks, and FIDES Hard-Veto rules.",
              )}
            </p>
          </div>

          {/* Quick Actions & Language Toggle */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <div className="inline-flex rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] p-0.5">
              <button
                type="button"
                onClick={() => setManualLang("vi")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition ${
                  isVi
                    ? "bg-[color:var(--surface-panel)] text-[var(--text-brand)] shadow-xs"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                Tiếng Việt
              </button>
              <button
                type="button"
                onClick={() => setManualLang("en")}
                className={`px-3 py-1 text-xs font-bold rounded-md transition ${
                  !isVi
                    ? "bg-[color:var(--surface-panel)] text-[var(--text-brand)] shadow-xs"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                }`}
              >
                English
              </button>
            </div>

            <Link
              href="/clinical/overview"
              className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] hover:bg-[color:var(--surface-panel)] transition"
            >
              <Icon name="arrow-left" size={13} />
              <span>{copy("Bàn điều phối", "Command Center")}</span>
            </Link>

            <Link
              href="/council/new"
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--brand-600)] px-3.5 py-1.5 text-xs font-semibold text-[var(--on-secondary-container)] shadow-xs transition hover:bg-[var(--brand-700)] active:scale-95"
            >
              <Icon name="plus" size={13} />
              <span>{copy("Tạo ca hội chẩn", "Launch Council")}</span>
            </Link>
          </div>
        </div>

        {/* High-density KPI Ribbon */}
        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5 border-t border-[color:var(--shell-border)]/60 pt-5">
          <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/50 p-3">
            <div className="text-[11px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
              {copy("Hội đồng Chuyên khoa", "AI Council")}
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-[var(--text-primary)]">5</span>
              <span className="text-xs text-[var(--text-secondary)]">{copy("Chuyên khoa song song", "Parallel agents")}</span>
            </div>
          </div>

          <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-3">
            <div className="text-[11px] font-semibold text-purple-300 uppercase tracking-wider">
              {copy("Xác thực FIDES", "FIDES Protocol")}
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-purple-300">7-Tier</span>
              <span className="text-xs text-purple-200/80">{copy("Factuality Matrix", "Matrix Engine")}</span>
            </div>
          </div>

          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3">
            <div className="text-[11px] font-semibold text-red-300 uppercase tracking-wider">
              {copy("Quy tắc Phủ quyết", "Hard-Veto Rule")}
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-red-400">100%</span>
              <span className="text-xs text-red-300/80">{copy("Chặn liều không căn cứ", "Zero ungrounded rx")}</span>
            </div>
          </div>

          <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-3">
            <div className="text-[11px] font-semibold text-sky-300 uppercase tracking-wider">
              {copy("Bảo mật Suy luận", "Zero-CoT Privacy")}
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-sky-300">0 Leak</span>
              <span className="text-xs text-sky-200/80">{copy("Triệt tiêu thẻ <think>", "Regex stream filter")}</span>
            </div>
          </div>

          <div className="col-span-2 sm:col-span-4 lg:col-span-1 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
            <div className="text-[11px] font-semibold text-emerald-300 uppercase tracking-wider">
              {copy("Pháp lý KBCB 2023", "CDSS Governance")}
            </div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-xl font-bold text-emerald-400">Level 3/4</span>
              <span className="text-xs text-emerald-300/80">{copy("Bác sĩ chịu trách nhiệm", "Clinician in loop")}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Layout: Sticky Sidebar Index + Deep Documentation Content */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Sticky Table of Contents Navigation Rail */}
        <aside className="lg:col-span-4 xl:col-span-3">
          <nav
            aria-label={copy("Mục lục tiêu chuẩn", "Standards Table of Contents")}
            className="sticky top-20 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-4 shadow-xs space-y-2"
          >
            <div className="flex items-center justify-between border-b border-[color:var(--shell-border)]/60 pb-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">
                {copy("MỤC LỤC ĐẶC TẢ LÂM SÀNG", "SPECIFICATION INDEX")}
              </span>
              <span className="text-[11px] font-mono text-[var(--text-brand)]">v2026.8</span>
            </div>

            <ul className="space-y-1 pt-1 text-xs">
              {STANDARD_SECTIONS.map((sec) => {
                const isSelected = activeSection === sec.id;
                return (
                  <li key={sec.id}>
                    <button
                      type="button"
                      onClick={() => scrollToSection(sec.id)}
                      className={`w-full text-left flex items-start gap-2.5 rounded-lg px-3 py-2 transition-colors ${
                        isSelected
                          ? "bg-[var(--surface-brand-soft)] font-bold text-[var(--text-brand)]"
                          : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] font-medium"
                      }`}
                    >
                      <Icon name={sec.icon} size={14} className="mt-0.5 shrink-0" />
                      <span className="leading-snug">
                        {isVi ? sec.titleVi : sec.titleEn}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="border-t border-[color:var(--shell-border)]/60 pt-3 text-[11px] text-[var(--text-muted)] space-y-1">
              <p>
                <strong>{copy("Cơ quan thẩm định:", "Governance:")}</strong> {copy("Hội đồng Chuyên môn CLARA & Bộ Y tế", "CLARA Clinical Board & Vietnam MoH")}
              </p>
              <p>
                <strong>{copy("Hiệu lực:", "Effective:")}</strong> 2026-2027 • ISO/IEC 42001 & HL7 FHIR R4
              </p>
            </div>
          </nav>
        </aside>

        {/* Deep Content Body */}
        <main className="space-y-12 lg:col-span-8 xl:col-span-9">
          {/* SECTION 1: CDSS Overview */}
          <section
            id="cdss-overview"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                  <Icon name="clinical-notes" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("1. Kiến trúc Hệ thống Hỗ trợ Quyết định Lâm sàng (CDSS)", "1. Clinical Decision Support System (CDSS) Architecture")}
                </h2>
              </div>
              <Badge tone="brand">{copy("CDSS Cốt lõi", "Core CDSS")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "CLARA được xây dựng theo định dạng Hệ thống Hỗ trợ Quyết định Lâm sàng Cấp độ 3/4 (CDSS - Clinical Decision Support System), hoạt động như một trợ lý y sinh cho bác sĩ và chuyên viên y tế tại điểm khám (Point of Care). Hệ thống KHÔNG tự động ban hành y lệnh điều trị hoặc chẩn đoán độc lập, mà tổng hợp và đối chiếu đa nguồn y văn để tối ưu hóa quyết định của bác sĩ.",
                  "CLARA is architected as a Level 3/4 Clinical Decision Support System (CDSS), functioning as a biomedical assistant for clinicians at the Point of Care. The system DOES NOT autonomously issue medical orders or execute unverified independent diagnoses; instead, it synthesizes and cross-references multi-source literature to optimize clinician decision-making.",
                )}
              </p>

              {/* CDSS Assistive vs Autonomous Table */}
              <div className="overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)]/50">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)] font-bold">
                      <th className="p-3">{copy("Tiêu chí Đánh giá", "Evaluation Criteria")}</th>
                      <th className="p-3 text-amber-300">{copy("Hệ thống AI Tự trị (Không cho phép)", "Autonomous AI (Disallowed)")}</th>
                      <th className="p-3 text-emerald-400">{copy("CLARA Assistive CDSS (Chuẩn hóa)", "CLARA Assistive CDSS (Standard)")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]/50">
                    <tr>
                      <td className="p-3 font-semibold text-[var(--text-primary)]">{copy("Chẩn đoán lâm sàng", "Diagnosis")}</td>
                      <td className="p-3 text-amber-200/80">{copy("Tự ý khẳng định bệnh tật mà không có bác sĩ", "Direct diagnosis without human review")}</td>
                      <td className="p-3 text-emerald-300 font-medium">{copy("Gợi ý chẩn đoán phân biệt kèm xác suất và y văn đối chứng", "Differential diagnosis suggestions with confidence calibration")}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-[var(--text-primary)]">{copy("Kê đơn & Chỉnh liều", "Prescribing & Dosage")}</td>
                      <td className="p-3 text-amber-200/80">{copy("Tự phát hành đơn thuốc độc lập", "Direct issuance of prescriptions")}</td>
                      <td className="p-3 text-emerald-300 font-medium">{copy("Tính toán liều dựa trên eGFR/cân nặng và cảnh báo DDI trước khi bác sĩ ký số", "eGFR-based dosage calculation & DDI preflights requiring physician signature")}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-semibold text-[var(--text-primary)]">{copy("Trách nhiệm pháp lý", "Legal Accountability")}</td>
                      <td className="p-3 text-amber-200/80">{copy("Thiếu chủ thể hành nghề có chứng chỉ", "Lack of licensed practitioner")}</td>
                      <td className="p-3 text-emerald-300 font-medium">{copy("Bác sĩ điều trị giữ toàn quyền và chịu trách nhiệm chuyên môn (Luật KBCB 2023)", "Attending physician maintains full legal & clinical authority")}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* SECTION 2: Multi-Specialist AI Council Orchestration */}
          <section
            id="ai-council"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                  <Icon name="progress" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("2. Điều phối Hội đồng Chuyên khoa AI (Multi-Specialist AI Council)", "2. Multi-Specialist AI Council Orchestration")}
                </h2>
              </div>
              <Badge tone="warn">{copy("5 Chuyên khoa Song song", "5 Parallel Specialists")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "Hội đồng AI (CLARA Council) vận hành bằng cách khởi tạo 5 Agent chuyên khoa độc lập chạy song song qua kiến trúc ThreadPoolExecutor, đánh giá ca bệnh từ 5 góc nhìn chuyên sâu và tự động phát hiện các bất đồng thuận (divergence) trước khi tổng hợp thành khuyến nghị thống nhất:",
                  "The CLARA AI Council operates by launching 5 parallel specialist agents via a ThreadPoolExecutor architecture, evaluating the case across 5 distinct domains and automatically detecting divergences before synthesizing a consensus recommendation:",
                )}
              </p>

              {/* 5 Specialists Grid */}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-rose-400 font-bold text-xs uppercase tracking-wide">
                    <Icon name="warning" size={14} />
                    <span>Cardiology • {copy("Tim mạch", "Cardiology")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Phân tích huyết động, Troponin, ECG, nguy cơ hội chứng vành cấp (ACS) và suy tim NYHA.", "Hemodynamics, Troponin, ECG, ACS risk, and NYHA heart failure staging.")}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-blue-400 font-bold text-xs uppercase tracking-wide">
                    <Icon name="progress" size={14} />
                    <span>Neurology • {copy("Thần kinh", "Neurology")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Tầm soát đột quỵ FAST, thang điểm NIHSS, thiếu máu não cục bộ thoáng qua (TIA) và thần kinh sọ.", "Stroke FAST screening, NIHSS grading, TIA alerts, and cranial neuropathy.")}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-amber-400 font-bold text-xs uppercase tracking-wide">
                    <Icon name="clinical-notes" size={14} />
                    <span>Nephrology • {copy("Thận học", "Nephrology")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Độ lọc cầu thận eGFR CKD-EPI, tổn thương thận cấp AKI (KDIGO), cân bằng điện giải và protein niệu.", "eGFR CKD-EPI clearance, KDIGO AKI staging, electrolytes, and proteinuria.")}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-xs uppercase tracking-wide">
                    <Icon name="medication" size={14} />
                    <span>Pharmacology • {copy("Dược lý học", "Pharmacology")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Dược động học PK/PD, tương tác thuốc CYP450, thải trừ qua gan/thận và liều điều trị TDM.", "PK/PD kinetics, CYP450 interactions, organ clearance, and TDM limits.")}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)]/60 p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase tracking-wide">
                    <Icon name="calendar" size={14} />
                    <span>Endocrinology • {copy("Nội tiết", "Endocrinology")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)]">
                    {copy("Biến thiên đường huyết, HbA1c, nguy cơ nhiễm toan DKA và chỉnh liều insulin / SGLT2i / GLP-1.", "Glycemic variability, HbA1c targets, DKA prevention, and insulin / SGLT2i adjustments.")}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] p-4 space-y-1.5">
                  <div className="flex items-center gap-2 text-[var(--text-brand)] font-bold text-xs uppercase tracking-wide">
                    <Icon name="check" size={14} />
                    <span>Divergence Engine • {copy("Phát hiện bất đồng", "Conflict Detection")}</span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("Tự động phân giải xung đột chỉ định giữa các chuyên khoa (vd: chống đông Tim mạch vs nguy cơ xuất huyết Thần kinh).", "Auto-reconciles therapeutic conflicts between specialties (e.g. anticoagulation vs bleed risk).")}
                  </p>
                </div>
              </div>

              {/* Mandatory Clinician Review Safety Directive */}
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-1 text-xs text-amber-200">
                <div className="font-bold flex items-center gap-1.5 text-amber-300">
                  <Icon name="warning" size={14} />
                  {copy("Chỉ thị Rà soát Lâm sàng Bắt buộc (Safety Invariant)", "Mandatory Clinician-Review Directive (Safety Invariant)")}
                </div>
                <p className="leading-relaxed">
                  &ldquo;{copy(
                    "Kết quả này là thông tin hỗ trợ quyết định, không thay thế chẩn đoán hay điều trị y khoa. Vui lòng rà soát cùng bác sĩ có chuyên môn (licensed clinician) trước khi đưa ra quyết định lâm sàng.",
                    "This is decision-support information and does not replace medical diagnosis or treatment; review it with a licensed clinician before acting.",
                  )}&rdquo;
                </p>
              </div>
            </div>
          </section>

          {/* SECTION 3: Ambient Clinical Scribe & SOAP & E-Sign */}
          <section
            id="ambient-scribe"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                  <Icon name="clinical-notes" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("3. Trợ lý Ghi chép Ambient Scribe, SOAP & Ký số Điện tử", "3. Ambient Clinical Scribe, SOAP Structuring & Electronic Signatures")}
                </h2>
              </div>
              <Badge tone="ok">{copy("Chuẩn SOAP & Ký số", "SOAP & E-Signature")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "CLARA Ambient Scribe lắng nghe và chuyển âm trực tiếp cuộc hội thoại khám bệnh giữa bác sĩ và bệnh nhân bằng engine Faster-Whisper tối ưu hóa riêng cho thuật ngữ y tế tiếng Việt. Bệnh án được tự động phân rã thành cấu trúc chuẩn SOAP 4 thành phần:",
                  "CLARA Ambient Scribe captures clinical dialogues in real-time via a specialized Vietnamese biomedical Faster-Whisper sidecar, automatically structuring the encounter into standard 4-quadrant SOAP documentation:",
                )}
              </p>

              {/* SOAP 4-Quadrant Cards */}
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-4 space-y-1">
                  <div className="font-bold text-sky-300 text-xs uppercase tracking-wide">
                    S • Subjective ({copy("Bệnh sử & Triệu chứng chủ quan", "Subjective History")})
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("Lý do đến khám (Chief Complaint), bệnh sử chi tiết (HPI), thời điểm khởi phát, mức độ đau (VAS scale) và tiền sử gia đình/dị ứng.", "Chief complaint, HPI timeline, onset, pain intensity scale, family history, and patient-reported symptoms.")}
                  </p>
                </div>

                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-1">
                  <div className="font-bold text-emerald-300 text-xs uppercase tracking-wide">
                    O • Objective ({copy("Khám thực thể & Cận lâm sàng", "Objective Findings")})
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("Chỉ số sinh hiệu (HA, HR, SpO2, Temp, RR), khám lâm sàng các cơ quan và kết quả xét nghiệm/hình ảnh học (X-quang, CT, siêu âm).", "Vital signs snapshot (BP, HR, SpO2, Temp, RR), physical exam findings, and lab/imaging reports.")}
                  </p>
                </div>

                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 space-y-1">
                  <div className="font-bold text-amber-300 text-xs uppercase tracking-wide">
                    A • Assessment ({copy("Đánh giá lâm sàng & Chẩn đoán phân biệt", "Clinical Assessment")})
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("Chẩn đoán sơ bộ, danh sách chẩn đoán phân biệt xếp hạng theo xác suất, phân tầng mức độ nguy cơ (Đỏ/Cam/Vàng/Xanh).", "Preliminary impression, differential diagnosis rankings, severity tiering (Red/Amber/Yellow/Green).")}
                  </p>
                </div>

                <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-4 space-y-1">
                  <div className="font-bold text-purple-300 text-xs uppercase tracking-wide">
                    P • Plan ({copy("Kế hoạch điều trị & Theo dõi", "Therapeutic Plan")})
                  </div>
                  <p className="text-xs text-[var(--text-secondary)]">
                    {copy("Phác đồ thuốc (tên thuốc, hàm lượng, liều dùng, số lần), chỉ định cận lâm sàng bổ sung, tư vấn dinh dưỡng và lịch hẹn tái khám.", "Medication regimen with dosage, additional diagnostic workup orders, patient counseling, and follow-up timeline.")}
                  </p>
                </div>
              </div>

              {/* Electronic Signature & Consent Protocol */}
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 space-y-2 text-xs">
                <div className="font-bold text-[var(--text-primary)] flex items-center gap-1.5">
                  <Icon name="check" size={14} className="text-emerald-400" />
                  {copy("Quy trình Ký số & Khóa Bệnh án Điện tử (Electronic Signature Protocol)", "Electronic Signature & Tamper-Evident Medical Record Protocol")}
                </div>
                <ul className="list-disc pl-5 space-y-1 text-[var(--text-secondary)]">
                  <li>
                    <strong>{copy("Bắt buộc đồng thuận:", "Consent Gate:")}</strong> {copy("Phải có xác nhận đồng thuận (bằng lời nói hoặc văn bản) trước khi kích hoạt thu âm theo Nghị định 13/2023/NĐ-CP.", "Requires verbal/written patient consent prior to audio capture per Decree 13/2023.")}
                  </li>
                  <li>
                    <strong>{copy("Băm mật mã SHA-256:", "SHA-256 Hashing:")}</strong> {copy("Bệnh án SOAP sau khi bác sĩ rà soát được tạo mã hash SHA-256 bất biến kèm chứng chỉ hành nghề của bác sĩ ký số.", "Finalized SOAP notes receive an immutable SHA-256 cryptographic hash bound to clinician license ID.")}
                  </li>
                  <li>
                    <strong>{copy("Tương thích HL7 / FHIR:", "HL7 / FHIR Interoperability:")}</strong> {copy("Xuất dữ liệu chuẩn FHIR Encounter / DiagnosticReport sang hệ thống HIS/EMR của bệnh viện.", "Exports structured FHIR R4 Encounter & DiagnosticReport resources directly to hospital HIS/EMR.")}
                  </li>
                </ul>
              </div>
            </div>
          </section>

          {/* SECTION 4: GLHS & Living Evidence */}
          <section
            id="glhs-evidence"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400">
                  <Icon name="progress" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("4. Đồ thị Tri thức GLHS & Tích hợp Living Evidence", "4. GLHS Knowledge Graph & Living Evidence Pipeline")}
                </h2>
              </div>
              <Badge tone="neutral">{copy("GLHS v2 & Bằng chứng Sống", "GLHS v2 & Living Evidence")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "Governed Longitudinal Health State (GLHS) là sổ cái trạng thái sức khỏe bất biến (append-only ledger) bảo vệ toàn vẹn lịch sử bệnh lý của bệnh nhân qua nhân kiểm soát giao dịch 6 giai đoạn (6-Phase OCC Kernel) và khóa phân cấp SS2PL chống đọc bóng ma (phantom reads):",
                  "Governed Longitudinal Health State (GLHS) is an immutable, append-only health state ledger that protects patient longitudinal trajectories via a 6-Phase OCC Commit Kernel and SS2PL lock hierarchy preventing phantom reads:",
                )}
              </p>

              {/* Living Evidence Sources Grid */}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-center space-y-1">
                  <div className="font-bold text-xs text-[var(--text-primary)]">{copy("Phác đồ Bộ Y tế", "MoH Guidelines")}</div>
                  <div className="text-[11px] text-[var(--text-muted)]">{copy("Quyết định ban hành chính thức", "Official MoH clinical guidelines")}</div>
                </div>
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-center space-y-1">
                  <div className="font-bold text-xs text-[var(--text-primary)]">{copy("Dược thư Quốc gia VN", "Vietnam Pharmacopoeia")}</div>
                  <div className="text-[11px] text-[var(--text-muted)]">{copy("Dược động & liều chuẩn hóa", "PK/PD & dosage benchmarks")}</div>
                </div>
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-center space-y-1">
                  <div className="font-bold text-xs text-[var(--text-primary)]">{copy("DrugBank v5.1.10", "DrugBank v5.1.10")}</div>
                  <div className="text-[11px] text-[var(--text-muted)]">{copy("Tương tác & cơ chế DDI", "DDI interactions & mechanisms")}</div>
                </div>
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-center space-y-1">
                  <div className="font-bold text-xs text-[var(--text-primary)]">{copy("PubMed & Cochrane", "PubMed & Cochrane")}</div>
                  <div className="text-[11px] text-[var(--text-muted)]">{copy("Thử nghiệm lâm sàng RCTs", "Peer-reviewed systematic RCTs")}</div>
                </div>
              </div>
            </div>
          </section>

          {/* SECTION 5: DDI & Renal eGFR Safety */}
          <section
            id="ddi-renal-safety"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-500/10 text-red-400">
                  <Icon name="medication" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("5. An toàn Tương tác thuốc (DDI) & Chỉnh liều Thận eGFR", "5. Drug-Drug Interactions (DDI) & Renal Clearance eGFR Protocols")}
                </h2>
              </div>
              <Badge tone="danger">{copy("An toàn Dược lý 4 Cấp", "4-Tier Rx Safety")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "Hệ thống kiểm chứng Dược lý đối chiếu danh mục thuốc đang sử dụng với cơ sở dữ liệu DrugBank v5.1.10 và thuật toán lọc cầu thận CKD-EPI 2021 để ngăn ngừa tai biến dùng thuốc:",
                  "The pharmacology engine cross-evaluates active medication regimens against DrugBank v5.1.10 databases and CKD-EPI 2021 eGFR equations to prevent adverse drug events:",
                )}
              </p>

              {/* DDI 4-Tier Severity Table */}
              <div className="overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)]/50">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)] font-bold">
                      <th className="p-3">{copy("Mức độ DDI", "DDI Severity")}</th>
                      <th className="p-3">{copy("Ý nghĩa Lâm sàng", "Clinical Significance")}</th>
                      <th className="p-3">{copy("Hành động Hệ thống", "System Action")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[color:var(--shell-border)]/50">
                    <tr className="bg-red-500/5">
                      <td className="p-3 font-bold text-red-400">
                        <span className="inline-flex items-center gap-1">
                          <Icon name="warning" size={12} />
                          Critical (Đỏ)
                        </span>
                      </td>
                      <td className="p-3 text-[var(--text-primary)]">
                        {copy("Chống chỉ định phối hợp tuyệt đối (vd: Sildenafil + Nitrates gây tụt HA nguy kịch, Clopidogrel + Omeprazole).", "Absolute contraindication (e.g. Sildenafil + Nitrates causing severe hypotension, Clopidogrel + Omeprazole).")}
                      </td>
                      <td className="p-3 font-bold text-red-400">{copy("Hard-Veto CHẶN TOÀN BỘ đơn thuốc", "Hard-Veto BLOCKS prescription")}</td>
                    </tr>
                    <tr className="bg-amber-500/5">
                      <td className="p-3 font-bold text-amber-300">Major (Cam)</td>
                      <td className="p-3 text-[var(--text-primary)]">
                        {copy("Tương tác nghiêm trọng làm tăng độc tính hoặc giảm hiệu lực (vd: Warfarin + NSAIDs tăng xuất huyết).", "Major interaction increasing toxicity or reducing efficacy (e.g. Warfarin + NSAIDs bleeding risk).")}
                      </td>
                      <td className="p-3 font-semibold text-amber-300">{copy("Cảnh báo bắt buộc bác sĩ xác nhận", "Warning requires clinician acknowledgment")}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-bold text-yellow-300">Moderate (Vàng)</td>
                      <td className="p-3 text-[var(--text-primary)]">
                        {copy("Cần theo dõi sát chỉ số lâm sàng hoặc xét nghiệm định kỳ (vd: ACEi + Spironolactone theo dõi Kali máu).", "Requires close monitoring of labs/vitals (e.g. ACEi + Spironolactone monitoring potassium).")}
                      </td>
                      <td className="p-3 text-[var(--text-secondary)]">{copy("Hiển thị khuyến cáo theo dõi", "Displays monitoring recommendation")}</td>
                    </tr>
                    <tr>
                      <td className="p-3 font-bold text-emerald-400">Minor (Xanh)</td>
                      <td className="p-3 text-[var(--text-primary)]">
                        {copy("Tác động dược động học nhẹ, ít ảnh hưởng lâm sàng.", "Minor PK alteration with low clinical impact.")}
                      </td>
                      <td className="p-3 text-[var(--text-muted)]">{copy("Ghi nhận thông tin", "Informational note")}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* eGFR Renal Protocol Box */}
              <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-4 space-y-2 text-xs">
                <div className="font-bold text-sky-300 flex items-center gap-1.5">
                  <Icon name="progress" size={14} />
                  {copy("Giao thức Hiệu chỉnh Liều theo eGFR (Renal Dose Titration)", "eGFR-Based Renal Dose Titration Protocol")}
                </div>
                <div className="grid gap-2 sm:grid-cols-3 text-[var(--text-secondary)]">
                  <div className="rounded-lg bg-[var(--surface-panel)] p-2.5 border border-[color:var(--shell-border)]">
                    <span className="font-bold text-emerald-400">eGFR &gt; 60 mL/min:</span>
                    <p className="mt-0.5">{copy("Dùng liều chuẩn cho hầu hết các thuốc thải qua thận.", "Standard dosing for most renal-cleared medications.")}</p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-panel)] p-2.5 border border-[color:var(--shell-border)]">
                    <span className="font-bold text-amber-300">eGFR 30 - 59 mL/min:</span>
                    <p className="mt-0.5">{copy("Giảm 25-50% liều hoặc giãn khoảng cách dùng (Metformin, DOAC, Kháng sinh).", "Reduce dose by 25-50% or extend interval (Metformin, DOACs, Antibiotics).")}</p>
                  </div>
                  <div className="rounded-lg bg-[var(--surface-panel)] p-2.5 border border-[color:var(--shell-border)]">
                    <span className="font-bold text-red-400">eGFR &lt; 30 mL/min:</span>
                    <p className="mt-0.5">{copy("Chống chỉ định Metformin, SGLT2i bắt đầu mới; cần chỉnh liều nghiêm ngặt theo phác đồ Thận.", "Contraindication for Metformin/new SGLT2i; strict nephrology adjustment required.")}</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* SECTION 6: Legal Guardrails & Law on Medical Examination and Treatment 2023 */}
          <section
            id="legal-guardrails"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400">
                  <Icon name="warning" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("6. Ranh giới Pháp lý theo Luật Khám bệnh, chữa bệnh 2023", "6. Legal Boundaries & Vietnam Medical Law 2023 Compliance")}
                </h2>
              </div>
              <Badge tone="warn">{copy("Luật số 15/2023/QH15", "Law 15/2023/QH15")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "CLARA tuân thủ nghiêm ngặt Luật Khám bệnh, chữa bệnh số 15/2023/QH15 (có hiệu lực từ ngày 01/01/2024), Nghị định 13/2023/NĐ-CP về Bảo vệ Dữ liệu Cá nhân và Luật Trí tuệ Nhân tạo 134/2025/QH15 với các ranh giới bất biến:",
                  "CLARA strictly adheres to the Vietnam Law on Medical Examination and Treatment No. 15/2023/QH15 (effective Jan 1, 2024), Decree 13/2023/ND-CP on Personal Data Protection, and Draft AI Law 134/2025 with invariant boundaries:",
                )}
              </p>

              <div className="space-y-3">
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-1.5 text-xs text-red-200">
                  <div className="font-bold text-red-300 flex items-center gap-1.5 text-sm">
                    <Icon name="warning" size={15} className="text-red-400" />
                    {copy("Điều 1: Khóa cứng Kê đơn & Chẩn đoán Độc lập (Hard Prescribing Guard)", "Article 1: Hard Prescribing & Autonomous Diagnosis Guard")}
                  </div>
                  <p className="leading-relaxed">
                    {copy(
                      "Theo quy định của Luật Khám bệnh, chữa bệnh 2023, chỉ có người hành nghề có Chứng chỉ hành nghề y tế hợp lệ mới có thẩm quyền ra y lệnh khám bệnh, chữa bệnh và kê đơn thuốc. Hệ thống CLARA chủ động CHẶN TOÀN BỘ các câu lệnh yêu cầu kê đơn tự động cho người bệnh hoặc đưa ra chẩn đoán khẳng định mang tính pháp lý mà không qua bác sĩ.",
                      "Under the Vietnam Law on Medical Examination and Treatment 2023, only licensed medical practitioners possess legal authority to issue clinical diagnoses and prescriptions. CLARA hard-blocks all autonomous prescribing prompts and legal diagnostic attributions without physician sign-off.",
                    )}
                  </p>
                </div>

                <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 space-y-1.5 text-xs text-rose-200">
                  <div className="font-bold text-rose-300 flex items-center gap-1.5 text-sm">
                    <Icon name="warning" size={15} className="text-rose-400" />
                    {copy("Điều 2: Luồng Cấp cứu Khẩn cấp Tức thời (Emergency Fast-Path 115)", "Article 2: Emergency Fast-Path 115 Protocol")}
                  </div>
                  <p className="leading-relaxed">
                    {copy(
                      "Khi phát hiện các triệu chứng báo động cấp tính (Đau thắt ngực dữ dội nghi ACS, Dấu hiệu đột quỵ FAST, Khó thở cấp, Mất ý thức, Xuất huyết nặng), hệ thống NGAY LẬP TỨC kích hoạt luồng chuyển hướng cấp cứu 115, bỏ qua bước suy luận chẩn đoán thông thường để bảo toàn tính mạng người bệnh.",
                      "Upon detecting acute red-flag symptoms (Acute chest pain / ACS, Stroke FAST signs, Severe respiratory distress, Loss of consciousness, Severe hemorrhage), the system IMMEDIATELY triggers the 115 emergency escalation path, skipping non-emergency reasoning loops to protect patient life.",
                    )}
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* SECTION 7: FIDES Verification & Hard-Veto Rule */}
          <section
            id="fides-verification"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-500/10 text-purple-400">
                  <Icon name="check" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("7. Giao thức Xác thực Y khoa FIDES & Quy tắc Hard-Veto", "7. FIDES Medical Verification Protocols & Hard-Veto Rule")}
                </h2>
              </div>
              <Badge tone="brand">{copy("FIDES Lite v1.2", "FIDES Lite v1.2")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "FIDES (Factuality & Inference Defense for Evidence-based Synthesis) là bộ kiểm chứng an toàn y tế độc quyền của CLARA, thực hiện phân tách câu trả lời của AI thành từng phát biểu (atomic claims) và xác minh tính đúng đắn qua ma trận 7 tầng:",
                  "FIDES (Factuality & Inference Defense for Evidence-based Synthesis) is CLARA's proprietary medical verification engine, decomposing AI responses into atomic claims and cross-verifying them across a 7-tier verification matrix:",
                )}
              </p>

              {/* 7 Tiers List */}
              <div className="grid gap-2 sm:grid-cols-2 text-xs">
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-[var(--text-brand)]">1. Factuality:</span> {copy("Tính xác thực của các thực thể y học.", "Medical entity truthfulness.")}
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-[var(--text-brand)]">2. Inference Soundness:</span> {copy("Tính chặt chẽ của lập luận.", "Logical deduction integrity.")}
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-red-400">3. Dosage Precision:</span> {copy("Độ chính xác tuyệt đối của liều dùng.", "Dosage precision & units.")}
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-[var(--text-brand)]">4. Evidence Grounding:</span> {copy("Căn cứ y văn và điểm trùng lặp.", "Literature overlap & source refs.")}
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-red-400">5. Contraindications:</span> {copy("Chống chỉ định & tương tác thuốc.", "Contraindications & DDIs.")}
                </div>
                <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-[var(--text-brand)]">6. Guideline Alignment:</span> {copy("Khớp phác đồ Bộ Y tế.", "MoH guideline adherence.")}
                </div>
                <div className="col-span-1 sm:col-span-2 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-2.5">
                  <span className="font-bold text-[var(--text-brand)]">7. Triage Calibration:</span> {copy("Độ nhạy phân tầng cấp cứu khẩn.", "Emergency triage sensitivity calibration.")}
                </div>
              </div>

              {/* The Hard-Veto Invariant Box */}
              <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 space-y-2 text-xs text-red-200">
                <div className="font-bold text-red-300 flex items-center gap-1.5 text-sm">
                  <Icon name="warning" size={15} className="text-red-400" />
                  {copy("QUY TẮC PHỦ QUYẾT TUYỆT ĐỐI (HARD-VETO INVARIANT RULE)", "THE ABSOLUTE HARD-VETO INVARIANT RULE")}
                </div>
                <p className="leading-relaxed">
                  {copy(
                    "Nếu BẤT KỲ phát biểu nào liên quan đến LIỀU DÙNG (dosage), TƯƠNG TÁC THUỐC (interaction) hoặc CHỐNG CHỈ ĐỊNH (contraindication) bị đánh giá là THIẾU CĂN CỨ (insufficient) hoặc MÂU THUẪN (contradicted) với y văn, cơ chế FIDES ngay lập tức kích hoạt HARD-VETO, đánh rớt toàn bộ câu trả lời (Verdict = FAIL, Policy Action = BLOCK), bất kể 100% các câu còn lại đều đúng.",
                    "If ANY claim categorized as DOSAGE, DRUG INTERACTION, or CONTRAINDICATION is evaluated as INSUFFICIENT or CONTRADICTED by evidence, FIDES immediately triggers a HARD-VETO resulting in a complete response block (Verdict = FAIL, Policy Action = BLOCK), regardless of whether 100% of surrounding general claims passed.",
                  )}
                </p>
                <p className="font-mono text-[11px] text-red-300/90 pt-1 border-t border-red-500/30">
                  {copy("Cơ chế Fail-Closed: Nội dung không an toàn bị thu hồi; hệ thống thay thế bằng chỉ dẫn an toàn và khuyến cáo khám chuyên khoa.", "Fail-Closed: Unsafe content is suppressed and replaced with certified clinical escalation text.")}
                </p>
              </div>
            </div>
          </section>

          {/* SECTION 8: Zero-CoT Privacy & Zero-PII */}
          <section
            id="zero-cot-privacy"
            className="scroll-mt-24 rounded-2xl border border-[color:var(--shell-border)] bg-[color:var(--surface-panel)] p-6 sm:p-8 shadow-xs space-y-6"
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[color:var(--shell-border)]/60 pb-4">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/10 text-sky-400">
                  <Icon name="warning" size={16} />
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {copy("8. Bảo mật Dòng Suy luận Zero-CoT & Chuẩn Zero-PII", "8. Zero-CoT Reasoning Stream Privacy & Zero-PII Guarantees")}
                </h2>
              </div>
              <Badge tone="ok">{copy("Bảo mật Zero-CoT", "Zero-CoT Privacy")}</Badge>
            </div>

            <div className="space-y-4 text-sm leading-relaxed text-[var(--text-secondary)]">
              <p>
                {copy(
                  "Để bảo vệ quyền riêng tư tuyệt đối của bệnh nhân và ngăn chặn rò rỉ dữ liệu qua chuỗi suy luận nội bộ của mô hình suy luận lớn (DeepSeek R1 / Reasoning LLMs), CLARA áp dụng kiến trúc lọc dòng suy luận Zero-CoT độc quyền:",
                  "To safeguard patient privacy and prevent data leakage via internal reasoning traces of Large Reasoning Models (DeepSeek R1 / Reasoning LLMs), CLARA enforces proprietary Zero-CoT streaming privacy architecture:",
                )}
              </p>

              <div className="space-y-2.5 text-xs">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 space-y-1">
                  <div className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Icon name="check" size={14} className="text-emerald-400" />
                    {copy("Lọc sạch thẻ <think> theo thời gian thực:", "Real-Time <think> Tag Sanitization:")}
                  </div>
                  <p className="text-[var(--text-secondary)]">
                    {copy(
                      "Toàn bộ chuỗi suy luận thô bên trong thẻ <think>...</think> được bóc tách và triệt tiêu trước khi các chunk SSE được gửi về trình duyệt.",
                      "All internal reasoning tokens within <think>...</think> tags are stripped in real-time before SSE chunks stream to the client browser.",
                    )}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 space-y-1">
                  <div className="font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Icon name="check" size={14} className="text-emerald-400" />
                    {copy("Không lưu vết PII trong Telemetry & Logs:", "Zero-PII in Telemetry & Persistent Logs:")}
                  </div>
                  <p className="text-[var(--text-secondary)]">
                    {copy(
                      "Nhật ký telemetry chỉ ghi nhận phân phối thời gian phản hồi và số lượng yêu cầu; tuyệt đối không chứa tên, tuổi, địa chỉ, MRN hay văn bản trao đổi nhạy cảm.",
                      "Telemetry logs store only aggregated latency percentiles and request counts; strictly free of names, MRNs, notes, or patient identifiers.",
                    )}
                  </p>
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default ClinicalStandards;
