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
    <section className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          {t(language, "research.workspace.knowledgeSources.title")}
        </p>
        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]">
          {selectedSourceIds.length}/{sources.length}
        </span>
      </div>

      <form onSubmit={onCreateSource} className="mt-3 flex gap-2">
        <input
          value={newSourceName}
          onChange={(event) => onSourceNameChange(event.target.value)}
          className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[color:var(--brand-primary)]/15"
          placeholder={t(language, "research.workspace.knowledgeSources.createPlaceholder")}
        />
        <button
          type="submit"
          disabled={isCreating || !newSourceName.trim()}
          className="rounded-lg bg-[var(--brand-600)] px-3 py-2 text-xs font-semibold text-[var(--on-secondary-container)] disabled:opacity-60"
        >
          +
        </button>
      </form>

      {sourceError ? (
        <p className="mt-2 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]">
          {sourceError}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {isLoading ? (
          <p className="text-sm text-[var(--text-muted)]">
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
                    ? "border-[color:var(--status-ok-border)] bg-[var(--surface-brand-soft)]"
                    : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]"
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={selected}
                  onChange={() => onToggleSource(source.id)}
                  className="mt-0.5 h-3.5 w-3.5 rounded border-[color:var(--shell-border)] accent-[var(--brand-600)]"
                />
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-[var(--text-primary)]">{source.name}</span>
                  <span className="text-[var(--text-muted)]">
                    {t(language, "research.workspace.knowledgeSources.documents", {
                      count: source.documents_count
                    })}
                  </span>
                </span>
              </label>
            );
          })
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            {t(language, "research.workspace.knowledgeSources.empty")}
          </p>
        )}
      </div>
    </section>
  );
}
