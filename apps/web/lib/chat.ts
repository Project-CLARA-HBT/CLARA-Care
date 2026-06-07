import api from "@/lib/http-client";
import { getAccessToken, getCsrfToken } from "@/lib/auth-store";

export type ChatResponse = {
  message?: string;
  reply?: string;
  answer?: string;
  fallback?: boolean;
  fallback_reason?: string;
  role?: string;
  intent?: string;
  confidence?: number;
  emergency?: boolean;
  model_used?: string;
};

export type ChatIntentDebug = Pick<ChatResponse, "role" | "intent" | "confidence" | "emergency" | "model_used">;

export function getChatReply(data: ChatResponse): string | null {
  if (typeof data.reply === "string" && data.reply.trim()) return data.reply;
  if (typeof data.answer === "string" && data.answer.trim()) return data.answer;
  return null;
}

export function getChatIntentDebug(data: ChatResponse): ChatIntentDebug {
  return {
    role: data.role,
    intent: data.intent,
    confidence: data.confidence,
    emergency: data.emergency,
    model_used: data.model_used
  };
}

export async function sendChatMessage(message: string): Promise<ChatResponse> {
  const response = await api.post("/chat", { message });
  return (response.data ?? {}) as ChatResponse;
}

// ---------------------------------------------------------------------------
// Streaming chat (SSE): live pipeline steps + token-by-token answer.
// ---------------------------------------------------------------------------

/** One live pipeline step (forwarded from the ML ``flow_events``). */
export type ChatStreamStep = {
  index?: number;
  stage?: string;
  status?: string;
  note?: string;
  source_count?: number;
  [key: string]: unknown;
};

export type ChatStreamHandlers = {
  /** Fired once before any step/token (open the live panel immediately). */
  onStart?: () => void;
  /** Fired per pipeline step as it is reported. */
  onStep?: (step: ChatStreamStep) => void;
  /** Fired per answer chunk; concatenating all chunks yields the full answer. */
  onToken?: (text: string) => void;
  /** Fired once with the final structured result (answer + provenance). */
  onDone?: (result: ChatResponse & Record<string, unknown>) => void;
  /** Fired on a terminal stream error (caller should fall back to non-stream). */
  onError?: (message: string) => void;
  signal?: AbortSignal;
};

function chatStreamUrl(): string {
  // Mirror http-client base resolution so we hit the same /api/v1 origin.
  const base = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
  return `${base.replace(/\/$/, "")}/chat/stream`;
}

function parseSseFrame(block: string): { event: string; data: string } | null {
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
 * Open an SSE chat stream and dispatch step/token/done/error callbacks.
 *
 * Falls back is the caller's responsibility: if this throws or fires onError,
 * the caller should retry the non-streaming `sendChatMessage`.
 */
export async function streamChatMessage(
  message: string,
  handlers: ChatStreamHandlers
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
    "Cache-Control": "no-cache",
  };
  const accessToken = getAccessToken();
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const csrfToken = getCsrfToken();
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const response = await fetch(chatStreamUrl(), {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify({ message }),
    signal: handlers.signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`chat stream failed (status=${response.status})`);
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
    if (event === "start") handlers.onStart?.();
    else if (event === "step") handlers.onStep?.((parsed ?? {}) as ChatStreamStep);
    else if (event === "token") {
      const text = (parsed as { text?: string })?.text;
      if (typeof text === "string") handlers.onToken?.(text);
    } else if (event === "done") {
      sawTerminal = true;
      handlers.onDone?.((parsed ?? {}) as ChatResponse & Record<string, unknown>);
    } else if (event === "error") {
      sawTerminal = true;
      const msg = (parsed as { message?: string })?.message ?? "chat stream error";
      handlers.onError?.(msg);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sepIndex = buffer.indexOf("\n\n");
      while (sepIndex !== -1) {
        const block = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const frame = parseSseFrame(block);
        if (frame) dispatch(frame.event, frame.data);
        sepIndex = buffer.indexOf("\n\n");
      }
    }
    const tail = parseSseFrame(buffer);
    if (tail) dispatch(tail.event, tail.data);
  } finally {
    reader.releaseLock();
  }

  if (!sawTerminal) {
    throw new Error("chat stream ended without a terminal event");
  }
}
