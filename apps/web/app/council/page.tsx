"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { getRole } from "@/lib/auth-store";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";
import type { UserRole } from "@/lib/navigation.config";

type SeverityLevel = "stable" | "warning" | "critical";
type CouncilBannerState = "stable" | "review" | "conflict" | "safety" | "incomplete";
type GuardAction = "override" | "pause";

const PANEL_CLASS = "rounded-lg border border-[#B6D4FE] bg-white shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const SOFT_PANEL_CLASS = "rounded-lg border border-[#93C5FD] bg-[#EEF6FF] shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const BODY_TEXT_CLASS = "text-[#1F2937] dark:text-slate-100";
const SECONDARY_TEXT_CLASS = "text-[#4B5563] dark:text-slate-300";
const MUTED_TEXT_CLASS = "text-[#64748B] dark:text-slate-400";

function parseNumericLab(value: string): number | null {
  const match = value.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatElapsed(fromIso?: string): string {
  if (!fromIso) return "00:00:00";
  const from = Date.parse(fromIso);
  if (!Number.isFinite(from)) return "00:00:00";

  const diffMs = Math.max(0, Date.now() - from);
  const totalSeconds = Math.floor(diffMs / 1000);
  const h = Math.floor(totalSeconds / 3600).toString().padStart(2, "0");
  const m = Math.floor((totalSeconds % 3600) / 60).toString().padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function getSeverity(view: ReturnType<typeof buildCouncilView> | null): SeverityLevel {
  if (!view) return "stable";
  if (view.quality.requiresHumanHandoff) return "critical";
  if ((view.summary.conflicts?.length ?? 0) > 0 || (view.quality.disagreementIndex ?? 0) >= 0.35) return "warning";
  return "stable";
}

const HANDOFF_SPECIALTIES = [
  {
    name: "Tim mạch",
    reason: "Phù hợp khi cần đánh giá huyết động, đau ngực, loạn nhịp hoặc nguy cơ tim mạch.",
  },
  {
    name: "Nội tiết",
    reason: "Phù hợp khi ca bệnh liên quan glucose, đái tháo đường, steroid hoặc rối loạn nội tiết.",
  },
  {
    name: "Thận",
    reason: "Đề xuất mời Thận học vì thiếu creatinine/eGFR và có tín hiệu nguy cơ độc thận.",
  },
  {
    name: "Dược lâm sàng",
    reason: "Phù hợp khi có thuốc cần chỉnh liều, tương tác thuốc hoặc cần rà soát an toàn đơn thuốc.",
  },
  {
    name: "ICU/Cấp cứu",
    reason: "Phù hợp khi có dấu hiệu nguy kịch, tụt huyết áp, suy hô hấp hoặc cần xử trí khẩn.",
  },
  {
    name: "Hô hấp",
    reason: "Phù hợp khi có khó thở, SpO2 giảm, viêm phổi hoặc bệnh phổi nền.",
  },
  {
    name: "Thần kinh",
    reason: "Phù hợp khi có rối loạn ý thức, yếu liệt, co giật hoặc nghi đột quỵ.",
  },
] as const;

function normalizeSearch(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

function summarizeClinicalText(value: string | undefined, fallback: string): string {
  const text = value?.trim();
  if (!text) return fallback;
  const firstLine = text.split(/\n|\.\s+/)[0]?.trim() || text;
  if (firstLine.length <= 130) return firstLine;
  return `${firstLine.slice(0, 127)}...`;
}

function translateSpecialistLabel(value: string): string {
  const normalized = normalizeSearch(value);
  if (/cardio|tim/.test(normalized)) return "Tim mạch";
  if (/endo|noi tiet/.test(normalized)) return "Nội tiết";
  if (/nephro|renal|than/.test(normalized)) return "Thận";
  if (/pharma|duoc/.test(normalized)) return "Dược lâm sàng";
  if (/icu|emergency|cap cuu/.test(normalized)) return "ICU/Cấp cứu";
  if (/pulmo|resp|ho hap/.test(normalized)) return "Hô hấp";
  if (/neuro|than kinh/.test(normalized)) return "Thần kinh";
  return value || "Chuyên khoa";
}

function getTimelineTitle(step: string): string {
  const normalized = step.toLowerCase();
  if (/intake|normal/.test(normalized)) return "Đã chuẩn hóa thông tin ca bệnh";
  if (/specialist|assessment/.test(normalized)) return "Đã phân tích theo từng chuyên khoa";
  if (/conflict|review/.test(normalized)) return "Đã kiểm tra điểm bất đồng";
  if (/consensus|decision/.test(normalized)) return "Đã tổng hợp mức đồng thuận";
  if (/safety|gate|guard/.test(normalized)) return "Đã kiểm tra cổng an toàn";
  if (/final|recommend/.test(normalized)) return "Đề xuất cuối cùng";
  return step;
}

function getTimelineStatus(title: string, hasMissingData: boolean, isProblemStep: boolean): "done" | "review" | "missing" | "pending" {
  if (hasMissingData && /(cổng an toàn|Đề xuất cuối cùng|đồng thuận)/i.test(title)) return "missing";
  if (isProblemStep || /bất đồng/i.test(title)) return "review";
  return "done";
}

function timelineStatusMeta(status: "done" | "review" | "missing" | "pending") {
  if (status === "missing") return { label: "Thiếu dữ liệu", className: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100" };
  if (status === "review") return { label: "Cần xem lại", className: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100" };
  if (status === "pending") return { label: "Chờ bác sĩ xác nhận", className: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100" };
  return { label: "Hoàn tất", className: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100" };
}

function bannerMeta(state: CouncilBannerState) {
  if (state === "safety") {
    return {
      icon: "emergency_home",
      title: "Cần xử trí khẩn / cần xác nhận",
      detail: "Có tín hiệu an toàn hoặc yêu cầu bàn giao cho bác sĩ phụ trách trước khi đưa ra khuyến nghị cuối cùng.",
      className: "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/70 dark:bg-rose-500/20 dark:text-rose-100",
      iconClassName: "bg-rose-600 text-white",
    };
  }
  if (state === "conflict") {
    return {
      icon: "warning",
      title: "Có bất đồng chuyên khoa",
      detail: "Phát hiện tín hiệu khác nhau giữa các chuyên khoa. Cần bác sĩ phụ trách xác nhận trước khi kết luận.",
      className: "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100",
      iconClassName: "bg-orange-500 text-white",
    };
  }
  if (state === "review") {
    return {
      icon: "error",
      title: "Cần bác sĩ xem lại",
      detail: "Có điểm cần kiểm tra thêm trước khi chốt khuyến nghị.",
      className: "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100",
      iconClassName: "bg-amber-500 text-white",
    };
  }
  if (state === "incomplete") {
    return {
      icon: "info",
      title: "Chưa đủ dữ liệu kết luận",
      detail: "Thiếu dữ liệu quan trọng nên hệ thống chưa thể đánh giá mức đồng thuận đáng tin cậy.",
      className: "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100",
      iconClassName: "bg-sky-500 text-white",
    };
  }
  return {
    icon: "check_circle",
    title: "Hội chẩn ổn định",
    detail: "Không phát hiện bất đồng quan trọng giữa các chuyên khoa trong dữ liệu hiện tại.",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100",
    iconClassName: "bg-emerald-600 text-white",
  };
}

export default function CouncilPage() {
  const [queryCaseId, setQueryCaseId] = useState<number | null | undefined>(undefined);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");
  const [role, setRoleState] = useState<UserRole>("normal");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [selectedSpecialty, setSelectedSpecialty] = useState<(typeof HANDOFF_SPECIALTIES)[number]["name"]>("Thận");
  const [guardAction, setGuardAction] = useState<GuardAction | null>(null);
  const [guardReason, setGuardReason] = useState("");
  const [actionNotice, setActionNotice] = useState("");

  useEffect(() => {
    setRoleState(getRole());
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
      setLoadError("");
      try {
        let loaded: CouncilCaseRecord;
        if (queryCaseId) {
          loaded = await getCouncilCase(queryCaseId);
        } else {
          loaded = await getLatestCouncilCase();
        }
        setActiveCouncilCaseId(loaded.id);
        setCaseItem(loaded);
      } catch (cause) {
        setLoadError(cause instanceof Error ? cause.message : "Chưa có case để hiển thị.");
      }
    };
    if (queryCaseId !== undefined) {
      void load();
    }
  }, [queryCaseId]);

  const snapshot = useMemo(() => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null), [caseItem]);
  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const isAnalyzedCase = useMemo(() => {
    if (!caseItem) return false;
    return caseItem.status === "analyzed" && Boolean(caseItem.result && Object.keys(caseItem.result).length > 0);
  }, [caseItem]);
  const severity = useMemo(() => getSeverity(view), [view]);

  const elapsed = useMemo(() => formatElapsed(snapshot?.createdAt), [snapshot?.createdAt]);

  const consensusText = view?.summary.consensus?.trim() || "";
  const escalationText = view?.summary.escalationReason?.trim() || "";

  const supportRatioPct = view?.quality.supportRatio != null
    ? Math.round((view.quality.supportRatio * 100 + Number.EPSILON) * 10) / 10
    : null;
  const disagreementPct = view?.quality.disagreementIndex != null
    ? Math.round((view.quality.disagreementIndex * 100 + Number.EPSILON) * 10) / 10
    : null;
  const confidencePct = view?.quality.neuralProbability != null
    ? Math.max(1, Math.min(100, Math.round(view.quality.neuralProbability * 100)))
    : view?.quality.supportRatio != null
      ? Math.max(1, Math.min(100, Math.round(view.quality.supportRatio * 100)))
      : null;

  const mapLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = normalizeSearch(lab.name);
      return key.includes("map") || key.includes("mean arterial") || key.includes("huyet ap trung binh");
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const creatinineLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = normalizeSearch(lab.name);
      return key.includes("creatin") || key.includes("cre");
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const egfrLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = normalizeSearch(lab.name);
      return key.includes("egfr") || key.includes("gfr") || key.includes("loc cau");
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const conflictSignalText = normalizeSearch(
    [
      ...(view?.summary.conflicts ?? []),
      ...(view?.summary.divergence ?? []),
      view?.summary.escalationReason ?? "",
      view?.summary.consensus ?? "",
    ].join(" ")
  );
  const hasConflictSignals =
    (view?.summary.conflicts?.length ?? 0) > 0 ||
    (view?.quality.disagreementIndex ?? 0) >= 0.35 ||
    /conflict|critical interaction|xung dot|bat dong|divergence|dissent/.test(conflictSignalText);
  const requiresSafetyConfirm = Boolean(view?.quality.requiresHumanHandoff || view?.urgencyTone === "emergency" || severity === "critical");
  const missingMap = mapLab == null;
  const missingRenal = creatinineLab == null && egfrLab == null;
  const missingCriticalData = missingMap || missingRenal;
  const missingDataLabels = [
    missingMap ? "MAP" : "",
    missingRenal ? "Creatinine/eGFR" : "",
  ].filter(Boolean);
  const bannerState: CouncilBannerState = requiresSafetyConfirm
    ? "safety"
    : hasConflictSignals
      ? "conflict"
      : missingCriticalData
        ? "incomplete"
        : severity === "warning"
          ? "review"
          : "stable";
  const banner = bannerMeta(bannerState);
  const finalDecisionBlocked = hasConflictSignals || requiresSafetyConfirm || missingCriticalData;
  const renalDataLabel = egfrLab != null
    ? `eGFR ${egfrLab}`
    : creatinineLab != null
      ? `${creatinineLab.toFixed(1)} mg/dL`
      : "Chưa có dữ liệu";
  const confidenceLabel = missingCriticalData ? "Chưa đủ dữ liệu" : confidencePct != null ? `${confidencePct}%` : "--";
  const confidenceStateLabel = missingCriticalData ? "Thấp" : bannerState === "stable" ? "Ổn định" : "Cần xác nhận";
  const confidenceBarWidth = missingCriticalData ? 28 : confidencePct ?? 0;

  const specialistLogs = view?.details.specialistLogs ?? [];
  const cardiologyIndex = specialistLogs.findIndex((log) => /cardio|tim/i.test(normalizeSearch(log.specialist)));
  const primarySpecialistIndex = cardiologyIndex >= 0 ? cardiologyIndex : 0;
  const cardiologyLog = specialistLogs[primarySpecialistIndex];
  const renalEndoLog =
    specialistLogs.find((log, index) => index !== primarySpecialistIndex && /endo|noi tiet|nephro|renal|than|pharma|duoc/i.test(normalizeSearch(log.specialist))) ??
    specialistLogs.find((_, index) => index !== primarySpecialistIndex);
  const cardiologyNode = translateSpecialistLabel(cardiologyLog?.specialist ?? "Tim mạch");
  const renalEndoNode = translateSpecialistLabel(renalEndoLog?.specialist ?? "Nội tiết/Thận");
  const cardiologyDetail = summarizeClinicalText(
    cardiologyLog?.recommendation ?? cardiologyLog?.reasoning,
    "Cân nhắc hỗ trợ huyết động hoặc tăng vận mạch nếu có dấu hiệu tụt huyết áp."
  );
  const renalEndoDetail = summarizeClinicalText(
    renalEndoLog?.recommendation ?? renalEndoLog?.reasoning,
    "Cảnh báo nguy cơ độc thận hoặc cần chỉnh liều theo creatinine/eGFR."
  );
  const conflictDetail = missingRenal
    ? "Chưa đủ dữ liệu creatinine/eGFR để quyết định thuốc hoặc xử trí có an toàn hay không."
    : hasConflictSignals
      ? "Các chuyên khoa đưa ra tín hiệu khác nhau nên cần bác sĩ phụ trách xác nhận trước khi kết luận."
      : "Chưa phát hiện điểm xung đột lớn trong dữ liệu hiện tại.";

  const timeline = useMemo(() => {
    const base = view?.timeline.steps ?? [];
    return base.slice(0, 6).map((step) => ({
      id: `${step.sequence}-${step.step}`,
      time: `Bước ${step.sequence}`,
      title: getTimelineTitle(step.step),
      detail: step.detail,
      status: getTimelineStatus(
        getTimelineTitle(step.step),
        missingCriticalData,
        hasConflictSignals && /conflict|review|consensus|safety|final/i.test(step.step)
      ),
    }));
  }, [view, missingCriticalData, hasConflictSignals]);

  const selectedSpecialtyMeta =
    HANDOFF_SPECIALTIES.find((item) => item.name === selectedSpecialty) ?? HANDOFF_SPECIALTIES[2];
  const canUseDoctorActions = role === "doctor" || role === "admin";

  const closeGuardDialog = () => {
    setGuardAction(null);
    setGuardReason("");
  };

  const confirmGuardAction = () => {
    if (!guardAction || !guardReason.trim()) return;
    const label = guardAction === "override" ? "ghi đè quyết định" : "tạm dừng quy trình";
    setActionNotice(`Đã ghi nhận yêu cầu ${label}. Lý do: ${guardReason.trim()}`);
    closeGuardDialog();
  };

  const confirmHandoff = () => {
    setActionNotice(`Đã chuẩn bị yêu cầu mời ${selectedSpecialtyMeta.name}. ${selectedSpecialtyMeta.reason}`);
    setHandoffOpen(false);
  };

  if (!view || !isAnalyzedCase) {
    return (
      <PageShell
        title="Hội chẩn AI CLARA"
        description="Tổng hợp nhận định từ nhiều chuyên khoa, phát hiện điểm bất đồng và đề xuất bước xử trí tiếp theo."
        variant="plain"
      >
        <div className="space-y-5">
          <CouncilWorkspaceNav />
          <CouncilEmptyState
            title="Chưa có dữ liệu phân tích"
            description={
              loadError ||
              "Ca hiện tại chưa chạy phân tích. Hãy vào Nhập ca bệnh, hoàn tất thông tin và chạy hội chẩn."
            }
          />
          <div className="flex">
            <Link
              href="/council/new"
              className="inline-flex min-h-[44px] items-center rounded-lg border border-[#2563EB] bg-[#2563EB] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[#1D4ED8]"
            >
              Mở trang nhập ca bệnh
            </Link>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Hội chẩn AI CLARA"
      description="Tổng hợp nhận định từ nhiều chuyên khoa, phát hiện điểm bất đồng và đề xuất bước xử trí tiếp theo."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className={`rounded-xl border p-4 shadow-sm ${banner.className}`}>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${banner.iconClassName}`}>
                <span className="material-symbols-outlined text-[22px]">{banner.icon}</span>
              </div>
              <div>
                <h2 className="text-lg font-extrabold tracking-tight">{banner.title}</h2>
                <p className="mt-1 max-w-3xl text-sm font-medium leading-relaxed">{banner.detail}</p>
                {missingDataLabels.length > 0 ? (
                  <p className="mt-2 text-xs font-bold">Dữ liệu còn thiếu: {missingDataLabels.join(", ")}</p>
                ) : null}
              </div>
            </div>
            <div className="rounded-lg border border-current/20 bg-white/60 px-3 py-2 text-left sm:text-right dark:bg-slate-950/20">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] opacity-80">Thời gian từ lúc chạy</p>
              <p className="font-mono text-xl font-bold">{elapsed}</p>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-8">
            <article className={`${PANEL_CLASS} overflow-hidden p-6`}>
              <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h3 className={`flex items-center gap-2 text-sm font-bold uppercase tracking-[0.14em] ${SECONDARY_TEXT_CLASS}`}>
                  <span className="h-4 w-1 rounded-full bg-[#2563EB]" />
                  Sơ đồ bất đồng chuyên khoa
                </h3>
                <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
                  Hệ thống chưa đạt đồng thuận tự động
                </span>
              </div>

              <div className={`${SOFT_PANEL_CLASS} p-5`}>
                <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-stretch">
                  <div className="rounded-lg border border-[#93C5FD] bg-white p-4 dark:border-sky-700 dark:bg-slate-950/40">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#DBEAFE] text-[#1D4ED8] dark:bg-sky-500/20 dark:text-sky-100">
                        <span className="material-symbols-outlined">cardiology</span>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#2563EB] dark:text-sky-200">{cardiologyNode}</p>
                        <p className={`mt-1 text-sm font-semibold ${BODY_TEXT_CLASS}`}>Tim mạch đề xuất gì?</p>
                      </div>
                    </div>
                    <p className={`mt-4 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>{cardiologyDetail}</p>
                  </div>

                  <div className="flex items-center justify-center">
                    <div className="flex min-h-[116px] w-full flex-col items-center justify-center rounded-lg border border-orange-300 bg-orange-50 px-4 text-center text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100 md:w-[150px]">
                      <span className="material-symbols-outlined text-3xl">sync_problem</span>
                      <p className="mt-2 text-xs font-black uppercase tracking-[0.12em]">Xung đột quan trọng</p>
                    </div>
                  </div>

                  <div className="rounded-lg border border-[#93C5FD] bg-white p-4 dark:border-sky-700 dark:bg-slate-950/40">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-rose-50 text-rose-700 dark:bg-rose-500/20 dark:text-rose-100">
                        <span className="material-symbols-outlined">medication</span>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-rose-700 dark:text-rose-200">{renalEndoNode}</p>
                        <p className={`mt-1 text-sm font-semibold ${BODY_TEXT_CLASS}`}>Nội tiết/Thận cảnh báo gì?</p>
                      </div>
                    </div>
                    <p className={`mt-4 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>{renalEndoDetail}</p>
                  </div>
                </div>

                <div className="mt-4 rounded-lg border border-orange-200 bg-white p-4 dark:border-orange-500/60 dark:bg-slate-950/40">
                  <p className="text-sm font-bold text-orange-800 dark:text-orange-100">Điểm xung đột là gì?</p>
                  <p className={`mt-1 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>{conflictDetail}</p>
                </div>
              </div>
            </article>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#2563EB] dark:text-sky-200">MAP</p>
                  <span className="material-symbols-outlined text-sm text-[#2563EB] dark:text-sky-200">show_chart</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}>
                    {mapLab != null ? `${mapLab} mmHg` : "Chưa có dữ liệu"}
                  </span>
                </div>
                <p className={`mt-3 text-xs ${MUTED_TEXT_CLASS}`}>Dùng để đánh giá huyết động trước khi kết luận.</p>
              </article>

              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#2563EB] dark:text-sky-200">Creatinine/eGFR</p>
                  <span className="material-symbols-outlined text-sm text-[#2563EB] dark:text-sky-200">science</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}>
                    {renalDataLabel}
                  </span>
                </div>
                <p className={`mt-3 text-xs ${MUTED_TEXT_CLASS}`}>Cần cho các thuốc phải chỉnh liều theo chức năng thận.</p>
              </article>

              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#2563EB] dark:text-sky-200">Độ tin cậy AI</p>
                  <span className="material-symbols-outlined text-sm text-[#2563EB] dark:text-sky-200">bolt</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}>
                    {confidenceLabel}
                  </span>
                  <span className={`mb-1 text-xs font-bold ${MUTED_TEXT_CLASS}`}>{confidenceStateLabel}</span>
                </div>
                <div className="mt-5 h-2 w-full overflow-hidden rounded-full bg-[#DBEAFE] dark:bg-slate-700">
                  <div className="h-full bg-[#2563EB]" style={{ width: `${confidenceBarWidth}%` }} />
                </div>
                {missingCriticalData ? (
                  <p className="mt-3 text-xs font-semibold text-amber-800 dark:text-amber-200">
                    Lý do: Thiếu {missingDataLabels.join(" và ")}.
                  </p>
                ) : null}
              </article>
            </div>
          </div>

          <div className="flex flex-col gap-6 xl:col-span-4">
            <article className={`${PANEL_CLASS} flex-1 p-6`}>
              <h3 className={`mb-6 flex items-center gap-2 text-sm font-bold uppercase tracking-[0.14em] ${SECONDARY_TEXT_CLASS}`}>
                <span className="material-symbols-outlined text-[#2563EB] dark:text-sky-200">history</span>
                Timeline hội chẩn
              </h3>

              {timeline.length ? (
                <div className="relative space-y-6">
                  <div className="absolute bottom-2 left-2.5 top-2 w-px bg-[#B6D4FE] dark:bg-sky-800" />
                  {timeline.map((step) => {
                    const meta = timelineStatusMeta(step.status);
                    const dotClass =
                      step.status === "missing"
                        ? "border-sky-400 bg-sky-100"
                        : step.status === "review"
                          ? "border-amber-400 bg-amber-100"
                          : step.status === "pending"
                            ? "border-orange-400 bg-orange-100"
                            : "border-emerald-400 bg-emerald-100";
                    const innerDotClass =
                      step.status === "missing"
                        ? "bg-sky-600"
                        : step.status === "review"
                          ? "bg-amber-600"
                          : step.status === "pending"
                            ? "bg-orange-600"
                            : "bg-emerald-600";
                    return (
                    <div className="relative pl-8" key={step.id}>
                      <div
                        className={[
                          "absolute left-0 top-1 flex h-5 w-5 items-center justify-center rounded-full border-2",
                          dotClass,
                        ].join(" ")}
                      >
                        <div className={`h-1.5 w-1.5 rounded-full ${innerDotClass}`} />
                      </div>
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <p className={`text-[10px] font-bold uppercase tracking-[0.14em] ${MUTED_TEXT_CLASS}`}>{step.time}</p>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${meta.className}`}>{meta.label}</span>
                      </div>
                      <p className={`text-sm font-bold ${BODY_TEXT_CLASS}`}>{step.title}</p>
                      <p className={`mt-1 text-xs leading-relaxed ${SECONDARY_TEXT_CLASS}`}>{step.detail}</p>
                    </div>
                  );
                  })}
                </div>
              ) : (
                <p className={`text-xs ${SECONDARY_TEXT_CLASS}`}>Chưa có timeline hội chẩn từ lần chạy gần nhất.</p>
              )}
            </article>

            <article className="space-y-3">
              <button
                type="button"
                onClick={() => setHandoffOpen(true)}
                className="group flex w-full items-center justify-between rounded-lg border border-[#2563EB] bg-[#2563EB] p-4 text-white shadow-sm transition hover:bg-[#1D4ED8]"
              >
                <div className="text-left">
                  <p className="text-base font-black leading-tight">Mời bác sĩ phụ trách xem lại</p>
                  <p className="mt-1 text-xs font-semibold text-blue-100">Gửi tóm tắt ca và điểm bất đồng cho người trực.</p>
                </div>
                <span className="material-symbols-outlined text-3xl transition-transform group-hover:translate-x-1">call</span>
              </button>

              {canUseDoctorActions ? (
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setGuardAction("override");
                      setGuardReason("");
                    }}
                    className={`${PANEL_CLASS} flex flex-col items-center gap-2 p-4 text-center transition hover:bg-[#F8FBFF] dark:hover:bg-slate-800`}
                  >
                    <span className="material-symbols-outlined text-[#2563EB] dark:text-sky-200">touch_app</span>
                    <p className="text-xs font-bold text-[#1E3A8A] dark:text-sky-100">Ghi đè quyết định</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setGuardAction("pause");
                      setGuardReason("");
                    }}
                    className="flex flex-col items-center gap-2 rounded-lg border border-rose-300 bg-rose-50 p-4 text-center transition hover:bg-rose-100 dark:border-rose-500/70 dark:bg-rose-500/20 dark:hover:bg-rose-500/30"
                  >
                    <span className="material-symbols-outlined text-rose-700 dark:text-rose-100">pause_circle</span>
                    <p className="text-xs font-bold text-rose-800 dark:text-rose-100">Tạm dừng quy trình</p>
                  </button>
                </div>
              ) : null}

              {actionNotice ? (
                <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100">
                  {actionNotice}
                </div>
              ) : null}

              <div className={`${SOFT_PANEL_CLASS} p-4`}>
                <p className={`text-sm font-bold ${BODY_TEXT_CLASS}`}>Tóm tắt hội chẩn</p>
                {finalDecisionBlocked ? (
                  <div className={`mt-3 space-y-3 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>
                    <p>Hệ thống chưa ghi nhận đồng thuận chắc chắn giữa các chuyên khoa.</p>
                    {hasConflictSignals ? (
                      <p>Có tín hiệu cần xem lại liên quan đến {cardiologyNode} và {renalEndoNode}.</p>
                    ) : null}
                    {missingDataLabels.length > 0 ? (
                      <div>
                        <p className={`font-bold ${BODY_TEXT_CLASS}`}>Dữ liệu còn thiếu:</p>
                        <ul className="mt-1 list-disc space-y-1 pl-5">
                          {missingDataLabels.map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div>
                      <p className={`font-bold ${BODY_TEXT_CLASS}`}>Đề xuất tiếp theo:</p>
                      <ul className="mt-1 list-disc space-y-1 pl-5">
                        <li>Bổ sung xét nghiệm chức năng thận nếu có thuốc cần chỉnh liều theo eGFR.</li>
                        <li>Mời Dược lâm sàng hoặc Thận học khi có tín hiệu nguy cơ thuốc.</li>
                        <li>Bác sĩ phụ trách cần xác nhận trước khi đưa ra khuyến nghị cuối cùng.</li>
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div className={`mt-3 space-y-2 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>
                    <p>Không phát hiện bất đồng quan trọng giữa các chuyên khoa.</p>
                    <p>Mức xử trí: theo dõi thường quy.</p>
                    {consensusText ? <p>Ghi nhận: {consensusText}</p> : null}
                  </div>
                )}
                {escalationText && finalDecisionBlocked ? (
                  <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-semibold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
                    Ghi chú hệ thống: {summarizeClinicalText(escalationText, "Cần bác sĩ xem lại.")}
                  </p>
                ) : null}
                <div className={`mt-4 flex items-center justify-between text-xs ${MUTED_TEXT_CLASS}`}>
                  <span>Tỷ lệ đồng thuận</span>
                  <span>{supportRatioPct != null ? `${supportRatioPct}%` : "--"}</span>
                </div>
                <div className={`mt-1 flex items-center justify-between text-xs ${MUTED_TEXT_CLASS}`}>
                  <span>Mức bất đồng</span>
                  <span>{disagreementPct != null ? `${disagreementPct}%` : "--"}</span>
                </div>
              </div>
            </article>
          </div>
        </section>

        {handoffOpen ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6" role="dialog" aria-modal="true">
            <div className="w-full max-w-2xl rounded-xl border border-[#B6D4FE] bg-white p-5 shadow-xl dark:border-sky-700 dark:bg-slate-900">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className={`text-xl font-black ${BODY_TEXT_CLASS}`}>Mời chuyên khoa hội chẩn</h3>
                  <p className={`mt-1 text-sm ${SECONDARY_TEXT_CLASS}`}>Chọn chuyên khoa phù hợp để gửi tóm tắt ca và điểm bất đồng.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setHandoffOpen(false)}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#B6D4FE] text-[#1F2937] hover:bg-[#F8FBFF] dark:border-sky-700 dark:text-slate-100 dark:hover:bg-slate-800"
                  aria-label="Đóng"
                >
                  <span className="material-symbols-outlined text-[20px]">close</span>
                </button>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {HANDOFF_SPECIALTIES.map((item) => {
                  const active = selectedSpecialty === item.name;
                  return (
                    <button
                      key={item.name}
                      type="button"
                      onClick={() => setSelectedSpecialty(item.name)}
                      className={[
                        "rounded-lg border p-3 text-left transition",
                        active
                          ? "border-[#2563EB] bg-[#DBEAFE] text-[#1E3A8A] shadow-sm dark:border-sky-400 dark:bg-sky-500/20 dark:text-sky-100"
                          : "border-[#B6D4FE] bg-white text-[#1F2937] hover:border-[#2563EB] hover:bg-[#F8FBFF] dark:border-sky-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500",
                      ].join(" ")}
                    >
                      <p className="font-bold">{item.name}</p>
                      <p className="mt-1 text-xs font-medium leading-relaxed text-[#4B5563] dark:text-slate-300">{item.reason}</p>
                    </button>
                  );
                })}
              </div>

              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setHandoffOpen(false)}
                  className="min-h-[44px] rounded-lg border border-[#B6D4FE] bg-white px-4 text-sm font-bold text-[#1F2937] hover:bg-[#F8FBFF] dark:border-sky-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={confirmHandoff}
                  className="min-h-[44px] rounded-lg border border-[#2563EB] bg-[#2563EB] px-4 text-sm font-bold text-white hover:bg-[#1D4ED8]"
                >
                  Gửi yêu cầu hội chẩn
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {guardAction ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6" role="dialog" aria-modal="true">
            <div className="w-full max-w-xl rounded-xl border border-[#B6D4FE] bg-white p-5 shadow-xl dark:border-sky-700 dark:bg-slate-900">
              <h3 className={`text-xl font-black ${BODY_TEXT_CLASS}`}>
                {guardAction === "override" ? "Ghi đè quyết định" : "Tạm dừng quy trình"}
              </h3>
              <p className={`mt-2 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}>
                {guardAction === "override"
                  ? "Bạn đang ghi đè đề xuất của hệ thống. Vui lòng nhập lý do lâm sàng."
                  : "Bạn đang tạm dừng quy trình hội chẩn. Vui lòng nhập lý do lâm sàng."}
              </p>
              <label className={`mt-4 block text-sm font-bold ${BODY_TEXT_CLASS}`} htmlFor="guard-reason">
                Lý do lâm sàng *
              </label>
              <textarea
                id="guard-reason"
                value={guardReason}
                onChange={(event) => setGuardReason(event.target.value)}
                className="mt-2 min-h-[120px] w-full rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 py-3 text-sm text-[#1F2937] outline-none transition placeholder:text-[#6B7280] focus:border-[#2563EB] focus:ring-4 focus:ring-blue-200/70 dark:border-sky-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/20"
                placeholder="Ví dụ: Dữ liệu lâm sàng mới cho thấy cần ưu tiên xử trí khác..."
              />
              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={closeGuardDialog}
                  className="min-h-[44px] rounded-lg border border-[#B6D4FE] bg-white px-4 text-sm font-bold text-[#1F2937] hover:bg-[#F8FBFF] dark:border-sky-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={confirmGuardAction}
                  disabled={!guardReason.trim()}
                  className="min-h-[44px] rounded-lg border border-rose-600 bg-rose-600 px-4 text-sm font-bold text-white transition hover:bg-rose-700 disabled:border-rose-300 disabled:bg-rose-100 disabled:text-rose-800 disabled:hover:bg-rose-100 dark:disabled:border-rose-500/60 dark:disabled:bg-rose-500/20 dark:disabled:text-rose-100"
                >
                  Xác nhận
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
