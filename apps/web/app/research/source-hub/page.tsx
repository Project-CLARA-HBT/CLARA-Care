"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  listSourceHubCatalog,
  listSourceHubRecords,
  SourceHubCatalogEntry,
  SourceHubRecord,
  SourceHubSourceKey,
  syncSourceHub,
} from "@/lib/research";
import { getRole, type UserRole } from "@/lib/auth-store";
import TelemetryPanel from "@/components/telemetry/telemetry-panel";
import { safeUserFacingError, stripTelemetryLabels } from "@/lib/user-facing-text";
import { trackResearchSourcesSynced, trackResearchViewed } from "@/lib/analytics/events";
import { formatLocaleDate, t, type UITranslationKey } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import type { UILanguage } from "@/lib/ui-language";

const SOURCE_LABEL_KEYS: Record<SourceHubSourceKey, UITranslationKey> = {
  pubmed: "research.sourceHub.source.pubmed",
  rxnorm: "research.sourceHub.source.rxnorm",
  openfda: "research.sourceHub.source.openfda",
  dailymed: "research.sourceHub.source.dailymed",
  clinicaltrials: "research.sourceHub.source.clinicaltrials",
  europepmc: "research.sourceHub.source.europepmc",
  semantic_scholar: "research.sourceHub.source.semanticScholar",
  vn_moh: "research.sourceHub.source.vnMoh",
  vn_kcb: "research.sourceHub.source.vnKcb",
  vn_canhgiacduoc: "research.sourceHub.source.vnCanhGiacDuoc",
  vn_vbpl_byt: "research.sourceHub.source.vnVbplByt",
  vn_dav: "research.sourceHub.source.vnDav",
  davidrug: "research.sourceHub.source.davidrug",
};

function sourceLabel(language: UILanguage, source: SourceHubSourceKey): string {
  return t(language, SOURCE_LABEL_KEYS[source]);
}

function formatDate(language: UILanguage, value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return formatLocaleDate(language, date, {
    dateStyle: "medium",
    timeStyle: "short",
    hour12: false,
  });
}

export default function ResearchSourceHubPage() {
  const language = useUILanguage();
  const [catalog, setCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [records, setRecords] = useState<SourceHubRecord[]>([]);
  const [activeSource, setActiveSource] = useState<SourceHubSourceKey>("pubmed");
  const [filterText, setFilterText] = useState("");
  const [syncQuery, setSyncQuery] = useState("diabetes type 2 guideline");
  const [syncLimit, setSyncLimit] = useState("12");
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // Raw connector diagnostics from the last sync. These can carry internal
  // telemetry (e.g. `openfda http_400`) so they are NEVER rendered inline;
  // they are surfaced through the role-gated TelemetryPanel (admin-only).
  const [syncWarnings, setSyncWarnings] = useState<string[]>([]);
  const [role, setRoleState] = useState<UserRole>("normal");

  // Hydrate the viewer role on mount and emit the coarse, non-PII
  // "Research surface viewed" product event (Req 9.1).
  useEffect(() => {
    setRoleState(getRole());
    trackResearchViewed();
  }, []);

  const loadCatalog = useCallback(async () => {
    const items = await listSourceHubCatalog();
    setCatalog(items);
    if (items.length) {
      setActiveSource((current) => (items.some((item) => item.key === current) ? current : items[0].key));
      setSyncQuery((current) => current || items[0].default_query || "diabetes type 2 guideline");
    }
  }, []);

  const loadRecords = useCallback(async (query?: string) => {
    setIsLoading(true);
    setError("");
    try {
      const items = await listSourceHubRecords({
        source: "all",
        query: query?.trim() || undefined,
        limit: 80,
      });
      setRecords(items);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "research.sourceHub.error.loadRecords")));
    } finally {
      setIsLoading(false);
    }
  }, [language]);

  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true);
      setError("");
      try {
        await loadCatalog();
        await loadRecords();
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "research.sourceHub.error.loadHub")));
        setIsLoading(false);
      }
    };
    void initialize();
  }, [loadCatalog, loadRecords]);

  const activeCatalogEntry = useMemo(
    () => catalog.find((item) => item.key === activeSource) ?? null,
    [activeSource, catalog]
  );

  const recordDistribution = useMemo(() => {
    const counter = new Map<SourceHubSourceKey, number>();
    for (const record of records) {
      counter.set(record.source, (counter.get(record.source) ?? 0) + 1);
    }
    return Array.from(counter.entries()).sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [records]);

  const maxRecordCount = useMemo(
    () => Math.max(1, ...recordDistribution.map(([, count]) => count)),
    [recordDistribution]
  );

  const onFilter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadRecords(filterText);
  };

  const onSync = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = syncQuery.trim();
    if (!query) {
      setError(t(language, "research.sourceHub.sync.queryRequired"));
      return;
    }
    const parsedLimit = Number(syncLimit);
    const safeLimit = Number.isFinite(parsedLimit) ? Math.max(3, Math.min(100, Math.trunc(parsedLimit))) : 12;

    setIsSyncing(true);
    setError("");
    setMessage("");
    setSyncWarnings([]);
    try {
      const result = await syncSourceHub({ source: activeSource, query, limit: safeLimit });
      await loadRecords(filterText);
      // Clean, End_User-safe success summary only — no raw connector strings.
      setMessage(
        stripTelemetryLabels(
          t(language, "research.sourceHub.sync.success", {
            source: sourceLabel(language, result.source),
            fetched: result.fetched,
            stored: result.stored,
          }),
        )
      );
      if (result.warnings.length) {
        // Retain raw warnings for the admin-only telemetry panel; surface a
        // calm, non-technical hint to End_Users instead of connector errors.
        setSyncWarnings(result.warnings);
      }
      // Coarse, non-PII analytics: source key + counts only (Req 9.1, 9.4).
      trackResearchSourcesSynced({
        source: result.source,
        fetched: result.fetched,
        stored: result.stored,
      });
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "research.sourceHub.error.sync")));
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <main className="min-h-[100dvh] bg-[var(--bg-canvas)] px-4 py-6 text-[var(--text-primary)] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--text-brand)]">{t(language, "research.sourceHub.eyebrow")}</p>
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-[2.35rem]">
                {t(language, "research.sourceHub.title")}
              </h1>
              <p className="mt-3 text-base leading-7 text-[var(--text-secondary)]">
                {t(language, "research.sourceHub.description")}
              </p>
            </div>
            <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800 dark:border-blue-800 dark:bg-blue-950/35 dark:text-blue-200">
              {t(language, "research.sourceHub.availableSummary", { sources: catalog.length, records: records.length })}
            </div>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "research.sourceHub.sync.eyebrow")}</p>
                <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">{t(language, "research.sourceHub.sync.title")}</h2>
              </div>
              {activeCatalogEntry?.docs_url ? (
                <a
                  href={activeCatalogEntry.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-10 items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-semibold text-[var(--text-brand)]"
                >
                  {t(language, "research.sourceHub.sync.docs")}
                </a>
              ) : null}
            </div>

            <form onSubmit={onSync} className="grid gap-3 md:grid-cols-[14rem_minmax(0,1fr)_7rem_auto]">
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">{t(language, "research.sourceHub.sync.source")}</span>
                <select
                  value={activeSource}
                  onChange={(event) => setActiveSource(event.target.value as SourceHubSourceKey)}
                  className="min-h-11 w-full rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 text-sm font-medium text-[var(--text-primary)] outline-none focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                >
                  {catalog.map((item) => (
                    <option key={item.key} value={item.key}>
                      {sourceLabel(language, item.key)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">{t(language, "research.sourceHub.sync.query")}</span>
                <input
                  value={syncQuery}
                  onChange={(event) => setSyncQuery(event.target.value)}
                  placeholder={activeCatalogEntry?.default_query || t(language, "research.sourceHub.sync.queryPlaceholder")}
                  className="min-h-11 w-full rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 text-sm font-medium text-[var(--text-primary)] outline-none placeholder:text-[color:var(--text-muted)] focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">{t(language, "research.sourceHub.sync.limit")}</span>
                <input
                  value={syncLimit}
                  onChange={(event) => setSyncLimit(event.target.value)}
                  inputMode="numeric"
                  className="min-h-11 w-full rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 text-sm font-medium text-[var(--text-primary)] outline-none focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                />
              </label>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={isSyncing || !catalog.length}
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-[var(--brand-600)] px-4 text-sm font-bold text-white transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:bg-blue-200 disabled:text-slate-700"
                >
                  {isSyncing ? t(language, "research.sourceHub.sync.running") : t(language, "research.sourceHub.sync.submit")}
                </button>
              </div>
            </form>

            {activeCatalogEntry ? (
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{activeCatalogEntry.description}</p>
            ) : null}
          </article>

          <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "research.sourceHub.distribution.eyebrow")}</p>
            <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">{t(language, "research.sourceHub.distribution.title")}</h2>
            <div className="mt-4 space-y-3">
              {recordDistribution.length ? (
                recordDistribution.map(([source, count]) => (
                  <div key={source}>
                    <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                      <span className="truncate font-semibold text-[var(--text-primary)]">{sourceLabel(language, source)}</span>
                      <span className="font-mono text-[var(--text-secondary)]">{count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-muted)]">
                      <div
                        className="h-full rounded-full bg-[var(--brand-600)]"
                        style={{ width: `${Math.max(8, Math.round((count / maxRecordCount) * 100))}%` }}
                      />
                    </div>
                  </div>
                ))
              ) : (
                <p className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm text-[var(--text-secondary)]">
                  {t(language, "research.sourceHub.distribution.empty")}
                </p>
              )}
            </div>
          </article>
        </section>

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "research.sourceHub.records.eyebrow")}</p>
              <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">{t(language, "research.sourceHub.records.title")}</h2>
            </div>
            <form onSubmit={onFilter} className="flex flex-wrap items-center gap-2">
              <input
                value={filterText}
                onChange={(event) => setFilterText(event.target.value)}
                placeholder={t(language, "research.sourceHub.records.filterPlaceholder")}
                className="min-h-10 w-72 rounded-lg border border-[color:var(--shell-border)] bg-[color:var(--surface-muted)] px-3 text-sm font-medium text-[var(--text-primary)] outline-none placeholder:text-[color:var(--text-muted)] focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
              />
              <button
                type="submit"
                className="min-h-10 rounded-lg border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] px-4 text-sm font-bold text-[var(--text-brand)]"
              >
                {t(language, "research.sourceHub.records.filter")}
              </button>
            </form>
          </div>

          {error ? (
            <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
              {error}
            </p>
          ) : null}
          {message ? (
            <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
              {message}
            </p>
          ) : null}
          {syncWarnings.length ? (
            <TelemetryPanel
              role={role}
              payload={syncWarnings}
              className="mb-3"
              summaryText={t(language, "research.sourceHub.warning.summary")}
            >
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                <p className="text-xs font-bold uppercase tracking-[0.12em]">{t(language, "research.sourceHub.warning.admin")}</p>
                <ul className="mt-1 list-disc space-y-1 pl-5 font-mono text-xs">
                  {syncWarnings.map((warning, index) => (
                    <li key={`${warning}-${index}`}>{warning}</li>
                  ))}
                </ul>
              </div>
            </TelemetryPanel>
          ) : null}

          <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                  <th className="px-3 py-3">{t(language, "research.sourceHub.table.source")}</th>
                  <th className="px-3 py-3">{t(language, "research.sourceHub.table.title")}</th>
                  <th className="px-3 py-3">{t(language, "research.sourceHub.table.query")}</th>
                  <th className="px-3 py-3">{t(language, "research.sourceHub.table.published")}</th>
                  <th className="px-3 py-3">{t(language, "research.sourceHub.table.synced")}</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="px-3 py-4 text-[var(--text-secondary)]" colSpan={5}>
                      {t(language, "research.sourceHub.table.loading")}
                    </td>
                  </tr>
                ) : records.length ? (
                  records.map((record) => (
                    <tr key={record.id} className="border-b border-[color:var(--shell-border)] align-top last:border-0">
                      <td className="px-3 py-3">
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-bold text-blue-800 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
                          {sourceLabel(language, record.source)}
                        </span>
                      </td>
                      <td className="max-w-xl px-3 py-3">
                        {record.url ? (
                          <a href={record.url} target="_blank" rel="noreferrer" className="font-bold text-[var(--text-brand)] hover:underline">
                            {record.title}
                          </a>
                        ) : (
                          <p className="font-bold text-[var(--text-primary)]">{record.title}</p>
                        )}
                        {record.snippet ? (
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--text-secondary)]">{record.snippet}</p>
                        ) : null}
                      </td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{record.query || "-"}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{formatDate(language, record.published_at)}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{formatDate(language, record.synced_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-4 text-[var(--text-secondary)]" colSpan={5}>
                      {t(language, "research.sourceHub.table.empty")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
