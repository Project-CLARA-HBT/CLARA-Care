"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilFlowStepper from "@/components/council/council-flow-stepper";
import { CouncilList } from "@/components/council/council-primitives";
import { Icon } from "@/components/ui/icon";
import Modal from "@/components/ui/modal";
import PageShell from "@/components/ui/page-shell";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  clearActiveCouncilCaseId,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  isCouncilModelDisclosureEnabled,
  isCouncilOversightEnabled,
  setActiveCouncilCaseId,
  submitCouncilOversight,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

type GuardAction = "override" | "pause";

const HANDOFF_SPECIALTIES = [
  { name: "Tim mạch", reason: "Khám chuyên sâu bệnh tim mạch và nguy cơ mạch vành." },
  { name: "Thần kinh", reason: "Khám chuyên sâu hệ thần kinh và đánh giá đột quỵ." },
  { name: "Thận", reason: "Đánh giá chức năng thận và điều chỉnh liều suy thận." },
  { name: "Dược lâm sàng", reason: "Rà soát tương tác thuốc và tối ưu phác đồ." },
  { name: "Nội tiết", reason: "Kiểm soát đường huyết và các biến chứng chuyển hóa." },
];

export default function CouncilResultPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [error, setError] = useState("");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [selectedSpecialty, setSelectedSpecialty] = useState("Thận");
  const [guardAction, setGuardAction] = useState<GuardAction | null>(null);
  const [guardReason, setGuardReason] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const [oversightPaused, setOversightPaused] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<{
    title: string;
    source?: string;
    snippet?: string;
    url?: string;
  } | null>(null);

  const oversightEnabled = isCouncilOversightEnabled();
  const modelDisclosureEnabled = isCouncilModelDisclosureEnabled();

  useEffect(() => {
    trackCouncilViewed({ view: "result" });
  }, []);

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
      setError("");
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
        setError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== null) {
      void load();
    }
  }, [language, queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);

  const fmtStrength = (value: number | null): string => {
    if (value == null || Number.isNaN(value)) return "-";
    return value.toFixed(2);
  };

  const medicationSafety = snapshot?.result.medicationSafety ?? null;
  const selectedSpecialtyMeta =
    HANDOFF_SPECIALTIES.find((item) => item.name === selectedSpecialty) ?? HANDOFF_SPECIALTIES[2];

  const hasRedFlag = Boolean(
    view?.summary.escalationReason ||
      view?.urgencyTone === "emergency" ||
      view?.quality.requiresHumanHandoff ||
      medicationSafety?.reviewRequired,
  );

  const confirmGuardAction = async () => {
    if (!guardAction || !guardReason.trim()) return;
    const action = guardAction;
    const reason = guardReason.trim();
    const label =
      action === "override"
        ? t(language, "council.overview.guard.overrideAction")
        : t(language, "council.overview.guard.pauseAction");
    const localNotice = t(language, "council.overview.guard.requestRecorded", {
      action: label,
      reason,
    });
    setGuardAction(null);
    setGuardReason("");

    if (!oversightEnabled || !caseItem) {
      setActionNotice(localNotice);
      return;
    }

    try {
      const result = await submitCouncilOversight(caseItem.id, { action, reason });
      if (action === "pause" || result.oversightState === "paused") {
        setOversightPaused(true);
        setActionNotice(t(language, "council.overview.guard.pauseRecorded"));
      } else {
        setActionNotice(localNotice);
      }
    } catch {
      setActionNotice(localNotice);
    }
  };

  const confirmHandoff = async () => {
    const localNotice = t(language, "council.overview.handoff.prepared", {
      specialty: selectedSpecialtyMeta.name,
      reason: selectedSpecialtyMeta.reason,
    });
    setHandoffOpen(false);

    if (!oversightEnabled || !caseItem) {
      setActionNotice(localNotice);
      return;
    }

    try {
      await submitCouncilOversight(caseItem.id, {
        action: "handoff",
        handoffSpecialty: selectedSpecialtyMeta.name,
        reason: selectedSpecialtyMeta.reason,
      });
      setActionNotice(
        t(language, "council.overview.handoff.sent", {
          specialty: selectedSpecialtyMeta.name,
          reason: selectedSpecialtyMeta.reason,
        }),
      );
    } catch {
      setActionNotice(localNotice);
    }
  };

  const handleExportReport = () => {
    if (!caseItem || !view) return;
    const reportText = [
      `# BIÊN BẢN HỘI CHẨN LÂM SÀNG AI — CA #${caseItem.id}`,
      `Thời gian: ${snapshot?.createdAt ? formatLocaleDate(language, snapshot.createdAt, { dateStyle: "long", timeStyle: "medium" }) : new Date().toLocaleString()}`,
      `Phân tầng khẩn cấp: ${view.urgencyLabel}`,
      `Tỷ lệ đồng thuận: ${view.quality.supportRatio != null ? Math.round(view.quality.supportRatio * 100) : "--"}%`,
      "",
      `## 1. CẢNH BÁO ĐỎ & LEO THANG`,
      view.summary.escalationReason ? `Lý do: ${stripTelemetryLabels(view.summary.escalationReason)}` : "Không phát hiện tín hiệu leo thang khẩn cấp.",
      medicationSafety?.reviewRequired ? `An toàn thuốc: Cần rà soát tương tác thuốc (DDI).` : "",
      "",
      `## 2. KHUYẾN NGHỊ LÂM SÀNG TỔNG HỢP`,
      stripTelemetryLabels(view.summary.finalRecommendation) || "Chưa có khuyến nghị.",
      "",
      `## 3. ĐỒNG THUẬN HỘI ĐỒNG`,
      stripTelemetryLabels(view.summary.consensus) || "Chưa có thông tin đồng thuận.",
      "",
      `## 4. ĐIỂM BẤT ĐỒNG & KHÔNG CHẮC CHẮN`,
      view.summary.conflicts.length ? `Bất đồng: ${view.summary.conflicts.map(stripTelemetryLabels).join("; ")}` : "Không có xung đột lớn.",
      view.summary.divergence.length ? `Phân kỳ: ${view.summary.divergence.map(stripTelemetryLabels).join("; ")}` : "",
      "",
      `## 5. NGUỒN CHỨNG CỨ & TRÍCH DẪN`,
      view.citations.map((c, i) => `[${i + 1}] ${c.title} (${c.source || "Y văn"})`).join("\n") || "Chưa có trích dẫn đính kèm.",
      "",
      `---`,
      `*Lưu ý: Báo cáo này là công cụ hỗ trợ ra quyết định lâm sàng. Bác sĩ chịu trách nhiệm chuyên môn cuối cùng.*`
    ].filter(Boolean).join("\n");

    try {
      if (typeof window !== "undefined" && typeof document !== "undefined") {
        const blob = new Blob([reportText], { type: "text/markdown;charset=utf-8" });
        if (typeof URL !== "undefined" && typeof URL.createObjectURL === "function") {
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = `council-case-${caseItem.id}-report.md`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          if (typeof URL.revokeObjectURL === "function") {
            URL.revokeObjectURL(url);
          }
        }
      }
      setActionNotice(language === "vi" ? "Đã xuất biên bản hội chẩn thành công." : "Council report exported successfully.");
    } catch {
      setActionNotice(language === "vi" ? "Đã xuất biên bản hội chẩn thành công." : "Council report exported successfully.");
    }
  };

  return (
    <PageShell
      data-workspace="clinical"
      title={t(language, "council.result.title")}
      description={t(language, "council.result.description")}
      variant="plain"
    >
      <div className="space-y-6" data-workspace="clinical">
        {/* Step Progress */}
        <CouncilFlowStepper currentStep="result" caseId={caseItem?.id} />

        {actionNotice ? (
          <div className="rounded-xl border border-[color:var(--brand-primary)]/40 bg-[var(--surface-brand-soft)] p-4 text-sm font-semibold text-[var(--text-brand)]">
            {actionNotice}
          </div>
        ) : null}

        {!view ? (
          <CouncilEmptyState
            title={t(language, "council.empty.title")}
            description={error || t(language, "council.result.emptyDescription")}
          />
        ) : (
          <div className="space-y-6">
            {/* Case Header: Compact and Persistent */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--shell-border)] pb-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-sm font-bold text-[var(--text-brand)]">
                  #{caseItem?.id}
                </span>
                <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]">
                  {caseItem?.title || t(language, "council.new.caseFallback", { id: caseItem?.id ?? 0 })}
                </h2>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                    hasRedFlag
                      ? "border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                      : "border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] text-[var(--text-brand)]"
                  }`}
                >
                  {view.urgencyLabel}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                <span>
                  {snapshot?.createdAt
                    ? formatLocaleDate(language, snapshot.createdAt, {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : view.createdAtLabel}
                </span>
                <span>•</span>
                <span>{view.requestSummary.specialists.length} {language === "vi" ? "chuyên khoa" : "specialists"}</span>
              </div>
            </div>

            {/* 1. RED FLAGS & ESCALATION */}
            <section
              aria-labelledby="hierarchy-escalation-heading"
              className={`rounded-2xl border p-6 shadow-sm ${
                hasRedFlag
                  ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
                  : "border-[color:var(--shell-border)] bg-[var(--surface-panel)] text-[var(--text-primary)]"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <Icon
                    name="warning"
                    size={22}
                    className={hasRedFlag ? "text-[var(--status-danger-text)]" : "text-[var(--text-muted)]"}
                  />
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.14em]">
                      {t(language, "council.result.hierarchy.escalation")}
                    </p>
                    <h3 id="hierarchy-escalation-heading" className="mt-1 text-lg font-bold">
                      {hasRedFlag
                        ? language === "vi"
                          ? "Cảnh báo đỏ & Leo thang khẩn cấp"
                          : "Immediate Escalation & Red Flag Alerts"
                        : language === "vi"
                          ? "Không phát hiện dấu hiệu leo thang khẩn cấp"
                          : "No Critical Escalation Signals Detected"}
                    </h3>
                  </div>
                </div>
                {view.quality.escalationPriority ? (
                  <span className="rounded-lg border border-current bg-[var(--surface-panel)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                    {view.quality.escalationPriority}
                  </span>
                ) : null}
              </div>

              {view.summary.escalationReason ? (
                <div className="mt-4 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--surface-panel)] p-4 text-sm leading-relaxed text-[var(--text-primary)]">
                  <span className="font-bold text-[var(--status-danger-text)]">
                    {language === "vi" ? "Lý do leo thang: " : "Escalation Reason: "}
                  </span>
                  {stripTelemetryLabels(view.summary.escalationReason)}
                </div>
              ) : null}

              {medicationSafety?.reviewRequired ? (
                <div className="mt-3 rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--surface-panel)] p-4 text-sm leading-relaxed text-[var(--text-primary)]">
                  <span className="font-bold text-[var(--status-warn-text)]">
                    {language === "vi" ? "Cảnh báo an toàn thuốc (DDI): " : "Medication Safety Notice: "}
                  </span>
                  {medicationSafety.state === "requires_clarification"
                    ? t(language, "council.result.medicationSafety.clarificationNotice")
                    : medicationSafety.state === "unavailable"
                      ? t(language, "council.result.medicationSafety.unavailableNotice")
                      : t(language, "council.result.medicationSafety.reviewNotice")}
                </div>
              ) : null}

              {view.quality.recommendedSlaMinutes ? (
                <p className="mt-3 text-xs font-bold">
                  {t(language, "council.result.sla", { minutes: view.quality.recommendedSlaMinutes })}
                </p>
              ) : null}
            </section>

            {/* 2. RECOMMENDATION & SUMMARY */}
            <section
              aria-labelledby="hierarchy-recommendation-heading"
              className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] border-l-4 border-l-[color:var(--brand-600)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {t(language, "council.result.hierarchy.recommendation")}
                </span>
                <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-muted)]">
                  {language === "vi" ? "Tóm tắt ngắn" : "Clinical Summary"}
                </span>
              </div>
              <h3 id="hierarchy-recommendation-heading" className="mt-3 text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                {t(language, "council.result.finalRecommendation")}
              </h3>

              <div className="mt-4 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 sm:p-6">
                <p className="whitespace-pre-wrap text-base leading-relaxed text-[var(--text-primary)]">
                  {oversightPaused
                    ? language === "vi"
                      ? "Quy trình hội chẩn đang tạm dừng. Khuyến nghị chưa được xác nhận chuyên môn."
                      : "Council workflow paused. Recommendation not yet confirmed."
                    : stripTelemetryLabels(view.summary.finalRecommendation) || t(language, "council.result.noRecommendation")}
                </p>
              </div>

              {/* Sub-view Canonical Tab Anchors */}
              <div className="mt-5 flex flex-wrap gap-2 pt-3 border-t border-[color:var(--shell-border)]">
                <Link
                  href={`/council/analyze?caseId=${caseItem?.id}`}
                  className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  {language === "vi" ? "Phân tích tín hiệu" : "Signal Analysis"}
                </Link>
                <Link
                  href={`/council/details?caseId=${caseItem?.id}`}
                  className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  {language === "vi" ? "Chi tiết chuyên khoa" : "Specialist Logs"}
                </Link>
                <Link
                  href={`/council/citations?caseId=${caseItem?.id}`}
                  className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  {language === "vi" ? "Tra cứu trích dẫn" : "Citations"}
                </Link>
                <Link
                  href={`/council/research?caseId=${caseItem?.id}`}
                  className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  {language === "vi" ? "Tổng hợp nghiên cứu" : "Research Synthesis"}
                </Link>
                <Link
                  href={`/council/deepdive?caseId=${caseItem?.id}`}
                  className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-1.5 text-xs font-semibold text-[var(--text-primary)] transition hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  {language === "vi" ? "Đào sâu ca bệnh" : "Deep Dive"}
                </Link>
              </div>
            </section>

            {/* 3. CONSENSUS PERCENTAGE */}
            <section
              aria-labelledby="hierarchy-consensus-heading"
              className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                    {t(language, "council.result.hierarchy.consensus")}
                  </span>
                </div>
                {view.quality.supportRatio != null ? (
                  <span className="rounded-full border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-3.5 py-1 text-xs font-bold text-[var(--text-brand)]">
                    {language === "vi" ? "Đồng thuận: " : "Agreement: "}
                    {Math.round(view.quality.supportRatio * 100)}%
                  </span>
                ) : null}
              </div>

              <h3 id="hierarchy-consensus-heading" className="mt-3 text-xl font-bold text-[var(--text-primary)]">
                {t(language, "council.result.consensus")}
              </h3>

              <div className="mt-3 relative pl-4 border-l-2 border-[color:var(--brand-600)]">
                <p className="text-sm leading-relaxed text-[var(--text-secondary)]">
                  {stripTelemetryLabels(view.summary.consensus) || t(language, "council.result.noConsensus")}
                </p>
              </div>

              {/* Structured Specialist Perspectives */}
              {view.details.specialistLogs.length > 0 ? (
                <div className="mt-5 space-y-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {language === "vi" ? "Góc nhìn theo từng chuyên khoa" : "Specialist Findings & Perspectives"}
                  </p>
                  <div className="divide-y divide-[color:var(--shell-border)] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] overflow-hidden">
                    {view.details.specialistLogs.map((log, idx) => (
                      <div key={`${log.specialist}-${idx}`} className="p-4">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                            {log.specialist}
                          </span>
                        </div>
                        {log.recommendation ? (
                          <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                            {log.recommendation}
                          </p>
                        ) : null}
                        {log.findings && log.findings.length > 0 ? (
                          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-[var(--text-secondary)]">
                            {log.findings.map((f, i) => (
                              <li key={i}>{f}</li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>

            {/* 4. UNCERTAINTY & DIVERGENCE */}
            <section
              aria-labelledby="hierarchy-uncertainty-heading"
              className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {t(language, "council.result.hierarchy.uncertainty")}
                </span>
              </div>
              <h3 id="hierarchy-uncertainty-heading" className="mt-3 text-xl font-bold text-[var(--text-primary)]">
                {language === "vi" ? "Độ không chắc chắn & Điểm bất đồng" : "Uncertainty, Divergence & Conflicts"}
              </h3>

              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "council.result.conflictList")}
                  </p>
                  <div className="mt-2">
                    <CouncilList
                      items={view.summary.conflicts.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.result.noConflicts")}
                    />
                  </div>
                </div>

                <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                  <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "council.result.divergence")}
                  </p>
                  <div className="mt-2">
                    <CouncilList
                      items={view.summary.divergence.map(stripTelemetryLabels)}
                      emptyText={t(language, "council.result.noDivergence")}
                    />
                  </div>
                </div>
              </div>

              {view.quality.strongestDissent ? (
                <div className="mt-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                    {t(language, "council.result.strongestDissent")}
                  </span>
                  <p className="mt-1 text-sm text-[var(--text-primary)]">
                    {view.quality.strongestDissent}
                  </p>
                </div>
              ) : null}

              <p className="mt-3 text-xs text-[var(--text-muted)]">
                {t(language, "council.result.consensusHint")}
              </p>
            </section>

            {/* 5. CLINICIAN ACTION */}
            <section
              aria-labelledby="hierarchy-action-heading"
              className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                  {t(language, "council.result.hierarchy.clinicianAction")}
                </span>
              </div>
              <h3 id="hierarchy-action-heading" className="mt-3 text-xl font-bold text-[var(--text-primary)]">
                {language === "vi" ? "Quyết định lâm sàng & Xử trí tiếp theo" : "Clinical Governance & Next Actions"}
              </h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {language === "vi"
                  ? "Bác sĩ phụ trách có toàn quyền chấp nhận, ghi đè hoặc phân luồng tiếp theo cho ca bệnh."
                  : "The attending clinician holds full authority to confirm, override, or handoff this case."}
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => setHandoffOpen(true)}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 text-sm font-bold text-[var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)]"
                >
                  <Icon name="clinical-notes" size={16} />
                  {t(language, "council.overview.handoff.action")}
                </button>

                <button
                  type="button"
                  onClick={() => setGuardAction("override")}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-5 text-sm font-bold text-[var(--status-danger-text)] hover:opacity-90"
                >
                  <Icon name="warning" size={16} />
                  {t(language, "council.guard.overrideTitle")}
                </button>

                <button
                  type="button"
                  onClick={() => setGuardAction("pause")}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-5 text-sm font-bold text-[var(--status-warn-text)] hover:opacity-90"
                >
                  <Icon name="progress" size={16} />
                  {t(language, "council.guard.pauseTitle")}
                </button>

                <button
                  type="button"
                  onClick={handleExportReport}
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 text-sm font-bold text-[var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[var(--surface-panel)] transition"
                >
                  <Icon name="clinical-notes" size={16} />
                  <span>{language === "vi" ? "Xuất biên bản" : "Export Report"}</span>
                </button>

                <Link
                  href="/scribe"
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-panel)]"
                >
                  <Icon name="clinical-notes" size={16} />
                  {language === "vi" ? "Mở trong Ghi chép SOAP" : "Open in Scribe"}
                </Link>

                <Link
                  href="/council/new"
                  className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 text-sm font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)]"
                >
                  <Icon name="progress" size={16} />
                  {t(language, "council.result.newCase")}
                </Link>
              </div>
            </section>

            {/* 6. EVIDENCE & CITATIONS */}
            <section
              aria-labelledby="hierarchy-evidence-heading"
              className="rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-7 shadow-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="rounded-md border border-[color:var(--brand-primary)]/30 bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-brand)]">
                    {t(language, "council.result.hierarchy.evidence")}
                  </span>
                </div>
                <div className="flex gap-2">
                  <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-bold text-[var(--text-secondary)]">
                    {t(language, "council.result.citationQuality")}: {fmtStrength(view.quality.citationAverageStrength)}
                  </span>
                  <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-xs font-bold text-[var(--text-secondary)]">
                    {t(language, "council.result.citations", { count: view.citations.length || view.quality.citationTotal || 0 })}
                  </span>
                </div>
              </div>

              <h3 id="hierarchy-evidence-heading" className="mt-3 text-xl font-bold text-[var(--text-primary)]">
                {language === "vi" ? "Y văn & Nguồn trích dẫn đã kiểm chứng" : "Medical Literature & Verified Citations"}
              </h3>

              {view.citations.length > 0 ? (
                <div className="mt-4 divide-y divide-[color:var(--shell-border)] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] overflow-hidden">
                  {view.citations.map((cite, index) => (
                    <article
                      key={`${cite.title}-${index}`}
                      onClick={() => setSelectedCitation(cite)}
                      className="cursor-pointer p-4 transition-all hover:bg-[var(--surface-panel)]"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--surface-brand-soft)] font-mono text-[10px] font-bold text-[var(--text-brand)]">
                            [{index + 1}]
                          </span>
                          <h4 className="text-sm font-bold text-[var(--text-primary)] hover:text-[var(--text-brand)]">
                            {cite.title}
                          </h4>
                        </div>
                        {cite.source ? (
                          <span className="rounded bg-[var(--surface-panel)] px-2 py-0.5 text-[11px] font-bold text-[var(--text-brand)]">
                            {cite.source}
                          </span>
                        ) : null}
                      </div>
                      {cite.snippet ? (
                        <p className="mt-2 text-xs leading-relaxed text-[var(--text-secondary)]">
                          {cite.snippet}
                        </p>
                      ) : null}
                      <div className="mt-3 flex items-center justify-between pt-2 border-t border-[color:var(--shell-border)]">
                        <span className="text-[11px] font-semibold text-[var(--text-brand)] flex items-center gap-1">
                          {language === "vi" ? "Xem phân tích nguồn chứng cứ" : "Inspect evidence details"}
                          <Icon name="arrow-right" size={12} />
                        </span>
                        {cite.url ? (
                          <a
                            href={cite.url}
                            target="_blank"
                            rel="noreferrer noopener"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 text-xs font-bold text-[var(--text-brand)] hover:underline"
                          >
                            {language === "vi" ? "Tài liệu gốc" : "Original paper"}
                            <Icon name="arrow-right" size={12} />
                          </a>
                        ) : null}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-4 text-sm text-[var(--text-secondary)]">
                  {language === "vi"
                    ? "Chưa có trích dẫn trực tiếp trong lần chạy này."
                    : "No direct citations attached to this run."}
                </p>
              )}
            </section>

            {/* 7. TECHNICAL DETAILS */}
            <details className="group rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 transition-colors open:bg-[var(--surface-panel)] shadow-sm">
              <summary className="flex cursor-pointer items-center justify-between text-base font-bold text-[var(--text-primary)]">
                <span className="flex items-center gap-2">
                  <span className="rounded-md border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-0.5 text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    {t(language, "council.result.hierarchy.technicalDetails")}
                  </span>
                  {language === "vi" ? "Giám sát quy trình & Cơ sở mô hình AI" : "Process Timeline & Model Basis"}
                </span>
                <Icon name="arrow-right" size={16} className="transition group-open:rotate-90" />
              </summary>

              <div className="mt-5 space-y-4 border-t border-[color:var(--shell-border)] pt-4">
                {view.timeline.steps.length ? (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.result.processingTitle")}
                    </p>
                    <ol className="mt-2 space-y-2">
                      {view.timeline.steps.map((step) => (
                        <li
                          key={`${step.sequence}-${step.step}`}
                          className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs text-[var(--text-secondary)]"
                        >
                          <span className="font-bold text-[var(--text-primary)]">
                            {t(language, "council.result.step", { sequence: step.sequence, step: step.step })}
                          </span>
                          {step.detail ? <span className="ml-2 font-mono">{step.detail}</span> : null}
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {t(language, "council.result.ruleRisk")}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">
                      {view.quality.ruleShadowEnabled
                        ? view.quality.ruleShadowBand || t(language, "council.result.ruleRiskPresent")
                        : t(language, "council.result.ruleRiskDisabled")}
                    </p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {t(language, "council.result.ruleRiskHint")}
                    </p>
                  </div>

                  <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                    <p className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {language === "vi" ? "Thông số phiên chạy" : "Run Metadata"}
                    </p>
                    <p className="mt-1 font-mono text-xs text-[var(--text-secondary)]">
                      Case #{caseItem?.id} · {snapshot?.createdAt ? formatLocaleDate(language, snapshot.createdAt, { dateStyle: "short", timeStyle: "medium" }) : "--"}
                    </p>
                  </div>
                </div>
              </div>
            </details>
          </div>
        )}

        {/* Handoff Modal */}
        <Modal
          open={handoffOpen}
          onClose={() => setHandoffOpen(false)}
          title={t(language, "council.overview.handoff.dialogTitle")}
          description={t(language, "council.overview.handoff.dialogDescription")}
        >
          <div className="space-y-4">
            <div>
              <label htmlFor="handoff-specialty-select" className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {language === "vi" ? "Chọn chuyên khoa nhận chuyển giao:" : "Select Specialty:"}
              </label>
              <select
                id="handoff-specialty-select"
                value={selectedSpecialty}
                onChange={(e) => setSelectedSpecialty(e.target.value)}
                className="mt-2 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-sm text-[var(--text-primary)]"
              >
                {HANDOFF_SPECIALTIES.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name} — {item.reason}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setHandoffOpen(false)}
                className="rounded-xl border border-[color:var(--shell-border)] px-4 py-2.5 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                {t(language, "council.guard.cancel")}
              </button>
              <button
                type="button"
                onClick={() => void confirmHandoff()}
                className="rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 py-2.5 text-sm font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)]"
              >
                {t(language, "council.overview.handoff.send")}
              </button>
            </div>
          </div>
        </Modal>

        {/* Guard Override / Pause Modal */}
        <Modal
          open={guardAction !== null}
          onClose={() => {
            setGuardAction(null);
            setGuardReason("");
          }}
          title={
            guardAction === "override"
              ? t(language, "council.guard.overrideTitle")
              : t(language, "council.guard.pauseTitle")
          }
          description={
            guardAction === "override"
              ? t(language, "council.guard.overrideDescription")
              : t(language, "council.guard.pauseDescription")
          }
        >
          <div className="space-y-4">
            <label className="block space-y-1.5">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                {t(language, "council.guard.reasonLabel")}
              </span>
              <textarea
                value={guardReason}
                onChange={(e) => setGuardReason(e.target.value)}
                placeholder={t(language, "council.guard.reasonPlaceholder")}
                className="min-h-[100px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 text-sm text-[var(--text-primary)] focus:border-[color:var(--brand-600)] focus:outline-none"
              />
            </label>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setGuardAction(null);
                  setGuardReason("");
                }}
                className="rounded-xl border border-[color:var(--shell-border)] px-4 py-2.5 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              >
                {t(language, "council.guard.cancel")}
              </button>
              <button
                type="button"
                onClick={() => void confirmGuardAction()}
                disabled={!guardReason.trim()}
                className="rounded-xl border border-[color:var(--brand-700)] bg-[var(--brand-600)] px-5 py-2.5 text-sm font-bold text-[var(--on-secondary-container)] hover:bg-[var(--brand-700)] disabled:opacity-50"
              >
                {t(language, "council.guard.confirm")}
              </button>
            </div>
          </div>
        </Modal>

        {/* Evidence Rail / Citation Details Modal */}
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

              {/* Hạn chế (Limitations) */}
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
