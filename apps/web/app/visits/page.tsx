"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import { EmptyState, InlineError, LoadingCards, SurfaceCard } from "@/components/ui/surface";
import { Badge } from "@/components/ui/badge";
import Button from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/field";
import {
  addVisitConcern, answerVisitIntake, approveVisitPack, confirmVisitPlan, createVisit,
  createVisitDocument, createVisitPack, deleteVisitDocument, extractVisitPlan,
  grantVisitScribeConsent, listVisitDocuments, listVisits, revokeVisitScribeConsent,
  shareVisitPack, withdrawVisitDocument, withdrawVisitPlan,
  type Visit, type VisitDocument, type VisitIntakeQuestion, type VisitPack,
  type VisitPlanDraft, type VisitShare,
} from "@/lib/visit-family";

const initialQuestion = (visit: Visit): VisitIntakeQuestion => visit.goal.trim()
  ? { key: "main_concern", text: "Điều chính bạn muốn được hỗ trợ trong buổi khám là gì?", reason: "Giúp bác sĩ và bạn bắt đầu đúng trọng tâm." }
  : { key: "visit_goal", text: "Điều gì sẽ giúp buổi khám này hữu ích nhất với bạn?", reason: "Giúp buổi khám tập trung vào điều quan trọng với bạn." };

function candidateText(candidate: Record<string, unknown>, index: number) {
  for (const key of ["text", "title", "instruction", "label", "name"]) {
    if (typeof candidate[key] === "string" && String(candidate[key]).trim()) return String(candidate[key]).trim();
  }
  return "Mục trích xuất " + String(index + 1);
}

export default function VisitsPage() {
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
      setError(cause instanceof Error ? cause.message : "Không thể tải lịch khám.");
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!selectedId) { setDocuments([]); return; }
    void listVisitDocuments(selectedId).then(setDocuments).catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : "Không thể tải tài liệu."),
    );
  }, [selectedId]);

  const choose = (id: string) => {
    setSelectedId(id); setQuestion(null); setComplete(false); setProgress({ answered: 0, total: 0 });
    setDraft(null); setCandidateIds([]); setPack(null); setShare(null); setConsented(false);
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
    }, "Không thể tạo buổi khám.");
  };
  const submitIntake = (state: "answered" | "skipped" | "unknown") => {
    if (!selectedId || !question) return;
    if (state === "answered" && !answer.trim()) { setError("Hãy trả lời ngắn, hoặc chọn “Bỏ qua” / “Chưa rõ”."); return; }
    void action(async () => {
      const result = await answerVisitIntake(selectedId, { question_key: question.key, response_state: state, answer_text: state === "answered" ? answer.trim() : undefined });
      setAnswer(""); setQuestion(result.next_question); setProgress(result.progress); setComplete(result.complete);
    }, "Không thể lưu câu trả lời.");
  };
  const saveDocument = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    void action(async () => {
      const link = documentLink.trim();
      if (link) new URL(link);
      const text = file ? await file.text() : "";
      if (!documentTitle.trim() && !file && !link) throw new Error("Hãy chọn tệp, dán liên kết hoặc đặt tên cho ghi chú.");
      const created = await createVisitDocument(selectedId, {
        title: documentTitle.trim() || file?.name || new URL(link).hostname,
        text_content: documentText.trim() || text.trim() || undefined,
        media_type: file?.type || (link ? "text/uri-list" : "text/plain"),
        metadata: { capture: "user_selected", ...(file ? { source_file_name: file.name, source_file_size: file.size } : {}), ...(link ? { external_url: link } : {}) },
      });
      setDocuments((current) => [created, ...current]);
      setDocumentTitle(""); setDocumentText(""); setDocumentLink(""); setFile(null);
    }, "Không thể lưu tài liệu. CLARA chỉ lưu nội dung bạn chọn.");
  };
  const changeDocument = (document: VisitDocument, kind: "withdraw" | "delete") => {
    if (!selectedId) return;
    void action(async () => {
      const next = kind === "withdraw" ? await withdrawVisitDocument(selectedId, document.id) : await deleteVisitDocument(selectedId, document.id);
      setDocuments((current) => current.map((item) => item.id === next.id ? next : item));
    }, "Không thể cập nhật quyền dùng tài liệu.");
  };
  const extract = (document: VisitDocument) => {
    if (!selectedId) return;
    void action(async () => { setDraft(await extractVisitPlan(selectedId, document.id)); setCandidateIds([]); }, "Không thể kiểm tra tài liệu.");
  };
  const confirm = () => {
    if (!selectedId || !draft || !candidateIds.length) return;
    void action(async () => {
      await confirmVisitPlan(selectedId, { draft_id: Number(draft.id), candidate_ids: candidateIds });
      setDraft({ ...draft, status: "confirmed" });
    }, "Không thể xác nhận các mục đã chọn.");
  };
  const withdrawDraft = () => {
    if (!selectedId || !draft) return;
    void action(async () => { await withdrawVisitPlan(selectedId, draft.id); setDraft({ ...draft, status: "withdrawn" }); setCandidateIds([]); }, "Không thể rút bản nháp.");
  };
  const addConcern = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedId) return;
    void action(async () => { await addVisitConcern(selectedId, concern.trim(), priority); setConcern(""); }, "Không thể lưu điều cần hỏi.");
  };
  const makePack = () => {
    if (!selectedId) return;
    void action(async () => {
      const created = await createVisitPack(selectedId, { visit_summary: true, confirmed_medications: true, concerns: true, recent_episode_events: true });
      setPack(await approveVisitPack(created.id)); setShare(null);
    }, "Không thể chuẩn bị Visit Pack.");
  };
  const makeShare = () => {
    if (!pack) return;
    void action(async () => setShare(await shareVisitPack(pack.id, new Date(Date.now() + 604800000).toISOString())), "Không thể tạo liên kết chia sẻ.");
  };
  const toggleConsent = () => {
    if (!selectedId) return;
    void action(async () => { if (consented) await revokeVisitScribeConsent(selectedId); else await grantVisitScribeConsent(selectedId); setConsented(!consented); }, "Không thể cập nhật đồng ý ghi âm.");
  };

  return <PageShell variant="plain" title="Chuẩn bị buổi khám" description="Chuẩn bị từng bước, chỉ thêm và chia sẻ điều bạn tự chọn.">
    {error ? <InlineError message={error} onRetry={() => void load()} /> : null}
    <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_330px]">
      <aside className="space-y-4">
        <SurfaceCard className="overflow-hidden"><div className="border-b border-[color:var(--shell-border)] px-4 py-3"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Buổi khám</p><h2 className="mt-1 font-semibold text-[var(--text-primary)]">Chọn một buổi</h2></div>
          {loading ? <div className="p-3"><LoadingCards count={2} /></div> : visits.length ? <div className="space-y-1 p-2">{visits.map((visit) => <button key={visit.id} type="button" onClick={() => choose(visit.id)} className={"focus-ring w-full rounded-[var(--radius-lg)] p-3 text-left transition " + (selectedId === visit.id ? "bg-[var(--surface-brand-soft)] ring-1 ring-[var(--brand-500)]" : "hover:bg-[var(--surface-muted)]")}><p className="font-medium text-[var(--text-primary)]">{visit.title}</p><p className="mt-1 text-xs text-[var(--text-secondary)]">{visit.scheduled_at ? new Date(visit.scheduled_at).toLocaleString("vi-VN") : "Chưa đặt thời gian"}</p></button>)}</div> : <EmptyState icon="event_available" title="Chưa có buổi khám" description="Tạo một buổi ở cột bên phải." />}
        </SurfaceCard>
        <SurfaceCard className="p-4"><p className="text-sm font-semibold text-[var(--text-primary)]">Bạn luôn kiểm soát</p><p className="mt-1 text-sm leading-5 text-[var(--text-secondary)]">Không có tài liệu, câu trả lời hay kế hoạch nào tự vào hồ sơ hoặc tự được chia sẻ.</p></SurfaceCard>
      </aside>
      <main className="space-y-5">
        {!selected && !loading ? <SurfaceCard><EmptyState icon="assignment" title="Tạo buổi khám để bắt đầu" description="CLARA hỏi từng câu ngắn và chỉ lưu điều bạn chọn." /></SurfaceCard> : null}
        {selected ? <><SurfaceCard className="p-5"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 1 · Chuẩn bị nhanh</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{selected.title}</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">Mỗi lần chỉ một câu. Bạn có thể bỏ qua hoặc nói “chưa rõ”.</p></div>{progress.total ? <Badge tone="neutral">{progress.answered}/{progress.total} câu</Badge> : null}</div>
          {!question && !complete ? <Button type="button" className="mt-4" onClick={() => setQuestion(initialQuestion(selected))}>Bắt đầu 3–4 câu ngắn</Button> : null}
          {question ? <div className="mt-4 rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4"><p className="font-semibold text-[var(--text-primary)]">{question.text}</p><p className="mt-1 text-sm text-[var(--text-secondary)]">{question.reason}</p><Textarea value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="Viết ngắn theo cách của bạn" className="min-h-24" wrapperClassName="mt-3" /><div className="mt-3 flex flex-wrap gap-2"><Button type="button" disabled={saving} onClick={() => submitIntake("answered")}>Lưu và tiếp tục</Button><Button type="button" variant="secondary" disabled={saving} onClick={() => submitIntake("skipped")}>Bỏ qua</Button><Button type="button" variant="secondary" disabled={saving} onClick={() => submitIntake("unknown")}>Chưa rõ</Button></div></div> : null}
          {complete ? <p className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-3 text-sm text-[var(--status-ok-text)]">Đã xong phần chuẩn bị nhanh. Bạn có thể thêm câu hỏi hoặc tài liệu bên dưới.</p> : null}
        </SurfaceCard>
        <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 2 · Tài liệu bạn chọn</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Thêm tài liệu hoặc liên kết</h2><p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">CLARA chỉ lưu nội dung văn bản bạn chọn. Liên kết không được tự mở, đọc hay chia sẻ.</p>
          <form className="mt-4 grid gap-3" onSubmit={saveDocument}><Field label="Tên để bạn dễ nhận ra" value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} /><label className="text-sm font-medium text-[var(--text-primary)]">Tệp văn bản (tuỳ chọn)<input type="file" accept=".txt,.md,.csv,text/plain,text/markdown,text/csv" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="mt-1.5 block w-full text-sm text-[var(--text-secondary)]" /></label><Textarea label="Hoặc dán nội dung" value={documentText} onChange={(event) => setDocumentText(event.target.value)} className="min-h-20" /><Field label="Hoặc dán liên kết" type="url" value={documentLink} onChange={(event) => setDocumentLink(event.target.value)} placeholder="https://…" /><Button type="submit" variant="secondary" className="justify-self-start" disabled={saving}>Lưu mục đã chọn</Button></form>
          <div className="mt-5 space-y-2">{documents.length ? documents.map((document) => <div key={document.id} className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="font-medium text-[var(--text-primary)]">{document.title}</p><p className="mt-0.5 text-xs text-[var(--text-secondary)]">{document.deleted_at ? "Đã xoá nội dung" : document.withdrawn_at ? "Đã rút khỏi xử lý" : document.status === "external_unverified" ? "Bạn đã thêm · chưa xác minh" : document.status}</p></div>{!document.deleted_at && !document.withdrawn_at ? <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" disabled={saving} onClick={() => extract(document)}>Kiểm tra kế hoạch</Button><Button type="button" size="sm" variant="secondary" disabled={saving} onClick={() => changeDocument(document, "withdraw")}>Rút khỏi xử lý</Button><Button type="button" size="sm" variant="danger" disabled={saving} onClick={() => changeDocument(document, "delete")}>Xoá nội dung</Button></div> : null}</div></div>) : <p className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-secondary)]">Chưa có tài liệu nào được thêm.</p>}</div>
        </SurfaceCard>
        {draft ? <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 3 · Rà soát có căn cứ</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Xác nhận trước khi tạo việc cần làm</h2>
          {draft.safe_unavailable || !draft.candidates.length ? <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] p-4 text-sm text-[var(--status-warn-text)]"><p className="font-semibold">CLARA chưa tạo kế hoạch từ tài liệu này.</p><p className="mt-1">{draft.reason || "Không có mục nào đủ căn cứ để đề xuất. Hãy xem lại với bác sĩ."}</p></div> : <div className="mt-4 space-y-2"><p className="text-sm text-[var(--text-secondary)]">Chỉ chọn mục có nguồn hiển thị rõ ràng. Không có mục nào được tạo nếu bạn không xác nhận.</p>{draft.candidates.map((candidate, index) => { const source = typeof candidate.source_span === "string" ? candidate.source_span : typeof candidate.source_text === "string" ? candidate.source_text : ""; const checked = candidateIds.includes(candidate.id); return <label key={candidate.id} className="block rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] p-3"><span className="flex gap-3"><input type="checkbox" disabled={!source} checked={checked} onChange={() => setCandidateIds((current) => checked ? current.filter((id) => id !== candidate.id) : [...current, candidate.id])} className="mt-1 h-4 w-4 accent-[var(--brand-600)]" /><span><span className="block font-medium text-[var(--text-primary)]">{candidateText(candidate, index)}</span><span className="mt-1 block text-sm text-[var(--text-secondary)]">{source ? "Nguồn: “" + source + "”" : "Không có đoạn nguồn — không thể xác nhận mục này."}</span></span></span></label>; })}</div>}
          <div className="mt-4 flex flex-wrap gap-2">{draft.candidates.length && !draft.safe_unavailable ? <Button type="button" disabled={saving || !candidateIds.length || draft.status === "confirmed"} onClick={confirm}>{draft.status === "confirmed" ? "Đã xác nhận" : "Xác nhận mục đã chọn"}</Button> : null}{draft.status !== "withdrawn" && draft.status !== "confirmed" ? <Button type="button" variant="secondary" disabled={saving} onClick={withdrawDraft}>Rút bản nháp</Button> : null}</div>
        </SurfaceCard> : null}
        <SurfaceCard className="p-5"><div className="flex flex-col gap-4 sm:flex-row sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 4 · Visit Pack</p><h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Tự duyệt trước khi chia sẻ</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">Gói chỉ là ảnh chụp bốn nhóm bạn thấy; không có chia sẻ ngầm.</p></div><Button type="button" disabled={saving} onClick={makePack}>{pack ? "Tạo bản mới" : "Tạo và duyệt gói"}</Button></div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">{["Tóm tắt buổi khám", "Thuốc đã xác nhận", "Điều cần hỏi", "Diễn biến gần đây"].map((item) => <div key={item} className="rounded-[var(--radius-lg)] bg-[var(--surface-muted)] p-3 text-sm text-[var(--text-primary)]">{item}</div>)}</div>
          {pack ? <div className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4"><p className="font-semibold text-[var(--status-ok-text)]">Bản {pack.version_no} đã được bạn duyệt</p><Button type="button" size="sm" className="mt-3" disabled={saving || Boolean(share)} onClick={makeShare}>Tạo liên kết 7 ngày</Button>{share ? <code className="mt-3 block break-all rounded-[var(--radius-md)] bg-[var(--surface-panel)] p-3 text-xs text-[var(--status-ok-text)]">{window.location.origin + "/api/v1/visit-packs/shared/" + share.token}</code> : null}</div> : null}
        </SurfaceCard></> : null}
      </main>
      <aside className="space-y-5"><SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Tạo buổi khám</h2><form className="mt-4 space-y-3" onSubmit={create}><Field label="Tên buổi khám" required minLength={2} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ví dụ: Tái khám tim mạch" /><Textarea label="Mục tiêu (tuỳ chọn)" value={goal} onChange={(event) => setGoal(event.target.value)} className="min-h-20" /><Field label="Thời gian dự kiến" type="datetime-local" value={when} onChange={(event) => setWhen(event.target.value)} /><Button type="submit" variant="secondary" block disabled={saving}>Lưu buổi khám</Button></form></SurfaceCard>
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Điều cần hỏi bác sĩ</h2><form className="mt-4 space-y-3" onSubmit={addConcern}><Textarea required minLength={2} disabled={!selectedId} value={concern} onChange={(event) => setConcern(event.target.value)} placeholder="Điều gì khiến bạn băn khoăn nhất?" className="min-h-24" /><Select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="routine">Khi thuận tiện</option><option value="soon">Nên hỏi sớm</option><option value="urgent">Ưu tiên trao đổi</option></Select><Button type="submit" block disabled={saving || !selectedId}>Lưu câu hỏi</Button></form></SurfaceCard>
        <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Ghi âm Scribe</h2><p className="mt-1 text-sm text-[var(--text-secondary)]">Đồng ý chỉ áp dụng cho buổi đang chọn và có thể rút lại ngay.</p><Button type="button" variant="secondary" block className="mt-4" disabled={saving || !selectedId} onClick={toggleConsent}>{consented ? "Rút lại đồng ý ghi âm" : "Đồng ý ghi âm buổi này"}</Button></SurfaceCard>
      </aside>
    </div>
  </PageShell>;
}
