import { describe, expect, it } from "vitest";
import fc from "fast-check";

import {
  asConversationId,
  buildConversationMarkdownExport,
  buildConversationPreview,
  formatConversationDayLabel,
  isDegradedAnswer,
  isNotFoundLikeError,
  mergeConversations,
  parsePromptText,
  parseTagsInput,
  toConversationTimestamp,
  toDayKey,
  type ConversationDayBucket,
} from "@/app/chat/_v2/lib/chat-format";
import type { WorkspaceConversationItem } from "@/lib/workspace";
import type { ConversationItem, Tier2Result } from "@/components/research/lib/research-page-types";

/**
 * Feature: clara-chat-redesign, Property P8 (formatting utilities + no-PII).
 * Validates Requirement 1.2, 1.3, 3.4, 6.5.
 */

function makeConversation(
  id: number,
  overrides: Partial<WorkspaceConversationItem> = {}
): WorkspaceConversationItem {
  return {
    conversation_id: id,
    title: `Conversation ${id}`,
    preview: "",
    query_id: null,
    message_count: 1,
    created_at: "2026-01-01T00:00:00.000Z",
    last_message_at: "2026-01-01T00:00:00.000Z",
    folder_id: null,
    channel_id: null,
    is_favorite: false,
    ...overrides,
  };
}

describe("parsePromptText", () => {
  it("trims and nulls blank input", () => {
    expect(parsePromptText("  hi  ")).toBe("hi");
    expect(parsePromptText("   ")).toBeNull();
    expect(parsePromptText(null)).toBeNull();
    expect(parsePromptText(undefined)).toBeNull();
  });

  it("Property: result is null or a non-empty trimmed string", () => {
    fc.assert(
      fc.property(fc.string(), (raw) => {
        const result = parsePromptText(raw);
        if (result === null) return raw.trim().length === 0;
        return result === raw.trim() && result.length > 0;
      })
    );
  });
});

describe("parseTagsInput", () => {
  it("splits, trims, drops blanks, caps at 20", () => {
    expect(parseTagsInput("a, b ,, c")).toEqual(["a", "b", "c"]);
    const many = Array.from({ length: 50 }, (_, i) => `t${i}`).join(",");
    expect(parseTagsInput(many)).toHaveLength(20);
  });

  it("Property: never exceeds 20 and never includes blanks", () => {
    fc.assert(
      fc.property(fc.array(fc.string()), (parts) => {
        const tags = parseTagsInput(parts.join(","));
        return tags.length <= 20 && tags.every((t) => t.length > 0 && t === t.trim());
      })
    );
  });
});

describe("buildConversationPreview", () => {
  it("truncates long titles with an ellipsis", () => {
    const long = "x".repeat(200);
    const preview = buildConversationPreview(makeConversation(1, { title: long }));
    expect(preview.endsWith("...")).toBe(true);
    expect(preview.length).toBe(83);
  });

  it("falls back to a default label", () => {
    expect(buildConversationPreview(makeConversation(1, { title: "", preview: "" }))).toBe(
      "Conversation"
    );
  });
});

describe("toConversationTimestamp", () => {
  it("prefers last_message_at over created_at", () => {
    const item = makeConversation(1, {
      created_at: "2026-01-01T00:00:00.000Z",
      last_message_at: "2026-02-01T00:00:00.000Z",
    });
    expect(toConversationTimestamp(item)).toBe(Date.parse("2026-02-01T00:00:00.000Z"));
  });

  it("returns 0 for unparseable timestamps", () => {
    expect(toConversationTimestamp(makeConversation(1, { created_at: "", last_message_at: "" }))).toBe(0);
  });
});

describe("toDayKey", () => {
  const now = new Date(2026, 5, 16, 12, 0, 0);
  it("buckets relative to now", () => {
    expect(toDayKey(now.getTime(), now)).toBe("today");
    expect(toDayKey(new Date(2026, 5, 15, 9).getTime(), now)).toBe("yesterday");
    expect(toDayKey(new Date(2026, 5, 12).getTime(), now)).toBe("week");
    expect(toDayKey(new Date(2026, 4, 1).getTime(), now)).toBe("older");
    expect(toDayKey(0, now)).toBe("unknown");
  });

  it("Property: returns one of the known buckets for any finite input", () => {
    const buckets: ConversationDayBucket[] = ["today", "yesterday", "week", "older", "unknown"];
    fc.assert(
      fc.property(fc.integer(), (ms) => buckets.includes(toDayKey(ms, now)))
    );
  });
});

describe("formatConversationDayLabel", () => {
  it("localizes each bucket", () => {
    expect(formatConversationDayLabel("today", "en")).toBe("Today");
    expect(formatConversationDayLabel("today", "vi")).toBe("Hôm nay");
    expect(formatConversationDayLabel("older", "vi")).toBe("Cũ hơn");
  });
});

describe("asConversationId", () => {
  it("normalizes positive ids and rejects others", () => {
    expect(asConversationId(12.9)).toBe(12);
    expect(asConversationId(0)).toBeNull();
    expect(asConversationId(-3)).toBeNull();
    expect(asConversationId(null)).toBeNull();
    expect(asConversationId(Number.NaN)).toBeNull();
  });
});

describe("isNotFoundLikeError", () => {
  it("detects 404-like errors", () => {
    expect(isNotFoundLikeError(new Error("Resource not found"))).toBe(true);
    expect(isNotFoundLikeError(new Error("status 404"))).toBe(true);
    expect(isNotFoundLikeError(new Error("không tồn tại"))).toBe(true);
    expect(isNotFoundLikeError(new Error("boom"))).toBe(false);
    expect(isNotFoundLikeError("not an error")).toBe(false);
  });
});

describe("buildConversationMarkdownExport", () => {
  const turns: ConversationItem[] = [
    {
      id: "1",
      query: "Hello",
      createdAt: 0,
      result: { tier: "tier1", answer: "Hi there", debug: null },
    },
  ];

  it("is deterministic when the exported time is injected", () => {
    const a = buildConversationMarkdownExport("T", turns, "2026-01-01T00:00:00.000Z");
    const b = buildConversationMarkdownExport("T", turns, "2026-01-01T00:00:00.000Z");
    expect(a).toBe(b);
    expect(a).toContain("# T");
    expect(a).toContain("Hello");
    expect(a).toContain("Hi there");
  });

  it("uses a default title and placeholders for empty turns", () => {
    const md = buildConversationMarkdownExport(
      "",
      [{ id: "1", query: "", createdAt: 0, result: { tier: "tier1", answer: "", debug: null } }],
      "2026-01-01T00:00:00.000Z"
    );
    expect(md).toContain("CLARA Conversation Export");
    expect(md).toContain("_(empty)_");
  });
});

describe("mergeConversations", () => {
  it("dedupes by id with server winning and sorts newest-first", () => {
    const server = [
      makeConversation(1, { title: "server-1", last_message_at: "2026-03-01T00:00:00.000Z" }),
    ];
    const local = [
      makeConversation(1, { title: "local-1", last_message_at: "2026-01-01T00:00:00.000Z" }),
      makeConversation(2, { title: "local-2", last_message_at: "2026-05-01T00:00:00.000Z" }),
    ];
    const merged = mergeConversations(server, local);
    expect(merged).toHaveLength(2);
    expect(merged[0].conversation_id).toBe(2);
    const one = merged.find((c) => c.conversation_id === 1);
    expect(one?.title).toBe("server-1");
  });

  it("Property: never mutates inputs and has unique ids", () => {
    fc.assert(
      fc.property(
        fc.array(fc.integer({ min: 1, max: 50 }), { maxLength: 10 }),
        fc.array(fc.integer({ min: 1, max: 50 }), { maxLength: 10 }),
        (serverIds, localIds) => {
          const server = serverIds.map((id) => makeConversation(id));
          const local = localIds.map((id) => makeConversation(id));
          const serverCopy = JSON.stringify(server);
          const merged = mergeConversations(server, local);
          const ids = merged.map((c) => c.conversation_id);
          const unique = new Set(ids);
          return ids.length === unique.size && JSON.stringify(server) === serverCopy;
        }
      )
    );
  });
});

describe("isDegradedAnswer", () => {
  function tier2(debugPipeline?: string, fallbackUsed?: boolean): Tier2Result {
    return {
      tier: "tier2",
      answer: "a",
      citations: [],
      steps: [],
      flowStages: [],
      flowEvents: [],
      telemetry: {
        keywords: [],
        scores: [],
        docs: [],
        sourceReasoning: [],
        sourceAttempts: [],
        verificationMatrix: [],
        stageSpans: [],
        errors: [],
        traceMetadata: {},
      } as unknown as Tier2Result["telemetry"],
      visualAssets: [],
      chartSpecs: [],
      reasoningDigest: { items: [] } as unknown as Tier2Result["reasoningDigest"],
      tracedClaims: [],
      citationRegistry: [],
      debug: {
        pipeline: debugPipeline,
        stageCount: 0,
        flowEventCount: 0,
        telemetryKeywordCount: 0,
        telemetryDocCount: 0,
        telemetrySourceAttemptCount: 0,
        telemetryErrorCount: 0,
        crawlDomainCount: 0,
      },
      fallbackUsed,
    };
  }

  it("flags local-synth and fallback pipelines as degraded", () => {
    expect(isDegradedAnswer(tier2("local-synth-v1"))).toBe(true);
    expect(isDegradedAnswer(tier2("local_synth"))).toBe(true);
    expect(isDegradedAnswer(tier2("deepseek-fallback"))).toBe(true);
    expect(isDegradedAnswer(tier2(undefined, true))).toBe(true);
  });

  it("does not flag normal answers", () => {
    expect(isDegradedAnswer(tier2("rag_full"))).toBe(false);
    expect(isDegradedAnswer({ tier: "tier1", answer: "x", debug: null })).toBe(false);
    expect(isDegradedAnswer(null)).toBe(false);
  });
});
