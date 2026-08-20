"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import AdminShell from "@/components/admin/admin-shell";
import useControlTowerConfig from "@/components/admin/use-control-tower-config";
import { PanelCard } from "@/components/admin/analytics-primitives";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import { trackAdminSurfaceViewed } from "@/lib/analytics/events";
import api from "@/lib/http-client";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
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

function formatDate(value: string | undefined, language: UILanguage): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(language === "vi" ? "vi-VN" : "en-US", { hour12: false });
}

// ---------------------------------------------------------------------------
// RAG source registry (Requirements 13.2, 15.3)
//
// Additive surface over the persistent-pipeline `kb_source_registry`. It reads
// the registry through the admin RBAC proxy (`GET /admin/rag/sources`) and lets
// an admin enable/disable a source or adjust its authority tier
// (`PATCH /admin/rag/sources/{id}`). The license_code/attribution columns make
// the UMLS/SNOMED/RxNorm attribution obligations (Req 15.3) visible in the UI.
// It reuses the shared axios client + safeUserFacingError + AsyncSection +
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
  // `degraded` is the explicit marker added by the admin RAG proxy (task 3.1):
  // it is derived from `fallback`/`ml_available` so a successful ML response is
  // never flagged degraded.
  ml_available?: boolean;
  fallback?: boolean;
  degraded?: boolean;
};

type RagSourcesListResponse = {
  sources: RagRegistrySource[];
  ml_available?: boolean;
  fallback?: boolean;
  degraded?: boolean;
  fallback_reason?: string;
};

/** True when an admin RAG proxy payload signals fail-soft degradation: the
 *  explicit `degraded` marker (task 3.1) or the underlying `fallback` /
 *  `ml_available=false` fields it is derived from. Used to drive the explicit
 *  "unavailable, retry" state instead of presenting stale success. */
function isRagPayloadDegraded(payload: {
  degraded?: boolean;
  fallback?: boolean;
  ml_available?: boolean;
}): boolean {
  return payload.degraded === true || payload.fallback === true || payload.ml_available === false;
}

/** Only the explicitly-changed knobs are sent; the backend accepts any of
 *  enabled / trust_tier (1..4) / weight (>= 0). */
type RagSourcePatch = {
  enabled?: boolean;
  trust_tier?: number;
  weight?: number;
};

const RAG_TRUST_TIER_OPTIONS = [1, 2, 3, 4] as const;

/** Authority tier label; the source tier remains a backend-controlled value. */
function ragTrustTierLabel(tier: number | null | undefined, language: UILanguage): string {
  switch (tier) {
    case 1:
      return t(language, "admin.knowledgeSources.tier.one");
    case 2:
      return t(language, "admin.knowledgeSources.tier.two");
    case 3:
      return t(language, "admin.knowledgeSources.tier.three");
    case 4:
      return t(language, "admin.knowledgeSources.tier.four");
    default:
      return t(language, "admin.knowledgeSources.tier.unassigned");
  }
}

function ragFetchModeLabel(mode: string, language: UILanguage): string {
  const key = (mode ?? "").trim().toLowerCase();
  if (key === "api") return "API";
  if (key === "crawl") return t(language, "admin.knowledgeSources.fetchMode.crawl");
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
  const language = useUILanguage();
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
      setError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.loadSources")));
    } finally {
      setIsLoadingSources(false);
    }
  }, [language]);

  const loadDocuments = useCallback(
    async (sourceId: number) => {
      setIsLoadingDocs(true);
      setError("");
      try {
        const items = await listKnowledgeSourceDocuments(sourceId);
        setDocuments(items);
      } catch (cause) {
        setError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.loadDocuments")));
      } finally {
        setIsLoadingDocs(false);
      }
    },
    [language]
  );

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
  }, [activeSourceId, loadDocuments]);

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
      setMessage(t(language, "admin.knowledgeSources.notice.created"));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.create")));
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
      setMessage(t(language, "admin.knowledgeSources.notice.uploaded"));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.upload")));
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
      setError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.updateDocument")));
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
      setSourceHubError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.loadCatalog")));
    }
  }, [language]);

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
      setSourceHubError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.loadRecords")));
    } finally {
      setIsLoadingSourceHubRecords(false);
    }
  }, [language]);

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
      setSourceHubError(t(language, "admin.knowledgeSources.error.syncQueryRequired"));
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
      setSourceHubMessage(t(language, "admin.knowledgeSources.notice.synced", {
        source: SOURCE_LABELS[result.source],
        fetched: result.fetched,
        stored: result.stored
      }));
      if (result.warnings.length) {
        setSourceHubMessage((prev) => `${prev} ${t(language, "admin.knowledgeSources.notice.warning")} ${result.warnings.join(" | ")}`);
      }
    } catch (cause) {
      setSourceHubError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.sync")));
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
      setRagRegistryDegraded(isRagPayloadDegraded(result));
    } catch (cause) {
      setRagRegistry(null);
      setRagRegistryError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.loadRegistry")));
    } finally {
      setRagRegistryLoading(false);
    }
  }, [language]);

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
        if (isRagPayloadDegraded(updated)) {
          setRagRegistryDegraded(true);
          setRagUpdateError(
            t(language, "admin.knowledgeSources.registry.updateUnavailable")
          );
          return;
        }
        setRagRegistry((prev) =>
          prev
            ? prev.map((item) => (item.id === targetId ? { ...item, ...updated } : item))
            : prev
        );
        setRagUpdateNotice(
          t(language, "admin.knowledgeSources.registry.updated", { source: updated.display_name || updated.source_key || source.source_key })
        );
      } catch (cause) {
        setRagUpdateError(safeUserFacingError(cause, t(language, "admin.knowledgeSources.error.updateRegistry")));
      } finally {
        setRagUpdatingId(null);
      }
    },
    [language, ragUpdatingId]
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
      title={t(language, "admin.knowledgeSources.title")}
      description={t(language, "admin.knowledgeSources.description")}
    >
      <div className="space-y-6">
        <section className="grid gap-4 lg:grid-cols-[1.35fr_0.65fr]">
          <article className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4">
            <div className="flex items-center justify-between gap-2">
              <h3 className="text-sm font-bold uppercase tracking-[0.16em] text-[var(--text-primary)]">{t(language, "admin.knowledgeSources.connectionMap")}</h3>
              <span className="rounded-full border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--status-ok-text)]">
                {t(language, "admin.knowledgeSources.live")}
              </span>
            </div>
            <div className="mt-3 grid gap-4 md:grid-cols-[1fr_0.9fr]">
              <div className="relative overflow-hidden rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <svg className="h-44 w-full" viewBox="0 0 560 210" aria-hidden="true">
                  <path d="M90 36 L280 106" stroke="var(--shell-border-strong)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M468 36 L280 106" stroke="var(--shell-border-strong)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M90 178 L280 106" stroke="var(--shell-border-strong)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <path d="M468 178 L280 106" stroke="var(--shell-border-strong)" strokeWidth="2" strokeDasharray="6 8" fill="none" />
                  <circle cx="280" cy="106" r="34" fill="var(--brand-700)" stroke="var(--brand-primary)" />
                  <text x="280" y="112" textAnchor="middle" fill="var(--on-secondary-container)" fontSize="11" fontWeight="700">
                    HUB CORE
                  </text>
                  <circle cx="90" cy="36" r="14" fill="var(--surface-brand-soft)" />
                  <circle cx="468" cy="36" r="14" fill="var(--surface-brand-soft)" />
                  <circle cx="90" cy="178" r="14" fill="var(--surface-brand-soft)" />
                  <circle cx="468" cy="178" r="14" fill="var(--surface-brand-soft)" />
                  <text x="90" y="39" textAnchor="middle" fill="var(--text-primary)" fontSize="9">RAG</text>
                  <text x="468" y="39" textAnchor="middle" fill="var(--text-primary)" fontSize="9">Docs</text>
                  <text x="90" y="181" textAnchor="middle" fill="var(--text-primary)" fontSize="9">Med DB</text>
                  <text x="468" y="181" textAnchor="middle" fill="var(--text-primary)" fontSize="9">Trials</text>
                </svg>
              </div>
              <div className="space-y-2.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.recordsBySource")}</p>
                {sourceRecordDistribution.length ? (
                  sourceRecordDistribution.map(([source, count]) => (
                    <div key={source}>
                      <div className="mb-1 flex items-center justify-between gap-2 text-xs text-[var(--text-primary)]">
                        <span className="truncate">{SOURCE_LABELS[source]}</span>
                        <span className="font-mono">{count}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-highest)]">
                        <div
                          className="h-full rounded-full bg-[var(--brand-primary)]"
                          style={{ width: `${Math.max(6, Math.round((count / maxSourceRecordCount) * 100))}%` }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-[var(--text-secondary)]">{t(language, "admin.knowledgeSources.noSyncedRecords")}</p>
                )}
              </div>
            </div>
          </article>

          <article className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
            <div className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.activeConnectors")}</p>
              <p className="mt-1 text-2xl font-black text-[var(--text-brand)]">{activeRagConnectors}</p>
              <p className="text-xs text-[var(--text-secondary)]">{t(language, "admin.knowledgeSources.kpi.activeConnectorsHint")}</p>
            </div>
            <div className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.sources")}</p>
              <p className="mt-1 text-2xl font-black text-[var(--text-brand)]">{sources.length}</p>
              <p className="text-xs text-[var(--text-secondary)]">{t(language, "admin.knowledgeSources.kpi.sourcesHint")}</p>
            </div>
            <div className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.federatedRecords")}</p>
              <p className="mt-1 text-2xl font-black text-[var(--text-brand)]">{sourceHubRecords.length}</p>
              <p className="text-xs text-[var(--text-secondary)]">{t(language, "admin.knowledgeSources.kpi.federatedRecordsHint")}</p>
            </div>
            <div className="rounded-[14px] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.activeDocuments")}</p>
              <p className="mt-1 text-2xl font-black text-[var(--text-brand)]">{activeDocumentCount}</p>
              <p className="text-xs text-[var(--text-secondary)]">{t(language, "admin.knowledgeSources.kpi.activeDocumentsHint")}</p>
            </div>
          </article>
        </section>

        {error ? (
          <p className="rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm text-[var(--status-danger-text)]">
            {error}
          </p>
        ) : null}
        {message ? (
          <p className="rounded-xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm text-[var(--status-ok-text)]">
            {message}
          </p>
        ) : null}

        <div className="grid grid-cols-12 gap-6">
          <section className="col-span-12 space-y-4 lg:col-span-5">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-[color:var(--text-brand)]">{t(language, "admin.knowledgeSources.orchestration")}</h3>
              <button
                type="button"
                onClick={() => void loadSources()}
                className="text-xs font-semibold uppercase tracking-[0.12em] text-[color:var(--text-brand)] hover:underline"
              >
                {t(language, "admin.knowledgeSources.refresh")}
              </button>
            </div>

            <form onSubmit={onCreateSource} className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 ">
              <label className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.createLabel")}</label>
              <div className="mt-2 flex gap-2">
                <input
                  value={newSourceName}
                  onChange={(event) => setNewSourceName(event.target.value)}
                  placeholder={t(language, "admin.knowledgeSources.createPlaceholder")}
                  className="w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-500)]/30"
                />
                <button
                  type="submit"
                  disabled={isCreatingSource || !newSourceName.trim()}
                  className="rounded-lg bg-[color:var(--brand-700)] px-3 py-2 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
                >
                  +
                </button>
              </div>
            </form>

            <div className="space-y-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.priorityConnectors")}</p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void reloadRag()}
                    className="rounded-md border border-[color:var(--shell-border)] px-2 py-1 text-[11px] font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
                  >
                    {t(language, "admin.knowledgeSources.reload")}
                  </button>
                  <button
                    type="button"
                    disabled={!isDirtyRag || isSavingRag || isLoadingRag || !config}
                    onClick={() => void saveRag()}
                    className="rounded-md bg-[color:var(--brand-700)] px-2 py-1 text-[11px] font-semibold text-[var(--on-secondary-container)] transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
                  >
                    {isSavingRag ? t(language, "admin.knowledgeSources.saving") : t(language, "admin.knowledgeSources.save")}
                  </button>
                </div>
              </div>

              {ragError ? (
                <p className="rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-xs text-[var(--status-danger-text)]">
                  {ragError}
                </p>
              ) : null}
              {ragMessage ? (
                <p className="rounded-lg border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-xs text-[var(--status-ok-text)]">
                  {ragMessage}
                </p>
              ) : null}

              {isLoadingRag ? (
                <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.loadingConnectors")}</p>
              ) : ragPriorityRows.length ? (
                ragPriorityRows.map((source) => (
                  <div key={source.id} className="w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-left  transition">
                    <div className="mb-3 flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-[color:var(--text-brand)]">{source.name}</p>
                        <p className="text-[11px] text-[var(--text-muted)]">id: {source.id}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSourceEnabled(source.id, !source.enabled)}
                        className={[
                          "rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-wide",
                          source.enabled
                            ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                            : "bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                        ].join(" ")}
                      >
                        {source.enabled ? t(language, "admin.knowledgeSources.enabled") : t(language, "admin.knowledgeSources.disabled")}
                      </button>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.priority")}</span>
                        <input
                          type="range"
                          min={1}
                          max={100}
                          value={source.priority}
                          onChange={(event) => setSourcePriority(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-muted)] accent-[color:var(--brand-700)]"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[color:var(--text-brand)]">{source.priority}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="min-w-16 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.weight")}</span>
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={source.weight}
                          onChange={(event) => setSourceWeight(source.id, Number(event.target.value))}
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-muted)] accent-[color:var(--brand-700)]"
                        />
                        <span className="w-8 text-right text-xs font-mono font-bold text-[color:var(--text-brand)]">{source.weight.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.noConnectors")}</p>
              )}

              <div className="mt-3 border-t border-[color:var(--shell-border)] pt-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.sourceAllocation")}</p>
                {isLoadingSources ? (
                  <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.loadingSources")}</p>
                ) : knowledgePriorityRows.length ? (
                  knowledgePriorityRows.map((source) => {
                    const active = source.id === activeSourceId;
                    return (
                      <button
                        key={source.id}
                        type="button"
                      onClick={() => setActiveSourceId(source.id)}
                      className={[
                        "w-full rounded-xl border bg-[var(--surface-panel)] p-4 text-left  transition",
                        active
                          ? "border-[color:var(--brand-200)] ring-2 ring-[var(--brand-500)]/30"
                          : "border-[color:var(--shell-border)] hover:border-[color:var(--shell-border-strong)]"
                      ].join(" ")}
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-[color:var(--text-brand)]">{source.name}</p>
                          <p className="text-[11px] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.documentCount", { count: source.documents_count })}</p>
                        </div>
                        <span className="rounded-full bg-[var(--status-ok-bg)] px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-[var(--status-ok-text)]">
                          {source.is_active ? t(language, "admin.knowledgeSources.active") : t(language, "admin.knowledgeSources.paused")}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={source.weightPercent}
                          readOnly
                          className="h-1 w-full cursor-pointer appearance-none rounded-lg bg-[var(--surface-muted)] accent-[color:var(--brand-700)]"
                        />
                        <span className="w-10 text-right text-xs font-mono font-bold text-[color:var(--text-brand)]">
                          {source.weightPercent}%
                        </span>
                      </div>
                    </button>
                  );
                })
              ) : (
                <p className="text-sm text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.noSources")}</p>
              )}
            </div>
            </div>
          </section>

          <section className="col-span-12 space-y-4 lg:col-span-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-[color:var(--text-brand)]">{t(language, "admin.knowledgeSources.assets")}</h3>
                <p className="text-xs text-[var(--text-muted)]">
                  {activeSource ? t(language, "admin.knowledgeSources.activeSource", { source: activeSource.name }) : t(language, "admin.knowledgeSources.noSelectedSource")}
                </p>
              </div>
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-[color:var(--brand-700)] px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-[var(--on-secondary-container)] transition hover:bg-[color:var(--brand-600)]">
                {isUploading ? t(language, "admin.knowledgeSources.uploading") : t(language, "admin.knowledgeSources.uploadFile")}
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

            <div className="overflow-x-auto rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                    <th className="px-4 py-3">{t(language, "admin.knowledgeSources.table.documentName")}</th>
                    <th className="px-4 py-3 text-right">{t(language, "admin.knowledgeSources.table.size")}</th>
                    <th className="px-4 py-3 text-right">{t(language, "admin.knowledgeSources.table.tokens")}</th>
                    <th className="px-4 py-3 text-center">{t(language, "admin.knowledgeSources.table.status")}</th>
                    <th className="px-4 py-3 text-right">{t(language, "admin.knowledgeSources.table.action")}</th>
                  </tr>
                </thead>
                <tbody>
                  {isLoadingDocs ? (
                    <tr>
                      <td className="px-4 py-4 text-[var(--text-muted)]" colSpan={5}>
                        {t(language, "admin.knowledgeSources.loadingDocuments")}
                      </td>
                    </tr>
                  ) : documents.length ? (
                    documents.map((document) => (
                      <tr key={document.id} className="border-b border-[color:var(--shell-border)] last:border-0 hover:bg-[var(--surface-muted)]">
                        <td className="px-4 py-3">
                          <p className="font-semibold text-[color:var(--text-brand)]">{document.filename}</p>
                          <p className="text-[11px] text-[var(--text-muted)]">ID: {document.id}</p>
                        </td>
                        <td className="px-4 py-3 text-right text-[var(--text-secondary)]">{formatSize(document.size)}</td>
                        <td className="px-4 py-3 text-right text-[var(--text-secondary)]">
                          {new Intl.NumberFormat(language === "vi" ? "vi-VN" : "en-US").format(document.token_count)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={[
                              "inline-flex items-center rounded-full px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em]",
                              document.is_active
                                ? "bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]"
                                : "bg-[var(--surface-muted)] text-[var(--text-secondary)]"
                            ].join(" ")}
                          >
                            {document.is_active ? t(language, "admin.knowledgeSources.ready") : t(language, "admin.knowledgeSources.paused")}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            onClick={() => onToggleDocument(document)}
                            className="rounded-md border border-[color:var(--shell-border)] px-2 py-1 text-xs font-semibold text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
                          >
                            {document.is_active ? t(language, "admin.knowledgeSources.disable") : t(language, "admin.knowledgeSources.enable")}
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-4 text-[var(--text-muted)]" colSpan={5}>
                        {t(language, "admin.knowledgeSources.noDocuments")}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 ">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.sources")}</p>
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)]">{sources.length}</p>
              </div>
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 ">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.documents")}</p>
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)]">{totalDocuments}</p>
              </div>
              <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 ">
                <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.kpi.activeDocuments")}</p>
                <p className="mt-1 text-xl font-black text-[color:var(--text-brand)]">{documents.filter((doc) => doc.is_active).length}</p>
              </div>
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 ">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-[color:var(--text-brand)]">{t(language, "admin.knowledgeSources.federatedTitle")}</h3>
              <p className="text-xs text-[var(--text-muted)]">
                {t(language, "admin.knowledgeSources.federatedDescription")}
              </p>
            </div>
            <form onSubmit={onFilterSourceHub} className="flex items-center gap-2">
              <input
                value={sourceHubSearchText}
                onChange={(event) => setSourceHubSearchText(event.target.value)}
                placeholder={t(language, "admin.knowledgeSources.filterPlaceholder")}
                className="min-h-[42px] w-72 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-sm text-[var(--text-primary)]"
              />
              <button
                type="submit"
                className="min-h-[42px] rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 text-sm font-semibold text-[var(--text-secondary)]"
              >
                {t(language, "admin.knowledgeSources.filter")}
              </button>
            </form>
          </div>

          <form onSubmit={onSyncSourceHub} className="mb-4 grid gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 md:grid-cols-4">
            <label className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.source")}</span>
              <select
                value={activeHubSource}
                onChange={(event) => setActiveHubSource(event.target.value as SourceHubSourceKey)}
                className="min-h-[40px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 text-sm text-[var(--text-primary)]"
              >
                {sourceHubCatalog.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 md:col-span-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.query")}</span>
              <input
                value={sourceHubSyncQuery}
                onChange={(event) => setSourceHubSyncQuery(event.target.value)}
                className="min-h-[40px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-sm text-[var(--text-primary)]"
              />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--text-muted)]">{t(language, "admin.knowledgeSources.limit")}</span>
              <input
                value={sourceHubSyncLimit}
                onChange={(event) => setSourceHubSyncLimit(event.target.value)}
                className="min-h-[40px] w-full rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 text-sm text-[var(--text-primary)]"
              />
            </label>
            <div className="md:col-span-4">
              <button
                type="submit"
                disabled={isSyncingSourceHub}
                className="min-h-[42px] rounded-[var(--radius-md)] bg-[color:var(--brand-700)] px-4 text-sm font-semibold text-[var(--on-secondary-container)] transition hover:bg-[color:var(--brand-600)] disabled:opacity-60"
              >
                {isSyncingSourceHub ? t(language, "admin.knowledgeSources.syncing") : t(language, "admin.knowledgeSources.sync")}
              </button>
            </div>
          </form>

          {sourceHubError ? (
            <p className="mb-3 rounded-lg border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-3 py-2 text-sm text-[var(--status-danger-text)]">
              {sourceHubError}
            </p>
          ) : null}
          {sourceHubMessage ? (
            <p className="mb-3 rounded-lg border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-3 py-2 text-sm text-[var(--status-ok-text)]">
              {sourceHubMessage}
            </p>
          ) : null}

          <div className="overflow-x-auto rounded-xl border border-[color:var(--shell-border)]">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--text-muted)]">
                  <th className="px-3 py-2">{t(language, "admin.knowledgeSources.source")}</th>
                  <th className="px-3 py-2">{t(language, "admin.knowledgeSources.table.title")}</th>
                  <th className="px-3 py-2">{t(language, "admin.knowledgeSources.query")}</th>
                  <th className="px-3 py-2">{t(language, "admin.knowledgeSources.table.published")}</th>
                  <th className="px-3 py-2">{t(language, "admin.knowledgeSources.table.synced")}</th>
                </tr>
              </thead>
              <tbody>
                {isLoadingSourceHubRecords ? (
                  <tr>
                    <td className="px-3 py-3 text-[var(--text-muted)]" colSpan={5}>
                      {t(language, "admin.knowledgeSources.loadingRecords")}
                    </td>
                  </tr>
                ) : sourceHubRecords.length ? (
                  sourceHubRecords.map((record) => (
                    <tr key={record.id} className="border-b border-[color:var(--shell-border)] align-top last:border-0">
                      <td className="px-3 py-2">
                        <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-xs font-semibold text-[var(--text-secondary)]">
                          {SOURCE_LABELS[record.source]}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-[var(--text-primary)]">{record.title}</p>
                        {record.snippet ? (
                          <p className="mt-1 line-clamp-2 text-xs text-[var(--text-muted)]">{record.snippet}</p>
                        ) : null}
                      </td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{record.query || "-"}</td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{formatDate(record.published_at, language)}</td>
                      <td className="px-3 py-2 text-[var(--text-secondary)]">{formatDate(record.synced_at, language)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-3 py-3 text-[var(--text-muted)]" colSpan={5}>
                      {t(language, "admin.knowledgeSources.noCrawledRecords")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* RAG source registry (Requirements 13.2, 15.3) — additive section */}
        <PanelCard
          title={t(language, "admin.knowledgeSources.registry.title")}
          description={t(language, "admin.knowledgeSources.registry.description")}
        >
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-[var(--text-muted)]">
              {t(language, "admin.knowledgeSources.registry.guidance")}
            </p>
            <button
              type="button"
              onClick={() => void loadRagRegistry()}
              disabled={ragRegistryLoading || ragUpdatingId != null}
              className="rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:opacity-60"
            >
              {ragRegistryLoading ? t(language, "admin.knowledgeSources.refreshing") : t(language, "admin.knowledgeSources.refresh")}
            </button>
          </div>

          {ragRegistryDegraded ? (
            <div
              role="alert"
              className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm text-[color:var(--status-warn-text)]"
            >
              <div>
                <p className="font-semibold">{t(language, "admin.knowledgeSources.registry.unavailableTitle")}</p>
                <p className="mt-0.5">
                  {t(language, "admin.knowledgeSources.registry.unavailableDescription")}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void loadRagRegistry()}
                disabled={ragRegistryLoading || ragUpdatingId != null}
                className="rounded-[var(--radius-sm)] border border-[color:var(--status-warn-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[color:var(--status-warn-text)] transition hover:text-[var(--text-primary)] disabled:opacity-60"
              >
                {ragRegistryLoading ? t(language, "admin.knowledgeSources.retrying") : t(language, "admin.knowledgeSources.retry")}
              </button>
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
            loadingLabel={t(language, "admin.knowledgeSources.registry.loading")}
            emptyTitle={t(language, "admin.knowledgeSources.registry.emptyTitle")}
            emptyDescription={t(language, "admin.knowledgeSources.registry.emptyDescription")}
          >
            {(rows) => (
              <RagSourceRegistryTable
                sources={rows}
                language={language}
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
// rag-ingestion surface. Static copy is resolved from the UI catalog.
// ---------------------------------------------------------------------------
function RagSourceRegistryTable({
  sources,
  language,
  updatingId,
  onToggleEnabled,
  onChangeTrustTier
}: {
  sources: RagRegistrySource[];
  language: UILanguage;
  updatingId: number | null;
  onToggleEnabled: (source: RagRegistrySource) => void;
  onChangeTrustTier: (source: RagRegistrySource, tier: number) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[color:var(--shell-border)] text-[var(--text-muted)]">
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.source")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.registry.trustTier")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.registry.license")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.registry.attribution")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.registry.fetchMode")}</th>
            <th className="py-2 pr-4 font-semibold">{t(language, "admin.knowledgeSources.table.status")}</th>
            <th className="py-2 font-semibold text-right">{t(language, "admin.knowledgeSources.table.action")}</th>
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
                    aria-label={t(language, "admin.knowledgeSources.registry.trustTierFor", { source: source.display_name || source.source_key })}
                    className="min-h-[36px] rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 text-sm text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {source.trust_tier == null ? (
                      <option value="">{t(language, "admin.knowledgeSources.tier.unassigned")}</option>
                    ) : null}
                    {RAG_TRUST_TIER_OPTIONS.map((tier) => (
                      <option key={tier} value={tier}>
                        {ragTrustTierLabel(tier, language)}
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
                  {ragFetchModeLabel(source.fetch_mode, language)}
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
                    {source.enabled ? t(language, "admin.knowledgeSources.enabled") : t(language, "admin.knowledgeSources.disabled")}
                  </span>
                </td>
                <td className="py-3 text-right">
                  <button
                    type="button"
                    onClick={() => onToggleEnabled(source)}
                    disabled={controlsDisabled}
                    title={
                      missingId
                        ? t(language, "admin.knowledgeSources.registry.missingId")
                        : source.enabled
                          ? t(language, "admin.knowledgeSources.registry.disableSource")
                          : t(language, "admin.knowledgeSources.registry.enableSource")
                    }
                    className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-xs font-semibold text-[var(--text-secondary)] transition hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isUpdating ? (
                      <span
                        aria-hidden="true"
                        className="h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                      />
                    ) : null}
                    {isUpdating ? t(language, "admin.knowledgeSources.saving") : source.enabled ? t(language, "admin.knowledgeSources.disable") : t(language, "admin.knowledgeSources.enable")}
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
