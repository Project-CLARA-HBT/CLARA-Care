"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilEmptyState from "@/components/council/council-empty-state";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import PageShell from "@/components/ui/page-shell";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  CouncilCaseRecord,
  buildSnapshotFromCouncilCase,
  getActiveCouncilCaseId,
  getCouncilCase,
  getLatestCouncilCase,
  setActiveCouncilCaseId,
} from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";
import { stripTelemetryLabels } from "@/lib/user-facing-text";

type SeverityLevel = "stable" | "warning" | "critical";

/**
 * Vietnamese, jargon-free copy for the primary End_User view (COU-1/COU-2).
 * Framed around consensus vs. divergence per the design and `/huong-dan`
 * vocabulary instead of telemetry/protocol labels.
 * Requirements: 4.1 (no telemetry labels), 5.5 (Vietnamese task-oriented copy).
 */
const SEVERITY_HEADLINE: Record<SeverityLevel, string> = {
  critical: "Cần hội chẩn bác sĩ",
  warning: "Cần xem lại kết quả",
  stable: "Các chuyên khoa đồng thuận",
};

const SEVERITY_SUBTEXT: Record<SeverityLevel, string> = {
  critical: "Có xung đột ý kiến giữa các chuyên khoa, cần bác sĩ xác nhận trước khi quyết định.",
  warning: "Có điểm khác biệt giữa các chuyên khoa, nên rà soát lại trước khi quyết định.",
  stable: "Chưa phát hiện xung đột trong phân tích lần này.",
};

const SEVERITY_ICON: Record<SeverityLevel, string> = {
  critical: "warning",
  warning: "info",
  stable: "check_circle",
};

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

/** Strip any leaked telemetry labels and fall back to calm Vietnamese copy. */
function cleanText(value: string | undefined, fallback: string): string {
  const stripped = stripTelemetryLabels(value ?? "");
  return stripped || fallback;
}

/** Keep node captions short so the diagram layout stays intact. */
function truncate(value: string, max = 48): string {
  const text = value.trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

function getSeverity(view: ReturnType<typeof buildCouncilView> | null): SeverityLevel {
  if (!view) return "stable";
  if (view.quality.requiresHumanHandoff) return "critical";
  if ((view.summary.conflicts?.length ?? 0) > 0 || (view.quality.disagreementIndex ?? 0) >= 0.35) return "warning";
  return "stable";
}

function severityClasses(severity: SeverityLevel): string {
  if (severity === "critical") return "border-red-300/40 bg-red-500/12 text-red-200";
  if (severity === "warning") return "border-amber-300/35 bg-amber-500/12 text-amber-200";
  return "border-emerald-300/35 bg-emerald-500/12 text-emerald-200";
}

export default function CouncilPage() {
  const [queryCaseId, setQueryCaseId] = useState<number | null>(null);
  const [caseItem, setCaseItem] = useState<CouncilCaseRecord | null>(null);
  const [loadError, setLoadError] = useState("");
  const [role, setRole] = useState<UserRole>("normal");

  useEffect(() => {
    setRole(getRole());
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
    if (queryCaseId !== null) {
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
  const isDivergent = severity !== "stable";

  const elapsed = useMemo(() => formatElapsed(snapshot?.createdAt), [snapshot?.createdAt]);

  const firstSpecialist = view?.details.specialistLogs[0];
  const secondSpecialist = view?.details.specialistLogs[1];
  const cardiologyNode = cleanText(firstSpecialist?.specialist, "Chuyên khoa 1");
  const pharmNode = cleanText(secondSpecialist?.specialist, "Chuyên khoa 2");
  const cardiologyDetail = truncate(
    cleanText(firstSpecialist?.recommendation || firstSpecialist?.reasoning, "Ý kiến chuyên khoa 1")
  );
  const pharmDetail = truncate(
    cleanText(secondSpecialist?.recommendation || secondSpecialist?.reasoning, "Ý kiến chuyên khoa 2")
  );
  const consensusText = cleanText(view?.summary.consensus, "Chưa có kết luận đồng thuận.");
  const escalationText = cleanText(view?.summary.escalationReason, "Chưa có ghi chú cần lưu ý.");

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
      const key = lab.name.toLowerCase();
      return key.includes("map") || key.includes("mean arterial") || key.includes("huyet ap");
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const creatinineLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = lab.name.toLowerCase();
      return key.includes("creatin") || key.includes("cre");
    });
    return parseNumericLab(found?.value ?? "");
  }, [view]);

  const timeline = useMemo(() => {
    const base = view?.timeline.steps ?? [];
    return base.slice(0, 6).map((step) => ({
      id: `${step.sequence}-${step.step}`,
      time: `BƯỚC ${step.sequence}`,
      title: cleanText(step.step, "Bước phân tích"),
      detail: cleanText(step.detail, ""),
      critical: step.sequence === base[base.length - 1]?.sequence,
    }));
  }, [view]);

  if (!view || !isAnalyzedCase) {
    return (
      <PageShell
        title="Hội chẩn AI CLARA"
        description="Trình tự: Tạo ca mới → Nhập thông tin → Chọn chuyên khoa → Chạy phân tích. Chưa có ca thì chưa có kết quả."
        variant="plain"
      >
        <div className="space-y-5">
          <CouncilWorkspaceNav />
          <CouncilEmptyState
            title="Chưa có dữ liệu phân tích"
            description={
              loadError ||
              "Ca hiện tại chưa chạy phân tích. Hãy tạo ca mới, hoàn tất nhập thông tin, chọn chuyên khoa rồi chạy phân tích."
            }
          />
          <div className="flex">
            <Link
              href="/council/new"
              className="inline-flex min-h-[44px] items-center rounded-lg border border-cyan-300/65 bg-gradient-to-r from-sky-600 to-cyan-500 px-4 text-sm font-semibold text-white"
            >
              Tạo ca hội chẩn mới
            </Link>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="Hội chẩn AI CLARA"
      description="Tổng hợp ý kiến nhiều chuyên khoa, nêu rõ điểm đồng thuận và điểm khác biệt, và đề xuất hội chẩn bác sĩ khi cần."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className={`relative overflow-hidden rounded-xl border p-4 ${severityClasses(severity)}`}>
          <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 via-transparent to-red-500/10 opacity-70" />
          <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-sm bg-red-400/90 p-1 text-slate-950">
                <span className="material-symbols-outlined">{SEVERITY_ICON[severity]}</span>
              </div>
              <div>
                <h2 className="text-lg font-extrabold tracking-tight">
                  {SEVERITY_HEADLINE[severity]}
                </h2>
                <p className="text-xs tracking-wide opacity-85">
                  {SEVERITY_SUBTEXT[severity]}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-widest opacity-80">Thời gian từ lúc phân tích</p>
              <p className="font-mono text-xl font-bold">{elapsed}</p>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="space-y-6 xl:col-span-8">
            <article className="overflow-hidden rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
              <div className="mb-8 flex items-center justify-between">
                <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                  <span className="h-4 w-1 rounded-full bg-cyan-400" />
                  Đối chiếu ý kiến chuyên khoa
                </h3>
              </div>

              <div className="relative flex h-[380px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
                <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 2px 2px, var(--brand-500) 1px, transparent 0)", backgroundSize: "24px 24px" }} />

                <div className="relative z-10 flex w-full items-center justify-around px-6 sm:px-12">
                  <div className="flex flex-col items-center gap-4 text-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-cyan-300 bg-cyan-500/10 shadow-[0_0_20px_rgba(40,217,243,0.2)]">
                      <span className="material-symbols-outlined text-3xl text-cyan-300">cardiology</span>
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-widest text-cyan-300">{cardiologyNode}</p>
                      <p className="mt-1 text-[10px] text-[var(--text-secondary)]">{cardiologyDetail}</p>
                    </div>
                  </div>

                  <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
                    <div
                      className={[
                        "relative flex h-12 w-12 items-center justify-center rounded text-slate-950",
                        isDivergent
                          ? "bg-red-300 shadow-[0_0_30px_rgba(255,180,171,0.4)]"
                          : "bg-emerald-300 shadow-[0_0_30px_rgba(110,231,183,0.4)]",
                      ].join(" ")}
                    >
                      <span className="material-symbols-outlined font-black">{isDivergent ? "close" : "done"}</span>
                      <div
                        className={[
                          "absolute -top-7 whitespace-nowrap text-[10px] font-bold",
                          isDivergent ? "text-red-200" : "text-emerald-200",
                        ].join(" ")}
                      >
                        {isDivergent ? "Điểm khác biệt" : "Đồng thuận"}
                      </div>
                    </div>
                  </div>

                  <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-55" preserveAspectRatio="none">
                    <path d="M 120 190 Q 380 120 640 190" fill="none" stroke="var(--brand-500)" strokeDasharray="8 4" strokeWidth="2" />
                    <path d="M 120 190 Q 380 260 640 190" fill="none" stroke={isDivergent ? "#ffb4ab" : "#6ee7b7"} strokeDasharray="8 4" strokeWidth="2" />
                  </svg>

                  <div className="flex flex-col items-center gap-4 text-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-red-300 bg-red-500/10 shadow-[0_0_20px_rgba(255,180,171,0.2)]">
                      <span className="material-symbols-outlined text-3xl text-red-200">medication</span>
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-widest text-red-200">{pharmNode}</p>
                      <p className="mt-1 text-[10px] text-[var(--text-secondary)]">{pharmDetail}</p>
                    </div>
                  </div>
                </div>
              </div>
            </article>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <article className="rounded-lg border border-cyan-500/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">Huyết áp trung bình (mmHg)</p>
                  <span className="material-symbols-outlined text-sm text-cyan-300">show_chart</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">
                    {mapLab != null ? String(mapLab) : "--"}
                  </span>
                  <span className="mb-1 text-xs font-bold text-[var(--text-muted)]">{mapLab != null ? "Trực tiếp" : "Chưa có"}</span>
                </div>
                <div className="relative mt-4 h-10 overflow-hidden rounded-sm bg-[var(--surface-muted)]">
                  <svg className="h-full w-full"><path d="M0 20 Q 20 10 40 25 T 80 15 T 120 30 T 160 10 T 200 20" fill="none" stroke="var(--brand-500)" strokeWidth="1" /></svg>
                </div>
              </article>

              <article className="rounded-lg border border-red-300/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Creatinine máu</p>
                  <span className="material-symbols-outlined text-sm text-red-200">science</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">
                    {creatinineLab != null ? creatinineLab.toFixed(1) : "--"}
                  </span>
                  <span className="mb-1 text-xs font-bold text-[var(--text-muted)]">{creatinineLab != null ? "Trực tiếp" : "Chưa có"}</span>
                </div>
                <div className="relative mt-4 h-10 overflow-hidden rounded-sm bg-[var(--surface-muted)]">
                  <svg className="h-full w-full"><path d="M0 30 L 50 25 L 100 20 L 150 15 L 200 10" fill="none" stroke="#ffb4ab" strokeWidth="1" /></svg>
                </div>
              </article>

              <article className="rounded-lg border border-cyan-500/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">Độ tin cậy phân tích</p>
                  <span className="material-symbols-outlined text-sm text-cyan-300">bolt</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">
                    {confidencePct != null ? `${confidencePct}%` : "--"}
                  </span>
                  <span className="mb-1 text-xs font-bold text-[var(--text-muted)]">{severity === "critical" ? "Chưa ổn định" : "Ổn định"}</span>
                </div>
                <div className="mt-6 h-2 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
                  <div className="h-full bg-cyan-400" style={{ width: `${confidencePct ?? 0}%` }} />
                </div>
              </article>
            </div>
          </div>

          <div className="flex flex-col gap-6 xl:col-span-4">
            <article className="flex-1 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
              <h3 className="mb-6 flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                <span className="material-symbols-outlined text-cyan-300">history</span>
                Diễn tiến phân tích
              </h3>

              {timeline.length ? (
                <div className="relative space-y-6">
                  <div className="absolute bottom-2 left-2.5 top-2 w-px bg-[color:var(--shell-border)]" />
                  {timeline.map((step) => (
                    <div className="relative pl-8" key={step.id}>
                      <div
                        className={[
                          "absolute left-0 top-1 flex h-5 w-5 items-center justify-center rounded-full border-2",
                          step.critical
                            ? "border-red-300 bg-red-500/20"
                            : "border-cyan-300 bg-cyan-500/10",
                        ].join(" ")}
                      >
                        <div className={`h-1.5 w-1.5 rounded-full ${step.critical ? "bg-red-300" : "bg-cyan-300"}`} />
                      </div>
                      <p className={`mb-1 text-[10px] font-mono uppercase ${step.critical ? "text-red-200" : "text-[var(--text-muted)]"}`}>{step.time}</p>
                      <p className={`text-xs font-bold tracking-tight ${step.critical ? "text-red-100" : "text-[var(--text-primary)]"}`}>{step.title}</p>
                      {step.detail ? (
                        <p className="mt-1 text-[10px] leading-relaxed text-[var(--text-secondary)]">{step.detail}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-secondary)]">Chưa có diễn tiến phân tích từ lần chạy gần nhất.</p>
              )}
            </article>

            <article className="space-y-3">
              <Link
                href="/council/new"
                className="group flex w-full items-center justify-between rounded-lg bg-gradient-to-r from-cyan-500 to-cyan-700 p-4 text-slate-950 transition-all hover:shadow-[0_0_20px_rgba(40,217,243,0.3)]"
              >
                <div className="text-left">
                  <p className="text-lg font-black uppercase leading-none tracking-tight">Hội chẩn bác sĩ phụ trách</p>
                  <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-900/70">Kết nối bác sĩ trực</p>
                </div>
                <span className="material-symbols-outlined text-3xl transition-transform group-hover:translate-x-1">call</span>
              </Link>

              <div className="grid grid-cols-2 gap-3">
                <Link href="/council/result" className="flex flex-col items-center gap-2 rounded-lg border border-cyan-300/25 bg-[var(--surface-panel)] p-4 transition hover:bg-[var(--surface-muted)]">
                  <span className="material-symbols-outlined text-cyan-300">touch_app</span>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-200">Tự quyết định</p>
                </Link>
                <button type="button" className="flex flex-col items-center gap-2 rounded-lg border border-red-300/25 bg-[var(--surface-panel)] p-4 transition hover:bg-[var(--surface-muted)]">
                  <span className="material-symbols-outlined text-red-200">pause_circle</span>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Tạm dừng phân tích</p>
                </button>
              </div>

              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-[10px] font-bold uppercase tracking-tight text-[var(--text-primary)]">Tóm tắt hội chẩn</p>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">{consensusText}</p>
                <p className="mt-3 text-[10px] uppercase tracking-widest text-cyan-300">Điểm cần lưu ý</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{escalationText}</p>

                <TelemetryPanel role={role} className="mt-3 border-t border-[color:var(--shell-border)] pt-3">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">
                    Chỉ số kỹ thuật (chỉ admin)
                  </p>
                  <div className="mt-2 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                    <span>Tỷ lệ đồng thuận</span>
                    <span>{supportRatioPct != null ? `${supportRatioPct}%` : "--"}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                    <span>Mức khác biệt</span>
                    <span>{disagreementPct != null ? `${disagreementPct}%` : "--"}</span>
                  </div>
                  {view.quality.neuralBand ? (
                    <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                      <span>Neural band</span>
                      <span>{view.quality.neuralBand}</span>
                    </div>
                  ) : null}
                  <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                    <span>Diagnostic code</span>
                    <span className="font-mono">CONVERGENCE_FAILURE_0x99</span>
                  </div>
                </TelemetryPanel>
              </div>
            </article>
          </div>
        </section>
      </div>
    </PageShell>
  );
}
