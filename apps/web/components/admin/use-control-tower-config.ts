"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ControlTowerConfig,
  ControlTowerRagFlowConfig,
  ControlTowerRagSource,
  getControlTowerConfig,
  updateControlTowerConfig
} from "@/lib/system";

export type RetrievalMetricKey = "precision_at_k" | "recall_at_k" | "ndcg_at_k";
export type LlmProviderKey = "deepseek" | "hitechcloud_gpt53_codex_high";

const FLOW_TOGGLES = [
  "role_router_enabled",
  "intent_router_enabled",
  "rule_verification_enabled",
  "nli_model_enabled",
  "rag_reranker_enabled",
  "rag_nli_enabled",
  "rag_graphrag_enabled",
  "deepseek_fallback_enabled",
  "scientific_retrieval_enabled",
  "web_retrieval_enabled",
  "file_retrieval_enabled"
] as const;

export type FlowToggleKey = (typeof FLOW_TOGGLES)[number];

const DEFAULT_FLOW: ControlTowerRagFlowConfig = {
  role_router_enabled: true,
  intent_router_enabled: true,
  rule_verification_enabled: true,
  nli_model_enabled: true,
  rag_reranker_enabled: true,
  rag_nli_enabled: true,
  rag_graphrag_enabled: false,
  verification_enabled: true,
  deepseek_fallback_enabled: true,
  low_context_threshold: 0.2,
  precision_at_k: 10,
  recall_at_k: 10,
  ndcg_at_k: 10,
  scientific_retrieval_enabled: true,
  web_retrieval_enabled: true,
  file_retrieval_enabled: true,
  llm_provider: "hitechcloud_gpt53_codex_high",
  llm_base_url: "https://platform.hitechcloud.one/v1",
  llm_model: "gpt-5.3-codex-high",
  llm_api_key: ""
};

const RETRIEVAL_METRIC_K_MIN = 1;
const RETRIEVAL_METRIC_K_MAX = 50;
const DEFAULT_RETRIEVAL_METRIC_K = 10;

const SOURCE_WEIGHT_MIN = 0;
const SOURCE_WEIGHT_MAX = 1;
const DEFAULT_SOURCE_WEIGHT = 1;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function normalizeWeight(value: number): number {
  const safe = clamp(
    Number.isFinite(value) ? value : DEFAULT_SOURCE_WEIGHT,
    SOURCE_WEIGHT_MIN,
    SOURCE_WEIGHT_MAX
  );
  return Math.round(safe * 100) / 100;
}

function normalizeSource(source: ControlTowerRagSource, index: number): ControlTowerRagSource {
  const safeId = typeof source.id === "string" && source.id.trim() ? source.id.trim() : `source-${index + 1}`;
  const safeName = typeof source.name === "string" && source.name.trim() ? source.name.trim() : safeId;
  const safePriority = Number.isFinite(source.priority) ? Math.trunc(source.priority) : index + 1;
  const safeCategory =
    typeof source.category === "string" && source.category.trim() ? source.category.trim().toLowerCase() : "general";

  return {
    id: safeId,
    name: safeName,
    enabled: Boolean(source.enabled),
    priority: clamp(safePriority, 1, 100),
    weight: normalizeWeight(source.weight),
    category: safeCategory
  };
}

function sortSources(sources: ControlTowerRagSource[]): ControlTowerRagSource[] {
  return [...sources].sort((a, b) => a.priority - b.priority || a.name.localeCompare(b.name));
}

function normalizeFlow(flow?: Partial<ControlTowerRagFlowConfig> | null): ControlTowerRagFlowConfig {
  const ruleVerificationEnabled =
    flow?.rule_verification_enabled ??
    flow?.verification_enabled ??
    DEFAULT_FLOW.rule_verification_enabled;
  const nliModelEnabled = flow?.nli_model_enabled ?? ruleVerificationEnabled;
  const ragNliEnabled = flow?.rag_nli_enabled ?? nliModelEnabled;

  return {
    role_router_enabled: flow?.role_router_enabled ?? DEFAULT_FLOW.role_router_enabled,
    intent_router_enabled: flow?.intent_router_enabled ?? DEFAULT_FLOW.intent_router_enabled,
    rule_verification_enabled: ruleVerificationEnabled,
    nli_model_enabled: nliModelEnabled,
    rag_reranker_enabled: flow?.rag_reranker_enabled ?? DEFAULT_FLOW.rag_reranker_enabled,
    rag_nli_enabled: ragNliEnabled,
    rag_graphrag_enabled: flow?.rag_graphrag_enabled ?? DEFAULT_FLOW.rag_graphrag_enabled,
    verification_enabled: flow?.verification_enabled ?? ruleVerificationEnabled,
    deepseek_fallback_enabled: flow?.deepseek_fallback_enabled ?? DEFAULT_FLOW.deepseek_fallback_enabled,
    low_context_threshold: clamp(Number(flow?.low_context_threshold ?? DEFAULT_FLOW.low_context_threshold), 0, 1),
    precision_at_k: clamp(
      Math.trunc(Number(flow?.precision_at_k ?? DEFAULT_FLOW.precision_at_k)),
      RETRIEVAL_METRIC_K_MIN,
      RETRIEVAL_METRIC_K_MAX
    ),
    recall_at_k: clamp(
      Math.trunc(Number(flow?.recall_at_k ?? DEFAULT_FLOW.recall_at_k)),
      RETRIEVAL_METRIC_K_MIN,
      RETRIEVAL_METRIC_K_MAX
    ),
    ndcg_at_k: clamp(
      Math.trunc(Number(flow?.ndcg_at_k ?? DEFAULT_FLOW.ndcg_at_k)),
      RETRIEVAL_METRIC_K_MIN,
      RETRIEVAL_METRIC_K_MAX
    ),
    scientific_retrieval_enabled:
      flow?.scientific_retrieval_enabled ?? DEFAULT_FLOW.scientific_retrieval_enabled,
    web_retrieval_enabled: flow?.web_retrieval_enabled ?? DEFAULT_FLOW.web_retrieval_enabled,
    file_retrieval_enabled: flow?.file_retrieval_enabled ?? DEFAULT_FLOW.file_retrieval_enabled,
    llm_provider:
      flow?.llm_provider === "hitechcloud_gpt53_codex_high"
        ? "hitechcloud_gpt53_codex_high"
        : "deepseek",
    llm_base_url:
      typeof flow?.llm_base_url === "string" && flow.llm_base_url.trim()
        ? flow.llm_base_url.trim()
        : DEFAULT_FLOW.llm_base_url,
    llm_model:
      typeof flow?.llm_model === "string" && flow.llm_model.trim()
        ? flow.llm_model.trim()
        : DEFAULT_FLOW.llm_model,
    llm_api_key: typeof flow?.llm_api_key === "string" ? flow.llm_api_key.trim() : DEFAULT_FLOW.llm_api_key
  };
}

function normalizeConfig(input: ControlTowerConfig): ControlTowerConfig {
  const sources = Array.isArray(input.rag_sources) ? input.rag_sources : [];
  return {
    rag_sources: sortSources(sources.map(normalizeSource)),
    rag_flow: normalizeFlow(input.rag_flow),
    careguard_runtime: {
      external_ddi_enabled: Boolean(input.careguard_runtime?.external_ddi_enabled)
    }
  };
}

export type UseControlTowerConfigResult = {
  config: ControlTowerConfig | null;
  isLoading: boolean;
  isSaving: boolean;
  isDirty: boolean;
  error: string;
  message: string;
  reload: () => Promise<void>;
  save: () => Promise<boolean>;
  setSourceEnabled: (sourceId: string, enabled: boolean) => void;
  setSourcePriority: (sourceId: string, value: number) => void;
  setSourceWeight: (sourceId: string, value: number) => void;
  setSourceCategory: (sourceId: string, category: string) => void;
  setFlowToggle: (key: FlowToggleKey, enabled: boolean) => void;
  setLowContextThreshold: (value: number) => void;
  setRetrievalMetricK: (key: RetrievalMetricKey, value: number) => void;
  setLlmProvider: (provider: LlmProviderKey) => void;
  setLlmBaseUrl: (value: string) => void;
  setLlmModel: (value: string) => void;
  setLlmApiKey: (value: string) => void;
  flowToggleKeys: FlowToggleKey[];
};

export default function useControlTowerConfig(): UseControlTowerConfigResult {
  const [config, setConfig] = useState<ControlTowerConfig | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [snapshot, setSnapshot] = useState("");

  const currentSnapshot = useMemo(() => (config ? JSON.stringify(config) : ""), [config]);
  const isDirty = Boolean(config) && currentSnapshot !== snapshot;

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError("");
    setMessage("");
    try {
      const next = normalizeConfig(await getControlTowerConfig());
      setConfig(next);
      setSnapshot(JSON.stringify(next));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to load control tower config.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback(async () => {
    if (!config) return false;

    setIsSaving(true);
    setError("");
    setMessage("");

    try {
      const updated = normalizeConfig(await updateControlTowerConfig(config));
      setConfig(updated);
      setSnapshot(JSON.stringify(updated));
      setMessage("Saved control tower configuration.");
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to save control tower config.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [config]);

  const setSourceEnabled = useCallback((sourceId: string, enabled: boolean) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_sources: sortSources(
          prev.rag_sources.map((source) => (source.id === sourceId ? { ...source, enabled } : source))
        )
      };
    });
  }, []);

  const setSourcePriority = useCallback((sourceId: string, value: number) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const priority = clamp(Math.trunc(Number.isFinite(value) ? value : 1), 1, 100);
      return {
        ...prev,
        rag_sources: sortSources(
          prev.rag_sources.map((source) => (source.id === sourceId ? { ...source, priority } : source))
        )
      };
    });
  }, []);

  const setSourceWeight = useCallback((sourceId: string, value: number) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const weight = normalizeWeight(value);
      return {
        ...prev,
        rag_sources: sortSources(
          prev.rag_sources.map((source) => (source.id === sourceId ? { ...source, weight } : source))
        )
      };
    });
  }, []);

  const setSourceCategory = useCallback((sourceId: string, category: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const safeCategory = category.trim().toLowerCase() || "general";
      return {
        ...prev,
        rag_sources: sortSources(
          prev.rag_sources.map((source) => (source.id === sourceId ? { ...source, category: safeCategory } : source))
        )
      };
    });
  }, []);

  const setFlowToggle = useCallback((key: FlowToggleKey, enabled: boolean) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          [key]: enabled
        }
      };
    });
  }, []);

  const setLowContextThreshold = useCallback((value: number) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          low_context_threshold: clamp(Number.isFinite(value) ? value : 0, 0, 1)
        }
      };
    });
  }, []);

  const setRetrievalMetricK = useCallback((key: RetrievalMetricKey, value: number) => {
    setConfig((prev) => {
      if (!prev) return prev;
      const fallbackMetricK = DEFAULT_FLOW[key] ?? DEFAULT_RETRIEVAL_METRIC_K;
      const metricK = clamp(
        Math.trunc(Number.isFinite(value) ? value : fallbackMetricK),
        RETRIEVAL_METRIC_K_MIN,
        RETRIEVAL_METRIC_K_MAX
      );
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          [key]: metricK
        }
      };
    });
  }, []);

  const setLlmProvider = useCallback((provider: LlmProviderKey) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_provider: provider
        }
      };
    });
  }, []);

  const setLlmBaseUrl = useCallback((value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_base_url: value.trim()
        }
      };
    });
  }, []);

  const setLlmModel = useCallback((value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_model: value.trim()
        }
      };
    });
  }, []);

  const setLlmApiKey = useCallback((value: string) => {
    setConfig((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        rag_flow: {
          ...prev.rag_flow,
          llm_api_key: value.trim()
        }
      };
    });
  }, []);

  return {
    config,
    isLoading,
    isSaving,
    isDirty,
    error,
    message,
    reload,
    save,
    setSourceEnabled,
    setSourcePriority,
    setSourceWeight,
    setSourceCategory,
    setFlowToggle,
    setLowContextThreshold,
    setRetrievalMetricK,
    setLlmProvider,
    setLlmBaseUrl,
    setLlmModel,
    setLlmApiKey,
    flowToggleKeys: [...FLOW_TOGGLES]
  };
}
