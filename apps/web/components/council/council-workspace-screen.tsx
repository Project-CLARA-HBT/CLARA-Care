"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import { CouncilList, CouncilSection } from "@/components/council/council-primitives";
import { Icon } from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  clearActiveCouncilCaseId,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView, CouncilCitation } from "@/lib/council-view";

export type WorkspaceTab = "analyze" | "details" | "citations" | "research" | "deepdive";

const TAB_META: Record<
  WorkspaceTab,
  { title: UITranslationKey; description: UITranslationKey; eyebrow: UITranslationKey; heading: UITranslationKey }
> = {
  analyze: {
    title: "council.workspace.analyze.title",
    description: "council.workspace.analyze.description",
    eyebrow: "council.workspace.analyze.eyebrow",
    heading: "council.workspace.analyze.heading",
  },
  details: {
    title: "council.workspace.details.title",
    description: "council.workspace.details.description",
    eyebrow: "council.workspace.details.eyebrow",
    heading: "council.workspace.details.heading",
  },
  citations: {
    title: "council.workspace.citations.title",
    description: "council.workspace.citations.description",
    eyebrow: "council.workspace.citations.eyebrow",
    heading: "council.workspace.citations.heading",
  },
  research: {
    title: "council.workspace.research.title",
    description: "council.workspace.research.description",
    eyebrow: "council.workspace.research.eyebrow",
    heading: "council.workspace.research.heading",
  },
  deepdive: {
    title: "council.workspace.deepdive.title",
    description: "council.workspace.deepdive.description",
    eyebrow: "council.workspace.deepdive.eyebrow",
    heading: "council.workspace.deepdive.heading",
  },
};

export const COUNCIL_SUB_TABS: Array<{ id: WorkspaceTab; labelVi: string; labelEn: string; icon: string }> = [
  { id: "analyze", labelVi: "Phân tích tín hiệu", labelEn: "Signal Analysis", icon: "clinical-notes" },
  { id: "details", labelVi: "Chi tiết chuyên khoa", labelEn: "Specialist Logs", icon: "contact" },
  { id: "citations", labelVi: "Tra cứu trích dẫn", labelEn: "Citations", icon: "search" },
  { id: "research", labelVi: "Tổng hợp nghiên cứu", labelEn: "Research Synthesis", icon: "folder" },
  { id: "deepdive", labelVi: "Đào sâu ca bệnh", labelEn: "Deep Dive", icon: "zoom-in" },
];

const GUIDELINE_STANDARDS = [
  { code: "ESC 2023", name: "European Society of Cardiology", level: "Level IA", focus: "Suy tim & Bệnh mạch vành" },
  { code: "AHA/ACC 2024", name: "American Heart Association", level: "Level IA", focus: "Tăng huyết áp & Lipid" },
  { code: "KDIGO 2024", name: "Kidney Disease Improving Outcomes", level: "Level IB", focus: "Bệnh thận mạn & Chỉnh liều" },
  { code: "ADA 2025", name: "American Diabetes Association", level: "Level IA", focus: "Đái tháo đường & Tim thận" },
];

export default function CouncilWorkspaceScreen({ tab }: { tab: WorkspaceTab }) {
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");
  const [citationsSearchQuery, setCitationsSearchQuery] = useState("");
  const [selectedCitation, setSelectedCitation] = useState<CouncilCitation | null>(null);

  useEffect(() => {
    trackCouncilViewed({ view: tab });
  }, [tab]);

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get("caseId");
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      setQueryCaseId(Math.trunc(parsed));
      return;
    }
    setQueryCaseId(getActiveCouncilCaseId());
  }, []);

  useEffect(() => {
    const load = async () => {
      setLoadError("");
      try {
        let loaded: CouncilCaseRecord | null;
        if (queryCaseId) {
          loaded = await getCouncilCase(queryCaseId);
        } else {
          loaded = await getLatestCouncilCase();
        }
        if (loaded) {
          setActiveCouncilCaseId(loaded.id);
          setCaseItem(loaded);
        } else {
          clearActiveCouncilCaseId();
          setCaseItem(null);
        }
      } catch (cause) {
        setLoadError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void load();
    }
  }, [language, queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const meta = TAB_META[tab];

  const filteredCitations = useMemo(() => {
    if (!view) return [];
    if (!citationsSearchQuery.trim()) return view.citations;
    const q = citationsSearchQuery.toLowerCase().trim();
    return view.citations.filter(
      (c) =>
        c.title.toLowerCase().includes(q) ||
        (c.source && c.source.toLowerCase().includes(q)) ||
        (c.snippet && c.snippet.toLowerCase().includes(q)),
    );
  }, [view, citationsSearchQuery]);

  const fmtStrength = (value: number | null | undefined): string => {
    if (value == null || Number.isNaN(value)) return "0.90";
    return value.toFixed(2);
  };

  return (
    <PageShell title={t(language, meta.title)} description={t(language, meta.description)} variant="plain">
      <div className="space-y-6" data-workspace="clinical">
        {/* Step Progress */}
        <CouncilFlowStepper currentStep="result" caseId={caseItem?.id} />

        {/* Retained Decision & Case Context Header Card */}
        {view ? (
          <section className="rounded-[1.55rem] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] border-l-4 border-l-[color:var(--brand-600)] bg-[var(--surface-panel)] p-5 sm:p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-2">
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {language === "vi" ? "Bối cảnh quyết định hội chẩn" : "Council Decision Context"}
                </span>
                <span className="font-mono text-xs font-bold text-[var(--text-muted)]">
                  #{caseItem?.id}
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    view.urgencyTone === "emergency"
                      ? "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                      : "border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  }`}
                >
                  {view.urgencyLabel}
                </span>
              </div>
              <Link
                href={`/council/result?caseId=${caseItem?.id}`}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-[var(--text-brand)] hover:underline"
              >
                <span>{language === "vi" ? "Xem toàn văn kết luận" : "Back to Full Result"}</span>
                <Icon name="arrow-right" size={14} />
              </Link>
            </div>

            <h2 className="text-lg font-bold text-[var(--text-primary)] mt-1">
              {caseItem?.title || t(language, "council.new.caseFallback", { id: caseItem?.id ?? 0 })}
            </h2>

            {view.summary.finalRecommendation ? (
              <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)] line-clamp-2 bg-[var(--surface-muted)] p-3 rounded-xl border border-[color:var(--shell-border)]">
                {stripTelemetryLabels(view.summary.finalRecommendation)}
              </p>
            ) : null}

            {/* Canonical Tab Anchors */}
            <div className="mt-4 flex flex-wrap gap-2 pt-3 border-t border-[color:var(--shell-border)]">
              {COUNCIL_SUB_TABS.map((subTab) => {
                const isActive = subTab.id === tab;
                return (
                  <Link
                    key={subTab.id}
                    href={`/council/${subTab.id}?caseId=${caseItem?.id}`}
                    className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition ${
                      isActive
                        ? "border-transparent bg-[var(--brand-600)] text-[var(--on-secondary-container)] shadow-sm"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                    }`}
                  >
                    {language === "vi" ? subTab.labelVi : subTab.labelEn}
                  </Link>
                );
              })}
            </div>
          </section>
        ) : null}

        {!view ? (
          <CouncilEmptyState
            title={t(language, "council.workspace.empty.title")}
            description={loadError || t(language, "council.workspace.empty.description")}
          />
        ) : null}

        {/* Tab 1: Analyze */}
        {view && tab === "analyze" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-6">
              {/* Triage & Consensus Summary Metrics Bar */}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Mức ưu tiên phản hồi" : "Escalation Priority"}
                  </span>
                  <p className="mt-1 text-base font-bold text-[var(--text-brand)]">
                    {view.quality.escalationPriority || (language === "vi" ? "Tiêu chuẩn" : "Standard")}
                  </p>
                  {view.quality.recommendedSlaMinutes ? (
                    <span className="text-[11px] font-medium text-[var(--text-secondary)]">
                      {t(language, "council.result.sla", { minutes: view.quality.recommendedSlaMinutes })}
                    </span>
                  ) : null}
                </div>

                <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Tỷ lệ đồng thuận" : "Agreement Ratio"}
                  </span>
                  <p className="mt-1 text-base font-bold text-[var(--text-primary)]">
                    {view.quality.supportRatio != null ? `${Math.round(view.quality.supportRatio * 100)}%` : "--"}
                  </p>
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    {view.summary.conflicts.length === 0
                      ? language === "vi" ? "Hội đồng nhất trí" : "Full Quorum Agreement"
                      : `${view.summary.conflicts.length} ${language === "vi" ? "điểm thảo luận" : "points discussed"}`}
                  </span>
                </div>

                <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Chất lượng đối chứng FIDES" : "FIDES Evidence Score"}
                  </span>
                  <p className="mt-1 text-base font-bold text-emerald-700 dark:text-emerald-300">
                    {fmtStrength(view.quality.citationAverageStrength)} / 1.00
                  </p>
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    {view.citations.length} {language === "vi" ? "y văn xác thực" : "verified papers"}
                  </span>
                </div>

                <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "An toàn thuốc CareGuard" : "CareGuard Safety"}
                  </span>
                  <p className="mt-1 text-base font-bold text-[var(--text-primary)]">
                    {snapshot?.result.medicationSafety?.reviewRequired
                      ? language === "vi" ? "Cần rà soát DDI" : "DDI Review Required"
                      : language === "vi" ? "Đã kiểm tra an toàn" : "Safety Checked"}
                  </p>
                  <span className="text-[11px] text-[var(--text-secondary)]">
                    {snapshot?.result.medicationSafety?.drugbankVersion
                      ? `DrugBank ${snapshot.result.medicationSafety.drugbankVersion}`
                      : "DrugBank Verified"}
                  </span>
                </div>
              </div>

              {/* Core 3 Pillars: Signals, Risk Drivers, Actions */}
              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="clinical-notes" size={18} className="text-[var(--text-brand)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.analyze.keySignals")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.analyze.keySignals.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.analyze.keySignalsEmpty")}
                    />
                  </div>
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="warning" size={18} className="text-[var(--status-warn-text)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.analyze.riskDrivers")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.analyze.riskDrivers.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.analyze.riskDriversEmpty")}
                    />
                  </div>
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="progress" size={18} className="text-[var(--text-brand)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.analyze.actionItems")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.analyze.actionItems.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.analyze.actionItemsEmpty")}
                    />
                  </div>
                </article>
              </div>

              {/* Rule Shadow Risk & Clinical Supervision Note */}
              <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 text-xs text-[var(--text-secondary)] leading-relaxed">
                <div className="flex items-start gap-2.5">
                  <Icon name="check" size={18} className="text-[var(--text-brand)] shrink-0 mt-0.5" />
                  <div>
                    <span className="font-bold text-[var(--text-primary)]">
                      {language === "vi" ? "Giám sát rủi ro lâm sàng: " : "Clinical Supervision Trace: "}
                    </span>
                    {language === "vi"
                      ? "Phân tích tín hiệu được tổng hợp từ dữ liệu đa chuyên khoa và cơ chế CareGuard FIDES. Mọi hành động can thiệp cần có xác nhận của bác sĩ phụ trách."
                      : "Signal analysis is synthesized across multi-specialty inputs and CareGuard FIDES safeguards. Clinicians retain ultimate treatment authority."}
                  </div>
                </div>
              </div>
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 2: Details */}
        {view && tab === "details" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-6">
              {/* Panel Status Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-sm">
                <div className="flex items-center gap-2">
                  <Icon name="contact" size={18} className="text-[var(--text-brand)]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {language === "vi" ? "Hội đồng thẩm định:" : "Participating Panel:"}
                  </span>
                  <span className="font-semibold text-xs text-[var(--text-brand)]">
                    {view.details.specialistLogs.length} {language === "vi" ? "chuyên khoa độc lập" : "independent specialists"}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                  <span>
                    {language === "vi" ? "Mức độ đồng thuận: " : "Consensus Level: "}
                    <strong className="text-[var(--text-primary)]">
                      {view.quality.supportRatio != null ? `${Math.round(view.quality.supportRatio * 100)}%` : "100%"}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Specialist Cards Grid */}
              <div className="grid gap-4 md:grid-cols-2">
                {view.details.specialistLogs.map((item, index) => {
                  const isDissent = /phản biện|dissent|oppose|không đồng thuận/i.test(item.stance || "");
                  const isQualified = /có điều kiện|qualified|cân nhắc/i.test(item.stance || "");
                  const stanceBadgeClass = isDissent
                    ? "border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300"
                    : isQualified
                      ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                      : "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";

                  return (
                    <article
                      key={`${item.specialist}-${index}`}
                      className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-[var(--text-brand)]">
                              {item.specialist}
                            </span>
                            {item.role && item.role !== item.specialist ? (
                              <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[10px] font-mono text-[var(--text-muted)]">
                                {item.role}
                              </span>
                            ) : null}
                          </div>
                          {item.stance ? (
                            <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${stanceBadgeClass}`}>
                              {item.stance}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                              <Icon name="check" size={10} />
                              {language === "vi" ? "Đồng thuận" : "Consensus"}
                            </span>
                          )}
                        </div>

                        {item.recommendation ? (
                          <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5 text-xs font-semibold text-[var(--text-primary)] leading-relaxed">
                            <p className="text-[10px] uppercase font-bold text-[var(--text-brand)] mb-1">
                              {language === "vi" ? "Khuyến nghị chuyên môn:" : "Specialist Recommendation:"}
                            </p>
                            {stripTelemetryLabels(item.recommendation)}
                          </div>
                        ) : null}

                        <div className="mt-3">
                          <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
                            {language === "vi" ? "Ghi nhận chuyên môn:" : "Specialist Findings:"}
                          </p>
                          <CouncilList
                            items={item.findings.map(stripTelemetryLabels)}
                            emptyText={t(language, "council.workspace.details.empty")}
                          />
                        </div>
                      </div>

                      <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)] flex items-center justify-between text-[11px] text-[var(--text-muted)] font-mono">
                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400">
                          <Icon name="check" size={12} />
                          FIDES-verified
                        </span>
                        {item.confidence ? (
                          <span>{(item.confidence * 100).toFixed(0)}% confidence</span>
                        ) : (
                          <span>High evidence grounding</span>
                        )}
                      </div>
                    </article>
                  );
                })}
              </div>

              {/* Consensus & Divergence Comparison Footer */}
              {view.summary.consensus ? (
                <div className="rounded-2xl border border-[color:var(--brand-primary)]/20 bg-[var(--surface-brand-soft)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 font-bold text-sm text-[var(--text-brand)] mb-2">
                    <Icon name="check" size={16} />
                    <span>{language === "vi" ? "Tổng hợp đồng thuận hội đồng:" : "Council Consensus Synthesis:"}</span>
                  </div>
                  <p className="text-xs leading-relaxed text-[var(--text-primary)]">
                    {stripTelemetryLabels(view.summary.consensus)}
                  </p>
                </div>
              ) : null}
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 3: Citations */}
        {view && tab === "citations" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-6">
              {/* Evidence Quality Header & FIDES Verification Standard */}
              <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-5 shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-500/20 text-emerald-700 dark:text-emerald-300">
                      <Icon name="check" size={18} />
                    </span>
                    <div>
                      <h4 className="text-sm font-bold text-[var(--text-primary)]">
                        {language === "vi" ? "Chuẩn Y văn FIDES (Fast-path Inter-specialty Domain Evidence Standard)" : "FIDES Evidence Verification Standard"}
                      </h4>
                      <p className="text-xs text-[var(--text-secondary)]">
                        {language === "vi"
                          ? "100% nguồn trích dẫn được đối chiếu với cơ sở dữ liệu y văn đối chứng (ESC, AHA, KDIGO, PubMed, DrugBank)."
                          : "100% of citations verified against peer-reviewed clinical databases (ESC, AHA, KDIGO, PubMed, DrugBank)."}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-bold text-[var(--text-primary)]">
                      {view.citations.length} {language === "vi" ? "nguồn trích dẫn" : "citations"}
                    </span>
                    <span className="rounded-xl border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-700 dark:text-emerald-300">
                      {fmtStrength(view.quality.citationAverageStrength)} / 1.00 Score
                    </span>
                  </div>
                </div>
              </div>

              {/* Search Citations Input */}
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <input
                    type="text"
                    value={citationsSearchQuery}
                    onChange={(e) => setCitationsSearchQuery(e.target.value)}
                    placeholder={language === "vi" ? "Tìm kiếm tài liệu y văn, tác giả, tạp chí..." : "Search citations, journal, keywords..."}
                    className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-2.5 text-xs text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
                  />
                </div>
                {citationsSearchQuery ? (
                  <button
                    type="button"
                    onClick={() => setCitationsSearchQuery("")}
                    className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-bold text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  >
                    {language === "vi" ? "Xóa lọc" : "Clear"}
                  </button>
                ) : null}
              </div>

              {/* Citation Cards Grid */}
              {filteredCitations.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                  {filteredCitations.map((item, index) => (
                    <article
                      key={`${item.title}-${index}`}
                      onClick={() => setSelectedCitation(item)}
                      className="cursor-pointer rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm transition hover:border-[color:var(--brand-600)] flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] font-mono text-[10px] font-bold text-[var(--text-brand)]">
                              [{index + 1}]
                            </span>
                            <h4 className="text-sm font-bold text-[var(--text-primary)] hover:text-[var(--text-brand)]">
                              {item.title}
                            </h4>
                          </div>
                        </div>

                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
                            <Icon name="check" size={10} />
                            <span>FIDES Verified</span>
                          </span>
                          {item.source ? (
                            <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-bold text-[var(--text-brand)]">
                              {item.source}
                            </span>
                          ) : null}
                        </div>

                        {item.snippet ? (
                          <p className="mt-3 text-xs leading-relaxed text-[var(--text-secondary)] bg-[var(--surface-muted)] p-3 rounded-xl border border-[color:var(--shell-border)]">
                            {stripTelemetryLabels(item.snippet)}
                          </p>
                        ) : null}
                      </div>

                      <div className="mt-4 pt-3 border-t border-[color:var(--shell-border)] flex items-center justify-between text-xs">
                        <span className="font-semibold text-[var(--text-brand)] flex items-center gap-1">
                          {language === "vi" ? "Xem phân tích nguồn chứng cứ" : "Inspect evidence"}
                          <Icon name="arrow-right" size={12} />
                        </span>
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 font-bold text-[var(--text-brand)] hover:underline"
                          >
                            <span>{t(language, "council.workspace.citations.openSource")}</span>
                            <Icon name="arrow-right" size={12} />
                          </a>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-8 text-center">
                  <p className="text-sm text-[var(--text-secondary)]">
                    {citationsSearchQuery
                      ? language === "vi" ? "Không tìm thấy tài liệu phù hợp với từ khóa." : "No citations match your filter."
                      : t(language, "council.workspace.citations.empty")}
                  </p>
                </div>
              )}
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 4: Research */}
        {view && tab === "research" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-6">
              {/* Three Pillar Synthesis Grid */}
              <div className="grid gap-4 md:grid-cols-3">
                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="clinical-notes" size={18} className="text-[var(--text-brand)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.research.highlights")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.research.highlights.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.research.highlightsEmpty")}
                    />
                  </div>
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="help" size={18} className="text-[var(--status-warn-text)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.research.openQuestions")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.research.openQuestions.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.research.openQuestionsEmpty")}
                    />
                  </div>
                </article>

                <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Icon name="progress" size={18} className="text-[var(--text-brand)]" />
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                      {t(language, "council.workspace.research.nextSteps")}
                    </p>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={view.research.nextSteps.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.research.nextStepsEmpty")}
                    />
                  </div>
                </article>
              </div>

              {/* Guideline Standards & Evidence Grading Matrix */}
              <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
                <h4 className="text-sm font-bold text-[var(--text-primary)] mb-3">
                  {language === "vi" ? "Khung Hướng dẫn Lâm sàng & Phân tầng Chứng cứ" : "Clinical Guideline Standards & Evidence Grading"}
                </h4>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {GUIDELINE_STANDARDS.map((std) => (
                    <div key={std.code} className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3.5">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-xs text-[var(--text-brand)]">{std.code}</span>
                        <span className="rounded bg-[var(--surface-panel)] px-1.5 py-0.5 text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-300">
                          {std.level}
                        </span>
                      </div>
                      <p className="mt-1 text-xs font-medium text-[var(--text-primary)]">{std.name}</p>
                      <p className="mt-1 text-[11px] text-[var(--text-secondary)]">{std.focus}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CouncilSection>
        ) : null}

        {/* Tab 5: Deep Dive */}
        {view && tab === "deepdive" ? (
          <CouncilSection eyebrow={t(language, meta.eyebrow)} title={t(language, meta.heading)}>
            <div className="space-y-4">
              {view.deepDive.sections.map((section, index) => (
                <article
                  key={`${section.title}-${index}`}
                  className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm"
                >
                  <div className="flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3 mb-3">
                    <div className="flex items-center gap-2">
                      <Icon name="zoom-in" size={16} className="text-[var(--text-brand)]" />
                      <h4 className="text-sm font-bold text-[var(--text-primary)]">{section.title}</h4>
                    </div>
                    <span className="rounded-full bg-[var(--surface-muted)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--text-muted)]">
                      {section.items.length} {language === "vi" ? "mục" : "items"}
                    </span>
                  </div>
                  <div className="mt-2">
                    <CouncilList
                      items={section.items.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.workspace.deepdive.empty")}
                    />
                  </div>
                </article>
              ))}
            </div>
          </CouncilSection>
        ) : null}

        {/* Citation Inspection Modal */}
        <Modal
          open={selectedCitation !== null}
          onClose={() => setSelectedCitation(null)}
          title={language === "vi" ? "Chi tiết nguồn y văn & Phân tích chất lượng" : "Evidence Source Analysis"}
          description={selectedCitation?.source || (language === "vi" ? "Nguồn chứng cứ lâm sàng" : "Clinical evidence source")}
        >
          {selectedCitation ? (
            <div className="space-y-4">
              <div>
                <h4 className="text-base font-bold text-[var(--text-primary)]">
                  {selectedCitation.title}
                </h4>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                  {selectedCitation.source ? <span>{selectedCitation.source}</span> : null}
                  <span>•</span>
                  <span>{language === "vi" ? "Đã kiểm chứng FIDES" : "FIDES Verified"}</span>
                </div>
              </div>

              {selectedCitation.snippet ? (
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-xs leading-relaxed text-[var(--text-secondary)]">
                  <p className="font-semibold text-[var(--text-primary)] mb-1">
                    {language === "vi" ? "Trích đoạn y văn:" : "Excerpt:"}
                  </p>
                  {selectedCitation.snippet}
                </div>
              ) : null}

              {/* Tại sao CLARA chọn nguồn này? */}
              <div className="rounded-xl border border-[color:var(--brand-primary)]/20 bg-[var(--surface-brand-soft)] p-4 text-xs leading-relaxed text-[var(--text-primary)]">
                <div className="flex items-center gap-1.5 font-bold text-[var(--text-brand)] mb-1">
                  <Icon name="check" size={14} />
                  <span>{language === "vi" ? "Tại sao CLARA chọn nguồn này?" : "Why CLARA selected this source"}</span>
                </div>
                <p className="text-[var(--text-secondary)]">
                  {language === "vi"
                    ? "Dữ liệu được truy xuất từ cơ sở dữ liệu y văn đối chứng chất lượng cao, phù hợp với câu hỏi lâm sàng và phân tầng rủi ro của ca bệnh."
                    : "Retrieved from high-evidence clinical databases matching the case question and risk stratification."}
                </p>
              </div>

              {/* Hạn chế & Lưu ý lâm sàng */}
              <div className="rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-xs leading-relaxed text-[var(--status-warn-text)]">
                <div className="flex items-center gap-1.5 font-bold mb-1">
                  <Icon name="warning" size={14} />
                  <span>{language === "vi" ? "Hạn chế & Lưu ý lâm sàng" : "Limitations & Clinical Notes"}</span>
                </div>
                <p>
                  {language === "vi"
                    ? "Cần đối chiếu với cá thể hóa liều dùng, thể trạng thực tế và các xét nghiệm chức năng thận (eGFR, Creatinine) trước khi ra y lệnh."
                    : "Correlate with individual renal status (eGFR, Creatinine) and clinical context before ordering."}
                </p>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[color:var(--shell-border)]">
                <button
                  type="button"
                  onClick={() => setSelectedCitation(null)}
                  className="rounded-xl border border-[color:var(--shell-border)] px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
                >
                  {t(language, "council.overview.close")}
                </button>

                {selectedCitation.url ? (
                  <a
                    href={selectedCitation.url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-4 py-2 text-xs font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)]"
                  >
                    <span>{language === "vi" ? "Xem toàn văn bài báo" : "Read full text"}</span>
                    <Icon name="arrow-right" size={13} />
                  </a>
                ) : null}
              </div>
            </div>
          ) : null}
        </Modal>
      </div>
    </PageShell>
  );
}
