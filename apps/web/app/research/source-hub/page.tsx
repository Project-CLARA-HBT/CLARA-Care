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

const SOURCE_LABELS: Record<SourceHubSourceKey, string> = {
  pubmed: "PubMed",
  rxnorm: "RxNorm",
  openfda: "openFDA",
  dailymed: "DailyMed",
  clinicaltrials: "ClinicalTrials.gov",
  europepmc: "Europe PMC",
  semantic_scholar: "Semantic Scholar",
  vn_moh: "Bộ Y tế Việt Nam",
  vn_kcb: "Cục Quản lý Khám chữa bệnh",
  vn_canhgiacduoc: "Cảnh giác Dược Quốc gia",
  vn_vbpl_byt: "VBPL Bộ Y tế",
  vn_dav: "Cục Quản lý Dược Việt Nam",
  davidrug: "DAVIDrug",
};

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN", { hour12: false });
}

export default function ResearchSourceHubPage() {
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
      setError(cause instanceof Error ? cause.message : "Không thể tải dữ liệu nguồn nghiên cứu.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialize = async () => {
      setIsLoading(true);
      setError("");
      try {
        await loadCatalog();
        await loadRecords();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Không thể tải Source Hub.");
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
      setError("Vui lòng nhập chủ đề cần đồng bộ.");
      return;
    }
    const parsedLimit = Number(syncLimit);
    const safeLimit = Number.isFinite(parsedLimit) ? Math.max(3, Math.min(100, Math.trunc(parsedLimit))) : 12;

    setIsSyncing(true);
    setError("");
    setMessage("");
    try {
      const result = await syncSourceHub({ source: activeSource, query, limit: safeLimit });
      await loadRecords(filterText);
      setMessage(`Đã đồng bộ ${SOURCE_LABELS[result.source]}: lấy ${result.fetched}, lưu ${result.stored} bản ghi.`);
      if (result.warnings.length) {
        setMessage((current) => `${current} Cảnh báo: ${result.warnings.join(" | ")}`);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đồng bộ nguồn nghiên cứu.");
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
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--text-brand)]">Research Source Hub</p>
              <h1 className="mt-2 text-3xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-[2.35rem]">
                Nguồn nghiên cứu
              </h1>
              <p className="mt-3 text-base leading-7 text-[var(--text-secondary)]">
                Đồng bộ PubMed, dữ liệu thuốc và nguồn y khoa để hỗ trợ phân tích có bằng chứng. Mục này chỉ hiện với nhà nghiên cứu, bác sĩ và admin.
              </p>
            </div>
            <div className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-800 dark:border-blue-800 dark:bg-blue-950/35 dark:text-blue-200">
              {catalog.length} nguồn khả dụng · {records.length} bản ghi đã lưu
            </div>
          </div>
        </section>

        <section className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
          <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">Đồng bộ nguồn</p>
                <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Lấy bản ghi nghiên cứu mới</h2>
              </div>
              {activeCatalogEntry?.docs_url ? (
                <a
                  href={activeCatalogEntry.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-10 items-center rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm font-semibold text-[var(--text-brand)]"
                >
                  Xem tài liệu nguồn
                </a>
              ) : null}
            </div>

            <form onSubmit={onSync} className="grid gap-3 md:grid-cols-[14rem_minmax(0,1fr)_7rem_auto]">
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Nguồn</span>
                <select
                  value={activeSource}
                  onChange={(event) => setActiveSource(event.target.value as SourceHubSourceKey)}
                  className="min-h-11 w-full rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 text-sm font-medium text-[var(--text-primary)] outline-none focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                >
                  {catalog.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Chủ đề tìm kiếm</span>
                <input
                  value={syncQuery}
                  onChange={(event) => setSyncQuery(event.target.value)}
                  placeholder={activeCatalogEntry?.default_query || "Ví dụ: metformin interaction"}
                  className="min-h-11 w-full rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 text-sm font-medium text-[var(--text-primary)] outline-none placeholder:text-[#6B7280] focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--text-secondary)]">Số lượng</span>
                <input
                  value={syncLimit}
                  onChange={(event) => setSyncLimit(event.target.value)}
                  inputMode="numeric"
                  className="min-h-11 w-full rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 text-sm font-medium text-[var(--text-primary)] outline-none focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
                />
              </label>
              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={isSyncing || !catalog.length}
                  className="inline-flex min-h-11 w-full items-center justify-center rounded-lg bg-[var(--brand-600)] px-4 text-sm font-bold text-white transition hover:bg-[var(--brand-700)] disabled:cursor-not-allowed disabled:bg-blue-200 disabled:text-slate-700"
                >
                  {isSyncing ? "Đang đồng bộ..." : "Đồng bộ"}
                </button>
              </div>
            </form>

            {activeCatalogEntry ? (
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">{activeCatalogEntry.description}</p>
            ) : null}
          </article>

          <article className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">Phân bố dữ liệu</p>
            <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Bản ghi theo nguồn</h2>
            <div className="mt-4 space-y-3">
              {recordDistribution.length ? (
                recordDistribution.map(([source, count]) => (
                  <div key={source}>
                    <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                      <span className="truncate font-semibold text-[var(--text-primary)]">{SOURCE_LABELS[source]}</span>
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
                  Chưa có bản ghi. Hãy đồng bộ một nguồn để bắt đầu.
                </p>
              )}
            </div>
          </article>
        </section>

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">Bản ghi đã lưu</p>
              <h2 className="mt-1 text-xl font-bold text-[var(--text-primary)]">Kết quả nguồn nghiên cứu</h2>
            </div>
            <form onSubmit={onFilter} className="flex flex-wrap items-center gap-2">
              <input
                value={filterText}
                onChange={(event) => setFilterText(event.target.value)}
                placeholder="Lọc theo tiêu đề hoặc query..."
                className="min-h-10 w-72 rounded-lg border border-[#93C5FD] bg-[#F8FBFF] px-3 text-sm font-medium text-[var(--text-primary)] outline-none placeholder:text-[#6B7280] focus:border-[var(--brand-600)] focus:ring-2 focus:ring-blue-500/15"
              />
              <button
                type="submit"
                className="min-h-10 rounded-lg border border-[color:var(--shell-border-strong)] bg-[var(--surface-muted)] px-4 text-sm font-bold text-[var(--text-brand)]"
              >
                Lọc
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

          <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-xs font-bold uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                  <th className="px-3 py-3">Nguồn</th>
                  <th className="px-3 py-3">Tiêu đề</th>
                  <th className="px-3 py-3">Query</th>
                  <th className="px-3 py-3">Công bố</th>
                  <th className="px-3 py-3">Đồng bộ</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="px-3 py-4 text-[var(--text-secondary)]" colSpan={5}>
                      Đang tải bản ghi...
                    </td>
                  </tr>
                ) : records.length ? (
                  records.map((record) => (
                    <tr key={record.id} className="border-b border-[color:var(--shell-border)] align-top last:border-0">
                      <td className="px-3 py-3">
                        <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-bold text-blue-800 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
                          {SOURCE_LABELS[record.source]}
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
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{formatDate(record.published_at)}</td>
                      <td className="px-3 py-3 text-[var(--text-secondary)]">{formatDate(record.synced_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-4 text-[var(--text-secondary)]" colSpan={5}>
                      Chưa có dữ liệu. Hãy đồng bộ một nguồn hoặc đổi bộ lọc.
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
