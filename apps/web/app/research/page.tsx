"use client";

import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import PageShell from "@/components/ui/page-shell";
import api from "@/lib/http-client";
import { UserRole, getRole } from "@/lib/auth-store";
import { ChatResponse, getChatIntentDebug, getChatReply } from "@/lib/chat";
import {
  ResearchTier,
  Tier2Citation,
  Tier2Step,
  UploadedResearchFile,
  normalizeResearchTier2,
  runResearchTier2,
  uploadResearchFile
} from "@/lib/research";

const ROLE_LABELS: Record<UserRole, string> = {
  normal: "Người dùng cá nhân",
  researcher: "Nhà nghiên cứu",
  doctor: "Bác sĩ",
  admin: "Quản trị hệ thống",
};

type Tier1Result = {
  tier: "tier1";
  answer: string;
  debug: ReturnType<typeof getChatIntentDebug> | null;
};

type Tier2Result = {
  tier: "tier2";
  answer: string;
  citations: Tier2Citation[];
  steps: Tier2Step[];
};

type ResearchResult = Tier1Result | Tier2Result;

const SUGGESTED_QUERIES = [
  "Tóm tắt điểm chính từ các file đã tải lên về tăng huyết áp ở người cao tuổi",
  "Liệt kê khuyến cáo điều trị có mức chứng cứ cao nhất trong tài liệu",
  "So sánh guideline giữa các nguồn trong file về theo dõi đường huyết"
] as const;

function formatFileSize(size?: number): string {
  if (!size || Number.isNaN(size)) return "Không rõ dung lượng";
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function mergeUploadedFiles(current: UploadedResearchFile[], incoming: UploadedResearchFile[]): UploadedResearchFile[] {
  const byId = new Map(current.map((item) => [item.id, item]));

  incoming.forEach((item) => {
    const existing = byId.get(item.id);
    byId.set(item.id, {
      id: item.id,
      name: item.name || existing?.name || `File #${item.id}`,
      size: item.size ?? existing?.size
    });
  });

  return Array.from(byId.values());
}

export default function ResearchPage() {
  const [role, setRole] = useState<UserRole>("normal");
  const [selectedTier, setSelectedTier] = useState<ResearchTier>("tier2");
  const [query, setQuery] = useState("");
  const [lastQuery, setLastQuery] = useState("");
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [uploadedFiles, setUploadedFiles] = useState<UploadedResearchFile[]>([]);
  const [uploadedFileIds, setUploadedFileIds] = useState<string[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isDev = process.env.NODE_ENV !== "production";
  const roleLabel = useMemo(() => ROLE_LABELS[role] ?? ROLE_LABELS.normal, [role]);
  const canRunProcess = uploadedFileIds.length > 0;

  const processSteps = useMemo(
    () => [
      {
        id: 1,
        title: "Upload tài liệu",
        detail: canRunProcess ? `${uploadedFileIds.length} file đã sẵn sàng` : "Chưa có tài liệu",
        done: canRunProcess
      },
      {
        id: 2,
        title: "Đặt câu hỏi",
        detail: lastQuery || "Nhập câu hỏi chính để bắt đầu phân tích",
        done: Boolean(lastQuery)
      },
      {
        id: 3,
        title: "Nhận kết quả",
        detail: result ? "Đã có câu trả lời + nguồn" : isSubmitting ? "Hệ thống đang xử lý" : "Chưa có kết quả",
        done: Boolean(result)
      }
    ],
    [canRunProcess, uploadedFileIds.length, lastQuery, result, isSubmitting]
  );

  useEffect(() => {
    setRole(getRole());
  }, []);

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return;

    setUploadError("");
    setError("");
    setIsUploading(true);

    const batchIds: string[] = [];
    const batchFiles: UploadedResearchFile[] = [];
    const failedUploads: string[] = [];

    for (const file of files) {
      try {
        const uploaded = await uploadResearchFile(file);

        if (!uploaded.uploadedFileIds.length) {
          throw new Error("Upload thành công nhưng chưa nhận được uploaded_file_ids.");
        }

        batchIds.push(...uploaded.uploadedFileIds);

        if (uploaded.files.length) {
          batchFiles.push(...uploaded.files);
        } else {
          batchFiles.push(
            ...uploaded.uploadedFileIds.map((id) => ({
              id,
              name: file.name,
              size: file.size
            }))
          );
        }
      } catch (uploadException) {
        const message = uploadException instanceof Error ? uploadException.message : "Upload thất bại.";
        failedUploads.push(`${file.name}: ${message}`);
      }
    }

    if (batchIds.length) {
      setUploadedFileIds((prev) => Array.from(new Set([...prev, ...batchIds])));
      setUploadedFiles((prev) => mergeUploadedFiles(prev, batchFiles));
      setLastQuery("");
      setResult(null);
      setQuery("");
    }

    if (failedUploads.length) {
      setUploadError(
        failedUploads.length === 1
          ? failedUploads[0]
          : `${failedUploads[0]} (+${failedUploads.length - 1} file lỗi khác)`
      );
    }

    if (!batchIds.length && !failedUploads.length) {
      setUploadError("Không nhận được dữ liệu uploaded_file_ids từ server.");
    }

    setIsUploading(false);
  };

  const onUploadInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    event.currentTarget.value = "";
    void uploadFiles(files);
  };

  const onDropUpload = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragActive(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    void uploadFiles(files);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = query.trim();
    if (!message || isSubmitting) return;

    setError("");
    setIsSubmitting(true);
    setLastQuery(message);
    setResult(null);

    try {
      if (selectedTier === "tier1") {
        const response = await api.post<ChatResponse>("/chat", { message });
        const answer = getChatReply(response.data);
        if (!answer) throw new Error("Chưa có nội dung trả lời hợp lệ.");

        setResult({ tier: "tier1", answer, debug: getChatIntentDebug(response.data) });
      } else {
        const response = await runResearchTier2(message, { uploadedFileIds });
        const normalized = normalizeResearchTier2(response);
        if (!normalized.answer && !normalized.citations.length) {
          throw new Error("Chưa có phản hồi chuyên sâu hợp lệ.");
        }
        setResult({
          tier: "tier2",
          answer: normalized.answer,
          citations: normalized.citations,
          steps: normalized.steps
        });
      }
      setQuery("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Không thể gửi câu hỏi.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const onRemoveUploadedFile = (fileId: string) => {
    setUploadedFileIds((prev) => prev.filter((id) => id !== fileId));
    setUploadedFiles((prev) => prev.filter((item) => item.id !== fileId));
    setResult(null);
    setLastQuery("");
    setError("");
  };

  const onClearUploadedFiles = () => {
    setUploadedFileIds([]);
    setUploadedFiles([]);
    setResult(null);
    setLastQuery("");
    setQuery("");
    setError("");
    setUploadError("");
  };

  return (
    <PageShell title="Hỏi đáp y tế" variant="plain">
      <div className="space-y-4">
        <section className="glass-card rounded-3xl p-4 sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700 dark:text-sky-300">clara research</p>
              <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Upload trước, hỏi sau, trả lời có nguồn</h2>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                Luồng mới: tải tài liệu trước để hệ thống trích xuất ngữ cảnh, sau đó nhập một câu hỏi chính để nhận câu trả lời + citation.
              </p>
            </div>
            <span className="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
              Vai trò: {roleLabel}
            </span>
          </div>
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white/95 p-5 shadow-[0_28px_90px_-54px_rgba(2,132,199,0.48)] dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700 dark:text-sky-300">Bước 1</p>
              <h3 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">Tải tài liệu nghiên cứu</h3>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                Kéo thả file vào vùng lớn bên dưới hoặc bấm chọn file. Hệ thống sẽ gọi endpoint
                <span className="mx-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                  /research/upload-file
                </span>
                và lưu <span className="font-mono text-xs">uploaded_file_ids</span> để dùng cho tier2.
              </p>
            </div>
            {uploadedFiles.length ? (
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                {uploadedFiles.length} file đã upload
              </span>
            ) : null}
          </div>

          <div
            onDrop={onDropUpload}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragActive(true);
            }}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                setIsDragActive(false);
              }
            }}
            className={`mt-4 rounded-3xl border-2 border-dashed p-8 text-center transition ${
              isDragActive
                ? "border-sky-400 bg-sky-50 dark:border-sky-500 dark:bg-sky-950/40"
                : "border-slate-300 bg-slate-50/80 dark:border-slate-600 dark:bg-slate-800/65"
            }`}
          >
            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Kéo & thả tài liệu vào đây</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Hỗ trợ PDF, DOC, DOCX, TXT, ảnh. Có thể chọn nhiều file.</p>

            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
              >
                {isUploading ? "Đang upload..." : "Chọn file"}
              </button>
              {uploadedFiles.length ? (
                <button
                  type="button"
                  onClick={onClearUploadedFiles}
                  disabled={isUploading}
                  className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
                >
                  Xóa toàn bộ
                </button>
              ) : null}
            </div>

            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,image/*"
              className="hidden"
              onChange={onUploadInputChange}
            />
          </div>

          {uploadError ? (
            <p className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
              {uploadError}
            </p>
          ) : null}

          {uploadedFiles.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {uploadedFiles.map((file, index) => (
                <div
                  key={file.id}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
                >
                  <span className="rounded-full bg-sky-100 px-2 py-0.5 font-semibold text-sky-700 dark:bg-sky-900 dark:text-sky-200">
                    [{index + 1}]
                  </span>
                  <span className="max-w-[200px] truncate" title={file.name}>
                    {file.name}
                  </span>
                  <span className="text-slate-500 dark:text-slate-400">{formatFileSize(file.size)}</span>
                  <button
                    type="button"
                    className="rounded-full px-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                    onClick={() => onRemoveUploadedFile(file.id)}
                    aria-label={`Xóa file ${file.name}`}
                  >
                    x
                  </button>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {canRunProcess ? (
          <>
            <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85 sm:p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500 dark:text-slate-400">Bước 2</p>
              <h3 className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">Process và trả lời</h3>

              <ol className="mt-4 grid gap-2 md:grid-cols-3">
                {processSteps.map((step) => (
                  <li
                    key={step.id}
                    className={`rounded-2xl border px-3 py-2 ${
                      step.done
                        ? "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/50"
                        : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/70"
                    }`}
                  >
                    <p
                      className={`text-xs font-semibold uppercase tracking-wide ${
                        step.done ? "text-emerald-700 dark:text-emerald-300" : "text-slate-500 dark:text-slate-400"
                      }`}
                    >
                      Step {step.id}
                    </p>
                    <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{step.title}</p>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-600 dark:text-slate-300">{step.detail}</p>
                  </li>
                ))}
              </ol>

              <form onSubmit={onSubmit} className="mt-4 space-y-3">
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/70 sm:p-4">
                  <textarea
                    className="min-h-[112px] w-full resize-none border-0 bg-transparent p-0 text-sm leading-7 text-slate-900 placeholder:text-slate-500 focus:outline-none focus:ring-0 dark:text-slate-100 dark:placeholder:text-slate-400"
                    placeholder="Nhập câu hỏi chính để phân tích trên bộ tài liệu đã upload..."
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    disabled={isSubmitting}
                  />

                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-200 pt-3 dark:border-slate-700">
                    <fieldset className="inline-flex rounded-full border border-slate-300 bg-white p-1 dark:border-slate-700 dark:bg-slate-900">
                      <legend className="sr-only">Chọn chế độ trả lời</legend>
                      <button
                        type="button"
                        onClick={() => setSelectedTier("tier1")}
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          selectedTier === "tier1"
                            ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                            : "text-slate-600 dark:text-slate-300"
                        }`}
                      >
                        Nhanh
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedTier("tier2")}
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          selectedTier === "tier2"
                            ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900"
                            : "text-slate-600 dark:text-slate-300"
                        }`}
                      >
                        Chuyên sâu
                      </button>
                    </fieldset>

                    <button
                      type="submit"
                      disabled={isSubmitting || !query.trim()}
                      className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
                    >
                      {isSubmitting ? "Đang xử lý..." : "Phân tích"}
                    </button>
                  </div>
                </div>
              </form>

              <div className="mt-3 flex flex-wrap gap-2">
                {SUGGESTED_QUERIES.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setQuery(item)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-700 hover:border-sky-300 hover:text-sky-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-sky-400 dark:hover:text-sky-300"
                  >
                    {item}
                  </button>
                ))}
              </div>
            </section>

            <section className="mx-auto max-w-5xl space-y-4">
              {lastQuery ? (
                <article className="flex justify-end">
                  <div className="max-w-3xl rounded-3xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Câu hỏi của bạn</p>
                    <p className="mt-1 whitespace-pre-wrap text-sm leading-7 text-slate-800 dark:text-slate-100">{lastQuery}</p>
                  </div>
                </article>
              ) : null}

              {isSubmitting ? (
                <article className="rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900/85 dark:text-slate-200">
                  <span className="inline-flex items-center gap-2">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-sky-500" />
                    CLARA đang tổng hợp phản hồi...
                  </span>
                </article>
              ) : null}

              {result?.tier === "tier1" ? (
                <article className="rounded-3xl border border-slate-200 bg-white px-5 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
                  <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">Trả lời nhanh</p>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-900 dark:text-slate-100">{result.answer}</p>
                </article>
              ) : null}

              {result?.tier === "tier2" ? (
                <>
                  <article className="rounded-3xl border border-slate-200 bg-white px-5 py-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
                    <p className="text-xs font-semibold uppercase tracking-wide text-sky-700 dark:text-sky-300">Trả lời chuyên sâu</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-900 dark:text-slate-100">{result.answer || "Chưa có nội dung."}</p>

                    {result.citations.length ? (
                      <div className="mt-4 border-t border-slate-200 pt-3 dark:border-slate-700">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Citation bar</p>
                        <div className="mt-2 flex flex-wrap gap-2">
                          {result.citations.map((citation, idx) => (
                            <a
                              key={`${citation.title}-${idx}`}
                              href={`#citation-${idx + 1}`}
                              className="inline-flex max-w-full items-center gap-2 rounded-full border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs text-slate-700 hover:border-sky-300 hover:text-sky-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:hover:border-sky-400 dark:hover:text-sky-300"
                            >
                              <span className="rounded-full bg-sky-100 px-1.5 py-0.5 font-semibold text-sky-700 dark:bg-sky-900 dark:text-sky-200">
                                [{idx + 1}]
                              </span>
                              <span className="max-w-[220px] truncate" title={citation.source ?? citation.title}>
                                {citation.source ?? citation.title}
                              </span>
                            </a>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </article>

                  <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85 sm:p-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Nguồn tham chiếu chi tiết</p>
                    {result.citations.length ? (
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {result.citations.map((citation, idx) => (
                          <article
                            id={`citation-${idx + 1}`}
                            key={`${citation.title}-${idx}-detail`}
                            className="scroll-mt-24 rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/75"
                          >
                            <p className="text-xs font-semibold text-sky-700 dark:text-sky-300">[{idx + 1}]</p>
                            <p className="mt-1 text-sm font-semibold text-slate-800 dark:text-slate-100">{citation.title}</p>
                            {(citation.source || citation.year) && (
                              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                                {[citation.source, citation.year].filter(Boolean).join(" | ")}
                              </p>
                            )}
                            {citation.snippet ? <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{citation.snippet}</p> : null}
                            {citation.url ? (
                              <a
                                href={citation.url}
                                target="_blank"
                                rel="noreferrer"
                                className="mt-2 inline-block text-xs font-semibold text-sky-700 hover:underline dark:text-sky-300"
                              >
                                Mở nguồn
                              </a>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Chưa có nguồn tham chiếu.</p>
                    )}
                  </section>

                  <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85 sm:p-5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Các bước phân tích</p>
                    {result.steps.length ? (
                      <ol className="mt-3 space-y-2">
                        {result.steps.map((step, idx) => (
                          <li
                            key={`${step.title}-${idx}`}
                            className="rounded-2xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-800/75"
                          >
                            <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                              {idx + 1}. {step.title}
                            </p>
                            {step.detail ? <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{step.detail}</p> : null}
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Chưa có chi tiết bước xử lý.</p>
                    )}
                  </section>
                </>
              ) : null}

              {isDev && result?.tier === "tier1" ? (
                <section className="rounded-3xl border border-dashed border-slate-300 bg-white p-4 dark:border-slate-600 dark:bg-slate-900/85">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Intent Debug (dev)</p>
                  <div className="mt-2 grid gap-1 text-sm text-slate-700 dark:text-slate-300">
                    <p>role: {result.debug?.role ?? "N/A"}</p>
                    <p>intent: {result.debug?.intent ?? "N/A"}</p>
                    <p>confidence: {result.debug?.confidence ?? "N/A"}</p>
                    <p>model: {result.debug?.model_used ?? "N/A"}</p>
                  </div>
                </section>
              ) : null}
            </section>
          </>
        ) : (
          <section className="rounded-2xl border border-dashed border-slate-300 bg-white/80 px-4 py-3 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-300">
            Upload tối thiểu một tài liệu để mở bước process và kết quả chi tiết.
          </section>
        )}

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
            {error}
          </div>
        ) : null}
      </div>
    </PageShell>
  );
}
