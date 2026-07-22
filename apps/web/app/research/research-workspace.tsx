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
  type SourceHubCatalogEntry,
} from "@/lib/research";

type Props = { initialTab?: "frame" | "search" | "synthesize" | "watch" };

function roleLabel(role: UserRole): string {
  if (role === "doctor") return "Bác sĩ";
  if (role === "researcher") return "Nhà nghiên cứu";
  if (role === "admin") return "Quản trị";
  return "Người dùng";
}

function resultText(payload: Record<string, unknown>): string {
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
  return "Kết quả đã hoàn tất. Mở Chi tiết để xem toàn bộ dữ liệu và bằng chứng.";
}

export default function ResearchWorkspace({ initialTab = "frame" }: Props) {
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
  const [status, setStatus] = useState("Sẵn sàng");
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
    setStatus(`Đang tải ${file.name}…`);
    try {
      const uploaded = await uploadResearchFile(file);
      setUploadedFileIds((current) => [
        ...new Set([...current, ...uploaded.uploadedFileIds]),
      ]);
      setUploadedNames((current) => [...current, file.name]);
      setStatus("Tệp đã sẵn sàng cho lượt phân tích");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Không thể tải tệp nghiên cứu.",
      );
      setStatus("Sẵn sàng");
    } finally {
      event.target.value = "";
    }
  };

  const run = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!protocol) {
      setError("Hãy nhập câu hỏi nghiên cứu trước khi chạy.");
      setTab("frame");
      return;
    }
    setError("");
    setResult(null);
    setClarifyPending(true);
    setStatus("Đang kiểm tra câu hỏi và các trường còn thiếu…");
    const clarification = await requestResearchClarification(protocol, {
      researchMode: "deep",
      uiLanguage: "vi",
    });
    if (
      clarification.ambiguous &&
      clarification.questions.length &&
      !Object.keys(clarifyingAnswers).length
    ) {
      setQuestions(clarification.questions);
      setClarifyPending(false);
      setTab("frame");
      setStatus("Cần bạn xác nhận thêm trước khi tìm kiếm");
      return;
    }
    setClarifyPending(false);
    setIsRunning(true);
    setTab("synthesize");
    setStatus("Đang tìm nguồn, đối chiếu bằng chứng và kiểm tra trích dẫn…");
    const options: ExecuteResearchTier2JobOptions = {
      researchMode: "deep",
      retrievalStackMode: "full",
      uploadedFileIds,
      sourceHubSources:
        selectedSources as ExecuteResearchTier2JobOptions["sourceHubSources"],
      clarifyingAnswers,
      uiLanguage: "vi",
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
      setStatus(
        "Hoàn tất — kiểm tra từng kết luận và nguồn trước khi sử dụng.",
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Lượt nghiên cứu không hoàn tất.",
      );
      setStatus("Lượt nghiên cứu chưa hoàn tất");
    } finally {
      setIsRunning(false);
    }
  };

  const tabs = [
    ["frame", "1 · Đặt câu hỏi"],
    ["search", "2 · Nguồn & tệp"],
    ["synthesize", "3 · Tổng hợp"],
    ["watch", "4 · Theo dõi"],
  ] as const;

  return (
    <div className="min-h-[100dvh] bg-[var(--bg-canvas)] px-3 py-5 text-[var(--text-primary)] sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-[1260px] space-y-5">
        <header className="overflow-hidden rounded-[1.75rem] border border-[color:var(--shell-border)] bg-[linear-gradient(135deg,var(--surface-panel),var(--surface-brand-soft))] p-5 shadow-sm sm:p-7">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--text-brand)]">
                CLARA Research
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.035em] sm:text-4xl">
                Từ câu hỏi đến bằng chứng có thể kiểm tra
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--text-secondary)]">
                Không chỉ trả lời. CLARA lưu câu hỏi, nguồn, cách tìm, điểm chưa
                chắc chắn và kết luận để bạn có thể kiểm tra, chia sẻ và cập
                nhật lại.
              </p>
            </div>
            <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1.5 text-xs font-semibold text-[var(--text-secondary)]">
              {roleLabel(role)}
            </span>
          </div>
          <nav
            className="mt-6 flex gap-1 overflow-x-auto"
            aria-label="Research stages"
          >
            {tabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`whitespace-nowrap rounded-xl px-3.5 py-2 text-sm font-semibold ${tab === id ? "bg-[var(--brand-600)] text-white" : "text-[var(--text-secondary)] hover:bg-[var(--surface-panel)]"}`}
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
          <section className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm sm:p-6">
            {tab === "frame" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  PICO / PECO frame
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  Bạn muốn biết điều gì?
                </h2>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows={5}
                  placeholder="Ví dụ: Ở người lớn bị đái tháo đường type 2, metformin so với…"
                  className="mt-4 w-full resize-y rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm leading-6 outline-none focus:border-[var(--brand-500)] focus:ring-2 focus:ring-blue-500/15"
                />
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {[
                    ["Population", population, setPopulation],
                    ["Intervention / Exposure", intervention, setIntervention],
                    ["Comparator", comparator, setComparator],
                    ["Outcomes", outcomes, setOutcomes],
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
                  <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                    <p className="text-sm font-bold text-amber-900">
                      Cần làm rõ trước khi chạy
                    </p>
                    {questions.map((item) => (
                      <label
                        key={item.id}
                        className="mt-3 block text-sm text-amber-950"
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
                          className="mt-1.5 min-h-10 w-full rounded-xl border border-amber-300 bg-white px-3 outline-none"
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
                  Search plan
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  Nguồn nào sẽ được đối chiếu?
                </h2>
                <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
                  Chọn nhóm nguồn hoặc để CLARA tự định tuyến theo loại câu hỏi.
                  Các bản ghi và thời điểm truy xuất sẽ được giữ trong lượt
                  chạy.
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
                          {source.description || "Nguồn y khoa được kết nối"}
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
                  ＋ Đính kèm bài báo, protocol hoặc tài liệu nội bộ
                </label>
                {uploadedNames.length ? (
                  <p className="mt-3 text-xs text-[var(--text-secondary)]">
                    Đã thêm: {uploadedNames.join(", ")}
                  </p>
                ) : null}
              </>
            ) : null}

            {tab === "synthesize" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  Evidence synthesis
                </p>
                <h2 className="mt-1 text-2xl font-bold">
                  Kết luận có nguồn và điểm chưa chắc chắn
                </h2>
                {result ? (
                  <div className="mt-5 space-y-4">
                    <div className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm leading-7 whitespace-pre-wrap">
                      {resultText(result)}
                    </div>
                    <details className="rounded-2xl border border-[color:var(--shell-border)] p-4">
                      <summary className="cursor-pointer text-sm font-semibold">
                        Mở dữ liệu chạy và bằng chứng
                      </summary>
                      <pre className="mt-3 max-h-[32rem] overflow-auto whitespace-pre-wrap text-xs text-[var(--text-secondary)]">
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    </details>
                  </div>
                ) : (
                  <p className="mt-4 rounded-2xl bg-[var(--surface-muted)] p-5 text-sm leading-6 text-[var(--text-secondary)]">
                    Chưa có lượt chạy. Hãy đặt câu hỏi, chọn nguồn, rồi bắt đầu
                    tổng hợp.
                  </p>
                )}
              </>
            ) : null}
            {tab === "watch" ? (
              <>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                  Living evidence
                </p>
                <h2 className="mt-1 text-2xl font-bold">Theo dõi thay đổi</h2>
                <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">
                  Lượt theo dõi sẽ phát hiện bài mới, kết quả thử nghiệm, đính
                  chính, rút bài và thay đổi hướng dẫn ảnh hưởng đến kết luận.
                  Bản cập nhật cần được bạn xem xét trước khi thay thế kết luận
                  hiện tại.
                </p>
                <div className="mt-5 rounded-2xl border border-dashed border-[color:var(--shell-border-strong)] p-5 text-sm text-[var(--text-muted)]">
                  Watch mode sẽ dùng protocol và snapshot của lượt chạy gần nhất
                  {jobId ? ` · job ${jobId}` : ""}.
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
                className="min-h-11 rounded-xl bg-[var(--brand-600)] px-5 text-sm font-bold text-white shadow-sm transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRunning ? "Đang tổng hợp…" : "Bắt đầu nghiên cứu"}
              </button>
            </div>
          </section>
          <aside className="space-y-4">
            <div className="rounded-[1.5rem] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                Run manifest
              </p>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">Protocol</dt>
                  <dd className="text-right font-semibold">
                    {protocol ? "Đã tạo" : "Chưa có"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">Nguồn chọn</dt>
                  <dd className="font-semibold">
                    {selectedSources.length || "Tự định tuyến"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">Tệp</dt>
                  <dd className="font-semibold">{uploadedFileIds.length}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-[var(--text-muted)]">Job</dt>
                  <dd className="max-w-[9rem] truncate font-mono text-xs">
                    {jobId || "—"}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="rounded-[1.5rem] border border-blue-200 bg-blue-50 p-5 text-sm leading-6 text-blue-950">
              <p className="font-bold">CLARA kiểm tra gì?</p>
              <p className="mt-2">
                Nguồn, thời điểm, quần thể, thiết kế nghiên cứu, mâu thuẫn và
                điểm chưa chắc chắn. Đây là tổng hợp bằng chứng, không thay thế
                quyết định y khoa.
              </p>
            </div>
          </aside>
        </form>
      </div>
    </div>
  );
}
