import api from "@/lib/http-client";

export type ScribeSoapRequest = {
  transcript: string;
};

export type ScribeSoapRawResponse = {
  subjective?: string | Record<string, unknown>;
  objective?: string | Record<string, unknown>;
  assessment?: string | Record<string, unknown>;
  plan?: string | Record<string, unknown>;
  S?: string;
  O?: string;
  A?: string;
  P?: string;
  soap?: {
    subjective?: string;
    objective?: string;
    assessment?: string;
    plan?: string;
    S?: string;
    O?: string;
    A?: string;
    P?: string;
  };
  [key: string]: unknown;
};

export type SoapSections = {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
};

export type ScribeSession = {
  id: number;
  title: string;
  status: string;
  transcript: string;
  soap?: Record<string, unknown> | null;
  insights?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  last_processed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ScribeSessionListResponse = {
  items: ScribeSession[];
  total: number;
};

export type ScribeSessionCreatePayload = {
  title?: string;
  transcript?: string;
  auto_generate_soap?: boolean;
};

export type ScribeSessionUpdatePayload = {
  title?: string;
  transcript?: string;
  status?: string;
  soap?: Record<string, unknown>;
  insights?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type ScribeRegeneratePayload = {
  transcript?: string;
  status?: string;
};

export type ScribeAnalyticsSummary = {
  total_sessions: number;
  completed_sessions: number;
  draft_sessions: number;
  sessions_today: number;
  avg_transcript_chars: number;
};

export type ScribeTranscribePayload = {
  audioFile: Blob;
  filename?: string;
  language?: string;
  prompt?: string;
  chunkIndex?: number;
  sessionId?: number;
  appendToSession?: boolean;
};

export type ScribeTranscribeResponse = {
  text: string;
  language?: string;
  model_used?: string;
  chunk_index?: number | null;
  session_id?: number | null;
  processing_ms?: number;
  received_bytes?: number;
  session_transcript_chars?: number;
  session_updated_at?: string | null;
};

function asText(value: unknown): string {
  if (typeof value !== "string") return "";
  return value.trim();
}

function formatSection(value: unknown): string {
  const direct = asText(value);
  if (direct) return direct;
  if (!value || typeof value !== "object" || Array.isArray(value)) return "";

  const record = value as Record<string, unknown>;
  const parts: string[] = [];
  for (const [key, item] of Object.entries(record)) {
    if (Array.isArray(item)) {
      const values = item.map((x) => asText(x)).filter(Boolean);
      if (values.length) parts.push(`${key}: ${values.join("; ")}`);
      continue;
    }
    if (item && typeof item === "object") {
      const nested = Object.entries(item as Record<string, unknown>)
        .map(([k, v]) => {
          const vv = asText(v);
          return vv ? `${k}=${vv}` : "";
        })
        .filter(Boolean);
      if (nested.length) parts.push(`${key}: ${nested.join(", ")}`);
      continue;
    }
    const text = asText(item);
    if (text) parts.push(`${key}: ${text}`);
  }
  return parts.join("\n");
}

export async function createSoap(payload: ScribeSoapRequest): Promise<ScribeSoapRawResponse> {
  const response = await api.post<ScribeSoapRawResponse>("/scribe/soap", payload);
  return response.data;
}

export function normalizeSoapSections(data: ScribeSoapRawResponse): SoapSections {
  const nested = data.soap;

  return {
    subjective: formatSection(data.subjective ?? data.S ?? nested?.subjective ?? nested?.S),
    objective: formatSection(data.objective ?? data.O ?? nested?.objective ?? nested?.O),
    assessment: formatSection(data.assessment ?? data.A ?? nested?.assessment ?? nested?.A),
    plan: formatSection(data.plan ?? data.P ?? nested?.plan ?? nested?.P),
  };
}

export async function listScribeSessions(limit = 20, offset = 0): Promise<ScribeSessionListResponse> {
  const response = await api.get<ScribeSessionListResponse>("/scribe/sessions", {
    params: { limit, offset },
  });
  return response.data;
}

export async function createScribeSession(payload: ScribeSessionCreatePayload): Promise<ScribeSession> {
  const response = await api.post<ScribeSession>("/scribe/sessions", payload);
  return response.data;
}

export async function getScribeSession(sessionId: number): Promise<ScribeSession> {
  const response = await api.get<ScribeSession>(`/scribe/sessions/${sessionId}`);
  return response.data;
}

export async function updateScribeSession(
  sessionId: number,
  payload: ScribeSessionUpdatePayload
): Promise<ScribeSession> {
  const response = await api.patch<ScribeSession>(`/scribe/sessions/${sessionId}`, payload);
  return response.data;
}

export async function regenerateScribeSession(
  sessionId: number,
  payload: ScribeRegeneratePayload
): Promise<ScribeSession> {
  const response = await api.post<ScribeSession>(`/scribe/sessions/${sessionId}/regenerate`, payload);
  return response.data;
}

export async function getScribeAnalyticsSummary(): Promise<ScribeAnalyticsSummary> {
  const response = await api.get<ScribeAnalyticsSummary>("/scribe/analytics/summary");
  return response.data;
}

export async function transcribeScribeAudio(
  payload: ScribeTranscribePayload
): Promise<ScribeTranscribeResponse> {
  const formData = new FormData();
  formData.append("audio_file", payload.audioFile, payload.filename ?? "scribe-live.webm");
  if (payload.language) formData.append("language", payload.language);
  if (payload.prompt) formData.append("prompt", payload.prompt);
  if (typeof payload.chunkIndex === "number") formData.append("chunk_index", String(payload.chunkIndex));
  if (typeof payload.sessionId === "number") formData.append("session_id", String(payload.sessionId));
  if (typeof payload.appendToSession === "boolean") {
    formData.append("append_to_session", payload.appendToSession ? "true" : "false");
  }
  const response = await api.post<ScribeTranscribeResponse>("/scribe/transcribe", formData);
  return response.data;
}
