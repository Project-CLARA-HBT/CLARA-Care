"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import {
  addVisitConcern, answerVisitIntake, approveVisitPack, confirmVisitPlan, createVisit,
  createVisitDocument, createVisitPack, deleteVisitDocument, extractVisitPlan,
  getVisitPackOptions,
  grantVisitScribeConsent, listVisitDocuments, listVisits, revokeVisitScribeConsent,
  revokeVisitShare, shareVisitPack, withdrawVisitDocument, withdrawVisitPlan,
  type Visit, type VisitDocument, type VisitIntakeQuestion, type VisitPack,
  type VisitPlanDraft, type VisitShare,
  type VisitPackOptions,
} from "@/lib/visit-family";

const initialQuestion = (visit: Visit, language: "vi" | "en"): VisitIntakeQuestion => visit.goal.trim()
  ? {
    key: "main_concern",
    text: t(language, "visits.initialQuestionWithGoal"),
    reason: t(language, "visits.initialQuestionWithGoalReason"),
  }
  : {
    key: "visit_goal",
    text: t(language, "visits.initialQuestionWithoutGoal"),
    reason: t(language, "visits.initialQuestionWithoutGoalReason"),
  };

function candidateText(candidate: Record<string, unknown>, index: number, language: "vi" | "en") {
  for (const key of ["text", "title", "instruction", "label", "name"]) {
    if (typeof candidate[key] === "string" && String(candidate[key]).trim()) return String(candidate[key]).trim();
  }
  return t(language, "visits.extractedItem", { index: index + 1 });
}

function candidateSource(candidate: Record<string, unknown>): string {
  const spans = candidate.source_spans;
  if (Array.isArray(spans)) {
    return spans
      .map((span) =>
        span && typeof span === "object" && typeof (span as { text?: unknown }).text === "string"
          ? String((span as { text: string }).text).trim()
          : "",
      )
      .filter(Boolean)
      .join(" … ");
  }
  if (typeof candidate.source_span === "string") return candidate.source_span;
  if (typeof candidate.source_text === "string") return candidate.source_text;
  return "";
}

export default function VisitsPage() {
  const language = useUILanguage();
  const copy = useCallback(
    (key: UITranslationKey, values?: Record<string, string | number>) =>
      t(language, key, values ?? {}),
    [language],
  );
  const [visits, setVisits] = useState<Visit[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [documents, setDocuments] = useState<VisitDocument[]>([]);
  const [question, setQuestion] = useState<VisitIntakeQuestion | null>(null);
  const [answer, setAnswer] = useState("");
  const [progress, setProgress] = useState({ answered: 0, total: 0 });
  const [complete, setComplete] = useState(false);
  const [draft, setDraft] = useState<VisitPlanDraft | null>(null);
  const [candidateIds, setCandidateIds] = useState<string[]>([]);
  const [pack, setPack] = useState<VisitPack | null>(null);
  const [packOptions, setPackOptions] = useState<VisitPackOptions>({
    concerns: [],
    episodes: [],
    events: [],
    medications: [],
    instructions: [],
  });
  const [packSelection, setPackSelection] = useState<Record<string, boolean>>({});
  const [share, setShare] = useState<VisitShare | null>(null);
  const [consented, setConsented] = useState(false);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [when, setWhen] = useState("");
  const [concern, setConcern] = useState("");
  const [priority, setPriority] = useState("routine");
  const [documentTitle, setDocumentTitle] = useState("");
  const [documentText, setDocumentText] = useState("");
  const [documentLink, setDocumentLink] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const selected = useMemo(() => visits.find((visit) => visit.id === selectedId) ?? null, [visits, selectedId]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const next = await listVisits();
      setVisits(next);
      setSelectedId((current) => current || next[0]?.id || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy("visits.loadError"));
    } finally { setLoading(false); }
  }, [copy]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!selectedId) { setDocuments([]); return; }
    void Promise.all([
      listVisitDocuments(selectedId),
      getVisitPackOptions(selectedId),
    ]).then(([nextDocuments, nextOptions]) => {
      setDocuments(nextDocuments);
      setPackOptions(nextOptions);
      setPackSelection({});
    }).catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : copy("visits.loadVisitDataError")),
    );
  }, [copy, selectedId]);

  const choose = (id: string) => {
    setSelectedId(id); setQuestion(null); setComplete(false); setProgress({ answered: 0, total: 0 });
    setDraft(null); setCandidateIds([]); setPack(null); setShare(null); setConsented(false); setPackSelection({});
  };
  const action = async (work: () => Promise<void>, fallback: string) => {
    setSaving(true); setError("");
    try { await work(); } catch (cause) { setError(cause instanceof Error ? cause.message : fallback); }
    finally { setSaving(false); }
  };
  const create = (event: FormEvent) => {
    event.preventDefault();
    void action(async () => {
      const visit = await createVisit({ title: title.trim(), goal: goal.trim(), visit_type: "other", scheduled_at: when ? new Date(when).toISOString() : undefined });
      setTitle(""); setGoal(""); setWhen(""); await load(); choose(visit.id);
    }, copy("visits.createError"));
  };
  const submitIntake = (state: "answered" | "skipped" | "unknown") => {
    if (!selectedId || !question) return;
    if (state === "answered" && !answer.trim()) { setError(copy("visits.answerRequired")); return; }
    void action(async () => {
      const result = await answerVisitIntake(selectedId, { question_key: question.key, response_state: state, answer_text: state === "answered" ? answer.trim() : undefined });
      setAnswer(""); setQuestion(result.next_question); setProgress(result.progress); setComplete(result.complete);
    }, copy("visits.answerError"));
  };
  const saveDocument = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    void action(async () => {
      const link = documentLink.trim();
      if (link) new URL(link);
      const text = file ? await file.text() : "";
      if (!documentTitle.trim() && !file && !link) throw new Error(copy("visits.documentRequired"));
      const created = await createVisitDocument(selectedId, {
        title: documentTitle.trim() || file?.name || new URL(link).hostname,
        text_content: documentText.trim() || text.trim() || undefined,
        media_type: file?.type || (link ? "text/uri-list" : "text/plain"),
        metadata: { capture: "user_selected", ...(file ? { source_file_name: file.name, source_file_size: file.size } : {}), ...(link ? { external_url: link } : {}) },
      });
      setDocuments((current) => [created, ...current]);
      setDocumentTitle(""); setDocumentText(""); setDocumentLink(""); setFile(null);
    }, copy("visits.documentSaveError"));
  };
  const changeDocument = (document: VisitDocument, kind: "withdraw" | "delete") => {
    if (!selectedId) return;
    void action(async () => {
      const next = kind === "withdraw" ? await withdrawVisitDocument(selectedId, document.id) : await deleteVisitDocument(selectedId, document.id);
      setDocuments((current) => current.map((item) => item.id === next.id ? next : item));
    }, copy("visits.documentPermissionError"));
  };
  const extract = (document: VisitDocument) => {
    if (!selectedId) return;
    void action(async () => { setDraft(await extractVisitPlan(selectedId, document.id)); setCandidateIds([]); }, copy("visits.extractError"));
  };
  const confirm = () => {
    if (!selectedId || !draft || !candidateIds.length) return;
    void action(async () => {
      await confirmVisitPlan(selectedId, { draft_id: draft.id, candidate_ids: candidateIds });
      setDraft({ ...draft, status: "confirmed" });
    }, copy("visits.confirmError"));
  };
  const withdrawDraft = () => {
    if (!selectedId || !draft) return;
    void action(async () => { await withdrawVisitPlan(selectedId, draft.id); setDraft({ ...draft, status: "withdrawn" }); setCandidateIds([]); }, copy("visits.withdrawDraftError"));
  };
  const addConcern = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    void action(async () => { await addVisitConcern(selectedId, concern.trim(), priority); setConcern(""); }, copy("visits.concernError"));
  };
  const makePack = () => {
    if (!selectedId) return;
    void action(async () => {
      const selected = (items: Array<{ id: string }>) =>
        items.filter((item) => packSelection[item.id]).map((item) => item.id);
      const created = await createVisitPack(selectedId, {
        concern_ids: selected(packOptions.concerns),
        episode_ids: selected(packOptions.episodes),
        event_ids: selected(packOptions.events),
        medication_course_ids: selected(packOptions.medications),
        instruction_candidate_ids: selected(packOptions.instructions),
        questions: [],
      });
      setPack(await approveVisitPack(created.id)); setShare(null);
    }, copy("visits.packError"));
  };
  const selectedPackCount = Object.values(packSelection).filter(Boolean).length;
  const packGroups = [
    { key: "concerns", label: copy("visits.groupConcerns"), items: packOptions.concerns },
    { key: "medications", label: copy("visits.groupMedications"), items: packOptions.medications },
    { key: "episodes", label: copy("visits.groupEpisodes"), items: packOptions.episodes },
    { key: "events", label: copy("visits.groupEvents"), items: packOptions.events },
    { key: "instructions", label: copy("visits.groupInstructions"), items: packOptions.instructions },
  ];
  const makeShare = () => {
    if (!pack) return;
    void action(async () => setShare(await shareVisitPack(pack.id, new Date(Date.now() + 604800000).toISOString())), copy("visits.shareCreateError"));
  };
  const removeShare = () => {
    if (!pack || !share) return;
    void action(async () => {
      await revokeVisitShare(pack.id, share.id);
      setShare(null);
    }, copy("visits.shareRevokeError"));
  };
  const toggleConsent = () => {
    if (!selectedId) return;
    void action(async () => { if (consented) await revokeVisitScribeConsent(selectedId); else await grantVisitScribeConsent(selectedId); setConsented(!consented); }, copy("visits.scribeConsentError"));
  };

  return <PageShell variant="plain" title={copy("visits.title")} description={copy("visits.description")}>
    {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
    <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_330px]">
      <aside className="space-y-4">
        <SurfaceCard className="overflow-hidden"><div className="border-b border-[color:var(--shell-border)] px-4 py-3"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("visits.listEyebrow")}</p><h2 className="mt-1 font-semibold text-[var(--text-primary)]">{copy("visits.choose")}</h2></div>
          {loading ? <div className="p-3"><LoadingCards count={2} /></div> : visits.length ? <div className="space-y-1 p-2">{visits.map((visit) => <button key={visit.id} type="button" onClick={() => choose(visit.id)} className={"focus-ring w-full rounded-[var(--radius-lg)] p-3 text-left transition " + (selectedId === visit.id ? "bg-[var(--surface-brand-soft)] ring-1 ring-[var(--brand-500)]" : "hover:bg-[var(--surface-muted)]")}><p className="font-medium text-[var(--text-primary)]">{visit.title}</p><p className="mt-1 text-xs text-[var(--text-secondary)]">{visit.scheduled_at ? formatLocaleDate(language, visit.scheduled_at, { dateStyle: "medium", timeStyle: "short" }) : copy("visits.noScheduledTime")}</p></button>)}</div> : <EmptyState icon="event_available" title={copy("visits.emptyTitle")} description={copy("visits.emptyDescription")} />}
        </SurfaceCard>
        <SurfaceCard className="p-4"><p className="text-sm font-semibold text-[var(--text-primary)]">{copy("visits.controlTitle")}</p><p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">{copy("visits.controlDescription")}</p></SurfaceCard>
      </aside>
      <main className="space-y-5">
        {!selected && !loading ? <SurfaceCard><EmptyState icon="assignment" title={copy("visits.startTitle")} description={copy("visits.startDescription")} /></SurfaceCard> : null}
        {selected ? <><SurfaceCard className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("visits.stepOne")}</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{selected.title}</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">{copy("visits.oneQuestionAtATime")}</p></div>{progress.total ? <Badge tone="neutral">{copy("visits.questionCount", { answered: progress.answered, total: progress.total })}</Badge> : null}</div>
          {!question && !complete ? <Button type="button" className="mt-4" onClick={() => setQuestion(initialQuestion(selected, language))}>{copy("visits.startShortQuestions")}</Button> : null}
          {question ? <div className="mt-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"><p className="font-semibold text-[var(--text-primary)]">{question.text}</p><p className="mt-1 text-sm text-[var(--text-secondary)]">{question.reason}</p><Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder={copy("visits.answerPlaceholder")} className="min-h-24" wrapperClassName="mt-3" /><div className="mt-3 flex flex-wrap gap-2"><Button type="button" disabled={saving} onClick={() => submitIntake("answered")}>{copy("visits.saveAndContinue")}</Button><Button type="button" variant="secondary" disabled={saving} onClick={() => submitIntake("skipped")}>{copy("visits.skip")}</Button><Button type="button" variant="secondary" disabled={saving} onClick={() => submitIntake("unknown")}>{copy("visits.unknown")}</Button></div></div> : null}
          {complete ? <p className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-sm text-[var(--status-ok-text)]">{copy("visits.quickPrepComplete")}</p> : null}
        </SurfaceCard>
        <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("visits.stepTwo")}</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{copy("visits.addDocument")}</h2><p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{copy("visits.documentPrivacy")}</p>
          <form className="mt-4 grid gap-3" onSubmit={saveDocument}><Field label={copy("visits.documentName")} value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} /><label className="text-sm font-medium text-[var(--text-primary)]">{copy("visits.textFileOptional")}<input type="file" accept=".txt,.md,.csv,text/plain,text/markdown,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1.5 block w-full text-sm text-[var(--text-secondary)]" /></label><Textarea label={copy("visits.pasteContent")} value={documentText} onChange={(event) => setDocumentText(event.target.value)} className="min-h-20" /><Field label={copy("visits.pasteLink")} type="url" value={documentLink} onChange={(event) => setDocumentLink(event.target.value)} placeholder="https://…" /><Button type="submit" variant="secondary" className="justify-self-start" disabled={saving}>{copy("visits.saveSelectedItem")}</Button></form>
          <div className="mt-5 space-y-2">{documents.length ? documents.map((document) => <div key={document.id} className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-[var(--text-primary)]">{document.title}</p><p className="mt-0.5 text-xs text-[var(--text-secondary)]">{document.deleted_at ? copy("visits.documentDeleted") : document.withdrawn_at ? copy("visits.documentWithdrawn") : document.status === "external_unverified" ? copy("visits.externalUnverified") : copy("visits.documentProcessing")}</p></div>{!document.deleted_at && !document.withdrawn_at ? <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" disabled={saving} onClick={() => extract(document)}>{copy("visits.checkPlan")}</Button><Button type="button" size="sm" variant="secondary" disabled={saving} onClick={() => changeDocument(document, "withdraw")}>{copy("visits.withdrawFromProcessing")}</Button><Button type="button" size="sm" variant="danger" disabled={saving} onClick={() => changeDocument(document, "delete")}>{copy("visits.deleteContent")}</Button></div> : null}</div></div>) : <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-secondary)]">{copy("visits.noDocuments")}</p>}</div>
        </SurfaceCard>
        {draft ? <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("visits.stepThree")}</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{copy("visits.confirmBeforeTasks")}</h2>
          {draft.safe_unavailable || !draft.candidates.length ? <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-sm text-[var(--status-warn-text)]"><p className="font-semibold">{copy("visits.noPlanTitle")}</p><p className="mt-1">{draft.reason || copy("visits.noPlanReason")}</p></div> : <div className="mt-4 space-y-2"><p className="text-sm text-[var(--text-secondary)]">{copy("visits.draftGuidance")}</p>{draft.candidates.map((candidate, index) => { const source = candidateSource(candidate); const checked = candidateIds.includes(candidate.id); const confirmable = Boolean(source) && candidate.classification === "clinician_instruction"; return <label key={candidate.id} className="block rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"><span className="flex gap-3"><input type="checkbox" disabled={!confirmable} checked={checked} onChange={() => setCandidateIds((current) => checked ? current.filter((id) => id !== candidate.id) : [...current, candidate.id])} className="mt-1 h-4 w-4 accent-[var(--brand-600)]" /><span><span className="block font-medium text-[var(--text-primary)]">{candidateText(candidate, index, language)}</span><span className="mt-1 block text-xs font-medium text-[var(--text-muted)]">{candidate.classification === "clinician_instruction" ? copy("visits.clinicianInstruction") : copy("visits.aiInterpretation")}</span><span className="mt-1 block text-sm text-[var(--text-secondary)]">{source ? copy("visits.source", { source }) : copy("visits.noSource")}</span></span></span></label>; })}</div>}
          <div className="mt-4 flex flex-wrap gap-2">{draft.candidates.length && !draft.safe_unavailable ? <Button type="button" disabled={saving || !candidateIds.length || draft.status === "confirmed"} onClick={confirm}>{draft.status === "confirmed" ? copy("visits.confirmed") : copy("visits.confirmSelected")}</Button> : null}{draft.status !== "withdrawn" && draft.status !== "confirmed" ? <Button type="button" variant="secondary" disabled={saving} onClick={withdrawDraft}>{copy("visits.withdrawDraft")}</Button> : null}</div>
        </SurfaceCard> : null}
        <SurfaceCard className="p-5"><div className="flex flex-col gap-4 sm:flex-row sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy("visits.stepFour")}</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{copy("visits.selectAndApprove")}</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">{copy("visits.packPrivacy")}</p></div><Button type="button" disabled={saving || selectedPackCount === 0} onClick={makePack}>{pack ? copy("visits.createNewVersion") : copy("visits.createAndApprove", { count: selectedPackCount })}</Button></div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">{packGroups.map((group) => <fieldset key={group.key} className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"><legend className="px-1 text-sm font-semibold text-[var(--text-primary)]">{group.label}</legend>{group.items.length ? <div className="mt-1 space-y-2">{group.items.map((item) => <label key={item.id} className="flex items-start gap-2 text-sm text-[var(--text-secondary)]"><input type="checkbox" checked={Boolean(packSelection[item.id])} onChange={(event) => setPackSelection((current) => ({ ...current, [item.id]: event.target.checked }))} className="mt-1 h-4 w-4 accent-[var(--brand-600)]" /><span>{item.label}</span></label>)}</div> : <p className="mt-1 text-xs text-[var(--text-muted)]">{copy("visits.noMatchingItems")}</p>}</fieldset>)}</div>
          {pack ? <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4"><p className="font-semibold text-[var(--status-ok-text)]">{copy("visits.approvedVersion", { version: pack.version_no })}</p><Button type="button" size="sm" className="mt-3" disabled={saving || Boolean(share)} onClick={makeShare}>{copy("visits.createShare")}</Button>{share ? <><code className="mt-3 block break-all rounded-[var(--radius-md)] bg-[var(--surface-panel)] p-3 text-xs text-[var(--status-ok-text)]">{window.location.origin + "/api/v1/visit-packs/shared/" + share.token}</code><Button type="button" size="sm" variant="secondary" className="mt-2" disabled={saving} onClick={removeShare}>{copy("visits.revokeShare")}</Button></> : null}</div> : null}
        </SurfaceCard></> : null}
      </main>
      <aside className="space-y-5"><SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">{copy("visits.createVisit")}</h2><form className="mt-4 space-y-3" onSubmit={create}><Field label={copy("visits.visitName")} required minLength={2} value={title} onChange={(event) => setTitle(event.target.value)} placeholder={copy("visits.visitNameExample")} /><Textarea label={copy("visits.goalOptional")} value={goal} onChange={(event) => setGoal(event.target.value)} className="min-h-20" /><Field label={copy("visits.scheduledTime")} type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} /><Button type="submit" variant="secondary" block disabled={saving}>{copy("visits.saveVisit")}</Button></form></SurfaceCard>
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">{copy("visits.concernTitle")}</h2><form className="mt-4 space-y-3" onSubmit={addConcern}><Textarea required minLength={2} disabled={!selectedId} value={concern} onChange={(event) => setConcern(event.target.value)} placeholder={copy("visits.concernPlaceholder")} className="min-h-24" /><Select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="routine">{copy("visits.priorityRoutine")}</option><option value="soon">{copy("visits.prioritySoon")}</option><option value="urgent">{copy("visits.priorityUrgent")}</option></Select><Button type="submit" block disabled={saving || !selectedId}>{copy("visits.saveQuestion")}</Button></form></SurfaceCard>
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">{copy("visits.scribeTitle")}</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">{copy("visits.scribeDescription")}</p><Button type="button" variant="secondary" block className="mt-4" disabled={saving || !selectedId} onClick={toggleConsent}>{consented ? copy("visits.revokeScribeConsent") : copy("visits.grantScribeConsent")}</Button></SurfaceCard>
      </aside>
    </div>
  </PageShell>;
}
