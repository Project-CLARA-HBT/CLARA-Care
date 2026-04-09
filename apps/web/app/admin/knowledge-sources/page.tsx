"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import {
  KnowledgeSource,
  KnowledgeSourceDocument,
  listSourceHubCatalog,
  listSourceHubRecords,
  SourceHubCatalogEntry,
  SourceHubRecord,
  SourceHubSourceKey,
  syncSourceHub,
  createKnowledgeSource,
  listKnowledgeSourceDocuments,
  listKnowledgeSources,
  setKnowledgeDocumentStatus,
  uploadFileToKnowledgeSource,
} from "@/lib/research";

function formatSize(size: number): string {
  if (!Number.isFinite(size) || size <= 0) return "0 B";
  if (size < 1024) return `${size} B`;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function formatCompactNumber(value: number): string {
  if (!Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value);
}

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
  davidrug: "DAVIDrug"
};

function formatDate(value?: string): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("vi-VN", { hour12: false });
}

export default function AdminKnowledgeSourcesPage() {
  const {
    config,
    isLoading: isLoadingRag,
    isSaving: isSavingRag,
    isDirty: isDirtyRag,
    error: ragError,
    message: ragMessage,
    reload: reloadRag,
    save: saveRag,
    setSourceEnabled,
    setSourcePriority,
    setSourceWeight
  } = useControlTowerConfig();

  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [activeSourceId, setActiveSourceId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<KnowledgeSourceDocument[]>([]);
  const [newSourceName, setNewSourceName] = useState("");
  const [isLoadingSources, setIsLoadingSources] = useState(true);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isCreatingSource, setIsCreatingSource] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [sourceHubError, setSourceHubError] = useState("");
  const [sourceHubMessage, setSourceHubMessage] = useState("");

  const [sourceHubCatalog, setSourceHubCatalog] = useState<SourceHubCatalogEntry[]>([]);
  const [sourceHubRecords, setSourceHubRecords] = useState<SourceHubRecord[]>([]);
  const [activeHubSource, setActiveHubSource] = useState<SourceHubSourceKey>("pubmed");
  const [sourceHubSearchText, setSourceHubSearchText] = useState("");
  const [sourceHubSyncQuery, setSourceHubSyncQuery] = useState("diabetes type 2");
  const [sourceHubSyncLimit, setSourceHubSyncLimit] = useState("12");
  const [isLoadingSourceHubRecords, setIsLoadingSourceHubRecords] = useState(true);
  const [isSyncingSourceHub, setIsSyncingSourceHub] = useState(false);

  const activeSource = useMemo(
    () => sources.find((source) => source.id === activeSourceId) ?? null,
    [sources, activeSourceId]
  );

  const loadSources = useCallback(async () => {
    setIsLoadingSources(true);
    setError("");
    try {
      const items = await listKnowledgeSources();
      setSources(items);
      setActiveSourceId((current) => {
        if (!items.length) return null;
        if (current && items.some((source) => source.id === current)) return current;
        return items[0].id;
      });
      if (!items.length) setDocuments([]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải knowledge sources.");
    } finally {
      setIsLoadingSources(false);
    }
  }, []);

  const loadDocuments = async (sourceId: number) => {
    setIsLoadingDocs(true);
    setError("");
    try {
      const items = await listKnowledgeSourceDocuments(sourceId);
      setDocuments(items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tải tài liệu của source.");
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  useEffect(() => {
    if (!activeSourceId) return;
    void loadDocuments(activeSourceId);
  }, [activeSourceId]);

  const onCreateSource = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newSourceName.trim();
    if (!name || isCreatingSource) return;

    setIsCreatingSource(true);
    setError("");
    setMessage("");
    try {
      const source = await createKnowledgeSource(name);
      setSources((prev) => [source, ...prev]);
      setActiveSourceId(source.id);
      setNewSourceName("");
      setMessage("Đã tạo knowledge source mới.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể tạo source.");
    } finally {
      setIsCreatingSource(false);
    }
  };

  const onUploadFile = async (file: File) => {
    if (!activeSourceId) return;
    setIsUploading(true);
    setError("");
    setMessage("");
    try {
      await uploadFileToKnowledgeSource(activeSourceId, file);
      await loadDocuments(activeSourceId);
      await loadSources();
      setMessage("Upload tài liệu thành công.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể upload file vào source.");
    } finally {
      setIsUploading(false);
    }
  };

  const onToggleDocument = async (document: KnowledgeSourceDocument) => {
    setError("");
    try {
      const updated = await setKnowledgeDocumentStatus(document.id, !document.is_active);
      setDocuments((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không thể cập nhật trạng thái document.");
    }
  };

  const loadSourceHubCatalog = useCallback(async () => {
    try {
      const items = await listSourceHubCatalog();
      setSourceHubCatalog(items);
      if (items.length) {
        setActiveHubSource((current) => (items.some((item) => item.key === current) ? current : items[0].key));
      }
    } catch (cause) {
      setSourceHubError(cause instanceof Error ? cause.message : "Không thể tải Source Hub catalog.");
    }
  }, []);

  const loadSourceHubRecords = useCallback(async (query?: string) => {
    setIsLoadingSourceHubRecords(true);
    setSourceHubError("");
    try {
      const items = await listSourceHubRecords({
        source: "all",
        query: query?.trim() || undefined,
        limit: 60
      });
      setSourceHubRecords(items);
    } catch (cause) {
      setSourceHubError(cause instanceof Error ? cause.message : "Không thể tải Source Hub records.");
    } finally {
      setIsLoadingSourceHubRecords(false);
    }
  }, []);

  useEffect(() => {
    const initialize = async () => {
      await loadSourceHubCatalog();
      await loadSourceHubRecords();
    };
    void initialize();
  }, [loadSourceHubCatalog, loadSourceHubRecords]);

  const onSyncSourceHub = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const query = sourceHubSyncQuery.trim();
    if (!query) {
      setSourceHubError("Vui lòng nhập query đồng bộ Source Hub.");
      return;
    }

    const parsedLimit = Number(sourceHubSyncLimit);
    const safeLimit = Number.isFinite(parsedLimit) ? Math.max(3, Math.min(500, Math.trunc(parsedLimit))) : 12;

    setIsSyncingSourceHub(true);
    setSourceHubError("");
    setSourceHubMessage("");
    try {
      const result = await syncSourceHub({
        source: activeHubSource,
        query,
        limit: safeLimit
      });
      await loadSourceHubRecords(sourceHubSearchText);
      setSourceHubMessage(
        `Sync ${SOURCE_LABELS[result.source]}: fetched ${result.fetched}, stored ${result.stored}.`
      );
      if (result.warnings.length) {
        setSourceHubMessage((prev) => `${prev} Cảnh báo: ${result.warnings.join(" | ")}`);
      }
    } catch (cause) {
      setSourceHubError(cause instanceof Error ? cause.message : "Không thể đồng bộ Source Hub.");
    } finally {
      setIsSyncingSourceHub(false);
    }
  };

  const onFilterSourceHub = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadSourceHubRecords(sourceHubSearchText);
  };

  const totalDocuments = useMemo(
    () => sources.reduce((sum, source) => sum + Math.max(0, source.documents_count), 0),
    [sources]
  );

  const activeSyncStreams = useMemo(
    () => sources.filter((source) => source.is_active).length,
    [sources]
  );

  const activeSourceTokenTotal = useMemo(
    () => documents.reduce((sum, document) => sum + Math.max(0, document.token_count), 0),
    [documents]
  );

  const activeSourceCoverage = useMemo(() => {
    if (documents.length === 0) return 0;
    const activeDocuments = documents.filter((document) => document.is_active).length;
    return Math.round((activeDocuments / documents.length) * 1000) / 10;
  }, [documents]);

  const knowledgePriorityRows = useMemo(() => {
    const maxDocumentCount = Math.max(1, ...sources.map((source) => source.documents_count));
    return sources.slice(0, 6).map((source) => ({
      ...source,
      weightPercent: Math.round((source.documents_count / maxDocumentCount) * 100)
    }));
  }, [sources]);

  const ragPriorityRows = useMemo(() => {
    return (config?.rag_sources ?? []).slice(0, 10);
  }, [config?.rag_sources]);

  return (
    <AdminShell
      activeTab="knowledge-sources"
      title="Knowledge Intelligence Hub"
      description="Global clinical connectivity và kiểm soát knowledge assets theo thời gian thực."
    >
      <div className="space-y-6">
        <section className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-3xl font-black tracking-tight text-[#003461] dark:text-cyan-300">Knowledge Intelligence Hub</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
              Global Clinical Connectivity &amp; Knowledge Priority Control
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Total Knowledge Tokens</p>
              <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{formatCompactNumber(activeSourceTokenTotal)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Active Sync Streams</p>
              <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{activeSyncStreams}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Query Coverage</p>
              <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{activeSourceCoverage}%</p>
            </div>
          </div>
        </section>

        <section className="relative h-[420px] overflow-hidden rounded-2xl border border-slate-200 bg-[#001c38] shadow-2xl dark:border-slate-700">
          <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:40px_40px] opacity-30" />
          <div className="absolute inset-0 bg-gradient-to-b from-cyan-400/15 via-transparent to-cyan-500/25" />

          <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1000 520" aria-hidden="true">
            <path d="M220 130 L500 260" fill="none" stroke="rgba(147,239,238,0.8)" strokeWidth="1" strokeDasharray="8 16" />
            <path d="M780 130 L500 260" fill="none" stroke="rgba(147,239,238,0.8)" strokeWidth="1" strokeDasharray="8 16" />
            <path d="M220 390 L500 260" fill="none" stroke="rgba(147,239,238,0.8)" strokeWidth="1" strokeDasharray="8 16" />
            <path d="M780 390 L500 260" fill="none" stroke="rgba(147,239,238,0.8)" strokeWidth="1" strokeDasharray="8 16" />
            <circle cx="500" cy="260" r="58" fill="none" stroke="rgba(147,239,238,0.7)" />
            <circle cx="500" cy="260" r="38" fill="rgba(0,52,97,0.75)" stroke="rgba(147,239,238,0.9)" />
            <text x="500" y="265" fill="#93efee" textAnchor="middle" fontSize="11" fontWeight="700">
              RAG CORE
            </text>
          </svg>

          <div className="absolute left-[22%] top-[24%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/40 bg-slate-900/60 px-4 py-3 text-center text-xs font-semibold text-cyan-100 backdrop-blur-sm">
            PubMed
          </div>
          <div className="absolute right-[22%] top-[24%] translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/40 bg-slate-900/60 px-4 py-3 text-center text-xs font-semibold text-cyan-100 backdrop-blur-sm">
            WHO
          </div>
          <div className="absolute bottom-[24%] left-[22%] -translate-x-1/2 translate-y-1/2 rounded-full border border-cyan-300/40 bg-slate-900/60 px-4 py-3 text-center text-xs font-semibold text-cyan-100 backdrop-blur-sm">
            ClinicalTrials
          </div>
          <div className="absolute bottom-[24%] right-[22%] translate-x-1/2 translate-y-1/2 rounded-full border border-cyan-300/40 bg-slate-900/60 px-4 py-3 text-center text-xs font-semibold text-cyan-100 backdrop-blur-sm">
            openFDA
          </div>

          <div className="absolute left-4 top-4 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-100">
            Neural Connectivity Map // Live
          </div>
          <button
            type="button"
            className="absolute bottom-4 right-4 rounded-full border border-white/20 bg-white/10 px-4 py-2 text-[10px] font-bold uppercase tracking-[0.16em] text-white transition hover:bg-white/20"
          >
            Adjust Simulation Depth
          </button>
        </section>

        {error ? (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
            {error}
          </p>
        ) : null}
        {message ? (
          <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
            {message}
          </p>
        ) : null}

        <div className="grid grid-cols-12 gap-6">
          <section className="col-span-12 space-y-4 lg:col-span-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-[#003461] dark:text-cyan-300">Source Priority Hub</h3>
              <button
                type="button"
                onClick={() => void loadSources()}
                className="text-xs font-semibold uppercase tracking-[0.12em] text-[#003461] hover:underline dark:text-cyan-300"
              >
                Refresh
              </button>
            </div>

            <form onSubmit={onCreateSource} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Create source</label>
              <div className="mt-2 flex gap-2">
                <input
                  value={newSourceName}
                  onChange={(event) => setNewSourceName(event.target.value)}
                  placeholder="Tên source mới"
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-sky-200 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
                <button
                  type="submit"
                  disabled={isCreatingSource || !newSourceName.trim()}
                  className="rounded-lg bg-[#003461] px-3 py-2 text-sm font-semibold text-white transition hover:bg-[#004b87] disabled:opacity-60"
                >
                  +
                </button>
              </div>
            </form>

            <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">RAG Source Priority</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void reloadRag()}
                    className="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Reload
                  </button>
                  <button
                    type="button"
                    disabled={!isDirtyRag || isSavingRag || isLoadingRag || !config}
                    onClick={() => void saveRag()}
                    className="rounded-md bg-[#003461] px-2 py-1 text-[11px] font-semibold text-white transition hover:bg-[#004b87] disabled:opacity-60"
                  >
                    {isSavingRag ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              {ragError ? (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
                  {ragError}
                </p>
              ) : null}
              {ragMessage ? (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
                  {ragMessage}
                </p>
              ) : null}

              {isLoadingRag ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">Đang tải RAG sources...</p>
              ) : ragPriorityRows.length ? (
                ragPriorityRows.map((source) => (
                  <div key={source.id} className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-[#003461] dark:text-cyan-300">{source.name}</p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">id: {source.id}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSourceEnabled(source.id, !source.enabled)}
                        className={[
                          "rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide",
                          source.enabled
                            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                            : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                        ].join(" ")}
                      >
                        {source.enabled ? "Enabled" : "Disabled"}
                      </button>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Priority</span>
                        <input
                          type="range"
                          min={1}
                          max={100}
                          value={source.priority}
                          onChange={(event) => setSourcePriority(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[#003461] dark:bg-slate-700"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[#003461] dark:text-cyan-300">{source.priority}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Weight</span>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={source.weight}
                          onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[#003461] dark:bg-slate-700"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[#003461] dark:text-cyan-300">{source.weight.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có RAG source.</p>
              )}

              <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-700">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Knowledge Source Focus</p>
                {isLoadingSources ? (
                  <p className="text-sm text-slate-500 dark:text-slate-400">Đang tải nguồn tri thức...</p>
                ) : knowledgePriorityRows.length ? (
                  knowledgePriorityRows.map((source) => {
                    const active = source.id === activeSourceId;
                    return (
                      <button
                        key={source.id}
                        type="button"
                      onClick={() => setActiveSourceId(source.id)}
                      className={[
                        "w-full rounded-xl border bg-white p-4 text-left shadow-sm transition dark:bg-slate-900",
                        active
                          ? "border-sky-300 ring-2 ring-sky-200 dark:border-sky-600 dark:ring-sky-900/50"
                          : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"
                      ].join(" ")}
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-[#003461] dark:text-cyan-300">{source.name}</p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">{source.documents_count} tài liệu</p>
                        </div>
                        <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300">
                          {source.is_active ? "Active" : "Paused"}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={source.weightPercent}
                          readOnly
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[#003461] dark:bg-slate-700"
                        />
                        <span className="w-10 text-right text-xs font-mono font-bold text-[#003461] dark:text-cyan-300">
                          {source.weightPercent}%
                        </span>
                      </div>
                    </button>
                  );
                })
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có source nào.</p>
              )}
            </div>
            </div>
          </section>

          <section className="col-span-12 space-y-4 lg:col-span-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-[#003461] dark:text-cyan-300">Knowledge Assets</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {activeSource ? `Source: ${activeSource.name}` : "Chưa chọn source"}
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-[#003461] px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-white transition hover:bg-[#004b87]">
                {isUploading ? "Uploading..." : "Upload File"}
                <input
                  type="file"
                  className="hidden"
                  disabled={!activeSource || isUploading}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.currentTarget.value = "";
                    if (file) {
                      void onUploadFile(file);
                    }
                  }}
                />
              </label>
            </div>

            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-lg shadow-slate-200/60 dark:border-slate-700 dark:bg-slate-900 dark:shadow-none">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    <th className="px-4 py-3">Document Name</th>
                    <th className="px-4 py-3 text-right">Size</th>
                    <th className="px-4 py-3 text-right">Tokens</th>
                    <th className="px-4 py-3 text-center">Status</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoadingDocs ? (
                    <tr>
                      <td className="px-4 py-4 text-slate-500 dark:text-slate-400" colSpan={5}>
                        Đang tải tài liệu...
                      </td>
                    </tr>
                  ) : documents.length ? (
                    documents.map((document) => (
                      <tr key={document.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60 dark:border-slate-800 dark:hover:bg-slate-800/40">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[#003461] dark:text-cyan-300">{document.filename}</p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400">ID: {document.id}</p>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-200">{formatSize(document.size)}</td>
                        <td className="px-4 py-3 text-right text-slate-700 dark:text-slate-200">
                          {new Intl.NumberFormat("en").format(document.token_count)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={[
                              "inline-flex items-center rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em]",
                              document.is_active
                                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                                : "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            ].join(" ")}
                          >
                            {document.is_active ? "Ready" : "Paused"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => onToggleDocument(document)}
                            className="rounded-md border border-slate-300 px-2 py-1 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                          >
                            {document.is_active ? "Disable" : "Enable"}
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-4 text-slate-500 dark:text-slate-400" colSpan={5}>
                        Chưa có document trong source này.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Sources</p>
                <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{sources.length}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Documents</p>
                <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{totalDocuments}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Active Docs</p>
                <p className="mt-1 text-xl font-black text-[#003461] dark:text-cyan-300">{documents.filter((doc) => doc.is_active).length}</p>
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-[#003461] dark:text-cyan-300">Source Hub Federation</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Đồng bộ dữ liệu từ PubMed, RxNorm, openFDA, DAVIDrug và các nguồn chuẩn khác.
              </p>
            </div>
            <form onSubmit={onFilterSourceHub} className="flex items-center gap-2">
              <input
                value={sourceHubSearchText}
                onChange={(event) => setSourceHubSearchText(event.target.value)}
                placeholder="Lọc theo query hoặc title..."
                className="min-h-[42px] w-72 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
              <button
                type="submit"
                className="min-h-[42px] rounded-xl border border-slate-300 bg-slate-50 px-4 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100"
              >
                Lọc
              </button>
            </form>
          </div>

          <form onSubmit={onSyncSourceHub} className="mb-4 grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/70 md:grid-cols-4">
            <label className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Source</span>
              <select
                value={activeHubSource}
                onChange={(event) => setActiveHubSource(event.target.value as SourceHubSourceKey)}
                className="min-h-[40px] w-full rounded-lg border border-slate-300 bg-white px-2 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              >
                {sourceHubCatalog.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Query</span>
              <input
                value={sourceHubSyncQuery}
                onChange={(event) => setSourceHubSyncQuery(event.target.value)}
                className="min-h-[40px] w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Limit</span>
              <input
                value={sourceHubSyncLimit}
                onChange={(event) => setSourceHubSyncLimit(event.target.value)}
                className="min-h-[40px] w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
              />
            </label>
            <div className="md:col-span-4">
              <button
                type="submit"
                disabled={isSyncingSourceHub}
                className="min-h-[42px] rounded-xl bg-[#003461] px-4 text-sm font-semibold text-white transition hover:bg-[#004b87] disabled:opacity-60"
              >
                {isSyncingSourceHub ? "Đang sync..." : "Sync Source Hub"}
              </button>
            </div>
          </form>

          {sourceHubError ? (
            <p className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/60 dark:text-red-300">
              {sourceHubError}
            </p>
          ) : null}
          {sourceHubMessage ? (
            <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
              {sourceHubMessage}
            </p>
          ) : null}

          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Query</th>
                  <th className="px-3 py-2">Published</th>
                  <th className="px-3 py-2">Synced</th>
                </tr>
              </thead>
              <tbody>
                {isLoadingSourceHubRecords ? (
                  <tr>
                    <td className="px-3 py-3 text-slate-500 dark:text-slate-400" colSpan={5}>
                      Đang tải Source Hub records...
                    </td>
                  </tr>
                ) : sourceHubRecords.length ? (
                  sourceHubRecords.map((record) => (
                    <tr key={record.id} className="border-b border-slate-100 align-top last:border-0 dark:border-slate-800">
                      <td className="px-3 py-2">
                        <span className="rounded-full border border-slate-300 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
                          {SOURCE_LABELS[record.source]}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-slate-800 dark:text-slate-100">{record.title}</p>
                        {record.snippet ? (
                          <p className="mt-1 line-clamp-2 text-xs text-slate-500 dark:text-slate-300">{record.snippet}</p>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{record.query || "-"}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{formatDate(record.published_at)}</td>
                      <td className="px-3 py-2 text-slate-700 dark:text-slate-200">{formatDate(record.synced_at)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3 text-slate-500 dark:text-slate-400" colSpan={5}>
                      Chưa có dữ liệu crawl.
                    </td>
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
