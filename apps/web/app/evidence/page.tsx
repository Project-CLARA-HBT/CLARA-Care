"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import PageShell from "@/components/ui/page-shell";
import {
  EmptyState,
  InlineError,
  LoadingCards,
  SurfaceCard,
} from "@/components/lifemap/lifemap-primitives";
import {
  confirmEvidenceQuestion,
  createEvidenceQuestion,
  deleteEvidenceSubscription,
  getEvidenceDetails,
  isEvidenceRunTerminal,
  pollEvidenceRun,
  runEvidenceQuestion,
  subscribeToEvidenceRun,
  type EvidenceApplicability,
  type EvidenceContradictions,
  type EvidenceMatrix,
  type EvidenceQuestion,
  type EvidenceRun,
  type EvidenceSubscription,
} from "@/lib/living-evidence";
import { getLifeMapToday, type LifeMapEpisode } from "@/lib/lifemap";

const sourceClassLabel: Record<string, string> = {
  guideline: "Hướng dẫn / đồng thuận",
  primary_randomized_trial: "Thử nghiệm ngẫu nhiên",
  primary_observational: "Nghiên cứu quan sát",
  primary_diagnostic: "Nghiên cứu chẩn đoán",
  primary_prognostic: "Nghiên cứu tiên lượng",
  systematic_review: "Tổng quan hệ thống / phân tích gộp",
  review: "Bài tổng quan",
  editorial_commentary: "Bình luận biên tập",
};

const missingContextLabel: Record<string, string> = {
  population_context: "bối cảnh hoặc nhóm người liên quan",
  outcomes: "điều bạn muốn biết kết quả",
  time_horizon: "khoảng thời gian bạn quan tâm",
  validated_study_eligibility_rules_unavailable: "quy tắc áp dụng nghiên cứu đã được kiểm định",
};

function labelForSourceClass(value: string) {
  return sourceClassLabel[value] ?? value;
}

function labelForUnknown(value: string) {
  return missingContextLabel[value] ?? value;
}

function toMessage(cause: unknown, fallback: string) {
  return cause instanceof Error && cause.message ? cause.message : fallback;
}

function EvidenceMatrixView({ matrix }: { matrix: EvidenceMatrix }) {
  const groups = Object.entries(matrix.source_classes);
  if (groups.length === 0) {
    return (
      <div className="rounded-xl bg-[var(--surface-muted)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
        {matrix.unavailable_reason ?? "Chưa có bản ghi bằng chứng đã xác minh cho lần chạy này."}
      </div>
    );
  }
  return (
    <div className="space-y-4">
      {groups.map(([sourceClass, records]) => (
        <section key={sourceClass} className="rounded-2xl border border-[color:var(--shell-border)]">
          <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)]/65 px-4 py-3">
            <h3 className="font-semibold text-[var(--text-primary)]">{labelForSourceClass(sourceClass)}</h3>
            <p className="mt-1 text-xs text-[var(--text-muted)]">{records.length} nguồn được lưu với provenance</p>
          </div>
          <ul className="divide-y divide-[color:var(--shell-border)]">
            {records.map((record) => (
              <li key={record.evidence_id} className="px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium leading-6 text-[var(--text-primary)]">{record.title}</p>
                    <p className="mt-1 text-xs text-[var(--text-muted)]">
                      {[record.provider, record.study_design, record.published_at].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  {record.url ? (
                    <a
                      href={record.url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-lg border border-[color:var(--shell-border)] px-2.5 py-1.5 text-xs font-semibold text-[var(--brand-700)] hover:bg-[var(--surface-brand-soft)] dark:text-sky-200"
                    >
                      Mở nguồn <span className="material-symbols-outlined text-sm" aria-hidden="true">open_in_new</span>
                    </a>
                  ) : null}
                </div>
                {Object.keys(record.identifiers).length ? (
                  <p className="mt-2 text-xs text-[var(--text-secondary)]">
                    {Object.entries(record.identifiers).map(([key, value]) => `${key.toUpperCase()}: ${value}`).join(" · ")}
                  </p>
                ) : null}
                {record.excerpt ? <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{record.excerpt}</p> : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function InterpretationView({
  applicability,
  contradictions,
}: {
  applicability: EvidenceApplicability;
  contradictions: EvidenceContradictions;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-2xl border border-[color:var(--shell-border)] p-4">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined mt-0.5 text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">person_search</span>
          <div>
            <h3 className="font-semibold text-[var(--text-primary)]">Có áp dụng cho bạn không?</h3>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{applicability.safe_message}</p>
          </div>
        </div>
        {applicability.unknowns.length ? (
          <ul className="mt-3 space-y-2 text-sm text-[var(--text-secondary)]">
            {applicability.unknowns.map((item) => <li key={item} className="flex gap-2"><span className="material-symbols-outlined text-base text-amber-700 dark:text-amber-200" aria-hidden="true">help</span><span>Còn thiếu: {labelForUnknown(item)}.</span></li>)}
          </ul>
        ) : null}
      </section>
      <section className="rounded-2xl border border-[color:var(--shell-border)] p-4">
        <div className="flex items-start gap-3">
          <span className="material-symbols-outlined mt-0.5 text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">compare_arrows</span>
          <div>
            <h3 className="font-semibold text-[var(--text-primary)]">Điểm chưa thống nhất</h3>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{contradictions.safe_message}</p>
          </div>
        </div>
        {contradictions.items.length ? (
          <ul className="mt-3 space-y-2">
            {contradictions.items.map((item, index) => <li key={`${item.claim}-${index}`} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-500/15 dark:text-amber-50"><p className="font-medium">{item.claim || "Các nguồn có kết quả cần đối chiếu thêm."}</p><p className="mt-1 text-xs opacity-80">Nguồn liên quan: {item.citation_ids.join(", ")}</p></li>)}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

export default function LivingEvidencePage() {
  const [episodes, setEpisodes] = useState<LifeMapEpisode[]>([]);
  const [loadingEpisodes, setLoadingEpisodes] = useState(true);
  const [selectedEpisodeId, setSelectedEpisodeId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [population, setPopulation] = useState("");
  const [outcomes, setOutcomes] = useState("");
  const [timeHorizon, setTimeHorizon] = useState("");
  const [question, setQuestion] = useState<EvidenceQuestion | null>(null);
  const [run, setRun] = useState<EvidenceRun | null>(null);
  const [matrix, setMatrix] = useState<EvidenceMatrix | null>(null);
  const [applicability, setApplicability] = useState<EvidenceApplicability | null>(null);
  const [contradictions, setContradictions] = useState<EvidenceContradictions | null>(null);
  const [subscription, setSubscription] = useState<EvidenceSubscription | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [pollAttempt, setPollAttempt] = useState(0);
  const [error, setError] = useState("");
  const pollControllerRef = useRef<AbortController | null>(null);

  const loadEpisodes = useCallback(async () => {
    setLoadingEpisodes(true);
    setError("");
    try {
      const today = await getLifeMapToday();
      setEpisodes(today.episodes);
      setSelectedEpisodeId((current) => current || today.episodes[0]?.id || "");
    } catch (cause) {
      setError(toMessage(cause, "Không thể tải hành trình LifeMap."));
    } finally {
      setLoadingEpisodes(false);
    }
  }, []);

  useEffect(() => { void loadEpisodes(); }, [loadEpisodes]);
  useEffect(() => () => pollControllerRef.current?.abort(), []);

  const createQuestion = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedEpisodeId || !questionText.trim()) return;
    pollControllerRef.current?.abort();
    setSaving(true);
    setError("");
    try {
      const created = await createEvidenceQuestion(selectedEpisodeId, {
        question: questionText.trim(),
        population_context: population.trim() || undefined,
        outcomes: outcomes.split("\n").map((item) => item.trim()).filter(Boolean),
        time_horizon: timeHorizon.trim() || undefined,
      });
      setQuestion(created);
      setRun(null);
      setMatrix(null);
      setApplicability(null);
      setContradictions(null);
      setSubscription(null);
    } catch (cause) {
      setError(toMessage(cause, "Không thể lưu câu hỏi bằng chứng."));
    } finally {
      setSaving(false);
    }
  };

  const confirmQuestion = async () => {
    if (!question) return;
    setSaving(true);
    setError("");
    try {
      setQuestion(await confirmEvidenceQuestion(question.id));
    } catch (cause) {
      setError(toMessage(cause, "Không thể xác nhận câu hỏi."));
    } finally {
      setSaving(false);
    }
  };

  const runResearch = async () => {
    if (!question?.confirmed) return;
    pollControllerRef.current?.abort();
    const controller = new AbortController();
    pollControllerRef.current = controller;
    setRunning(true);
    setPollAttempt(0);
    setError("");
    setMatrix(null);
    setApplicability(null);
    setContradictions(null);
    try {
      const createdRun = await runEvidenceQuestion(question.id);
      setRun(createdRun);
      const completedRun = isEvidenceRunTerminal(createdRun)
        ? createdRun
        : await pollEvidenceRun(createdRun.id, {
          signal: controller.signal,
          onUpdate: (updatedRun, attempt) => {
            setRun(updatedRun);
            setPollAttempt(attempt);
          },
        });
      setRun(completedRun);
      if (completedRun.status.toLowerCase() !== "completed") {
        throw new Error("Quá trình truy xuất bằng chứng không hoàn tất. Không có kết luận y khoa nào được phát hành.");
      }
      const details = await getEvidenceDetails(completedRun.id);
      setMatrix(details.matrix);
      setApplicability(details.applicability);
      setContradictions(details.contradictions);
    } catch (cause) {
      if (!(cause instanceof Error && cause.name === "AbortError")) {
        setRun((current) => current && isEvidenceRunTerminal(current) ? current : null);
        setError(toMessage(cause, "Chưa thể truy xuất bằng chứng đã kiểm chứng."));
      }
    } finally {
      if (pollControllerRef.current === controller) {
        pollControllerRef.current = null;
        setRunning(false);
      }
    }
  };

  const toggleSubscription = async () => {
    if (!run) return;
    setSaving(true);
    setError("");
    try {
      if (subscription) {
        await deleteEvidenceSubscription(subscription.id);
        setSubscription(null);
      } else {
        setSubscription(await subscribeToEvidenceRun(run.id));
      }
    } catch (cause) {
      setError(toMessage(cause, "Không thể cập nhật đăng ký theo dõi."));
    } finally {
      setSaving(false);
    }
  };

  const selectedEpisode = episodes.find((episode) => episode.id === selectedEpisodeId);
  const evidenceAvailable = run?.release_status === "evidence_available";

  return (
    <PageShell
      variant="plain"
      title="Bằng chứng đang cập nhật"
      description="Đặt một câu hỏi gắn với hành trình của bạn. CLARA chỉ hiển thị nguồn đã kiểm chứng và nói rõ khi chưa đủ bằng chứng."
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <main className="space-y-5">
          {error ? <InlineError message={error} onRetry={() => void (question?.confirmed ? runResearch() : loadEpisodes())} /> : null}
          {running ? (
            <SurfaceCard className="overflow-hidden">
              <div role="status" aria-live="polite">
                <div className="border-b border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)]/55 px-5 py-4">
                  <div className="flex items-start gap-3">
                    <span className="material-symbols-outlined mt-0.5 animate-spin text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">progress_activity</span>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Đang xử lý chuyên sâu</p>
                      <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{question?.question}</h2>
                      <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                        {pollAttempt === 0
                          ? "Đang khởi tạo run và gửi câu hỏi đến hệ thống truy xuất."
                          : pollAttempt < 15
                            ? "Đang tìm và phân loại guideline, nghiên cứu gốc, tổng quan và bình luận."
                            : pollAttempt < 60
                              ? "Đang kiểm tra provenance, chất lượng nguồn và các điểm mâu thuẫn."
                              : "Đang hoàn tất ma trận bằng chứng và hiệu chỉnh độ không chắc chắn."}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-5">
                  <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-muted)]" aria-hidden="true">
                    <div className="h-full w-2/5 animate-pulse rounded-full bg-[var(--brand-500)]" />
                  </div>
                  <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">
                    {pollAttempt > 0 ? `Đã cập nhật tiến trình ${pollAttempt} lần. ` : ""}
                    Tác vụ có thể mất vài phút. Bạn không cần gửi lại câu hỏi.
                  </p>
                </div>
              </div>
            </SurfaceCard>
          ) : run ? (
            <SurfaceCard className="overflow-hidden">
              <div className="border-b border-[color:var(--shell-border)] px-5 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Kết quả bằng chứng</p>
                    <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">{question?.question}</h2>
                  </div>
                  <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${evidenceAvailable ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-100" : "bg-amber-100 text-amber-900 dark:bg-amber-500/15 dark:text-amber-100"}`}>
                    {evidenceAvailable ? `${run.evidence_count} nguồn đã xác minh` : "Không phát hành kết luận"}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{run.safe_message}</p>
              </div>
              <div className="space-y-5 p-5">
                {evidenceAvailable && matrix ? <EvidenceMatrixView matrix={matrix} /> : <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950 dark:border-amber-400/50 dark:bg-amber-500/15 dark:text-amber-50"><p className="font-semibold">CLARA dừng ở đây để an toàn.</p><p className="mt-1">Không có câu trả lời y khoa được tạo khi provenance không đầy đủ. Bạn có thể bổ sung bối cảnh hoặc thảo luận câu hỏi này với chuyên gia y tế.</p></div>}
                {applicability && contradictions ? <InterpretationView applicability={applicability} contradictions={contradictions} /> : null}
                <details className="rounded-xl bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                  <summary className="cursor-pointer font-semibold text-[var(--text-primary)]">Độ không chắc chắn của lần chạy này</summary>
                  <ul className="mt-3 space-y-2 leading-6">{run.uncertainty.map((item, index) => <li key={`${item.dimension}-${index}`}><span className="font-medium text-[var(--text-primary)]">{item.dimension}:</span> {item.reason}</li>)}</ul>
                </details>
              </div>
            </SurfaceCard>
          ) : (
            <SurfaceCard className="p-5">
              <div className="flex items-start gap-3">
                <span className="material-symbols-outlined inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--brand-700)] dark:text-sky-200" aria-hidden="true">fact_check</span>
                <div>
                  <h2 className="font-semibold text-[var(--text-primary)]">Không phải một câu trả lời đoán trước</h2>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">Câu hỏi được gắn với LifeMap, sau đó mới truy xuất hướng dẫn, nghiên cứu chính, tổng quan và bình luận theo từng nhóm nguồn. Thiếu nguồn đáng tin cậy thì CLARA sẽ nói là chưa có kết luận.</p>
                </div>
              </div>
            </SurfaceCard>
          )}
        </main>

        <aside className="space-y-5">
          <SurfaceCard className="p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 1 · Câu hỏi của bạn</p>
            <h2 className="mt-1 text-lg font-semibold text-[var(--text-primary)]">Đặt câu hỏi theo hành trình</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">Bạn luôn xem và xác nhận câu hỏi trước khi truy xuất chuyên sâu.</p>
            {loadingEpisodes ? <div className="mt-4"><LoadingCards count={1} /></div> : episodes.length === 0 ? <EmptyState icon="route" title="Cần một hành trình" description="Tạo một hành trình LifeMap trước, rồi quay lại để đặt câu hỏi có ngữ cảnh." ><Link href="/lifemap" className="text-sm font-semibold text-[var(--brand-700)] hover:underline dark:text-sky-200">Mở LifeMap</Link></EmptyState> : <form className="mt-4 space-y-3" onSubmit={(event) => void createQuestion(event)}>
              <label className="block text-sm font-medium text-[var(--text-primary)]">Thuộc hành trình<select value={selectedEpisodeId} onChange={(event) => setSelectedEpisodeId(event.target.value)} className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25">{episodes.map((episode) => <option key={episode.id} value={episode.id}>{episode.title}</option>)}</select></label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">Điều bạn muốn biết<textarea required value={questionText} onChange={(event) => setQuestionText(event.target.value)} placeholder="Ví dụ: Có bằng chứng nào giúp tôi chuẩn bị cuộc hẹn về huyết áp?" className="mt-1.5 min-h-28 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm leading-6 text-[var(--text-primary)] outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-[var(--brand-500)]/25" /></label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">Bối cảnh bạn đã xác nhận <span className="font-normal text-[var(--text-muted)]">(không bắt buộc)</span><textarea value={population} onChange={(event) => setPopulation(event.target.value)} placeholder="Ví dụ: người lớn, đã được bác sĩ nói có tăng huyết áp" className="mt-1.5 min-h-20 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)]" /></label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">Điều bạn muốn theo dõi <span className="font-normal text-[var(--text-muted)]">(mỗi dòng một ý)</span><textarea value={outcomes} onChange={(event) => setOutcomes(event.target.value)} placeholder={"Ví dụ:\nGiảm huyết áp\nTác dụng không mong muốn"} className="mt-1.5 min-h-20 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)]" /></label>
              <label className="block text-sm font-medium text-[var(--text-primary)]">Khoảng thời gian <span className="font-normal text-[var(--text-muted)]">(không bắt buộc)</span><input value={timeHorizon} onChange={(event) => setTimeHorizon(event.target.value)} placeholder="Ví dụ: 3 tháng tới" className="mt-1.5 w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2.5 text-sm text-[var(--text-primary)]" /></label>
              <button disabled={saving || !selectedEpisodeId} className="w-full rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-700)] disabled:opacity-60">{saving ? "Đang lưu…" : "Lưu để xem lại"}</button>
            </form>}
          </SurfaceCard>

          {question ? <SurfaceCard className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">Bước 2 · Xác nhận</p><h2 className="mt-1 font-semibold text-[var(--text-primary)]">{question.question}</h2><p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">{question.confirmed ? "Bạn đã xác nhận câu hỏi này." : "Hãy kiểm tra câu hỏi và bối cảnh trước khi CLARA tìm nguồn."}</p>{question.compiled.missing_dimensions?.length ? <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-500/15 dark:text-amber-50">Có thể sẽ cần thêm: {question.compiled.missing_dimensions.map(labelForUnknown).join(", ")}.</p> : null}{!question.confirmed ? <button type="button" disabled={saving} onClick={() => void confirmQuestion()} className="mt-4 w-full rounded-xl border border-[var(--brand-500)] px-4 py-2.5 text-sm font-semibold text-[var(--brand-700)] hover:bg-[var(--surface-brand-soft)] disabled:opacity-60 dark:text-sky-200">Tôi đã kiểm tra câu hỏi</button> : <button type="button" disabled={running} onClick={() => void runResearch()} className="mt-4 w-full rounded-xl bg-[var(--brand-600)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-700)] disabled:opacity-60">{running ? "Đang tìm nguồn đã xác minh…" : "Tìm bằng chứng"}</button>}</SurfaceCard> : null}

          {run ? <SurfaceCard className="p-5"><h2 className="font-semibold text-[var(--text-primary)]">Theo dõi thay đổi quan trọng</h2><p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">Chỉ thay đổi đã được xem xét là có thể làm đổi độ chắc chắn hoặc bước tiếp theo mới đủ điều kiện thông báo.</p><button type="button" disabled={saving} onClick={() => void toggleSubscription()} className="mt-4 w-full rounded-xl border border-[color:var(--shell-border)] px-4 py-2.5 text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-60">{subscription ? "Dừng theo dõi cập nhật" : "Theo dõi cập nhật quan trọng"}</button>{selectedEpisode ? <p className="mt-3 text-xs text-[var(--text-muted)]">Gắn với: {selectedEpisode.title}</p> : null}</SurfaceCard> : null}
        </aside>
      </div>
    </PageShell>
  );
}
