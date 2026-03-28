import api from "@/lib/http-client";

export type ResearchTier = "tier1" | "tier2";

export const RESEARCH_UPLOAD_TIMEOUT_MS = 60000;
export const RESEARCH_TIER2_TIMEOUT_MS = 120000;

export type Tier2Citation = {
  title: string;
  source?: string;
  url?: string;
  snippet?: string;
  year?: string;
};

export type Tier2Step = {
  title: string;
  detail?: string;
};

export type ResearchTier2RawResponse = {
  answer?: string;
  summary?: string;
  message?: string;
  citations?: unknown;
  sources?: unknown;
  steps?: unknown;
  workflow_steps?: unknown;
  [key: string]: unknown;
};

export type ResearchTier2Result = {
  answer: string;
  citations: Tier2Citation[];
  steps: Tier2Step[];
};

export type UploadedResearchFile = {
  id: string;
  name: string;
  size?: number;
};

export type ResearchUploadRawResponse = {
  id?: unknown;
  file_id?: unknown;
  uploaded_file_id?: unknown;
  uploaded_file_ids?: unknown;
  file_ids?: unknown;
  file?: unknown;
  files?: unknown;
  uploaded_files?: unknown;
  [key: string]: unknown;
};

export type ResearchUploadResult = {
  uploadedFileIds: string[];
  files: UploadedResearchFile[];
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const next = value.trim();
  return next ? next : undefined;
}

function asNumber(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value !== "string") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function asId(value: unknown): string | undefined {
  const text = asText(value);
  if (text) return text;
  const numeric = asNumber(value);
  return numeric !== undefined ? String(numeric) : undefined;
}

function uniqueIds(ids: string[]): string[] {
  return Array.from(new Set(ids));
}

function parseIdList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return uniqueIds(
      value
        .map((item) => {
          if (typeof item === "string" || typeof item === "number") {
            return asId(item);
          }

          const record = asRecord(item);
          if (!record) return undefined;
          return asId(record.id) ?? asId(record.file_id) ?? asId(record.uploaded_file_id);
        })
        .filter((item): item is string => Boolean(item))
    );
  }

  const single = asId(value);
  return single ? [single] : [];
}

function parseCitation(value: unknown): Tier2Citation | null {
  if (typeof value === "string") {
    const title = asText(value);
    return title ? { title } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const title =
    asText(item.title) ??
    asText(item.name) ??
    asText(item.source) ??
    asText(item.url) ??
    asText(item.id);

  if (!title) return null;

  return {
    title,
    source: asText(item.source) ?? asText(item.publisher) ?? asText(item.source_id),
    url: asText(item.url),
    snippet: asText(item.snippet) ?? asText(item.summary) ?? asText(item.relevance),
    year: asText(item.year)
  };
}

function parseStep(value: unknown): Tier2Step | null {
  if (typeof value === "string") {
    const title = asText(value);
    return title ? { title } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const title =
    asText(item.title) ??
    asText(item.step) ??
    asText(item.name) ??
    asText(item.label) ??
    asText(item.action);

  if (!title) return null;

  return {
    title,
    detail:
      asText(item.detail) ??
      asText(item.description) ??
      asText(item.result) ??
      asText(item.notes) ??
      asText(item.objective) ??
      asText(item.output)
  };
}

function parseUploadedFile(value: unknown): UploadedResearchFile | null {
  if (typeof value === "string" || typeof value === "number") {
    const id = asId(value);
    return id ? { id, name: `File #${id}` } : null;
  }

  const item = asRecord(value);
  if (!item) return null;

  const id = asId(item.id) ?? asId(item.file_id) ?? asId(item.uploaded_file_id);
  if (!id) return null;

  const name = asText(item.file_name) ?? asText(item.filename) ?? asText(item.name) ?? `File #${id}`;
  const size = asNumber(item.file_size) ?? asNumber(item.size);

  return { id, name, size };
}

function parseList<T>(value: unknown, parser: (item: unknown) => T | null): T[] {
  if (!Array.isArray(value)) {
    const single = parser(value);
    return single ? [single] : [];
  }

  return value.map((item) => parser(item)).filter((item): item is T => Boolean(item));
}

export async function uploadResearchFile(file: File): Promise<ResearchUploadResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await api.post<ResearchUploadRawResponse>("/research/upload-file", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: RESEARCH_UPLOAD_TIMEOUT_MS
  });

  const data = response.data;
  const files = parseList(data.files ?? data.uploaded_files ?? data.file, parseUploadedFile);
  const idsFromPayload = uniqueIds([
    ...parseIdList(data.uploaded_file_ids),
    ...parseIdList(data.file_ids),
    ...parseIdList(data.uploaded_file_id),
    ...parseIdList(data.file_id),
    ...parseIdList(data.id)
  ]);
  const idsFromFiles = files.map((item) => item.id);
  const uploadedFileIds = uniqueIds([...idsFromPayload, ...idsFromFiles]);

  if (!files.length && uploadedFileIds.length) {
    return {
      uploadedFileIds,
      files: uploadedFileIds.map((id, index) => ({
        id,
        name: index === 0 ? file.name : `${file.name} (${index + 1})`,
        size: file.size
      }))
    };
  }

  return { uploadedFileIds, files };
}

export async function runResearchTier2(
  query: string,
  options?: { uploadedFileIds?: string[] }
): Promise<ResearchTier2RawResponse> {
  const uploadedFileIds = uniqueIds((options?.uploadedFileIds ?? []).map((item) => item.trim()).filter(Boolean));
  const payload: Record<string, unknown> = { query, message: query };

  if (uploadedFileIds.length) {
    payload.uploaded_file_ids = uploadedFileIds;
  }

  const response = await api.post<ResearchTier2RawResponse>("/research/tier2", payload, {
    timeout: RESEARCH_TIER2_TIMEOUT_MS
  });
  return response.data;
}

export function normalizeResearchTier2(data: ResearchTier2RawResponse): ResearchTier2Result {
  const answer = asText(data.answer) ?? asText(data.summary) ?? asText(data.message) ?? "";
  const citations = parseList(data.citations ?? data.sources, parseCitation);
  const steps = parseList(data.steps ?? data.workflow_steps, parseStep);

  return { answer, citations, steps };
}
