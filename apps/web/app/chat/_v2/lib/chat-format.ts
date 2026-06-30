/**
 * Pure formatting utilities for the rebuilt CLARA Chat (CHAT_V2).
 *
 * These are presentation-free helpers extracted from the legacy chat page so
 * they can be unit/property tested in isolation (Requirement 1.2, 1.3; design
 * Property P8). They contain NO React, NO API calls, and NO DOM access (aside
 * from the explicit, browser-guarded `triggerBlobDownload`).
 */

import type { UILanguage } from "@/lib/ui-language";
import type {
  ConversationItem,
  ResearchResult,
} from "@/components/research/lib/research-page-types";
import type {
  WorkspaceConversationItem,
  WorkspaceNote,
  WorkspaceSearchResponse,
} from "@/lib/workspace";

export type ConversationDayBucket =
  | "today"
  | "yesterday"
  | "week"
  | "older"
  | "unknown";

/** Maximum number of locally-cached fallback conversations to retain. */
export const LOCAL_WORKSPACE_MAX_ITEMS = 80;

/** Trims a free-text prompt to a non-empty string, or null when blank. */
export function parsePromptText(
  value: string | null | undefined,
): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

/** Parses a comma-separated tag string into a bounded, trimmed list. */
export function parseTagsInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
    .slice(0, 20);
}

/** Builds a short, single-line preview label for a conversation row. */
export function buildConversationPreview(
  item: WorkspaceConversationItem,
): string {
  const candidate = item.title || item.preview || "Conversation";
  return candidate.length > 80 ? `${candidate.slice(0, 80)}...` : candidate;
}

/** Resolves the most relevant timestamp (ms) for ordering a conversation. */
export function toConversationTimestamp(
  item: WorkspaceConversationItem,
): number {
  const lastTs = Date.parse(item.last_message_at || "");
  if (Number.isFinite(lastTs) && lastTs > 0) return lastTs;
  const createdTs = Date.parse(item.created_at || "");
  if (Number.isFinite(createdTs) && createdTs > 0) return createdTs;
  return 0;
}

/** Buckets a timestamp into a coarse day group relative to `now`. */
export function toDayKey(
  ts: number,
  now: Date = new Date(),
): ConversationDayBucket {
  if (!Number.isFinite(ts) || ts <= 0) return "unknown";
  const date = new Date(ts);
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  ).getTime();
  const startOfThatDay = new Date(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  ).getTime();
  const dayDiff = Math.floor(
    (startOfToday - startOfThatDay) / (24 * 60 * 60 * 1000),
  );
  if (dayDiff === 0) return "today";
  if (dayDiff === 1) return "yesterday";
  if (dayDiff > 1 && dayDiff <= 7) return "week";
  if (dayDiff > 7) return "older";
  // Future-dated timestamps (dayDiff < 0) are treated as "today".
  return "today";
}

/** Localized label for a conversation day bucket. */
export function formatConversationDayLabel(
  bucket: ConversationDayBucket,
  language: UILanguage,
): string {
  if (bucket === "today") return language === "en" ? "Today" : "Hôm nay";
  if (bucket === "yesterday")
    return language === "en" ? "Yesterday" : "Hôm qua";
  if (bucket === "week")
    return language === "en" ? "Last 7 days" : "7 ngày qua";
  if (bucket === "older") return language === "en" ? "Older" : "Cũ hơn";
  return language === "en" ? "Unknown" : "Không rõ";
}

/** Extracts the answer text from a turn, if any. */
export function latestAnswerFromTurn(turn: ConversationItem | null): string {
  if (!turn) return "";
  return turn.result.answer || "";
}

/** Normalizes a possibly-null numeric id to a positive integer or null. */
export function asConversationId(
  value: number | null | undefined,
): number | null {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value) ||
    value <= 0
  ) {
    return null;
  }
  return Math.trunc(value);
}

/** Heuristic: does this error look like a 404 / "not found" upstream signal? */
export function isNotFoundLikeError(cause: unknown): boolean {
  if (!(cause instanceof Error)) return false;
  const message = cause.message.toLowerCase();
  return (
    message.includes("not found") ||
    message.includes("404") ||
    message.includes("không tồn tại")
  );
}

/**
 * Builds a deterministic Markdown export for a conversation. The exported time
 * is injectable so the output is reproducible under test (Property P8).
 */
export function buildConversationMarkdownExport(
  title: string,
  turns: ConversationItem[],
  exportedAtIso: string = new Date().toISOString(),
): string {
  const lines: string[] = [
    `# ${title || "CLARA Conversation Export"}`,
    "",
    `- Exported at: \`${exportedAtIso}\``,
    "",
  ];

  for (const turn of turns) {
    const query = (turn.query || "").trim();
    const answer = (turn.result?.answer || "").trim();
    lines.push("## User");
    lines.push("");
    lines.push(query || "_(empty)_");
    lines.push("");
    lines.push("## CLARA");
    lines.push("");
    lines.push(answer || "_(empty)_");
    lines.push("");
    lines.push("---");
    lines.push("");
  }

  return lines.join("\n").trim();
}

/**
 * Merges local-fallback conversations with server conversations, de-duplicating
 * by id (server wins on conflict) and sorting newest-first. Pure: returns a new
 * array and never mutates the inputs (Requirement 6.5).
 */
export function mergeConversations(
  server: WorkspaceConversationItem[],
  local: WorkspaceConversationItem[],
): WorkspaceConversationItem[] {
  const merged = new Map<number, WorkspaceConversationItem>();
  for (const item of local) {
    merged.set(item.conversation_id, item);
  }
  for (const item of server) {
    merged.set(item.conversation_id, item);
  }
  return Array.from(merged.values()).sort((a, b) => {
    const aTs = Date.parse(a.last_message_at || a.created_at || "") || 0;
    const bTs = Date.parse(b.last_message_at || b.created_at || "") || 0;
    return bTs - aTs;
  });
}

/**
 * Pure, local-fallback workspace search over already-loaded notes (Requirement
 * 6.4, 6.5). When the workspace search API is unavailable, the chat can still
 * search the notes it holds in memory. Matches case-insensitively across the
 * note title, markdown body, summary, and tags. Returns a `WorkspaceSearchResponse`
 * shape so callers can treat local and server results uniformly. A blank query
 * yields no matches.
 */
export function localWorkspaceSearch(
  notes: WorkspaceNote[],
  query: string,
): WorkspaceSearchResponse {
  const keyword = query.trim().toLowerCase();
  const matchedNotes = keyword
    ? notes.filter((note) => {
        const haystack = [
          note.title ?? "",
          note.content_markdown ?? "",
          note.summary ?? "",
          ...(note.tags ?? []),
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(keyword);
      })
    : [];
  return {
    query,
    conversations: [],
    notes: matchedNotes,
    folders: [],
    channels: [],
    suggestions: [],
  };
}

/** Whether a DOM target is an editable element (input/textarea/contenteditable). */
export function isEditableElement(target: EventTarget | null): boolean {
  if (typeof HTMLElement === "undefined") return false;
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  return Boolean(
    target.closest("input, textarea, select, [contenteditable='true']"),
  );
}

/**
 * Triggers a browser download for a blob. Guarded so importing this module is
 * safe under SSR / test environments; callers in the browser get the download.
 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  if (typeof document === "undefined" || typeof URL === "undefined") return;
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

/** Localized quick-prompt suggestions for the empty composer state. */
export const QUICK_PROMPTS_BY_LANGUAGE: Record<UILanguage, string[]> = {
  vi: [
    "Tôi đang uống metformin, cần lưu ý gì?",
    "Thuốc này có tương tác với thuốc nào?",
    "Giải thích kết quả xét nghiệm này giúp tôi.",
    "Khi nào tôi nên đi khám bác sĩ?",
    "Tác dụng phụ thường gặp của thuốc này là gì?",
  ],
  en: [
    "I take metformin. What should I watch for?",
    "Which medicines can this interact with?",
    "Help me understand this lab result.",
    "When should I see a doctor?",
    "What common side effects can this medicine cause?",
  ],
};

/**
 * Whether a normalized answer string came from the deterministic local-synthesis
 * fallback path. Such answers must be visibly labeled "degraded" (design
 * Property P5; Requirement 3.4). The ML local fallback tags its synthetic ids /
 * pipeline markers with a `local-synth` / `local_synth` prefix.
 */
export function isDegradedAnswer(
  result: ResearchResult | null | undefined,
): boolean {
  if (!result) return false;
  if (result.tier !== "tier2") return false;
  const pipeline = (result.debug?.pipeline ?? "").toLowerCase();
  if (pipeline.includes("local-synth") || pipeline.includes("local_synth"))
    return true;
  if (pipeline.includes("fallback")) return true;
  return result.fallbackUsed === true;
}
