"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { getRole } from "@/lib/auth-store";
import { trackCouncilViewed } from "@/lib/analytics/events";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import {
  CouncilAiDisclosure,
  CouncilCaseRecord,
  CouncilEvidenceAttachment,
  CouncilEvidenceSnapshotOption,
  CouncilRunRecord,
  CouncilStreamStage,
  attachCouncilEvidenceSnapshot,
  buildSnapshotFromCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  listCouncilEvidenceAttachments,
  listCouncilEvidenceSnapshotOptions,
  getCouncilRuns,
  getLatestCouncilCase,
  isCouncilModelDisclosureEnabled,
  isCouncilOversightEnabled,
  isCouncilStreamingEnabled,
  normalizeCouncilRunResult,
  runCouncilCaseById,
  setActiveCouncilCaseId,
  streamCouncilRun,
  submitCouncilOversight,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import type { UserRole } from "@/lib/navigation.config";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

type SeverityLevel = "stable" | "warning" | "critical";
type CouncilBannerState =
  "stable" | "review" | "conflict" | "safety" | "incomplete";
type GuardAction = "override" | "pause";

const PANEL_CLASS =
  "rounded-lg border border-[color:var(--shell-border)] bg-white shadow-sm dark:border-sky-700/60 dark:bg-slate-900/90";
const SOFT_PANEL_CLASS =
  "rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] shadow-sm dark:border-sky-700/70 dark:bg-slate-800/90";
const BODY_TEXT_CLASS = "text-[color:var(--text-primary)] dark:text-slate-100";
const SECONDARY_TEXT_CLASS =
  "text-[color:var(--text-muted)] dark:text-slate-300";
const MUTED_TEXT_CLASS = "text-[color:var(--text-muted)] dark:text-slate-400";

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
  const h = Math.floor(totalSeconds / 3600)
    .toString()
    .padStart(2, "0");
  const m = Math.floor((totalSeconds % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function formatRunTimestamp(language: UILanguage, iso: string): string {
  const parsed = Date.parse(iso);
  if (!Number.isFinite(parsed)) {
    return t(language, "council.history.timestampUnknown");
  }
  try {
    return formatLocaleDate(language, parsed, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return t(language, "council.history.timestampUnknown");
  }
}

// Derive a short, non-PII outcome label for a historical run from its snapshot.
function summarizeRunOutcome(language: UILanguage, run: CouncilRunRecord): string {
  if (run.emergencyTriggered) {
    return t(language, "council.history.outcome.emergency");
  }
  if (!run.result) return t(language, "council.history.outcome.completed");
  try {
    const normalized = normalizeCouncilRunResult(run.result);
    if (normalized.isEmergency) {
      return t(language, "council.history.outcome.emergency");
    }
    if ((normalized.conflicts?.length ?? 0) > 0) {
      return t(language, "council.history.outcome.conflict");
    }
    if (normalized.consensus?.trim()) {
      return t(language, "council.history.outcome.consensus");
    }
    return t(language, "council.history.outcome.completed");
  } catch {
    return t(language, "council.history.outcome.completed");
  }
}

// Derive a concise, user-facing label for the model basis behind a Council
// result (Req 6.3, 6.4). Coarse and non-identifying — safe for every role; the
// raw model identifiers stay admin-only at the call site.
function describeModelBasis(
  language: UILanguage,
  disclosure: CouncilAiDisclosure,
): string {
  const family = disclosure.modelFamily.toLowerCase();
  const version = disclosure.modelVersion.toLowerCase();
  if (/rule/.test(family) || /rule/.test(version)) {
    return t(language, "council.model.ruleBased");
  }
  if (/heuristic|fallback/.test(family) || /heuristic|fallback/.test(version)) {
    return t(language, "council.model.fallback");
  }
  if (/deepseek/.test(family)) {
    return t(language, "council.model.deepseek");
  }
  return disclosure.modelFamily || t(language, "council.model.generic");
}

function getSeverity(
  view: ReturnType<typeof buildCouncilView> | null,
): SeverityLevel {
  if (!view) return "stable";
  if (view.quality.requiresHumanHandoff) return "critical";
  if (
    (view.summary.conflicts?.length ?? 0) > 0 ||
    (view.quality.disagreementIndex ?? 0) >= 0.35
  )
    return "warning";
  return "stable";
}

const HANDOFF_SPECIALTIES = [
  {
    name: "Tim mạch",
    reason:
      "Phù hợp khi cần đánh giá huyết động, đau ngực, loạn nhịp hoặc nguy cơ tim mạch.",
  },
  {
    name: "Nội tiết",
    reason:
      "Phù hợp khi ca bệnh liên quan glucose, đái tháo đường, steroid hoặc rối loạn nội tiết.",
  },
  {
    name: "Thận",
    reason:
      "Đề xuất mời Thận học vì thiếu creatinine/eGFR và có tín hiệu nguy cơ độc thận.",
  },
  {
    name: "Dược lâm sàng",
    reason:
      "Phù hợp khi có thuốc cần chỉnh liều, tương tác thuốc hoặc cần rà soát an toàn đơn thuốc.",
  },
  {
    name: "ICU/Cấp cứu",
    reason:
      "Phù hợp khi có dấu hiệu nguy kịch, tụt huyết áp, suy hô hấp hoặc cần xử trí khẩn.",
  },
  {
    name: "Hô hấp",
    reason: "Phù hợp khi có khó thở, SpO2 giảm, viêm phổi hoặc bệnh phổi nền.",
  },
  {
    name: "Thần kinh",
    reason:
      "Phù hợp khi có rối loạn ý thức, yếu liệt, co giật hoặc nghi đột quỵ.",
  },
] as const;

function normalizeSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function summarizeClinicalText(
  value: string | undefined,
  fallback: string,
): string {
  const text = stripTelemetryLabels(value ?? "").trim();
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

function getTimelineTitle(language: UILanguage, step: string): string {
  const normalized = step.toLowerCase();
  if (/intake|normal/.test(normalized))
    return t(language, "council.overview.timeline.intake");
  if (/specialist|assessment/.test(normalized))
    return t(language, "council.overview.timeline.specialists");
  if (/conflict|review/.test(normalized))
    return t(language, "council.overview.timeline.conflicts");
  if (/consensus|decision/.test(normalized))
    return t(language, "council.overview.timeline.consensus");
  if (/safety|gate|guard/.test(normalized))
    return t(language, "council.overview.timeline.safety");
  if (/final|recommend/.test(normalized))
    return t(language, "council.overview.timeline.final");
  return step;
}

function getTimelineStatus(
  step: string,
  hasMissingData: boolean,
  isProblemStep: boolean,
): "done" | "review" | "missing" | "pending" {
  const normalized = normalizeSearch(step);
  if (
    hasMissingData &&
    /(safety|gate|guard|final|recommend|consensus|decision)/.test(normalized)
  )
    return "missing";
  if (isProblemStep || /conflict|review/.test(normalized)) return "review";
  return "done";
}

function timelineStatusMeta(
  language: UILanguage,
  status: "done" | "review" | "missing" | "pending",
) {
  if (status === "missing")
    return {
      label: t(language, "council.overview.timeline.status.missing"),
      className:
        "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100",
    };
  if (status === "review")
    return {
      label: t(language, "council.overview.timeline.status.review"),
      className:
        "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100",
    };
  if (status === "pending")
    return {
      label: t(language, "council.overview.timeline.status.pending"),
      className:
        "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100",
    };
  return {
    label: t(language, "council.overview.timeline.status.done"),
    className:
      "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100",
  };
}

function bannerMeta(language: UILanguage, state: CouncilBannerState) {
  if (state === "safety") {
    return {
      icon: "emergency_home",
      title: t(language, "council.overview.banner.safety.title"),
      detail: t(language, "council.overview.banner.safety.detail"),
      className:
        "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-500/70 dark:bg-rose-500/20 dark:text-rose-100",
      iconClassName: "bg-rose-600 text-white",
    };
  }
  if (state === "conflict") {
    return {
      icon: "warning",
      title: t(language, "council.overview.banner.conflict.title"),
      detail: t(language, "council.overview.banner.conflict.detail"),
      className:
        "border-orange-300 bg-orange-50 text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100",
      iconClassName: "bg-orange-500 text-white",
    };
  }
  if (state === "review") {
    return {
      icon: "error",
      title: t(language, "council.overview.banner.review.title"),
      detail: t(language, "council.overview.banner.review.detail"),
      className:
        "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100",
      iconClassName: "bg-amber-500 text-white",
    };
  }
  if (state === "incomplete") {
    return {
      icon: "info",
      title: t(language, "council.overview.banner.incomplete.title"),
      detail: t(language, "council.overview.banner.incomplete.detail"),
      className:
        "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-500/70 dark:bg-sky-500/20 dark:text-sky-100",
      iconClassName: "bg-sky-500 text-white",
    };
  }
  return {
    icon: "check_circle",
    title: t(language, "council.overview.banner.stable.title"),
    detail: t(language, "council.overview.banner.stable.detail"),
    className:
      "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100",
    iconClassName: "bg-emerald-600 text-white",
  };
}

export default function CouncilPage() {
  const language = useUILanguage();
  const [queryCaseId, setQueryCaseId] = useState<number | null | undefined>(
    undefined,
  );
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");
  const [role, setRoleState] = useState<UserRole>("normal");
  const [handoffOpen, setHandoffOpen] = useState(false);
  const [selectedSpecialty, setSelectedSpecialty] =
    useState<(typeof HANDOFF_SPECIALTIES)[number]["name"]>("Thận");
  const [guardAction, setGuardAction] = useState<GuardAction | null>(null);
  const [guardReason, setGuardReason] = useState("");
  const [actionNotice, setActionNotice] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [streamStages, setStreamStages] = useState<CouncilStreamStage[]>([]);
  const [runNotice, setRunNotice] = useState("");
  const [runHistory, setRunHistory] = useState<CouncilRunRecord[]>([]);
  const [evidenceOptions, setEvidenceOptions] = useState<
    CouncilEvidenceSnapshotOption[]
  >([]);
  const [evidenceAttachments, setEvidenceAttachments] = useState<
    CouncilEvidenceAttachment[]
  >([]);
  const [evidenceShadowAvailable, setEvidenceShadowAvailable] = useState(false);
  const [selectedEvidenceJobId, setSelectedEvidenceJobId] = useState("");
  const [isAttachingEvidence, setIsAttachingEvidence] = useState(false);
  const [evidenceNotice, setEvidenceNotice] = useState("");
  const [oversightPaused, setOversightPaused] = useState(false);
  const streamingEnabled = isCouncilStreamingEnabled();
  const oversightEnabled = isCouncilOversightEnabled();
  const modelDisclosureEnabled = isCouncilModelDisclosureEnabled();

  useEffect(() => {
    setRoleState(getRole());
    // The Council surface was viewed (Req 9.1). No PII — coarse view label only.
    trackCouncilViewed({ view: "landing" });
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
        setLoadError(safeUserFacingError(cause, t(language, "council.error.loadCase")));
      }
    };
    if (queryCaseId !== undefined) {
      void load();
    }
  }, [queryCaseId]);

  // Load the owner-isolated, newest-first run history for the active case
  // (Req 2.4). Owner isolation is enforced server-side; we render only what the
  // server returns. The /runs endpoint is only mounted when
  // COUNCIL_RUN_HISTORY_ENABLED is on, so an absent endpoint or empty payload
  // degrades gracefully to "no history" (the section simply does not render).
  const activeCaseId = caseItem?.id ?? null;
  useEffect(() => {
    if (!activeCaseId) {
      setRunHistory([]);
      return;
    }
    setEvidenceShadowAvailable(false);
    let active = true;
    const loadRuns = async () => {
      try {
        const runs = await getCouncilRuns(activeCaseId);
        if (active) setRunHistory(runs);
      } catch {
        // Run history disabled (endpoint not mounted) or unavailable — no-op.
        if (active) setRunHistory([]);
      }
    };
    void loadRuns();
    return () => {
      active = false;
    };
  }, [activeCaseId]);

  // This selector receives only completed owner-scoped Research job IDs and
  // opaque provenance counts/categories. It intentionally never loads query
  // text, report prose, citation titles, URLs, or a client-built packet.
  useEffect(() => {
    if (!activeCaseId) {
      setEvidenceOptions([]);
      setEvidenceAttachments([]);
      setSelectedEvidenceJobId("");
      setEvidenceShadowAvailable(false);
      return;
    }
    let active = true;
    const loadEvidence = async () => {
      try {
        const [options, attachments] = await Promise.all([
          listCouncilEvidenceSnapshotOptions(activeCaseId),
          listCouncilEvidenceAttachments(activeCaseId),
        ]);
        if (!active) return;
        setEvidenceOptions(options);
        setEvidenceAttachments(attachments);
        setEvidenceShadowAvailable(true);
      } catch {
        // This optional shadow-review aid must never block the Council case.
        if (active) {
          setEvidenceOptions([]);
          setEvidenceAttachments([]);
          setEvidenceShadowAvailable(false);
        }
      }
    };
    void loadEvidence();
    return () => {
      active = false;
    };
  }, [activeCaseId]);

  // Sync the "not yet confirmed" pause state from the loaded case. The server is
  // the source of truth: `oversight_state === "paused"` means the case was
  // paused via the real oversight endpoint (Req 3.2). Resets when switching
  // cases or when the server reports the pause cleared. Pre-feature payloads
  // omit `oversight_state`, so this is a no-op when the feature is off.
  useEffect(() => {
    setOversightPaused(caseItem?.oversight_state === "paused");
  }, [caseItem?.id, caseItem?.oversight_state]);

  // Re-run the deliberation on the result surface. When streaming is enabled
  // (NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED) we open the SSE deliberation stream
  // and surface progressive stage updates; otherwise we fall back to the
  // existing blocking run. Either way the persisted case is reloaded once the
  // terminal result lands so the rendered view reflects the newest run. (Req 1.3)
  const handleRerun = async () => {
    if (!caseItem || isRunning) return;
    const caseId = caseItem.id;
    const requestPayload =
      caseItem.request && typeof caseItem.request === "object"
        ? { request: caseItem.request as Record<string, unknown> }
        : {};

    setIsRunning(true);
    setRunNotice("");
    setStreamStages([]);

    const reload = async () => {
      try {
        const refreshed = await getCouncilCase(caseId);
        setActiveCouncilCaseId(refreshed.id);
        setCaseItem(refreshed);
      } catch {
        /* keep the current view if the refresh fails; the run itself succeeded */
      }
      try {
        // Refresh run history so a new run appears (newest-first) when the
        // run-history feature is on; no-op gracefully when it is off.
        setRunHistory(await getCouncilRuns(caseId));
      } catch {
        /* run history disabled or unavailable — leave the current list as-is */
      }
    };

    const runBlocking = async () => {
      await runCouncilCaseById(caseId, requestPayload);
      await reload();
      setRunNotice("Đã chạy lại hội chẩn.");
    };

    try {
      if (streamingEnabled) {
        let streamFailed = false;
        try {
          await streamCouncilRun(caseId, requestPayload, {
            onStage: (stage) =>
              setStreamStages((prev) => {
                const next = prev.filter(
                  (item) => item.sequence !== stage.sequence,
                );
                next.push(stage);
                return next.sort((a, b) => a.sequence - b.sequence);
              }),
            onResult: () => {
              setRunNotice("Hội chẩn hoàn tất.");
            },
            onError: () => {
              streamFailed = true;
            },
          });
        } catch {
          streamFailed = true;
        }
        if (streamFailed) {
          // Stream unavailable or errored mid-deliberation: fall back to blocking.
          await runBlocking();
        } else {
          await reload();
        }
      } else {
        await runBlocking();
      }
    } catch (cause) {
      setRunNotice(safeUserFacingError(cause, t(language, "council.error.run")));
    } finally {
      setIsRunning(false);
    }
  };

  const handleAttachEvidence = async () => {
    if (!caseItem || !selectedEvidenceJobId || isAttachingEvidence) return;
    setIsAttachingEvidence(true);
    setEvidenceNotice("");
    try {
      const attached = await attachCouncilEvidenceSnapshot(
        caseItem.id,
        selectedEvidenceJobId,
      );
      setEvidenceAttachments((current) => [attached, ...current]);
      setSelectedEvidenceJobId("");
      setEvidenceNotice(t(language, "council.evidence.attached"));
    } catch (cause) {
      setEvidenceNotice(
        safeUserFacingError(cause, t(language, "council.evidence.attachError")),
      );
    } finally {
      setIsAttachingEvidence(false);
    }
  };

  const snapshot = useMemo(
    () => (caseItem ? buildSnapshotFromCouncilCase(caseItem) : null),
    [caseItem],
  );
  const view = useMemo(
    () => (snapshot ? buildCouncilView(snapshot) : null),
    [snapshot],
  );
  const isAnalyzedCase = useMemo(() => {
    if (!caseItem) return false;
    return (
      caseItem.status === "analyzed" &&
      Boolean(caseItem.result && Object.keys(caseItem.result).length > 0)
    );
  }, [caseItem]);
  const severity = useMemo(() => getSeverity(view), [view]);

  const elapsed = useMemo(
    () => formatElapsed(snapshot?.createdAt),
    [snapshot?.createdAt],
  );

  const consensusText = view?.summary.consensus?.trim() || "";
  const escalationText = view?.summary.escalationReason?.trim() || "";

  // Model & fallback disclosure (Req 6.4, 6.5). Rendered only when the
  // client-readable flag is on AND the ML tier attached an `ai_disclosure`
  // block (present only when COUNCIL_MODEL_DISCLOSURE_ENABLED is on server-side).
  // With the flag off, `disclosure` is null and nothing about disclosure
  // renders — byte-identical to today. The coarse basis + fallback note is safe
  // for every role; the raw model identifiers are gated to admins below.
  const disclosure = modelDisclosureEnabled
    ? (snapshot?.result.aiDisclosure ?? null)
    : null;
  const isAdmin = role === "admin";

  const mapLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = normalizeSearch(lab.name);
      return (
        key.includes("map") ||
        key.includes("mean arterial") ||
        key.includes("huyet ap trung binh")
      );
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
      return (
        key.includes("egfr") || key.includes("gfr") || key.includes("loc cau")
      );
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const conflictSignalText = normalizeSearch(
    [
      ...(view?.summary.conflicts ?? []),
      ...(view?.summary.divergence ?? []),
      view?.summary.escalationReason ?? "",
      view?.summary.consensus ?? "",
    ].join(" "),
  );
  const hasConflictSignals =
    (view?.summary.conflicts?.length ?? 0) > 0 ||
    (view?.quality.disagreementIndex ?? 0) >= 0.35 ||
    /conflict|critical interaction|xung dot|bat dong|divergence|dissent/.test(
      conflictSignalText,
    );
  const requiresSafetyConfirm = Boolean(
    view?.quality.requiresHumanHandoff ||
    view?.urgencyTone === "emergency" ||
    severity === "critical",
  );
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
  const banner = bannerMeta(language, bannerState);
  const finalDecisionBlocked =
    hasConflictSignals || requiresSafetyConfirm || missingCriticalData;
  const renalDataLabel =
    egfrLab != null
      ? `eGFR ${egfrLab}`
      : creatinineLab != null
        ? `${creatinineLab.toFixed(1)} mg/dL`
        : t(language, "council.overview.dataUnavailable");
  const assessmentLabel = missingCriticalData
    ? t(language, "council.overview.assessment.insufficientData")
    : requiresSafetyConfirm
      ? t(language, "council.overview.assessment.clinicianReview")
      : hasConflictSignals
        ? t(language, "council.overview.assessment.reviewDifferences")
        : t(language, "council.overview.assessment.continueDiscussion");
  const assessmentStateLabel = missingCriticalData
    ? t(language, "council.overview.assessment.missingInformation")
    : bannerState === "stable"
      ? t(language, "council.overview.assessment.draft")
      : t(language, "council.overview.assessment.requiresConfirmation");

  const specialistLogs = view?.details.specialistLogs ?? [];
  const cardiologyIndex = specialistLogs.findIndex((log) =>
    /cardio|tim/i.test(normalizeSearch(log.specialist)),
  );
  const primarySpecialistIndex = cardiologyIndex >= 0 ? cardiologyIndex : 0;
  const cardiologyLog = specialistLogs[primarySpecialistIndex];
  const renalEndoLog =
    specialistLogs.find(
      (log, index) =>
        index !== primarySpecialistIndex &&
        /endo|noi tiet|nephro|renal|than|pharma|duoc/i.test(
          normalizeSearch(log.specialist),
        ),
    ) ?? specialistLogs.find((_, index) => index !== primarySpecialistIndex);
  const cardiologyNode = translateSpecialistLabel(
    cardiologyLog?.specialist ?? "Tim mạch",
  );
  const renalEndoNode = translateSpecialistLabel(
    renalEndoLog?.specialist ?? "Nội tiết/Thận",
  );
  const cardiologyDetail = summarizeClinicalText(
    cardiologyLog?.recommendation ?? cardiologyLog?.findings.join(", "),
    "Cân nhắc hỗ trợ huyết động hoặc tăng vận mạch nếu có dấu hiệu tụt huyết áp.",
  );
  const renalEndoDetail = summarizeClinicalText(
    renalEndoLog?.recommendation ?? renalEndoLog?.findings.join(", "),
    "Cảnh báo nguy cơ độc thận hoặc cần chỉnh liều theo creatinine/eGFR.",
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
      time: t(language, "council.overview.timeline.step", {
        sequence: step.sequence,
      }),
      title: getTimelineTitle(language, step.step),
      status: getTimelineStatus(
        step.step,
        missingCriticalData,
        hasConflictSignals &&
          /conflict|review|consensus|safety|final/i.test(step.step),
      ),
    }));
  }, [language, view, missingCriticalData, hasConflictSignals]);

  const selectedSpecialtyMeta =
    HANDOFF_SPECIALTIES.find((item) => item.name === selectedSpecialty) ??
    HANDOFF_SPECIALTIES[2];
  const canUseDoctorActions = role === "doctor" || role === "admin";

  const closeGuardDialog = () => {
    setGuardAction(null);
    setGuardReason("");
  };

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
    closeGuardDialog();

    // Flag OFF (or no active case): byte-identical legacy local-notice behavior;
    // nothing is persisted. (Req 3.6)
    if (!oversightEnabled || !caseItem) {
      setActionNotice(localNotice);
      return;
    }

    // Flag ON: persist server-side. A `pause` flips the case oversight_state so
    // the final recommendation renders as "chưa được xác nhận". (Req 3.2)
    try {
      const result = await submitCouncilOversight(caseItem.id, {
        action,
        reason,
      });
      if (action === "pause" || result.oversightState === "paused") {
        setOversightPaused(true);
        setActionNotice(t(language, "council.overview.guard.pauseRecorded"));
      } else {
        setActionNotice(localNotice);
      }
    } catch {
      // Endpoint absent/unavailable (e.g. server flag still off): fall back to
      // the local-notice behavior so the control never silently fails.
      setActionNotice(localNotice);
    }
  };

  const confirmHandoff = async () => {
    const localNotice = t(language, "council.overview.handoff.prepared", {
      specialty: selectedSpecialtyMeta.name,
      reason: selectedSpecialtyMeta.reason,
    });
    setHandoffOpen(false);

    // Flag OFF (or no active case): byte-identical legacy local-notice behavior;
    // nothing is persisted. (Req 3.6)
    if (!oversightEnabled || !caseItem) {
      setActionNotice(localNotice);
      return;
    }

    // Flag ON: persist the handoff against the case. (Req 3.1)
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
      // Endpoint absent/unavailable: fall back to the local-notice behavior.
      setActionNotice(localNotice);
    }
  };

  if (!view || !isAnalyzedCase) {
    return (
      <PageShell title="" variant="plain">
        <div className="space-y-5">
          <CouncilWorkspaceNav />
          <CouncilEmptyState
            title={t(language, "council.overview.empty.title")}
            description={
              loadError ||
              t(language, "council.overview.empty.description")
            }
          />
          <div className="flex">
            <Link
              href="/council/new"
              className="inline-flex min-h-[44px] items-center rounded-lg border border-[color:var(--brand-600)] bg-[color:var(--brand-600)] px-4 text-sm font-semibold text-white shadow-sm hover:bg-[color:var(--brand-700)]"
            >
              {t(language, "council.overview.empty.openCase")}
            </Link>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="" variant="plain">
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section
          className={`rounded-xl border p-4 shadow-sm ${banner.className}`}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${banner.iconClassName}`}
              >
                <span className="material-symbols-outlined text-[22px]">
                  {banner.icon}
                </span>
              </div>
              <div>
                <h2 className="text-lg font-extrabold tracking-tight">
                  {banner.title}
                </h2>
                <p className="mt-1 max-w-3xl text-sm font-medium leading-relaxed">
                  {banner.detail}
                </p>
                {missingDataLabels.length > 0 ? (
                  <p className="mt-2 text-xs font-bold">
                    {t(language, "council.overview.summary.missingData")} {missingDataLabels.join(", ")}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="rounded-lg border border-current/20 bg-white/60 px-3 py-2 text-left sm:text-right dark:bg-slate-950/20">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] opacity-80">
                {t(language, "council.overview.elapsed")}
              </p>
              <p className="font-mono text-xl font-bold">{elapsed}</p>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-8">
            <article className={`${PANEL_CLASS} overflow-hidden p-6`}>
              <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h3
                  className={`flex items-center gap-2 text-sm font-bold uppercase tracking-[0.14em] ${SECONDARY_TEXT_CLASS}`}
                >
                  <span className="h-4 w-1 rounded-full bg-[color:var(--brand-600)]" />
                  {t(language, "council.overview.conflictMap.title")}
                </h3>
                <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1 text-xs font-bold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
                  {t(language, "council.overview.conflictMap.noAutomaticConsensus")}
                </span>
              </div>

              <div className={`${SOFT_PANEL_CLASS} p-5`}>
                <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-stretch">
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-white p-4 dark:border-sky-700 dark:bg-slate-950/40">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[color:var(--surface-brand-soft)] text-[color:var(--brand-700)] dark:bg-sky-500/20 dark:text-sky-100">
                        <span className="material-symbols-outlined">
                          cardiology
                        </span>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[color:var(--brand-600)] dark:text-sky-200">
                          {cardiologyNode}
                        </p>
                        <p
                          className={`mt-1 text-sm font-semibold ${BODY_TEXT_CLASS}`}
                        >
                          {t(language, "council.overview.conflictMap.cardiologyPrompt")}
                        </p>
                      </div>
                    </div>
                    <p
                      className={`mt-4 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                    >
                      {cardiologyDetail}
                    </p>
                  </div>

                  <div className="flex items-center justify-center">
                    <div className="flex min-h-[116px] w-full flex-col items-center justify-center rounded-lg border border-orange-300 bg-orange-50 px-4 text-center text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100 md:w-[150px]">
                      <span className="material-symbols-outlined text-3xl">
                        sync_problem
                      </span>
                      <p className="mt-2 text-xs font-black uppercase tracking-[0.12em]">
                        {t(language, "council.overview.conflictMap.criticalConflict")}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-white p-4 dark:border-sky-700 dark:bg-slate-950/40">
                    <div className="flex items-center gap-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-rose-50 text-rose-700 dark:bg-rose-500/20 dark:text-rose-100">
                        <span className="material-symbols-outlined">
                          medication
                        </span>
                      </div>
                      <div>
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-rose-700 dark:text-rose-200">
                          {renalEndoNode}
                        </p>
                        <p
                          className={`mt-1 text-sm font-semibold ${BODY_TEXT_CLASS}`}
                        >
                          {t(language, "council.overview.conflictMap.renalPrompt")}
                        </p>
                      </div>
                    </div>
                    <p
                      className={`mt-4 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                    >
                      {renalEndoDetail}
                    </p>
                  </div>
                </div>

                <div className="mt-4 rounded-lg border border-orange-200 bg-white p-4 dark:border-orange-500/60 dark:bg-slate-950/40">
                  <p className="text-sm font-bold text-orange-800 dark:text-orange-100">
                    {t(language, "council.overview.conflictMap.question")}
                  </p>
                  <p
                    className={`mt-1 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                  >
                    {conflictDetail}
                  </p>
                </div>
              </div>
            </article>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[color:var(--brand-600)] dark:text-sky-200">
                    MAP
                  </p>
                  <span className="material-symbols-outlined text-sm text-[color:var(--brand-600)] dark:text-sky-200">
                    show_chart
                  </span>
                </div>
                <div className="flex items-end gap-2">
                  <span
                    className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}
                  >
                    {mapLab != null
                      ? `${mapLab} mmHg`
                      : t(language, "council.overview.dataUnavailable")}
                  </span>
                </div>
                <p className={`mt-3 text-xs ${MUTED_TEXT_CLASS}`}>
                  {t(language, "council.overview.assessment.mapHint")}
                </p>
              </article>

              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[color:var(--brand-600)] dark:text-sky-200">
                    Creatinine/eGFR
                  </p>
                  <span className="material-symbols-outlined text-sm text-[color:var(--brand-600)] dark:text-sky-200">
                    science
                  </span>
                </div>
                <div className="flex items-end gap-2">
                  <span
                    className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}
                  >
                    {renalDataLabel}
                  </span>
                </div>
                <p className={`mt-3 text-xs ${MUTED_TEXT_CLASS}`}>
                  {t(language, "council.overview.assessment.renalHint")}
                </p>
              </article>

              <article className={`${PANEL_CLASS} p-4`}>
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[color:var(--brand-600)] dark:text-sky-200">
                    {t(language, "council.overview.assessment.title")}
                  </p>
                  <span className="material-symbols-outlined text-sm text-[color:var(--brand-600)] dark:text-sky-200">
                    bolt
                  </span>
                </div>
                <div className="flex items-end gap-2">
                  <span
                    className={`text-2xl font-bold tracking-tight ${BODY_TEXT_CLASS}`}
                  >
                    {assessmentLabel}
                  </span>
                  <span
                    className={`mb-1 text-xs font-bold ${MUTED_TEXT_CLASS}`}
                  >
                    {assessmentStateLabel}
                  </span>
                </div>
                <p className={`mt-4 text-xs ${MUTED_TEXT_CLASS}`}>
                  {t(language, "council.overview.assessment.disclaimer")}
                </p>
                {missingCriticalData ? (
                  <p className="mt-3 text-xs font-semibold text-amber-800 dark:text-amber-200">
                    {t(language, "council.overview.assessment.missingReason", {
                      items: missingDataLabels.join(
                        t(language, "council.overview.listJoin"),
                      ),
                    })}
                  </p>
                ) : null}
              </article>
            </div>
          </div>

          <div className="flex flex-col gap-6 xl:col-span-4">
            <article className={`${PANEL_CLASS} flex-1 p-6`}>
              <h3
                className={`mb-6 flex items-center gap-2 text-sm font-bold uppercase tracking-[0.14em] ${SECONDARY_TEXT_CLASS}`}
              >
                <span className="material-symbols-outlined text-[color:var(--brand-600)] dark:text-sky-200">
                  history
                </span>
                {t(language, "council.overview.timeline.title")}
              </h3>

              {timeline.length ? (
                <div className="relative space-y-6">
                  <div className="absolute bottom-2 left-2.5 top-2 w-px bg-[color:var(--shell-border)] dark:bg-sky-800" />
                  {timeline.map((step) => {
                    const meta = timelineStatusMeta(language, step.status);
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
                          <div
                            className={`h-1.5 w-1.5 rounded-full ${innerDotClass}`}
                          />
                        </div>
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <p
                            className={`text-[10px] font-bold uppercase tracking-[0.14em] ${MUTED_TEXT_CLASS}`}
                          >
                            {step.time}
                          </p>
                          <span
                            className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${meta.className}`}
                          >
                            {meta.label}
                          </span>
                        </div>
                        <p className={`text-sm font-bold ${BODY_TEXT_CLASS}`}>
                          {step.title}
                        </p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className={`text-xs ${SECONDARY_TEXT_CLASS}`}>
                  {t(language, "council.overview.timeline.empty")}
                </p>
              )}

              {streamingEnabled && streamStages.length > 0 ? (
                <div className="mt-6 rounded-lg border border-sky-200 bg-sky-50 p-4 dark:border-sky-500/60 dark:bg-sky-500/10">
                  <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-200">
                    {t(language, "council.overview.timeline.liveProgress")}
                  </p>
                  <ul className="mt-2 space-y-2">
                    {streamStages.map((stage) => (
                      <li
                        key={`${stage.sequence}-${stage.step}`}
                        className="flex items-start gap-2"
                      >
                        <span className="material-symbols-outlined text-base text-sky-600 dark:text-sky-200">
                          bolt
                        </span>
                        <div>
                          <p
                            className={`text-sm font-semibold ${BODY_TEXT_CLASS}`}
                          >
                            {getTimelineTitle(language, stage.step)}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="mt-6 flex flex-col gap-2">
                <button
                  type="button"
                  onClick={() => void handleRerun()}
                  disabled={isRunning}
                  className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-lg border border-[color:var(--brand-600)] bg-white px-4 text-sm font-bold text-[color:var(--text-brand)] transition hover:bg-[color:var(--surface-muted)] disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-600 dark:bg-slate-900 dark:text-sky-100 dark:hover:bg-slate-800"
                >
                  <span
                    className={`material-symbols-outlined text-[20px] ${isRunning ? "animate-spin" : ""}`}
                  >
                    {isRunning ? "progress_activity" : "refresh"}
                  </span>
                  {isRunning
                    ? streamingEnabled
                      ? t(language, "council.overview.rerun.live")
                      : t(language, "council.overview.rerun.running")
                    : t(language, "council.overview.rerun.action")}
                </button>
                {runNotice ? (
                  <p
                    className={`text-xs font-semibold ${SECONDARY_TEXT_CLASS}`}
                  >
                    {runNotice}
                  </p>
                ) : null}
              </div>

              {evidenceShadowAvailable ? (
              <div className="mt-6 border-t border-[color:var(--shell-border)] pt-5 dark:border-sky-700/60">
                <div className="flex items-start gap-2">
                  <span className="material-symbols-outlined mt-0.5 text-lg text-[color:var(--brand-600)] dark:text-sky-200">
                    verified
                  </span>
                  <div>
                    <h4 className={`text-sm font-bold ${BODY_TEXT_CLASS}`}>
                      {t(language, "council.evidence.title")}
                    </h4>
                    <p className={`mt-1 text-xs leading-relaxed ${SECONDARY_TEXT_CLASS}`}>
                      {t(language, "council.evidence.description")}
                    </p>
                  </div>
                </div>

                {evidenceAttachments.length > 0 ? (
                  <p className={`mt-3 text-xs font-semibold ${SECONDARY_TEXT_CLASS}`}>
                    {t(language, "council.evidence.current", {
                      count: evidenceAttachments[0].evidence_count,
                      date: formatRunTimestamp(language, evidenceAttachments[0].created_at),
                    })}
                  </p>
                ) : (
                  <p className={`mt-3 text-xs ${MUTED_TEXT_CLASS}`}>
                    {t(language, "council.evidence.noneAttached")}
                  </p>
                )}

                {evidenceOptions.length > 0 ? (
                  <div className="mt-4 space-y-3">
                    <label className={`block text-xs font-bold ${BODY_TEXT_CLASS}`} htmlFor="council-evidence-snapshot">
                      {t(language, "council.evidence.selectorLabel")}
                    </label>
                    <select
                      id="council-evidence-snapshot"
                      value={selectedEvidenceJobId}
                      onChange={(event) => setSelectedEvidenceJobId(event.target.value)}
                      className="min-h-[44px] w-full rounded-lg border border-[color:var(--shell-border)] bg-white px-3 text-sm text-[color:var(--text-primary)] dark:border-sky-700 dark:bg-slate-950 dark:text-slate-100"
                    >
                      <option value="">{t(language, "council.evidence.selectorPlaceholder")}</option>
                      {evidenceOptions.map((option) => (
                        <option key={option.job_id} value={option.job_id}>
                          {t(language, "council.evidence.option", {
                            count: option.evidence_count,
                            date: option.captured_at
                              ? formatRunTimestamp(language, option.captured_at)
                              : t(language, "council.history.timestampUnknown"),
                          })}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleAttachEvidence()}
                      disabled={!selectedEvidenceJobId || isAttachingEvidence}
                      className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-4 text-sm font-bold text-[color:var(--text-primary)] transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700"
                    >
                      <span className={`material-symbols-outlined text-[18px] ${isAttachingEvidence ? "animate-spin" : ""}`}>
                        {isAttachingEvidence ? "progress_activity" : "attach_file"}
                      </span>
                      {isAttachingEvidence
                        ? t(language, "council.evidence.attaching")
                        : t(language, "council.evidence.attach")}
                    </button>
                  </div>
                ) : (
                  <p className={`mt-4 text-xs ${MUTED_TEXT_CLASS}`}>
                    {t(language, "council.evidence.noEligible")}
                  </p>
                )}
                {evidenceNotice ? (
                  <p aria-live="polite" className={`mt-3 text-xs font-semibold ${SECONDARY_TEXT_CLASS}`}>
                    {evidenceNotice}
                  </p>
                ) : null}
              </div>
              ) : null}
            </article>

            {runHistory.length > 0 ? (
              <article className={`${PANEL_CLASS} p-6`}>
                <h3
                  className={`mb-4 flex items-center gap-2 text-sm font-bold uppercase tracking-[0.14em] ${SECONDARY_TEXT_CLASS}`}
                >
                  <span className="material-symbols-outlined text-[color:var(--brand-600)] dark:text-sky-200">
                    manage_history
                  </span>
                  {t(language, "council.history.title")}
                </h3>
                <ol className="space-y-3">
                  {runHistory.map((run, index) => (
                    <li
                      key={run.id}
                      className={`${SOFT_PANEL_CLASS} flex items-start justify-between gap-3 p-3`}
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`text-sm font-bold ${BODY_TEXT_CLASS}`}
                          >
                            {index === 0
                              ? t(language, "council.history.latestRun")
                              : t(language, "council.history.runNumber", {
                                  count: runHistory.length - index,
                                })}
                          </span>
                          {run.emergencyTriggered ? (
                            <span className="rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-800 dark:border-rose-500/70 dark:bg-rose-500/20 dark:text-rose-100">
                              {t(language, "council.history.emergencyBadge")}
                            </span>
                          ) : null}
                        </div>
                        <p className={`mt-1 text-xs ${SECONDARY_TEXT_CLASS}`}>
                          {summarizeRunOutcome(language, run)}
                        </p>
                        {run.modelVersion ? (
                          <p
                            className={`mt-0.5 text-[10px] font-medium uppercase tracking-[0.1em] ${MUTED_TEXT_CLASS}`}
                          >
                            {run.modelVersion}
                          </p>
                        ) : null}
                      </div>
                      <span
                        className={`shrink-0 text-right text-[11px] font-mono ${MUTED_TEXT_CLASS}`}
                      >
                        {formatRunTimestamp(language, run.createdAt)}
                      </span>
                    </li>
                  ))}
                </ol>
              </article>
            ) : null}

            <article className="space-y-3">
              <button
                type="button"
                onClick={() => setHandoffOpen(true)}
                className="group flex w-full items-center justify-between rounded-lg border border-[color:var(--brand-600)] bg-[color:var(--brand-600)] p-4 text-white shadow-sm transition hover:bg-[color:var(--brand-700)]"
              >
                <div className="text-left">
                  <p className="text-base font-black leading-tight">
                    {t(language, "council.overview.handoff.action")}
                  </p>
                  <p className="mt-1 text-xs font-semibold text-blue-100">
                    {t(language, "council.overview.handoff.actionHint")}
                  </p>
                </div>
                <span className="material-symbols-outlined text-3xl transition-transform group-hover:translate-x-1">
                  call
                </span>
              </button>

              {canUseDoctorActions ? (
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setGuardAction("override");
                      setGuardReason("");
                    }}
                    className={`${PANEL_CLASS} flex flex-col items-center gap-2 p-4 text-center transition hover:bg-[color:var(--surface-muted)] dark:hover:bg-slate-800`}
                  >
                    <span className="material-symbols-outlined text-[color:var(--brand-600)] dark:text-sky-200">
                      touch_app
                    </span>
                    <p className="text-xs font-bold text-[color:var(--text-brand)] dark:text-sky-100">
                      {t(language, "council.overview.guard.overrideAction")}
                    </p>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setGuardAction("pause");
                      setGuardReason("");
                    }}
                    className="flex flex-col items-center gap-2 rounded-lg border border-rose-300 bg-rose-50 p-4 text-center transition hover:bg-rose-100 dark:border-rose-500/70 dark:bg-rose-500/20 dark:hover:bg-rose-500/30"
                  >
                    <span className="material-symbols-outlined text-rose-700 dark:text-rose-100">
                      pause_circle
                    </span>
                    <p className="text-xs font-bold text-rose-800 dark:text-rose-100">
                      {t(language, "council.overview.guard.pauseAction")}
                    </p>
                  </button>
                </div>
              ) : null}

              {actionNotice ? (
                <div className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm font-semibold text-emerald-800 dark:border-emerald-500/70 dark:bg-emerald-500/20 dark:text-emerald-100">
                  {actionNotice}
                </div>
              ) : null}

              <div className={`${SOFT_PANEL_CLASS} p-4`}>
                <div className="flex items-center justify-between gap-2">
                  <p className={`text-sm font-bold ${BODY_TEXT_CLASS}`}>
                    {t(language, "council.overview.summary.title")}
                  </p>
                  {oversightPaused ? (
                    <span className="rounded-full border border-orange-300 bg-orange-50 px-3 py-1 text-xs font-bold text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100">
                      {t(language, "council.overview.summary.unconfirmed")}
                    </span>
                  ) : null}
                </div>
                {oversightPaused ? (
                  <p className="mt-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-xs font-semibold text-orange-800 dark:border-orange-500/70 dark:bg-orange-500/20 dark:text-orange-100">
                    {t(language, "council.overview.summary.pausedNotice")}
                  </p>
                ) : null}
                {finalDecisionBlocked ? (
                  <div
                    className={`mt-3 space-y-3 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                  >
                    <p>
                      {t(language, "council.overview.summary.noConsensus")}
                    </p>
                    {hasConflictSignals ? (
                      <p>
                        {t(language, "council.overview.summary.conflictSignal", {
                          first: cardiologyNode,
                          second: renalEndoNode,
                        })}
                      </p>
                    ) : null}
                    {missingDataLabels.length > 0 ? (
                      <div>
                        <p className={`font-bold ${BODY_TEXT_CLASS}`}>
                          {t(language, "council.overview.summary.missingData")}
                        </p>
                        <ul className="mt-1 list-disc space-y-1 pl-5">
                          {missingDataLabels.map((label) => (
                            <li key={label}>{label}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    <div>
                      <p className={`font-bold ${BODY_TEXT_CLASS}`}>
                        {t(language, "council.overview.summary.nextStep")}
                      </p>
                      <ul className="mt-1 list-disc space-y-1 pl-5">
                        <li>
                          {t(language, "council.overview.summary.nextStep.renal")}
                        </li>
                        <li>
                          {t(language, "council.overview.summary.nextStep.pharmacy")}
                        </li>
                        <li>
                          {t(language, "council.overview.summary.nextStep.review")}
                        </li>
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div
                    className={`mt-3 space-y-2 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                  >
                    <p>
                      {t(language, "council.overview.summary.noMaterialConflict")}
                    </p>
                    <p>{t(language, "council.overview.summary.routine")}</p>
                    {consensusText ? (
                      <p>
                        {t(language, "council.overview.summary.recorded", {
                          consensus: consensusText,
                        })}
                      </p>
                    ) : null}
                  </div>
                )}
                {escalationText && finalDecisionBlocked ? (
                  <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs font-semibold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
                    {t(language, "council.overview.summary.systemNote")}{" "}
                    {summarizeClinicalText(
                      escalationText,
                      t(language, "council.overview.summary.professionalReview"),
                    )}
                  </p>
                ) : null}
                <div
                  className={`mt-4 flex items-center justify-between text-xs ${MUTED_TEXT_CLASS}`}
                >
                  <span>{t(language, "council.overview.summary.specialtyConsensus")}</span>
                  <span>
                    {hasConflictSignals
                      ? t(language, "council.overview.summary.needsReview")
                      : t(language, "council.overview.summary.noMaterialConflict")}
                  </span>
                </div>
                <div
                  className={`mt-1 flex items-center justify-between text-xs ${MUTED_TEXT_CLASS}`}
                >
                  <span>{t(language, "council.overview.summary.finalDecision")}</span>
                  <span>
                    {finalDecisionBlocked
                      ? t(language, "council.overview.summary.waitForProfessional")
                      : t(language, "council.overview.summary.checkBeforeUse")}
                  </span>
                </div>
                {disclosure ? (
                  <div className="mt-4 border-t border-[color:var(--shell-border)] pt-3 dark:border-sky-700/60">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-[0.14em] ${MUTED_TEXT_CLASS}`}
                      >
                        {t(language, "council.model.basisLabel")}
                      </span>
                      {disclosure.isFallback ? (
                        <span className="rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-800 dark:border-amber-500/70 dark:bg-amber-500/20 dark:text-amber-100">
                          {t(language, "council.model.degradedBadge")}
                        </span>
                      ) : null}
                    </div>
                    <p
                      className={`mt-1 text-xs leading-relaxed ${SECONDARY_TEXT_CLASS}`}
                    >
                      {t(language, "council.model.generatedBy", {
                        basis: describeModelBasis(language, disclosure),
                      })}
                      {disclosure.isFallback
                        ? t(language, "council.model.fallbackNotice")
                        : ""}
                    </p>
                    {isAdmin &&
                    (disclosure.modelFamily || disclosure.modelVersion) ? (
                      <p
                        className={`mt-1 font-mono text-[10px] ${MUTED_TEXT_CLASS}`}
                      >
                        {[disclosure.modelFamily, disclosure.modelVersion]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </article>
          </div>
        </section>

        {handoffOpen ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6"
            role="dialog"
            aria-modal="true"
          >
            <div className="w-full max-w-2xl rounded-xl border border-[color:var(--shell-border)] bg-white p-5 shadow-xl dark:border-sky-700 dark:bg-slate-900">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className={`text-xl font-black ${BODY_TEXT_CLASS}`}>
                    {t(language, "council.overview.handoff.dialogTitle")}
                  </h3>
                  <p className={`mt-1 text-sm ${SECONDARY_TEXT_CLASS}`}>
                    {t(language, "council.overview.handoff.dialogDescription")}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setHandoffOpen(false)}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-[color:var(--shell-border)] text-[color:var(--text-primary)] hover:bg-[color:var(--surface-muted)] dark:border-sky-700 dark:text-slate-100 dark:hover:bg-slate-800"
                  aria-label={t(language, "council.overview.close")}
                >
                  <span className="material-symbols-outlined text-[20px]">
                    close
                  </span>
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
                          ? "border-[color:var(--brand-600)] bg-[color:var(--surface-brand-soft)] text-[color:var(--text-brand)] shadow-sm dark:border-sky-400 dark:bg-sky-500/20 dark:text-sky-100"
                          : "border-[color:var(--shell-border)] bg-white text-[color:var(--text-primary)] hover:border-[color:var(--brand-600)] hover:bg-[color:var(--surface-muted)] dark:border-sky-800 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500",
                      ].join(" ")}
                    >
                      <p className="font-bold">{item.name}</p>
                      <p className="mt-1 text-xs font-medium leading-relaxed text-[color:var(--text-muted)] dark:text-slate-300">
                        {item.reason}
                      </p>
                    </button>
                  );
                })}
              </div>

              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setHandoffOpen(false)}
                  className="min-h-[44px] rounded-lg border border-[color:var(--shell-border)] bg-white px-4 text-sm font-bold text-[color:var(--text-primary)] hover:bg-[color:var(--surface-muted)] dark:border-sky-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  {t(language, "council.guard.cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmHandoff}
                  className="min-h-[44px] rounded-lg border border-[color:var(--brand-600)] bg-[color:var(--brand-600)] px-4 text-sm font-bold text-white hover:bg-[color:var(--brand-700)]"
                >
                  {t(language, "council.overview.handoff.send")}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {guardAction ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 py-6"
            role="dialog"
            aria-modal="true"
          >
            <div className="w-full max-w-xl rounded-xl border border-[color:var(--shell-border)] bg-white p-5 shadow-xl dark:border-sky-700 dark:bg-slate-900">
              <h3 className={`text-xl font-black ${BODY_TEXT_CLASS}`}>
                {guardAction === "override"
                  ? t(language, "council.guard.overrideTitle")
                  : t(language, "council.guard.pauseTitle")}
              </h3>
              <p
                className={`mt-2 text-sm leading-relaxed ${SECONDARY_TEXT_CLASS}`}
              >
                {guardAction === "override"
                  ? t(language, "council.guard.overrideDescription")
                  : t(language, "council.guard.pauseDescription")}
              </p>
              <label
                className={`mt-4 block text-sm font-bold ${BODY_TEXT_CLASS}`}
                htmlFor="guard-reason"
              >
                {t(language, "council.guard.reasonLabel")}
              </label>
              <textarea
                id="guard-reason"
                value={guardReason}
                onChange={(event) => setGuardReason(event.target.value)}
                className="mt-2 min-h-[120px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 py-3 text-sm text-[color:var(--text-primary)] outline-none transition placeholder:text-[color:var(--text-muted)] focus:border-[color:var(--brand-600)] focus:ring-4 focus:ring-blue-200/70 dark:border-sky-700 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-sky-500/20"
                placeholder={t(language, "council.guard.reasonPlaceholder")}
              />
              <div className="mt-5 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={closeGuardDialog}
                  className="min-h-[44px] rounded-lg border border-[color:var(--shell-border)] bg-white px-4 text-sm font-bold text-[color:var(--text-primary)] hover:bg-[color:var(--surface-muted)] dark:border-sky-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  {t(language, "council.guard.cancel")}
                </button>
                <button
                  type="button"
                  onClick={confirmGuardAction}
                  disabled={!guardReason.trim()}
                  className="min-h-[44px] rounded-lg border border-rose-600 bg-rose-600 px-4 text-sm font-bold text-white transition hover:bg-rose-700 disabled:border-rose-300 disabled:bg-rose-100 disabled:text-rose-800 disabled:hover:bg-rose-100 dark:disabled:border-rose-500/60 dark:disabled:bg-rose-500/20 dark:disabled:text-rose-100"
                >
                  {t(language, "council.guard.confirm")}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
