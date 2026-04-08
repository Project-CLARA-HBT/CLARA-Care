"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import CouncilWorkspaceNav from "@/components/council/council-workspace-nav";
import PageShell from "@/components/ui/page-shell";
import { CouncilRunSnapshot, loadCouncilSnapshot } from "@/lib/council";
import { buildCouncilView } from "@/lib/council-view";

type SeverityLevel = "stable" | "warning" | "critical";

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

function severityClasses(severity: SeverityLevel): string {
  if (severity === "critical") return "border-red-300/40 bg-red-500/12 text-red-200";
  if (severity === "warning") return "border-amber-300/35 bg-amber-500/12 text-amber-200";
  return "border-emerald-300/35 bg-emerald-500/12 text-emerald-200";
}

export default function CouncilPage() {
  const [snapshot, setSnapshot] = useState<CouncilRunSnapshot | null>(null);

  useEffect(() => {
    setSnapshot(loadCouncilSnapshot());
  }, []);

  const view = useMemo(() => (snapshot ? buildCouncilView(snapshot) : null), [snapshot]);
  const severity = useMemo(() => getSeverity(view), [view]);

  const elapsed = useMemo(() => formatElapsed(snapshot?.createdAt), [snapshot?.createdAt]);

  const cardiologyNode = view?.details.specialistLogs[0]?.specialist || "Cardiology Specialist AI";
  const pharmNode = view?.details.specialistLogs[1]?.specialist || "Pharmacology Advisor";
  const consensusText = view?.summary.consensus || "Chưa có kết luận đồng thuận.";
  const escalationText = view?.summary.escalationReason || "Không có leo thang bắt buộc.";

  const supportRatioPct = Math.round(((view?.quality.supportRatio ?? 0.42) * 100 + Number.EPSILON) * 10) / 10;
  const disagreementPct = Math.round(((view?.quality.disagreementIndex ?? 0.18) * 100 + Number.EPSILON) * 10) / 10;
  const confidencePct = Math.max(1, Math.min(100, Math.round((view?.quality.neuralProbability ?? view?.quality.supportRatio ?? 0.42) * 100)));

  const mapLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = lab.name.toLowerCase();
      return key.includes("map") || key.includes("mean arterial") || key.includes("huyet ap");
    });
    return parseNumericLab(found?.value ?? "") ?? 58;
  }, [view]);

  const creatinineLab = useMemo(() => {
    const found = view?.requestSummary.labs.find((lab) => {
      const key = lab.name.toLowerCase();
      return key.includes("creatin") || key.includes("cre");
    });
    return parseNumericLab(found?.value ?? "") ?? 2.4;
  }, [view]);

  const timeline = useMemo(() => {
    const base = view?.timeline.steps ?? [];
    if (base.length > 0) {
      return base.slice(0, 3).map((step) => ({
        id: `${step.sequence}-${step.step}`,
        time: `STEP ${step.sequence}`,
        title: step.step,
        detail: step.detail,
        critical: step.sequence === base[base.length - 1]?.sequence,
      }));
    }
    return [
      {
        id: "fallback-1",
        time: "TRIGGER",
        title: "Vitals breach baseline",
        detail: "MAP dropped below threshold. Council lock initiated for manual verification.",
        critical: false,
      },
      {
        id: "fallback-2",
        time: "ANALYSIS",
        title: "Contraindication flagged",
        detail: "Potential nephrotoxicity conflict detected by pharmacology node.",
        critical: false,
      },
      {
        id: "fallback-3",
        time: "ESCALATION",
        title: "Protocol lock",
        detail: "Human-in-the-loop confirmation required before intervention.",
        critical: true,
      },
    ];
  }, [view]);

  return (
    <PageShell
      title="CLARA AI Council"
      description="Risk Escalation Protocol: đồng bộ reasoning nodes, phát hiện conflict, và kích hoạt human-in-the-loop khi cần."
      variant="plain"
    >
      <div className="space-y-5">
        <CouncilWorkspaceNav />

        <section className={`relative overflow-hidden rounded-xl border p-4 ${severityClasses(severity)}`}>
          <div className="absolute inset-0 bg-gradient-to-r from-red-500/10 via-transparent to-red-500/10 opacity-70" />
          <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="rounded-sm bg-red-400/90 p-1 text-slate-950">
                <span className="material-symbols-outlined">warning</span>
              </div>
              <div>
                <h2 className="text-lg font-extrabold uppercase tracking-tight">
                  {severity === "critical" ? "Risk Escalation: Conflict Detected" : severity === "warning" ? "Risk Signal: Review Required" : "Council Stable"}
                </h2>
                <p className="text-xs uppercase tracking-wider opacity-85">
                  {severity === "critical"
                    ? "Protocol Level 4 Active | Manual confirmation required"
                    : severity === "warning"
                      ? "Protocol Level 2 | Conflict signals detected"
                      : "No hard conflict lock in current snapshot"}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-[10px] uppercase tracking-widest opacity-80">Time Since Trigger</p>
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
                  Conflict Logic Diagram
                </h3>
                <span className="rounded bg-cyan-500/10 px-2 py-1 text-[10px] font-mono text-cyan-300">CONVERGENCE_FAILURE_0x99</span>
              </div>

              <div className="relative flex h-[380px] items-center justify-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)]">
                <div className="absolute inset-0 opacity-10" style={{ backgroundImage: "radial-gradient(circle at 2px 2px, #28d9f3 1px, transparent 0)", backgroundSize: "24px 24px" }} />

                <div className="relative z-10 flex w-full items-center justify-around px-6 sm:px-12">
                  <div className="flex flex-col items-center gap-4 text-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-cyan-300 bg-cyan-500/10 shadow-[0_0_20px_rgba(40,217,243,0.2)]">
                      <span className="material-symbols-outlined text-3xl text-cyan-300">cardiology</span>
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-widest text-cyan-300">{cardiologyNode}</p>
                      <p className="mt-1 text-[10px] text-[var(--text-secondary)]">Vasopressor escalation signal</p>
                    </div>
                  </div>

                  <div className="absolute left-1/2 top-1/2 z-20 -translate-x-1/2 -translate-y-1/2">
                    <div className="relative flex h-12 w-12 items-center justify-center rounded bg-red-300 text-slate-950 shadow-[0_0_30px_rgba(255,180,171,0.4)]">
                      <span className="material-symbols-outlined font-black">close</span>
                      <div className="absolute -top-7 whitespace-nowrap text-[10px] font-bold text-red-200">CRITICAL INTERACTION</div>
                    </div>
                  </div>

                  <svg className="pointer-events-none absolute inset-0 h-full w-full opacity-55" preserveAspectRatio="none">
                    <path d="M 120 190 Q 380 120 640 190" fill="none" stroke="#28d9f3" strokeDasharray="8 4" strokeWidth="2" />
                    <path d="M 120 190 Q 380 260 640 190" fill="none" stroke="#ffb4ab" strokeDasharray="8 4" strokeWidth="2" />
                  </svg>

                  <div className="flex flex-col items-center gap-4 text-center">
                    <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-red-300 bg-red-500/10 shadow-[0_0_20px_rgba(255,180,171,0.2)]">
                      <span className="material-symbols-outlined text-3xl text-red-200">medication</span>
                    </div>
                    <div>
                      <p className="text-xs font-bold uppercase tracking-widest text-red-200">{pharmNode}</p>
                      <p className="mt-1 text-[10px] text-[var(--text-secondary)]">Potential nephrotoxicity risk</p>
                    </div>
                  </div>
                </div>
              </div>
            </article>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <article className="rounded-lg border border-cyan-500/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">MAP (mmHg)</p>
                  <span className="material-symbols-outlined text-sm text-cyan-300">show_chart</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">{mapLab}</span>
                  <span className="mb-1 text-xs font-bold text-red-200">▼ 12%</span>
                </div>
                <div className="relative mt-4 h-10 overflow-hidden rounded-sm bg-[var(--surface-muted)]">
                  <svg className="h-full w-full"><path d="M0 20 Q 20 10 40 25 T 80 15 T 120 30 T 160 10 T 200 20" fill="none" stroke="#28d9f3" strokeWidth="1" /></svg>
                </div>
              </article>

              <article className="rounded-lg border border-red-300/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Serum Creatinine</p>
                  <span className="material-symbols-outlined text-sm text-red-200">science</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">{creatinineLab.toFixed(1)}</span>
                  <span className="mb-1 text-xs font-bold text-red-200">▲ 0.8</span>
                </div>
                <div className="relative mt-4 h-10 overflow-hidden rounded-sm bg-[var(--surface-muted)]">
                  <svg className="h-full w-full"><path d="M0 30 L 50 25 L 100 20 L 150 15 L 200 10" fill="none" stroke="#ffb4ab" strokeWidth="1" /></svg>
                </div>
              </article>

              <article className="rounded-lg border border-cyan-500/20 bg-[var(--surface-panel)] p-4">
                <div className="mb-2 flex items-start justify-between">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-300">AI Confidence</p>
                  <span className="material-symbols-outlined text-sm text-cyan-300">bolt</span>
                </div>
                <div className="flex items-end gap-2">
                  <span className="text-3xl font-bold tracking-tighter text-[var(--text-primary)]">{confidencePct}%</span>
                  <span className="mb-1 text-xs font-bold text-[var(--text-muted)]">{severity === "critical" ? "UNSTABLE" : "STABLE"}</span>
                </div>
                <div className="mt-6 h-2 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]">
                  <div className="h-full bg-cyan-400" style={{ width: `${confidencePct}%` }} />
                </div>
              </article>
            </div>
          </div>

          <div className="flex flex-col gap-6 xl:col-span-4">
            <article className="flex-1 rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6">
              <h3 className="mb-6 flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-[var(--text-secondary)]">
                <span className="material-symbols-outlined text-cyan-300">history</span>
                Escalation Log
              </h3>

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
                    <p className={`text-xs font-bold uppercase tracking-tight ${step.critical ? "text-red-100" : "text-[var(--text-primary)]"}`}>{step.title}</p>
                    <p className="mt-1 text-[10px] leading-relaxed text-[var(--text-secondary)]">{step.detail}</p>
                  </div>
                ))}
              </div>
            </article>

            <article className="space-y-3">
              <Link
                href="/council/new"
                className="group flex w-full items-center justify-between rounded-lg bg-gradient-to-r from-cyan-500 to-cyan-700 p-4 text-slate-950 transition-all hover:shadow-[0_0_20px_rgba(40,217,243,0.3)]"
              >
                <div className="text-left">
                  <p className="text-lg font-black uppercase leading-none tracking-tight">Consult Human Lead</p>
                  <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-slate-900/70">Patch to On-call specialist</p>
                </div>
                <span className="material-symbols-outlined text-3xl transition-transform group-hover:translate-x-1">call</span>
              </Link>

              <div className="grid grid-cols-2 gap-3">
                <Link href="/council/result" className="flex flex-col items-center gap-2 rounded-lg border border-cyan-300/25 bg-[var(--surface-panel)] p-4 transition hover:bg-[var(--surface-muted)]">
                  <span className="material-symbols-outlined text-cyan-300">touch_app</span>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-cyan-200">Manual Override</p>
                </Link>
                <button type="button" className="flex flex-col items-center gap-2 rounded-lg border border-red-300/25 bg-[var(--surface-panel)] p-4 transition hover:bg-[var(--surface-muted)]">
                  <span className="material-symbols-outlined text-red-200">pause_circle</span>
                  <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Pause Protocol</p>
                </button>
              </div>

              <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-[10px] font-bold uppercase tracking-tight text-[var(--text-primary)]">Council Summary</p>
                <p className="mt-2 text-xs text-[var(--text-secondary)]">{consensusText}</p>
                <p className="mt-3 text-[10px] uppercase tracking-widest text-cyan-300">Escalation note</p>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">{escalationText}</p>
                <div className="mt-3 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                  <span>Support ratio</span>
                  <span>{supportRatioPct}%</span>
                </div>
                <div className="mt-1 flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                  <span>Disagreement</span>
                  <span>{disagreementPct}%</span>
                </div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </PageShell>
  );
}
