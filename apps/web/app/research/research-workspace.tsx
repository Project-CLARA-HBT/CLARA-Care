"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { getRole, type UserRole } from "@/lib/auth-store";
import {
  executeResearchTier2Job,
  type ExecuteResearchTier2JobOptions,
} from "@/lib/research-tier2-job-runner";
import {
  listSourceHubCatalog,
  requestResearchClarification,
  uploadResearchFile,
  type ResearchClarifyQuestion,
  type ResearchClarifyResult,
  type SourceHubCatalogEntry,
} from "@/lib/research";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import type { UILanguage } from "@/lib/ui-language";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";

type Props = { initialTab?: "frame" | "search" | "synthesize" | "watch" };

function roleLabel(language: UILanguage, role: UserRole): string {
  const key = {
    normal: "research.role.normal",
    researcher: "research.role.researcher",
    doctor: "research.role.doctor",
    admin: "research.role.admin",
  } as const;
  return t(language, key[role]);
}

function resultText(language: UILanguage, payload: Record<string, unknown>): string {
  for (const key of [
    "answer",
    "answer_markdown",
    "markdown",
    "summary",
    "report",
  ]) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return t(language, "research.result.complete");
}

export default function ResearchWorkspace({ initialTab = "frame" }: Props) {
  const language = useUILanguage();
  const [role, setRole] = useState<UserRole>("normal");
  const [tab, setTab] = useState(initialTab);
  const [question, setQuestion] = useState("");
  const [population, setPopulation] = useState("");
  const [intervention, setIntervention] = useState("");
  const [comparator, setComparator] = useState("");
  const [outcomes, setOutcomes] = useState("");
  const [catalog, setCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [uploadedFileIds, setUploadedFileIds] = useState<string[]>([]);
  const [uploadedNames, setUploadedNames] = useState<string[]>([]);
  const [questions, setQuestions] = useState<ResearchClarifyQuestion[]>([]);
  const [clarifyingAnswers, setClarifyingAnswers] = useState<
    Record<string, string>
  >({});
  const [clarifyPending, setClarifyPending] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState(() => t(language, "research.status.ready"));
  const [error, setError] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [jobId, setJobId] = useState("");

  useEffect(() => {
    setRole(getRole());
    void listSourceHubCatalog()
      .then(setCatalog)
      .catch(() => setCatalog([]));
  }, []);

  const protocol = useMemo(() => {
    const fields = [
      population && `Population: ${population}`,
      intervention && `Intervention/Exposure: ${intervention}`,
      comparator && `Comparator: ${comparator}`,
      outcomes && `Outcomes: ${outcomes}`,
    ].filter(Boolean);
    return fields.length
      ? `${question.trim()}\n\n${fields.join("\n")}`
      : question.trim();
  }, [comparator, intervention, outcomes, population, question]);

  const onFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setStatus(t(language, "research.status.uploading", { file: file.name }));
    try {
      const uploaded = await uploadResearchFile(file);
      setUploadedFileIds((current) => [
        ...new Set([...current, ...uploaded.uploadedFileIds]),
      ]);
      setUploadedNames((current) => [...current, file.name]);
      setStatus(t(language, "research.status.fileReady"));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? sanitizeUpstreamError(cause.message)
          : t(language, "research.error.upload"),
      );
      setStatus(t(language, "research.status.ready"));
    } finally {
      event.target.value = "";
    }
  };

  const run = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!protocol) {
      setError(t(language, "research.error.questionRequired"));
      setTab("frame");
      return;
    }
    setError("");
    setResult(null);
    setClarifyPending(true);
    setStatus(t(language, "research.status.reviewingQuestion"));
    let clarification: ResearchClarifyResult;
    try {
      clarification = await requestResearchClarification(protocol, {
        researchMode: "deep",
        uiLanguage: language,
      });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? sanitizeUpstreamError(cause.message)
          : t(language, "research.error.run"),
      );
      setClarifyPending(false);
      setStatus(t(language, "research.status.incomplete"));
      return;
    }
    if (
      clarification.ambiguous &&
      clarification.questions.length &&
      !Object.keys(clarifyingAnswers).length
    ) {
      setQuestions(clarification.questions);
      setClarifyPending(false);
      setTab("frame");
      setStatus(t(language, "research.status.needsClarification"));
      return;
    }
    setClarifyPending(false);
    setIsRunning(true);
    setTab("synthesize");
    setStatus(t(language, "research.status.synthesizing"));
    const options: ExecuteResearchTier2JobOptions = {
      researchMode: "deep",
      retrievalStackMode: "full",
      uploadedFileIds,
      sourceHubSources:
        selectedSources as ExecuteResearchTier2JobOptions["sourceHubSources"],
      clarifyingAnswers,
      uiLanguage: language,
      onJobCreated: (job) => setJobId(job.job_id),
      onSnapshot: (snapshot) => {
        if (snapshot.progress && typeof snapshot.progress === "object") {
          const note = (snapshot.progress as { status_note?: unknown })
            .status_note;
          if (typeof note === "string" && note.trim()) setStatus(note);
        }
      },
    };
    try {
      const completed = await executeResearchTier2Job(protocol, options);
      setResult(completed.finalPayload);
      setStatus(t(language, "research.status.complete"));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? sanitizeUpstreamError(cause.message)
          : t(language, "research.error.run"),
      );
      setStatus(t(language, "research.status.incomplete"));
    } finally {
      setIsRunning(false);
    }
  };

  const tabs = [
    ["frame", t(language, "research.tab.frame")],
    ["search", t(language, "research.tab.search")],
    ["synthesize", t(language, "research.tab.synthesize")],
    ["watch", t(language, "research.tab.watch")],
  ] as const;

  return (
    <div className="min-h-[100dvh] bg-[var(--bg-canvas)] px-3 py-5 text-[var(--text-primary)] sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-[1120px] space-y-8">
        <header className="overflow-hidden rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-6 sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--text-brand)]">
                {t(language, "research.eyebrow")}
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.035em] sm:text-4xl">
                {t(language, "research.title")}
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                {t(language, "research.description")}
              </p>
            </div>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)]">
              {roleLabel(language, role)}
            </span>
          </div>
          <nav
            className="mt-6 flex gap-1 overflow-x-auto"
            aria-label={t(language, "research.stageLabel")}
          >
            {tabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`whitespace-nowrap rounded-lg px-3.5 py-2 text-sm font-semibold ${tab === id ? "bg-[#0053db] text-[#cdd7ff]" : "text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"}`}
              >
                {label}
              </button>
            ))}
          </nav>
        </header>

        <form
          onSubmit={run}
          className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_19rem]"
        >
          <section className="rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-6">
            {tab === "frame" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {t(language, "research.frame.eyebrow")}
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  {t(language, "research.frame.title")}
                </h2>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows={5}
                  placeholder={t(language, "research.frame.placeholder")}
                  className="mt-4 w-full resize-y rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm leading-6 outline-none focus:border-[#a4c9ff] focus:ring-2 focus:ring-[#a4c9ff]/15"
                />
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {[
                    [t(language, "research.field.population"), population, setPopulation],
                    [t(language, "research.field.intervention"), intervention, setIntervention],
                    [t(language, "research.field.comparator"), comparator, setComparator],
                    [t(language, "research.field.outcomes"), outcomes, setOutcomes],
                  ].map(([label, value, setter]) => (
                    <label key={label as string} className="space-y-1.5">
                      <span className="text-xs font-semibold text-[var(--text-secondary)]">
                        {label as string}
                      </span>
                      <input
                        value={value as string}
                        onChange={(e) =>
                          (setter as (value: string) => void)(e.target.value)
                        }
                        className="min-h-11 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm outline-none focus:border-[var(--brand-500)]"
                      />
                    </label>
                  ))}
                </div>
                {questions.length ? (
                  <div className="mt-5 rounded-xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4">
                    <p className="text-sm font-bold text-[var(--status-warn-text)]">
                      {t(language, "research.clarify.title")}
                    </p>
                    {questions.map((item) => (
                      <label
                        key={item.id}
                        className="mt-3 block text-sm text-[var(--status-warn-text)]"
                      >
                        <span className="font-semibold">{item.question}</span>
                        <input
                          value={clarifyingAnswers[item.id] ?? ""}
                          onChange={(e) =>
                            setClarifyingAnswers((current) => ({
                              ...current,
                              [item.id]: e.target.value,
                            }))
                          }
                          className="mt-1.5 min-h-10 w-full rounded-lg border border-[color:var(--status-warn-border)] bg-[var(--bg-elev-2)] px-3 text-[var(--text-primary)] outline-none"
                        />
                      </label>
                    ))}
                  </div>
                ) : null}
              </>
            ) : null}

            {tab === "search" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {t(language, "research.search.eyebrow")}
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  {t(language, "research.search.title")}
                </h2>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  {t(language, "research.search.description")}
                </p>
                <div className="mt-5 grid gap-2 sm:grid-cols-2">
                  {catalog.map((source) => (
                    <label
                      key={source.key}
                      className="flex cursor-pointer gap-3 rounded-xl border border-[color:var(--shell-border)] p-3 hover:bg-[var(--surface-muted)]"
                    >
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(source.key)}
                        onChange={(e) =>
                          setSelectedSources((current) =>
                            e.target.checked
                              ? [...current, source.key]
                              : current.filter((item) => item !== source.key),
                          )
                        }
                        className="mt-1"
                      />
                      <span>
                        <span className="block text-sm font-semibold">
                          {source.label}
                        </span>
                        <span className="block text-xs text-[var(--text-muted)]">
                          {source.description || t(language, "research.search.defaultSource")}
                        </span>
                      </span>
                    </label>
                  ))}
                </div>
                <label className="mt-5 flex min-h-12 cursor-pointer items-center justify-center rounded-xl border border-dashed border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-brand)]">
                  <input
                    type="file"
                    onChange={onFileChange}
                    className="sr-only"
                    accept=".pdf,.txt,.md,.doc,.docx"
                  />
                  {t(language, "research.search.attach")}
                </label>
                {uploadedNames.length ? (
                  <p className="mt-3 text-xs text-[var(--text-secondary)]">
                    {t(language, "research.search.uploaded", { files: uploadedNames.join(", ") })}
                  </p>
                ) : null}
              </>
            ) : null}

            {tab === "synthesize" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {t(language, "research.synthesis.eyebrow")}
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  {t(language, "research.synthesis.title")}
                </h2>
                {result ? (
                  <div className="mt-5 space-y-4">
                    <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm leading-7 whitespace-pre-wrap">
                      {resultText(language, result)}
                    </div>
                    <details className="rounded-2xl border border-[color:var(--shell-border)] p-4">
                      <summary className="cursor-pointer text-sm font-semibold">
                        {t(language, "research.synthesis.details")}
                      </summary>
                      <pre className="mt-3 max-h-[32rem] overflow-auto whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : (
                  <p className="mt-4 rounded-2xl bg-[var(--surface-muted)] p-5 text-sm leading-6 text-[var(--text-secondary)]">
                    {t(language, "research.synthesis.empty")}
                  </p>
                )}
              </>
            ) : null}
            {tab === "watch" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  {t(language, "research.watch.eyebrow")}
                </p>
                <h2 className="mt-1 text-2xl font-bold">{t(language, "research.watch.title")}</h2>
                <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
                  {t(language, "research.watch.description")}
                </p>
                <div className="mt-5 rounded-2xl border border-dashed border-[color:var(--shell-border-strong)] p-5 text-sm text-[var(--text-muted)]">
                  {t(language, "research.watch.note", { job: jobId ? ` · ${jobId}` : "" })}
                </div>
              </>
            ) : null}

            {error ? (
              <p
                role="alert"
                className="mt-4 rounded-xl bg-[var(--status-danger-bg)] px-3 py-2 text-sm text-[var(--status-danger-text)]"
              >
                {error}
              </p>
            ) : null}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)] pt-4">
              <span
                className="text-xs text-[var(--text-muted)]"
                aria-live="polite"
              >
                {status}
              </span>
              <button
                type="submit"
                disabled={isRunning || clarifyPending}
                className="min-h-11 rounded-lg bg-[#60a5fa] px-5 text-sm font-bold text-[#003a6b] transition hover:bg-[#a4c9ff] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRunning ? t(language, "research.action.running") : t(language, "research.action.start")}
              </button>
            </div>
          </section>
          <aside className="space-y-4">
            <div className="rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] p-6">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                {t(language, "research.manifest.eyebrow")}
              </p>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">{t(language, "research.manifest.protocol")}</dt>
                  <dd className="text-right font-semibold">
                    {protocol ? t(language, "research.manifest.created") : t(language, "research.manifest.none")}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">{t(language, "research.manifest.sources")}</dt>
                  <dd className="font-semibold">
                    {selectedSources.length || t(language, "research.manifest.auto")}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">{t(language, "research.manifest.files")}</dt>
                  <dd className="font-semibold">{uploadedFileIds.length}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">{t(language, "research.manifest.job")}</dt>
                  <dd className="max-w-[9rem] truncate font-mono text-xs">
                    {jobId || t(language, "research.manifest.none")}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="rounded-[14px] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-5 text-sm leading-6 text-[var(--text-secondary)]">
              <p className="font-bold">{t(language, "research.guard.title")}</p>
              <p className="mt-2">
                {t(language, "research.guard.description")}
              </p>
            </div>
          </aside>
        </form>
      </div>
    </div>
  );
}
