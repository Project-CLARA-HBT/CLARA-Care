"use client";

import type { DragEvent } from "react";
import { formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { UploadedResearchFile } from "@/lib/research";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

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

function formatFileSize(
  size: number | undefined,
  unknown: string,
  language: UILanguage,
): string {
  if (!size || Number.isNaN(size)) return unknown;
  if (size < 1024) return `${formatLocaleNumber(language, size)} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${formatLocaleNumber(language, kb)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${formatLocaleNumber(language, mb)} MB`;
  return `${formatLocaleNumber(language, mb / 1024)} GB`;
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
  onDragLeave,
}: UploadedFilesPanelProps) {
  const language = useUILanguage();

  return (
    <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          {t(language, "research.workspace.files.title")}
        </p>
        {files.length ? (
          <button
            type="button"
            onClick={onClearAll}
            disabled={isUploading}
            className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1 text-[11px] text-[var(--text-secondary)] hover:bg-[var(--surface-brand-soft)]"
          >
            {t(language, "research.workspace.files.clearAll")}
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
            ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]"
            : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
        ].join(" ")}
      >
        <p className="text-xs text-[var(--text-secondary)]">
          {t(language, "research.workspace.files.dropzone")}
        </p>
      </div>

      {uploadError ? (
        <p className="mt-3 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]">
          {uploadError}
        </p>
      ) : null}

      {files.length ? (
        <div className="mt-3 space-y-2">
          {files.map((file) => (
            <div
              key={file.id}
              className="flex items-center justify-between gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs"
            >
              <div className="min-w-0">
                <p
                  className="truncate font-semibold text-[var(--text-primary)]"
                  title={file.name}
                >
                  {file.name}
                </p>
                <p className="text-[var(--text-muted)]">
                  {formatFileSize(
                    file.size,
                    t(language, "research.workspace.files.sizeUnknown"),
                    language,
                  )}
                </p>
              </div>
              <button
                type="button"
                className="rounded-full px-1.5 text-[var(--text-muted)] hover:bg-[var(--surface-panel)] hover:text-[var(--text-primary)]"
                onClick={() => onRemoveFile(file.id)}
                aria-label={t(language, "research.workspace.files.remove", {
                  name: file.name,
                })}
              >
                x
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-[var(--text-muted)]">
          {t(language, "research.workspace.files.empty")}
        </p>
      )}
    </section>
  );
}
