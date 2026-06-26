"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import { PanelCard } from "@/components/admin/analytics-primitives";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import api from "@/lib/http-client";
import { sanitizeUpstreamError } from "@/lib/user-facing-text";
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

// ---------------------------------------------------------------------------
// RAG source registry (Requirements 13.2, 15.3)
//
// Additive surface over the persistent-pipeline `kb_source_registry`. It reads
// the registry through the admin RBAC proxy (`GET /admin/rag/sources`) and lets
// an admin enable/disable a source or adjust its authority tier
// (`PATCH /admin/rag/sources/{id}`). The license_code/attribution columns make
// the UMLS/SNOMED/RxNorm attribution obligations (Req 15.3) visible in the UI.
// It reuses the shared axios client + sanitizeUpstreamError + AsyncSection +
// design tokens used by the rag-ingestion page so both surfaces stay consistent.
// ---------------------------------------------------------------------------

/** Mirrors `SourceInfo` from `admin_rag.py`; license_code/attribution flow
 *  through the extra="allow" passthrough on the proxy model. */
type RagRegistrySource = {
  id: number | null;
  source_key: string;
  display_name: string;
  trust_tier: number | null;
  enabled: boolean;
  weight: number | null;
  fetch_mode: string;
  license_code?: string;
  attribution?: string;
  last_watermark?: string;
  last_run_at?: string | null;
  // Fail-soft markers the proxy may attach when services/ml is unavailable.
  ml_available?: boolean;
  fallback?: boolean;
};

type RagSourcesListResponse = {
  sources: RagRegistrySource[];
  ml_available?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
};

/** Only the explicitly-changed knobs are sent; the backend accepts any of
 *  enabled / trust_tier (1..4) / weight (>= 0). */
type RagSourcePatch = {
  enabled?: boolean;
  trust_tier?: number;
  weight?: number;
};

const RAG_TRUST_TIER_OPTIONS = [1, 2, 3, 4] as const;

/** Authority tier → Vietnamese label (1 = cao nhất). */
function ragTrustTierLabel(tier: number | null | undefined): string {
  switch (tier) {
    case 1:
      return "Bậc 1 · Cơ quan quản lý / nhãn thuốc";
    case 2:
      return "Bậc 2 · Hướng dẫn lâm sàng";
    case 3:
      return "Bậc 3 · Tài liệu bình duyệt";
    case 4:
      return "Bậc 4 · Nguồn bổ sung";
    default:
      return "Chưa phân bậc";
  }
}

function ragFetchModeLabel(mode: string): string {
  const key = (mode ?? "").trim().toLowerCase();
  if (key === "api") return "API";
  if (key === "crawl") return "Thu thập web";
  return mode || "--";
}

async function fetchRagRegistrySources(): Promise<RagSourcesListResponse> {
  const response = await api.get<RagSourcesListResponse>("/admin/rag/sources");
  return response.data;
}

async function patchRagRegistrySource(
  sourceId: number,
  patch: RagSourcePatch
): Promise<RagRegistrySource> {
  const response = await api.patch<RagRegistrySource>(`/admin/rag/sources/${sourceId}`, patch);
  return response.data;
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

  // RAG source registry (Req 13.2, 15.3) — additive, independent of the
  // legacy control-tower/source-hub state above.
  const [ragRegistry, setRagRegistry] = useState<RagRegistrySource[] | null>(null);
  const [ragRegistryLoading, setRagRegistryLoading] = useState(true);
  const [ragRegistryError, setRagRegistryError] = useState("");
  const [ragRegistryDegraded, setRagRegistryDegraded] = useState(false);
  const [ragUpdateError, setRagUpdateError] = useState("");
  const [ragUpdateNotice, setRagUpdateNotice] = useState("");
  const [ragUpdatingId, setRagUpdatingId] = useState<number | null>(null);

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
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể tải knowledge sources."
        )
      );
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
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể tải tài liệu của source."
        )
      );
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    void loadSources();
  }, [loadSources]);

  // Emit a single named product event when the Knowledge Sources surface is
  // opened (Req 9.1). No PII — only the coarse Admin view label.
  useEffect(() => {
    trackAdminSurfaceViewed({ view: "knowledge_sources" });
  }, []);

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
      setError(
        sanitizeUpstreamError(cause instanceof Error ? cause.message : "Không thể tạo source.")
      );
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
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể upload file vào source."
        )
      );
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
      setError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể cập nhật trạng thái document."
        )
      );
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
      setSourceHubError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể tải federated catalog."
        )
      );
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
      setSourceHubError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể tải federated records."
        )
      );
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
      setSourceHubError("Vui lòng nhập query đồng bộ federation.");
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
      setSourceHubError(
        sanitizeUpstreamError(
          cause instanceof Error ? cause.message : "Không thể đồng bộ federation."
        )
      );
    } finally {
      setIsSyncingSourceHub(false);
    }
  };

  const onFilterSourceHub = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await loadSourceHubRecords(sourceHubSearchText);
  };

  const loadRagRegistry = useCallback(async () => {
    setRagRegistryLoading(true);
    setRagRegistryError("");
    try {
      const result = await fetchRagRegistrySources();
      setRagRegistry(Array.isArray(result.sources) ? result.sources : []);
      setRagRegistryDegraded(result.fallback === true || result.ml_available === false);
    } catch (cause) {
      setRagRegistry(null);
      setRagRegistryError(
        sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause))
      );
    } finally {
      setRagRegistryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRagRegistry();
  }, [loadRagRegistry]);

  const onUpdateRagSource = useCallback(
    async (source: RagRegistrySource, patch: RagSourcePatch) => {
      if (source.id == null || ragUpdatingId != null) return;
      const targetId = source.id;
      setRagUpdatingId(targetId);
      setRagUpdateError("");
      setRagUpdateNotice("");
      try {
        const updated = await patchRagRegistrySource(targetId, patch);
        if (updated.fallback === true || updated.ml_available === false) {
          setRagUpdateError(
            "Dịch vụ xử lý tạm thời không khả dụng — thay đổi chưa được áp dụng. Vui lòng thử lại sau ít phút."
          );
          return;
        }
        setRagRegistry((prev) =>
          prev
            ? prev.map((item) => (item.id === targetId ? { ...item, ...updated } : item))
            : prev
        );
        setRagUpdateNotice(
          `Đã cập nhật nguồn ${updated.display_name || updated.source_key || source.source_key}.`
        );
      } catch (cause) {
        setRagUpdateError(
          sanitizeUpstreamError(cause instanceof Error ? cause.message : String(cause))
        );
      } finally {
        setRagUpdatingId(null);
      }
    },
    [ragUpdatingId]
  );

  const ragRegistryState = useMemo<AsyncState<RagRegistrySource[]>>(() => {
    if (ragRegistryLoading) return { kind: "loading" };
    if (ragRegistryError) return { kind: "error", message: ragRegistryError };
    if (!ragRegistry || ragRegistry.length === 0) return { kind: "empty" };
    return { kind: "populated", data: ragRegistry };
  }, [ragRegistryLoading, ragRegistryError, ragRegistry]);

  const totalDocuments = useMemo(
    () => sources.reduce((sum, source) => sum + Math.max(0, source.documents_count), 0),
    [sources]
  );

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

  const activeRagConnectors = useMemo(
    () => (config?.rag_sources ?? []).filter((source) => source.enabled).length,
    [config?.rag_sources]
  );

  const activeDocumentCount = useMemo(
    () => documents.filter((document) => document.is_active).length,
    [documents]
  );

  const sourceRecordDistribution = useMemo(() => {
    const counter = new Map<SourceHubSourceKey, number>();
    for (const record of sourceHubRecords) {
      counter.set(record.source, (counter.get(record.source) ?? 0) + 1);
    }
    return Array.from(counter.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6);
  }, [sourceHubRecords]);

  const maxSourceRecordCount = useMemo(
    () => Math.max(1, ...sourceRecordDistribution.map(([, count]) => count)),
    [sourceRecordDistribution]
  );

  return (
    <AdminShell
      activeTab="knowledge-sources"
      title="Nguồn tri thức"
      description="Kho tri thức hợp nhất và ưu tiên nguồn truy xuất."
    >
      <div className="space-y-6">
        <section className="grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
          <article className="rounded-2xl border border-slate-200 bg-[#001c38] p-4 shadow-lg dark:border-slate-700">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-bold uppercase tracking-[0.16em] text-cyan-100">Sơ đồ kết nối nguồn tri thức</h3>
              <span className="rounded-full border border-cyan-300/40 bg-cyan-300/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cyan-100">
                Live
              </span>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-[1fr_0.9fr]">
              <div className="relative overflow-hidden rounded-xl border border-cyan-300/20 bg-slate-900/45 p-4">
                <svg className="h-44 w-full" viewBox="0 0 560 210" aria-hidden="true">
                  <path d="M90 36 L280 106" stroke="rgba(147,239,238,0.65)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M468 36 L280 106" stroke="rgba(147,239,238,0.65)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M90 178 L280 106" stroke="rgba(147,239,238,0.65)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M468 178 L280 106" stroke="rgba(147,239,238,0.65)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <circle cx="280" cy="106" r="34" fill="rgba(0,75,135,0.85)" stroke="rgba(147,239,238,0.85)" />
                  <text x="280" y="112" textAnchor="middle" fill="#93efee" fontSize="11" fontWeight="700">
                    HUB CORE
                  </text>
                  <circle cx="90" cy="36" r="14" fill="rgba(147,239,238,0.24)" />
                  <circle cx="468" cy="36" r="14" fill="rgba(147,239,238,0.24)" />
                  <circle cx="90" cy="178" r="14" fill="rgba(147,239,238,0.24)" />
                  <circle cx="468" cy="178" r="14" fill="rgba(147,239,238,0.24)" />
                  <text x="90" y="39" textAnchor="middle" fill="#d3e4ff" fontSize="9">RAG</text>
                  <text x="468" y="39" textAnchor="middle" fill="#d3e4ff" fontSize="9">Docs</text>
                  <text x="90" y="181" textAnchor="middle" fill="#d3e4ff" fontSize="9">Med DB</text>
                  <text x="468" y="181" textAnchor="middle" fill="#d3e4ff" fontSize="9">Trials</text>
                </svg>
              </div>
              <div className="space-y-2.5 rounded-xl border border-cyan-300/20 bg-slate-900/45 p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-cyan-100/80">Số bản ghi theo nguồn</p>
                {sourceRecordDistribution.length ? (
                  sourceRecordDistribution.map(([source, count]) => (
                    <div key={source}>
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs text-cyan-100">
                        <span className="truncate">{SOURCE_LABELS[source]}</span>
                        <span className="font-mono">{count}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-blue-400"
                          style={{ width: `${Math.max(6, Math.round((count / maxSourceRecordCount) * 100))}%` }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-slate-300">Chưa có record sync từ backend.</p>
                )}
              </div>
            </div>
          </article>

          <article className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Active Connectors</p>
              <p className="mt-1 text-2xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{activeRagConnectors}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Retrieval connectors bật</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Knowledge Sources</p>
              <p className="mt-1 text-2xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{sources.length}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Kho tri thức đã tạo</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Federated Records</p>
              <p className="mt-1 text-2xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{sourceHubRecords.length}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Records từ nguồn y khoa</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Active Docs</p>
              <p className="mt-1 text-2xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{activeDocumentCount}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">Trong source đang chọn</p>
            </div>
          </article>
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
              <h3 className="text-lg font-bold text-[color:var(--text-brand)] dark:text-cyan-300">Điều phối nguồn tri thức</h3>
              <button
                type="button"
                onClick={() => void loadSources()}
                className="text-xs font-semibold uppercase tracking-[0.12em] text-[color:var(--text-brand)] hover:underline dark:text-cyan-300"
              >
                Làm mới
              </button>
            </div>

            <form onSubmit={onCreateSource} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
              <label className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Tạo nguồn tri thức</label>
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
                  className="rounded-lg bg-[color:var(--brand-700)] px-3 py-2 text-sm font-semibold text-white transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
                >
                  +
                </button>
              </div>
            </form>

            <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Ưu tiên connector truy xuất</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void reloadRag()}
                    className="rounded-md border border-slate-300 px-2 py-1 text-[11px] font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
                  >
                    Tải lại
                  </button>
                  <button
                    type="button"
                    disabled={!isDirtyRag || isSavingRag || isLoadingRag || !config}
                    onClick={() => void saveRag()}
                    className="rounded-md bg-[color:var(--brand-700)] px-2 py-1 text-[11px] font-semibold text-white transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
                  >
                    {isSavingRag ? "Đang lưu..." : "Lưu"}
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
                <p className="text-sm text-slate-500 dark:text-slate-400">Đang tải connectors...</p>
              ) : ragPriorityRows.length ? (
                ragPriorityRows.map((source) => (
                  <div key={source.id} className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition dark:border-slate-700 dark:bg-slate-900">
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-[color:var(--text-brand)] dark:text-cyan-300">{source.name}</p>
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
                        {source.enabled ? "Bật" : "Tắt"}
                      </button>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Ưu tiên</span>
                        <input
                          type="range"
                          min={1}
                          max={100}
                          value={source.priority}
                          onChange={(event) => setSourcePriority(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[color:var(--brand-700)] dark:bg-slate-700"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[color:var(--text-brand)] dark:text-cyan-300">{source.priority}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-slate-500">Trọng số</span>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={source.weight}
                          onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[color:var(--brand-700)] dark:bg-slate-700"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[color:var(--text-brand)] dark:text-cyan-300">{source.weight.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có connector nào.</p>
              )}

              <div className="mt-3 border-t border-slate-200 pt-3 dark:border-slate-700">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">Phân bổ nguồn tri thức</p>
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
                          <p className="text-sm font-semibold text-[color:var(--text-brand)] dark:text-cyan-300">{source.name}</p>
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
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-[color:var(--brand-700)] dark:bg-slate-700"
                        />
                        <span className="w-10 text-right text-xs font-mono font-bold text-[color:var(--text-brand)] dark:text-cyan-300">
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
                <h3 className="text-lg font-bold text-[color:var(--text-brand)] dark:text-cyan-300">Knowledge Assets</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {activeSource ? `Source: ${activeSource.name}` : "Chưa chọn source"}
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-[color:var(--brand-700)] px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-white transition hover:bg-[color:var(--brand-600)]">
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
                          <p className="font-semibold text-[color:var(--text-brand)] dark:text-cyan-300">{document.filename}</p>
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
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{sources.length}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Documents</p>
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{totalDocuments}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500">Active Docs</p>
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)] dark:text-cyan-300">{documents.filter((doc) => doc.is_active).length}</p>
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900/85">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-[color:var(--text-brand)] dark:text-cyan-300">Nguồn lâm sàng liên thông</h3>
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
                className="min-h-[42px] rounded-xl bg-[color:var(--brand-700)] px-4 text-sm font-semibold text-white transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
              >
                {isSyncingSourceHub ? "Đang đồng bộ..." : "Đồng bộ nguồn"}
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
                      Đang tải records...
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

        {/* RAG source registry (Requirements 13.2, 15.3) — additive section */}
        <PanelCard
          title="Sổ đăng ký nguồn RAG"
          description="Quản lý kho tri thức RAG bền vững: bậc tin cậy, giấy phép, ghi nguồn và trạng thái kích hoạt của từng nguồn."
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-[var(--text-muted)]">
              Bật/tắt nguồn và điều chỉnh bậc tin cậy. Cột Giấy phép và Ghi nguồn hiển thị nghĩa vụ
              ghi nhận bản quyền (UMLS/SNOMED/RxNorm).
            </p>
            <button
              type="button"
              onClick={() => void loadRagRegistry()}
              disabled={ragRegistryLoading || ragUpdatingId != null}
              className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:opacity-60"
            >
              {ragRegistryLoading ? "Đang làm mới..." : "Làm mới"}
            </button>
          </div>

          {ragRegistryDegraded ? (
            <div
              role="alert"
              className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
            >
              Dịch vụ xử lý tạm thời không khả dụng — danh sách nguồn RAG có thể chưa đầy đủ. Vui
              lòng thử lại sau ít phút.
            </div>
          ) : null}

          {ragUpdateError ? (
            <div
              role="alert"
              className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[color:var(--status-danger-text)]"
            >
              {ragUpdateError}
            </div>
          ) : null}

          {ragUpdateNotice ? (
            <div
              role="status"
              className="mb-4 rounded-[var(--radius-md)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm text-[color:var(--status-ok-text)]"
            >
              {ragUpdateNotice}
            </div>
          ) : null}

          <AsyncSection<RagRegistrySource[]>
            state={ragRegistryState}
            loadingLabel="Đang tải sổ đăng ký nguồn RAG..."
            emptyTitle="Chưa có nguồn RAG"
            emptyDescription="Chưa có nguồn nào được đăng ký trong kho tri thức RAG."
          >
            {(rows) => (
              <RagSourceRegistryTable
                sources={rows}
                updatingId={ragUpdatingId}
                onToggleEnabled={(source) =>
                  void onUpdateRagSource(source, { enabled: !source.enabled })
                }
                onChangeTrustTier={(source, tier) =>
                  void onUpdateRagSource(source, { trust_tier: tier })
                }
              />
            )}
          </AsyncSection>
        </PanelCard>
      </div>
    </AdminShell>
  );
}

// ---------------------------------------------------------------------------
// RAG source registry table (local, single-file) — Requirements 13.2, 15.3
//
// Renders one row per kb_source_registry entry with a trust-tier <select> and
// an enable/disable toggle. Both controls drive PATCH /admin/rag/sources/{id}
// via the parent's `onChangeTrustTier` / `onToggleEnabled` callbacks. Styling
// uses the shared design tokens (no hardcoded colors) for consistency with the
// rag-ingestion surface. All copy is Vietnamese.
// ---------------------------------------------------------------------------
function RagSourceRegistryTable({
  sources,
  updatingId,
  onToggleEnabled,
  onChangeTrustTier
}: {
  sources: RagRegistrySource[];
  updatingId: number | null;
  onToggleEnabled: (source: RagRegistrySource) => void;
  onChangeTrustTier: (source: RagRegistrySource, tier: number) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
            <th className="py-2 pr-4 font-semibold">Nguồn</th>
            <th className="py-2 pr-4 font-semibold">Bậc tin cậy</th>
            <th className="py-2 pr-4 font-semibold">Giấy phép</th>
            <th className="py-2 pr-4 font-semibold">Ghi nguồn</th>
            <th className="py-2 pr-4 font-semibold">Chế độ thu thập</th>
            <th className="py-2 pr-4 font-semibold">Trạng thái</th>
            <th className="py-2 font-semibold text-right">Hành động</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((source, index) => {
            const rowKey =
              source.source_key || (source.id != null ? String(source.id) : `rag-src-${index}`);
            const missingId = source.id == null;
            const isUpdating = updatingId != null && source.id === updatingId;
            const controlsDisabled = missingId || updatingId != null;
            return (
              <tr
                key={rowKey}
                className="border-b border-[color:var(--shell-border)] align-top last:border-0"
              >
                <td className="py-3 pr-4">
                  <p className="font-semibold text-[var(--text-primary)]">
                    {source.display_name || source.source_key}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">{source.source_key}</p>
                </td>
                <td className="py-3 pr-4">
                  <select
                    value={source.trust_tier ?? ""}
                    disabled={controlsDisabled}
                    onChange={(event) => {
                      const next = Number(event.target.value);
                      if (Number.isFinite(next) && next !== source.trust_tier) {
                        onChangeTrustTier(source, next);
                      }
                    }}
                    aria-label={`Bậc tin cậy của ${source.display_name || source.source_key}`}
                    className="min-h-[36px] rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-sm text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {source.trust_tier == null ? (
                      <option value="">Chưa phân bậc</option>
                    ) : null}
                    {RAG_TRUST_TIER_OPTIONS.map((tier) => (
                      <option key={tier} value={tier}>
                        {ragTrustTierLabel(tier)}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {source.license_code?.trim() ? source.license_code : "--"}
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {source.attribution?.trim() ? (
                    <span className="block max-w-[260px] truncate" title={source.attribution}>
                      {source.attribution}
                    </span>
                  ) : (
                    "--"
                  )}
                </td>
                <td className="py-3 pr-4 text-[var(--text-secondary)]">
                  {ragFetchModeLabel(source.fetch_mode)}
                </td>
                <td className="py-3 pr-4">
                  <span
                    className={[
                      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
                      source.enabled
                        ? "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] text-[color:var(--status-ok-text)]"
                        : "border-[color:var(--status-neutral-border)] bg-[var(--status-neutral-bg)] text-[color:var(--status-neutral-text)]"
                    ].join(" ")}
                  >
                    {source.enabled ? "Đang bật" : "Đã tắt"}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onToggleEnabled(source)}
                    disabled={controlsDisabled}
                    title={
                      missingId
                        ? "Thiếu định danh nguồn — không thể cập nhật"
                        : source.enabled
                          ? "Tắt nguồn này"
                          : "Bật nguồn này"
                    }
                    className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isUpdating ? (
                      <span
                        aria-hidden="true"
                        className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                      />
                    ) : null}
                    {isUpdating ? "Đang lưu..." : source.enabled ? "Tắt" : "Bật"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
