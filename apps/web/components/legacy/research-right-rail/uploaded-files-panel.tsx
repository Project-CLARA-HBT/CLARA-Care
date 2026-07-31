import { DragEvent } from "react";
import { UploadedResearchFile } from "@/lib/research";

type UploadedFilesPanelProps = {
  files: UploadedResearchFile[];
  isUploading: boolean;
  isDragActive: boolean;
  uploadError: string;
  onClearAll: () => void;
  onRemoveFile: (fileId: string) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDragEnter: (event: DragEvent<HTMLDivElement>) => void;
  onDragLeave: (event: DragEvent<HTMLDivElement>) => void;
};

function formatFileSize(size?: number): string {
  if (!size || Number.isNaN(size)) return "Không rõ dung lượng";
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

export default function UploadedFilesPanel({
  files,
  isUploading,
  isDragActive,
  uploadError,
  onClearAll,
  onRemoveFile,
  onDrop,
  onDragOver,
  onDragEnter,
  onDragLeave
}: UploadedFilesPanelProps) {
  return (
    <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Uploaded Files</p>
        {files.length ? (
          <button
            type="button"
            onClick={onClearAll}
            disabled={isUploading}
            className="rounded-full border border-slate-300 bg-white px-2.5 py-1 text-[11px] text-slate-700 hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Xóa hết
          </button>
        ) : null}
      </div>

      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        className={[
          "mt-3 rounded-2xl border-2 border-dashed p-3 text-center transition",
          isDragActive
            ? "border-sky-400 bg-sky-50 dark:border-sky-500 dark:bg-sky-950/40"
            : "border-slate-300 bg-slate-50/80 dark:border-slate-600 dark:bg-slate-800/65"
        ].join(" ")}
      >
        <p className="text-xs text-slate-600 dark:text-slate-300">Kéo thả tài liệu vào đây</p>
      </div>

      {uploadError ? (
        <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
          {uploadError}
        </p>
      ) : null}

      {files.length ? (
        <div className="mt-3 space-y-2">
          {files.map((file) => (
            <div
              key={file.id}
              className="flex items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs dark:border-slate-700 dark:bg-slate-800/75"
            >
              <div className="min-w-0">
                <p className="truncate font-semibold text-slate-800 dark:text-slate-100" title={file.name}>
                  {file.name}
                </p>
                <p className="text-slate-500 dark:text-slate-400">{formatFileSize(file.size)}</p>
              </div>
              <button
                type="button"
                className="rounded-full px-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                onClick={() => onRemoveFile(file.id)}
                aria-label={`Xóa file ${file.name}`}
              >
                x
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">Chưa có file đính kèm.</p>
      )}
    </section>
  );
}
