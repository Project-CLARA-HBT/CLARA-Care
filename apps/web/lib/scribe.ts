import api from "@/lib/http-client";
import { getAccessToken, getCsrfToken } from "@/lib/auth-store";
import { parseContentDispositionFilename } from "@/lib/scribe-review";

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
  /** Additive, review-only ASR terminology candidates. Never applied by the API. */
  medical_correction?: ScribeMedicalCorrectionResult;
};

export type ScribeMedicalCorrectionSuggestion = {
  source_text: string;
  replacement_text: string;
  kind: "medication_term" | "clinical_term" | "procedure_term";
  rationale: string;
  start: number;
  end: number;
  status: "suggested_requires_clinician_review";
};

/**
 * The API keeps this additive metadata separate from the verbatim transcript.
 * Any client that uses it must require an explicit clinician action per row.
 */
export type ScribeMedicalCorrectionResult = {
  status?: string;
  suggestions?: ScribeMedicalCorrectionSuggestion[];
  applied?: false;
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

// ---------------------------------------------------------------------------
// Enterprise workflow clients (consent, sign/amend, audit, export) + SSE stream.
// ---------------------------------------------------------------------------

export type ScribeAuditEntry = {
  id: number;
  actor: number | null;
  action: string;
  from_status: string;
  to_status: string;
  detail: Record<string, unknown>;
  created_at: string | null;
};

export async function captureScribeConsent(
  sessionId: number,
  payload: { method?: string; scope?: string } = {}
): Promise<{ session_id: number; consent_id: number; captured: boolean }> {
  const response = await api.post(`/scribe/sessions/${sessionId}/consent`, payload);
  return response.data;
}

export async function generateScribeNote(
  sessionId: number,
  payload: { template_id?: string; transcript?: string } = {}
): Promise<ScribeSession> {
  const response = await api.post<ScribeSession>(`/scribe/sessions/${sessionId}/notes`, payload);
  return response.data;
}

export async function signScribeNote(sessionId: number): Promise<ScribeSession> {
  const response = await api.post<ScribeSession>(`/scribe/sessions/${sessionId}/sign`, {});
  return response.data;
}

export async function amendScribeNote(
  sessionId: number,
  payload: { template_id?: string; transcript?: string } = {}
): Promise<ScribeSession> {
  const response = await api.post<ScribeSession>(`/scribe/sessions/${sessionId}/amend`, payload);
  return response.data;
}

export async function getScribeAudit(
  sessionId: number
): Promise<{ session_id: number; entries: ScribeAuditEntry[] }> {
  const response = await api.get(`/scribe/sessions/${sessionId}/audit`);
  return response.data;
}

/** Supported export formats (Requirement 9): Markdown, DOCX, FHIR DocumentReference. */
export type ScribeExportFormat = "md" | "docx" | "fhir";

/**
 * Normalized export result. `md` carries the rendered markdown (+ the raw
 * payload), `fhir` the DocumentReference-shaped JSON, and `docx` the binary
 * blob plus a filename ready to download.
 */
export type ScribeExportResult =
  | { format: "md"; markdown: string; data: Record<string, unknown> }
  | { format: "fhir"; document: Record<string, unknown> }
  | { format: "docx"; blob: Blob; filename: string };

/**
 * Export a signed/exported note (Requirement 9). `md`/`fhir` return JSON; `docx`
 * is fetched as a binary blob (reusing the workspace DOCX render path on the
 * server) with the filename taken from the `Content-Disposition` header.
 *
 * The server gates export on enterprise flags + signed status; callers should
 * surface a friendly message when the request is rejected (4xx) rather than
 * assuming the capability is available.
 */
export async function exportScribeNote(
  sessionId: number,
  format: ScribeExportFormat = "md"
): Promise<ScribeExportResult> {
  if (format === "docx") {
    const response = await api.get(`/scribe/sessions/${sessionId}/export`, {
      params: { format },
      responseType: "blob",
    });
    const blob = response.data as Blob;
    const headers = (response.headers ?? {}) as Record<string, string>;
    const filename =
      parseContentDispositionFilename(headers["content-disposition"]) ??
      `clinical-note-${sessionId}.docx`;
    return { format: "docx", blob, filename };
  }

  const response = await api.get<Record<string, unknown>>(`/scribe/sessions/${sessionId}/export`, {
    params: { format },
  });
  const data = response.data ?? {};
  if (format === "fhir") {
    return { format: "fhir", document: data };
  }
  const markdown = typeof data.markdown === "string" ? data.markdown : "";
  return { format: "md", markdown, data };
}

// ---------------------------------------------------------------------------
// Transcript grounding / claim traceability (Requirement 12.7). Read-only
// client for the additive grounding report persisted on a note version. The
// server gates this behind `RAG_SCRIBE_GROUNDING_ENABLED` and answers 404 both
// when the flag is off and when a version has no grounding metadata, so callers
// MUST treat a rejection as "no grounding available" and render unchanged.
// ---------------------------------------------------------------------------

/** A single note statement with its grounding verdict + transcript provenance. */
export type ScribeGroundedStatement = {
  statement: string;
  /** The note section key the statement was enumerated from. */
  section: string;
  /** Clinically significant assertion (vs boilerplate/heading). */
  significant: boolean;
  /** Critical-safety statement (medication, dose, allergy, vital, diagnosis). */
  critical_safety: boolean;
  /** True iff at least one transcript span entails the statement. */
  grounded: boolean;
  /** Transcript span ids that entail the statement (empty when ungrounded). */
  supporting_span_ids: string[];
  /** Verification method label. */
  method: string;
  /** "grounded" | "unverified". */
  status: string;
  /** Whether the statement is asserted in the note clinical text. */
  asserted: boolean;
  /** Corroborating FIDES fact-check verdict ("n/a" when unavailable). */
  fact_check: string;
};

/** Additive grounding metadata for a note version (server `GroundingReport`). */
export type ScribeGroundingReport = {
  version?: string;
  enabled: boolean;
  statements: ScribeGroundedStatement[];
  /** grounded_significant / total_significant. */
  grounded_claim_rate: number;
  /** Critical ungrounded statements surfaced for clinician confirmation. */
  unverified_candidates: string[];
  total_significant: number;
  grounded_significant: number;
};

/** Read response for `GET /scribe/sessions/{id}/notes/{ver}/grounding`. */
export type ScribeGroundingResponse = {
  session_id: number;
  version_no: number;
  grounding: ScribeGroundingReport;
};

/**
 * Fetch the additive grounding report for a note version (Requirement 12.7),
 * mirroring the other read clients (`getScribeAudit` / `exportScribeNote`).
 *
 * The server gates this on `RAG_SCRIBE_GROUNDING_ENABLED` and returns 404 when
 * the flag is off or the version carries no grounding metadata; callers should
 * catch the rejection and render the editor exactly as before (no chips/panel).
 */
export async function getScribeGrounding(
  sessionId: number,
  versionNo: number
): Promise<ScribeGroundingResponse> {
  const response = await api.get<ScribeGroundingResponse>(
    `/scribe/sessions/${sessionId}/notes/${versionNo}/grounding`
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// E/M + CPT coding suggestions (Requirement 14.3 / 14.5). Read-only client for
// the additive coding result persisted on a note version. The server gates this
// behind `RAG_SCRIBE_EM_CPT_CODING_ENABLED` and answers 404 both when the flag
// is off and when a version has no coding metadata, so callers MUST treat a
// rejection as "no coding available" and render the editor unchanged. Every
// suggestion is advisory and `selected: false` from the server — nothing is
// auto-selected; confirmation is an explicit local clinician action.
// ---------------------------------------------------------------------------

/** A single advisory E/M visit-level or CPT/procedure suggestion (Req 14.2/14.6). */
export type ScribeEmCptSuggestion = {
  /** The code value (e.g. an E/M level code or a CPT procedure code). */
  code: string;
  /** "E/M" | "CPT". */
  kind: string;
  /** Coding system label ("E/M" | "CPT"). */
  system: string;
  /** English display label. */
  display: string;
  /** Vietnamese display label (Vietnamese-first, Req 14.6). */
  display_vi: string;
  /** E/M visit level (1..5) for kind "E/M"; null for a CPT procedure. */
  level: number | null;
  /** Justifying note/transcript text span(s) (Req 14.2). */
  spans: string[];
  /** Short rationale for the suggestion. */
  rationale: string;
  /** Always false from the server — never auto-selected (Req 14.3/14.5). */
  selected: boolean;
  /** Always "advisory" until a clinician confirms. */
  status: string;
};

/**
 * Additive coding metadata for a note version (server `CodingResult`). Carries
 * the legacy Req 7 ICD/medication/interaction advisory data plus the additive
 * `em_cpt` E/M + CPT suggestions (present only when the coding flag is on).
 */
export type ScribeCodingReport = {
  icd?: Array<Record<string, unknown>>;
  medications?: Array<Record<string, unknown>>;
  interactions?: string[];
  advisory?: boolean;
  /** E/M + CPT suggestions; absent/empty when the E/M+CPT pass produced none. */
  em_cpt?: ScribeEmCptSuggestion[];
  [key: string]: unknown;
};

/** Read response for `GET /scribe/sessions/{id}/notes/{ver}/coding`. */
export type ScribeCodingResponse = {
  session_id: number;
  version_no: number;
  coding: ScribeCodingReport;
};

/**
 * Fetch the additive E/M + CPT coding suggestions for a note version
 * (Requirement 14.3/14.5), mirroring `getScribeGrounding`.
 *
 * The server gates this on `RAG_SCRIBE_EM_CPT_CODING_ENABLED` and returns 404
 * when the flag is off or the version carries no coding metadata; callers should
 * catch the rejection and render the editor exactly as before (no suggestions).
 */
export async function getScribeCoding(
  sessionId: number,
  versionNo: number
): Promise<ScribeCodingResponse> {
  const response = await api.get<ScribeCodingResponse>(
    `/scribe/sessions/${sessionId}/notes/${versionNo}/coding`
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// Addendum workflow (Requirement 18.2) — append-only, time-stamped notes
// attached to a SIGNED note version. An addendum is DISTINCT from amend: it
// leaves the signed version byte-for-byte unchanged and creates no new note
// version (amend creates a new `amended` version). Both clients are gated
// server-side by `RAG_SCRIBE_ADDENDUM_ENABLED`; when the flag is off the
// endpoints answer 404, so callers MUST treat a rejection as "addendum
// unavailable" and render the editor exactly as before (amend-only, Req 18.1).
// ---------------------------------------------------------------------------

/** A single append-only addendum attached to a signed note version (Req 18.2). */
export type ScribeAddendum = {
  session_id: number;
  version_no: number;
  addendum_id: number;
  /** The authoring clinician's user id (server-derived, never client-supplied). */
  author: number | null;
  text: string;
  /** Server-clock timestamp (ISO string) — never client-supplied. */
  created_at: string | null;
};

/** Read response for `GET /scribe/sessions/{id}/notes/{ver}/addenda`. */
export type ScribeAddendaListResponse = {
  session_id: number;
  version_no: number;
  addenda: ScribeAddendum[];
};

/**
 * Attach a time-stamped addendum to a SIGNED note version (Requirement 18.2),
 * mirroring the other workflow clients. Only the free text is sent; the author
 * and timestamp are derived server-side from the authenticated clinician and
 * the server clock. The signed version is left unchanged (Req 18.3) and no new
 * note version is created (Req 18.5).
 *
 * The server gates this on `RAG_SCRIBE_ADDENDUM_ENABLED` and answers 404 when
 * the flag is off; callers should catch the rejection and keep the legacy
 * amend-only surface.
 */
export async function addScribeAddendum(
  sessionId: number,
  versionNo: number,
  text: string
): Promise<ScribeAddendum> {
  const response = await api.post<ScribeAddendum>(
    `/scribe/sessions/${sessionId}/notes/${versionNo}/addendum`,
    { text }
  );
  return response.data;
}

/**
 * List a signed note version's addenda in append (chronological) order
 * (Requirement 18.6), mirroring `getScribeAudit`. Returns an empty `addenda`
 * list when the version exists but has no addenda yet.
 *
 * The server gates this on `RAG_SCRIBE_ADDENDUM_ENABLED` and answers 404 when
 * the flag is off; callers should catch the rejection and render the editor
 * exactly as before (no addendum panel).
 */
export async function listScribeAddenda(
  sessionId: number,
  versionNo: number
): Promise<ScribeAddendaListResponse> {
  const response = await api.get<ScribeAddendaListResponse>(
    `/scribe/sessions/${sessionId}/notes/${versionNo}/addenda`
  );
  return response.data;
}

/** Interim transcript text for a chunk, emitted before the chunk is finalized. */
export type ScribeStreamPartial = {
  index: number;
  text: string;
  /** True when the underlying chunk is a degraded ASR result (no fabricated text). */
  degraded?: boolean;
};

/** A finalized transcript segment (additive metadata: speaker + degraded flag). */
export type ScribeStreamSegment = {
  index: number;
  text: string;
  speaker: string;
  start_ms: number;
  end_ms: number;
  confidence?: number;
  degraded: boolean;
};

/** ASR observability metadata carried on the terminal ``done`` frame. */
export type ScribeStreamAsrMeta = {
  provider?: string;
  language?: string;
  degraded_count?: number;
};

/** Generated note draft carried on the terminal ``done`` frame (may be null). */
export type ScribeStreamNote = {
  template_id?: string;
  sections?: Record<string, string>;
  insufficient_input?: boolean;
} | null;

/** Terminal ``done`` payload: full transcript + segments + optional note draft. */
export type ScribeStreamDone = {
  transcript?: string;
  segments?: ScribeStreamSegment[];
  note?: ScribeStreamNote;
  asr_meta?: ScribeStreamAsrMeta;
  [key: string]: unknown;
};

export type ScribeStreamHandlers = {
  /** Fired once before any partial/segment/token (open the live transcript panel). */
  onStart?: () => void;
  /** Fired per interim transcript chunk before it is finalized as a segment. */
  onPartial?: (partial: ScribeStreamPartial) => void;
  /** Fired per finalized transcript segment (speaker + degraded flag preserved). */
  onSegment?: (segment: ScribeStreamSegment) => void;
  /** Fired per note-draft chunk; concatenating all chunks yields the note section. */
  onToken?: (text: string) => void;
  /** Fired once with the terminal structured result (transcript/segments/note/asr_meta). */
  onDone?: (result: ScribeStreamDone) => void;
  /** Fired on a terminal error; ``message`` names the failure class (no raw internals). */
  onError?: (message: string) => void;
  signal?: AbortSignal;
};

function scribeStreamUrl(sessionId: number): string {
  const base = (process.env.NEXT_PUBLIC_API_URL ?? "/api/v1").replace(/\/$/, "");
  return `${base}/scribe/sessions/${sessionId}/stream`;
}

function parseScribeSseFrame(block: string): { event: string; data: string } | null {
  const lines = block.split("\n");
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

/**
 * Open an SSE scribe transcription stream for a session and dispatch
 * start/partial/segment/token/done/error callbacks, mirroring the
 * `streamChatMessage` conventions (same auth/credentials + SSE frame parsing).
 *
 * POSTs the audio as multipart form-data (`audio_file`, optional `language` and
 * `template_id`) to `/scribe/sessions/{id}/stream`. Degraded segments are passed
 * through verbatim (no fabricated text). Caller should fall back to the batch
 * transcribe path on a terminal `error` or a thrown transport failure.
 */
export async function streamScribe(
  sessionId: number,
  audio: Blob,
  options: { filename?: string; language?: string; templateId?: string } & ScribeStreamHandlers
): Promise<void> {
  const form = new FormData();
  form.append("audio_file", audio, options.filename ?? "scribe-live.webm");
  if (options.language) form.append("language", options.language);
  if (options.templateId) form.append("template_id", options.templateId);

  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const accessToken = getAccessToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const csrfToken = getCsrfToken();
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const response = await fetch(scribeStreamUrl(sessionId), {
    method: "POST",
    headers,
    credentials: "include",
    body: form,
    signal: options.signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`scribe stream failed (status=${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let sawTerminal = false;

  const dispatch = (event: string, data: string) => {
    let parsed: unknown = data;
    try {
      parsed = JSON.parse(data);
    } catch {
      parsed = data;
    }
    if (event === "start") options.onStart?.();
    else if (event === "partial") options.onPartial?.((parsed ?? {}) as ScribeStreamPartial);
    else if (event === "segment") options.onSegment?.(parsed as ScribeStreamSegment);
    else if (event === "token") {
      const text = (parsed as { text?: string })?.text;
      if (typeof text === "string") options.onToken?.(text);
    } else if (event === "done") {
      sawTerminal = true;
      options.onDone?.((parsed ?? {}) as ScribeStreamDone);
    } else if (event === "error") {
      sawTerminal = true;
      options.onError?.((parsed as { message?: string })?.message ?? "scribe stream error");
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx = buffer.indexOf("\n\n");
      while (idx !== -1) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const frame = parseScribeSseFrame(block);
        if (frame) dispatch(frame.event, frame.data);
        idx = buffer.indexOf("\n\n");
      }
    }
    const tail = parseScribeSseFrame(buffer);
    if (tail) dispatch(tail.event, tail.data);
  } finally {
    reader.releaseLock();
  }

  if (!sawTerminal) throw new Error("scribe stream ended without a terminal event");
}
