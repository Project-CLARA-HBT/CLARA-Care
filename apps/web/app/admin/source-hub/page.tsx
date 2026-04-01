"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
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

export default function AdminSourceHubPage() {
  const [catalog, setCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [records, setRecords] = useState<SourceHubRecord[]>([]);
  const [activeSource, setActiveSource] = useState<SourceHubSourceKey>("pubmed");
  const [searchText, setSearchText] = useState("");
  const [syncQuery, setSyncQuery] = useState("diabetes type 2");
  const [syncLimit, setSyncLimit] = useState("12");
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const selectedCatalog = useMemo(
    () => catalog.find((item) => item.key === activeSource) ?? null,
    [catalog, activeSource]
  );

  const loadCatalog = useCallback(async () => {
    try {
      const items = await listSourceHubCatalog();
      setCatalog(items);
      if (items.length) {
        setActiveSource((current) =>
          items.some((item) => item.key === current) ? current : items[0].key
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải catalog nguồn dữ liệu.");
    }
  }, []);

  const loadRecords = useCallback(async (source?: SourceHubSourceKey | "all", query?: string) => {
    setIsLoading(true);
    setError("");
    try {
      const items = await listSourceHubRecords({
        source: source ?? "all",
        query: query?.trim() || undefined,
        limit: 80,
      });
      setRecords(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải dữ liệu Source Hub.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialize = async () => {
      await loadCatalog();
      await loadRecords("all");
    };
    void initialize();
  }, [loadCatalog, loadRecords]);

  const onSync = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = syncQuery.trim();
    if (!query) {
      setError("Vui lòng nhập query đồng bộ.");
      return;
    }

    const parsedLimit = Number(syncLimit);
    const safeLimit = Number.isFinite(parsedLimit)
      ? Math.max(3, Math.min(500, Math.trunc(parsedLimit)))
      : 12;

    setIsSyncing(true);
    setError("");
    setMessage("");
    try {
      const result = await syncSourceHub({
        source: activeSource,
        query,
        limit: safeLimit,
      });
      await loadRecords("all", searchText);
      setMessage(
        `Đồng bộ ${SOURCE_LABELS[result.source]} thành công: fetch ${result.fetched}, lưu ${result.stored} record.`
      );
      if (result.warnings.length) {
        setMessage((prev) => `${prev} Cảnh báo: ${result.warnings.join(" | ")}`);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể đồng bộ dữ liệu nguồn.");
    } finally {
      setIsSyncing(false);
    }
  };

  const onFilter = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadRecords("all", searchText);
  };

  return (
    <AdminShell
      activeTab="source-hub"
      title="Source Hub y khoa"
      description="Quản lý đồng bộ dữ liệu từ PubMed, Europe PMC, ClinicalTrials.gov, DailyMed, RxNorm, openFDA, Semantic Scholar, Bộ Y tế Việt Nam, Cục Quản lý Khám chữa bệnh, Cảnh giác Dược, VBPL Bộ Y tế, Cục Quản lý Dược và DAVIDrug. Theo dõi record crawl, query đã dùng và metadata chi tiết để phục vụ RAG và kiểm chứng."
    >
      <div className="space-y-5">
        <section className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
          <article className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-5 shadow-soft dark:border-slate-700 dark:bg-slate-900/85">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Catalog nguồn dữ liệu</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Chọn nguồn chính để chạy sync query mới.</p>

            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {catalog.map((item) => {
                const active = item.key === activeSource;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => {
                      setActiveSource(item.key);
                      if (item.default_query) {
                        setSyncQuery(item.default_query);
                      }
                    }}
                    className={[
                      "rounded-xl border px-3 py-3 text-left transition",
                      active
                        ? "border-sky-400 bg-sky-50 text-sky-900 dark:border-sky-500 dark:bg-sky-950/45 dark:text-sky-100"
                        : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200",
                    ].join(" ")}
                  >
                    <p className="text-sm font-semibold">{item.label}</p>
                    <p className="mt-1 text-xs leading-5 opacity-90">{item.description}</p>
                  </button>
                );
              })}
            </div>
          </article>

          <article className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-5 shadow-soft dark:border-slate-700 dark:bg-slate-900/85">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Đồng bộ dữ liệu mới</h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">Thiết lập query và số bản ghi rồi chạy sync theo nguồn đã chọn.</p>

            <form className="mt-4 space-y-3" onSubmit={onSync}>
              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-800 dark:text-slate-100">Nguồn đang chọn</span>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100">
                  {selectedCatalog?.label ?? SOURCE_LABELS[activeSource]}
                </div>
              </label>

              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-800 dark:text-slate-100">Query</span>
                <input
                  value={syncQuery}
                  onChange={(event) => setSyncQuery(event.target.value)}
                  placeholder="Ví dụ: statin adverse effects"
                  className="min-h-[46px] w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>

              <label className="block space-y-1">
                <span className="text-sm font-medium text-slate-800 dark:text-slate-100">Số record/lần sync (3-500)</span>
                <input
                  value={syncLimit}
                  onChange={(event) => setSyncLimit(event.target.value)}
                  className="min-h-[46px] w-full rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>

              <button
                type="submit"
                disabled={isSyncing}
                className="inline-flex min-h-[48px] items-center rounded-xl border border-sky-300 bg-gradient-to-r from-sky-600 to-cyan-500 px-5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {isSyncing ? "Đang đồng bộ..." : "Sync nguồn dữ liệu"}
              </button>

              {selectedCatalog?.docs_url ? (
                <a
                  href={selectedCatalog.docs_url}
                  target="_blank"
                  rel="noreferrer"
                  className="ml-3 inline-flex text-sm font-medium text-sky-700 underline underline-offset-2 dark:text-sky-300"
                >
                  Mở docs nguồn
                </a>
              ) : null}
            </form>
          </article>
        </section>

        <section className="rounded-[1.5rem] border border-slate-200 bg-white/90 p-5 shadow-soft dark:border-slate-700 dark:bg-slate-900/85">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Kho record đã crawl</h3>
              <p className="text-sm text-slate-600 dark:text-slate-300">Lưu latest-first, lọc theo query để kiểm tra chất lượng nguồn.</p>
            </div>

            <form className="flex flex-wrap items-center gap-2" onSubmit={onFilter}>
              <input
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Lọc theo query hoặc tiêu đề..."
                className="min-h-[44px] w-64 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
              <button
                type="submit"
                className="min-h-[44px] rounded-xl border border-slate-300 bg-slate-50 px-4 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                Lọc
              </button>
            </form>
          </div>

          {error ? <p className="mt-3 rounded-xl border border-red-300/40 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-700/40 dark:bg-red-950/20 dark:text-red-300">{error}</p> : null}
          {message ? <p className="mt-3 rounded-xl border border-emerald-300/45 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-700/45 dark:bg-emerald-950/20 dark:text-emerald-300">{message}</p> : null}

          <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Query</th>
                  <th className="px-3 py-2">Published</th>
                  <th className="px-3 py-2">Synced</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td className="px-3 py-3 text-slate-500 dark:text-slate-400" colSpan={5}>Đang tải dữ liệu...</td>
                  </tr>
                ) : records.length ? (
                  records.map((record) => (
                    <tr key={record.id} className="border-b border-slate-100 bg-white align-top last:border-0 dark:border-slate-800 dark:bg-slate-900/70">
                      <td className="px-3 py-2">
                        <span className="rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
                          {SOURCE_LABELS[record.source]}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-800 dark:text-slate-100">{record.title}</p>
                        {record.snippet ? <p className="mt-1 line-clamp-3 text-xs text-slate-500 dark:text-slate-300">{record.snippet}</p> : null}
                        {record.url ? (
                          <a
                            href={record.url}
                            target="_blank"
                            rel="noreferrer"
                            className="mt-1 inline-flex text-xs font-semibold text-sky-700 underline underline-offset-2 dark:text-sky-300"
                          >
                            Mở nguồn gốc
                          </a>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{record.query || "-"}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{formatDate(record.published_at)}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{formatDate(record.synced_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3 text-slate-500 dark:text-slate-400" colSpan={5}>Chưa có dữ liệu crawl. Hãy chạy sync ở phía trên.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
