"use client";

import { FormEvent } from "react";
import { KnowledgeSource } from "@/lib/research";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

type KnowledgeSourcesPanelProps = {
  sources: KnowledgeSource[];
  selectedSourceIds: number[];
  isLoading: boolean;
  isCreating: boolean;
  sourceError: string;
  newSourceName: string;
  onSourceNameChange: (value: string) => void;
  onToggleSource: (sourceId: number) => void;
  onCreateSource: (event: FormEvent<HTMLFormElement>) => void;
};

export default function KnowledgeSourcesPanel({
  sources,
  selectedSourceIds,
  isLoading,
  isCreating,
  sourceError,
  newSourceName,
  onSourceNameChange,
  onToggleSource,
  onCreateSource
}: KnowledgeSourcesPanelProps) {
  const language = useUILanguage();

  return (
    <section className="rounded-3xl border border-slate-200/85 bg-white/90 p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">
          {t(language, "research.workspace.knowledgeSources.title")}
        </p>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {selectedSourceIds.length}/{sources.length}
        </span>
      </div>

      <form onSubmit={onCreateSource} className="mt-3 flex gap-2">
        <input
          value={newSourceName}
          onChange={(event) => onSourceNameChange(event.target.value)}
          className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200"
          placeholder={t(language, "research.workspace.knowledgeSources.createPlaceholder")}
        />
        <button
          type="submit"
          disabled={isCreating || !newSourceName.trim()}
          className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60 dark:bg-slate-100 dark:text-slate-900"
        >
          +
        </button>
      </form>

      {sourceError ? (
        <p className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
          {sourceError}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {isLoading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t(language, "research.workspace.knowledgeSources.loading")}
          </p>
        ) : sources.length ? (
          sources.map((source) => {
            const selected = selectedSourceIds.includes(source.id);
            return (
              <label
                key={source.id}
                className={[
                  "flex cursor-pointer items-start gap-2 rounded-2xl border px-3 py-2 text-xs transition",
                  selected
                    ? "border-sky-300 bg-sky-50 dark:border-sky-600 dark:bg-sky-950/40"
                    : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/75"
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => onToggleSource(source.id)}
                  className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 accent-sky-600"
                />
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-slate-800 dark:text-slate-100">{source.name}</span>
                  <span className="text-slate-500 dark:text-slate-400">
                    {t(language, "research.workspace.knowledgeSources.documents", {
                      count: source.documents_count
                    })}
                  </span>
                </span>
              </label>
            );
          })
        ) : (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t(language, "research.workspace.knowledgeSources.empty")}
          </p>
        )}
      </div>
    </section>
  );
}
