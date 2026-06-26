import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import fc from "fast-check";

import {
  AnalyticsClient,
  isPiiKey,
  type AnalyticsConfig,
  type AnalyticsEvent,
  type AnalyticsTransport,
} from "@/lib/analytics";
import { ANALYTICS_EVENTS } from "@/lib/analytics/events";
import TelemetryPanel from "@/app/chat/_v2/components/TelemetryPanel";
import type { ResearchTier2Result } from "@/lib/research";
import type { Tier2Result } from "@/components/research/lib/research-page-types";
import type { UserRole } from "@/lib/auth-store";

/**
 * Feature: clara-chat-redesign, task 8.2 — rollout privacy/guardrail re-assertion.
 *
 * Design **Property P8 (No-PII client analytics)** / Requirement 8.5: analytics
 * payloads emitted by the v2 chat client contain NO query text / PII.
 *
 * Design **Property P10 (Consent / disclaimer / RBAC preserved)** /
 * Requirement 8.4: the rebuilt chat preserves consent gating on analytics, the
 * persistent medical disclaimer, and admin-only (RBAC) detailed telemetry.
 *
 * **Validates: Requirements 8.4, 8.5** (design Properties P8 and P10).
 *
 * The shell composes colocated hooks + heavy children; those are stubbed so no
 * API/SSE call runs (mirroring `ChatShell.test.tsx`). The real analytics
 * facade (`@/lib/analytics`) and the real role-gated `TelemetryPanel` are kept
 * un-mocked so the guardrails are asserted against the production code paths.
 */

// --- The v2 chat's analytics emitter, captured -----------------------------
// ChatShell calls `trackChatMessageSent({ mode, transport })`; we record every
// call so we can assert the free-text query is NEVER passed through it.
const trackChatMessageSent = vi.hoisted(() => vi.fn());

vi.mock("@/lib/analytics/events", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/analytics/events")>(
      "@/lib/analytics/events",
    );
  return { ...actual, trackChatMessageSent };
});

// --- Hook stubs (no network / SSE) -----------------------------------------
const loadConversations = vi.fn().mockResolvedValue([]);
const loadNotes = vi.fn().mockResolvedValue(undefined);
const loadShares = vi.fn().mockResolvedValue(undefined);
const streamRun = vi
  .fn()
  .mockResolvedValue({ tier: "tier1", answer: "ok", debug: null });

vi.mock("@/app/chat/_v2/hooks/useConversations", () => ({
  useConversations: () => ({
    conversations: [],
    merged: [],
    localIds: new Set<number>(),
    activeId: null,
    isLoading: false,
    apiUnavailable: false,
    load: loadConversations,
    select: vi.fn(),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    setFavorite: vi.fn(),
    setFolder: vi.fn(),
    upsertLocal: vi.fn(),
    removeLocal: vi.fn(),
    patch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatTurns", () => ({
  useChatTurns: () => ({
    turns: [],
    cachedTurns: () => [],
    setActive: vi.fn(),
    load: vi.fn().mockResolvedValue(undefined),
    clear: vi.fn(),
    appendTurn: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useChatStream", () => ({
  useChatStream: () => ({
    isRunning: false,
    statusNote: "",
    run: streamRun,
    cancel: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useWorkspace", () => ({
  useWorkspace: () => ({
    notes: [],
    shares: [],
    searchResults: null,
    loadNotes,
    loadShares,
    saveNote: vi.fn(),
    removeNote: vi.fn(),
    share: vi.fn(),
    revokeShare: vi.fn(),
    exportConversation: vi.fn(),
    search: vi.fn(),
    clearSearch: vi.fn(),
  }),
}));

vi.mock("@/app/chat/_v2/hooks/useCommandPalette", () => ({
  useCommandPalette: () => ({
    isOpen: false,
    open: vi.fn(),
    close: vi.fn(),
    query: "",
    setQuery: vi.fn(),
    results: [],
    activeIndex: 0,
    setActiveIndex: vi.fn(),
    runActive: vi.fn(),
  }),
}));

// Heavy child components → light sentinels. The real Composer is kept so the
// submit flow (and thus the analytics emission) actually runs.
vi.mock("@/app/chat/_v2/components/ConversationSidebar", () => ({
  default: () => <div data-testid="sidebar" />,
}));
vi.mock("@/app/chat/_v2/components/MessageLog", () => ({
  default: () => <div data-testid="message-log" />,
}));
vi.mock("@/app/chat/_v2/components/CommandPaletteLazy", () => ({
  default: () => <div data-testid="command-palette" />,
}));
vi.mock("@/app/chat/_v2/components/WorkspaceDrawerLazy", () => ({
  default: () => <div data-testid="workspace-drawer" />,
}));
vi.mock("@/app/chat/_v2/components/TelemetryPanelLazy", () => ({
  default: () => <div data-testid="telemetry-panel-lazy" />,
}));

// Lib modules imported at the top of ChatShell — stubbed to avoid side effects.
vi.mock("@/lib/auth-store", () => ({ getRole: () => "normal" }));
vi.mock("@/lib/user-facing-text", () => ({
  sanitizeUpstreamError: (m: string) => m,
  toModeLabel: (m: string) => m,
  stripTelemetryLabels: (m: string) => m,
}));
vi.mock("@/lib/ui-language", () => ({
  getStoredUILanguage: () => "en",
  onUILanguageChange: () => vi.fn(),
}));
vi.mock("@/lib/research", () => ({
  resolveChatTransport: () => "tier1_chat",
  appendResearchConversationMessage: vi.fn().mockResolvedValue({ id: 1 }),
  createResearchConversation: vi.fn().mockResolvedValue({ id: 1 }),
  listResearchConversationMessages: vi.fn().mockResolvedValue([]),
}));
vi.mock("@/lib/workspace", () => ({
  searchWorkspace: vi.fn().mockResolvedValue({ conversations: [] }),
  updateWorkspaceConversationMeta: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("@/components/research/lib/research-page-helpers", () => ({
  createConversationItem: (query: string, result: unknown) => ({
    id: "turn-1",
    query,
    result,
    createdAt: Date.now(),
  }),
}));

async function renderShell() {
  const mod = await import("@/app/chat/_v2/ChatShell");
  const ChatShell = mod.default;
  const utils = render(<ChatShell />);
  await waitFor(() => expect(loadConversations).toHaveBeenCalled());
  return utils;
}

/** Submits the composer with `query`, then waits for the analytics emission. */
async function submitQuery(query: string) {
  const textarea = screen.getByLabelText(/your medical question/i);
  fireEvent.change(textarea, { target: { value: query } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(trackChatMessageSent).toHaveBeenCalled());
}

beforeEach(() => {
  vi.clearAllMocks();
  loadConversations.mockResolvedValue([]);
  streamRun.mockResolvedValue({ tier: "tier1", answer: "ok", debug: null });
});

afterEach(() => {
  vi.resetModules();
});

// ---------------------------------------------------------------------------
// Property P8 / Req 8.5 — No-PII client analytics
// ---------------------------------------------------------------------------

describe("v2 chat analytics carry no PII (Property P8 / Req 8.5)", () => {
  it("emits chat_message_sent with only coarse mode/transport — never the query", async () => {
    await renderShell();
    const piiQuery =
      "Patient Nguyen Van A (nguyen.van.a@example.com) takes warfarin 5mg for atrial fibrillation";
    await submitQuery(piiQuery);

    expect(trackChatMessageSent).toHaveBeenCalledTimes(1);
    const [payload] = trackChatMessageSent.mock.calls[0];
    // Only the coarse, non-identifying signals are passed.
    expect(Object.keys(payload as object).sort()).toEqual(["mode", "transport"]);
    expect(payload).toEqual({ mode: "fast", transport: "tier1_chat" });

    // The free-text query (and every PII token in it) is absent from every
    // argument the v2 chat passes to the analytics emitter.
    const serialized = JSON.stringify(trackChatMessageSent.mock.calls);
    for (const token of [
      "Nguyen Van A",
      "nguyen.van.a@example.com",
      "warfarin",
      "atrial fibrillation",
    ]) {
      expect(serialized).not.toContain(token);
    }
  });

  it("never forwards the query for arbitrary inputs (property)", async () => {
    await renderShell();
    await fc.assert(
      fc.asyncProperty(
        fc.oneof(
          fc.string({ minLength: 1, maxLength: 80 }),
          fc.emailAddress(),
          fc.lorem({ maxCount: 6 }),
        ),
        async (rawQuery) => {
          // Keep a non-empty, trimmed message so submit actually fires.
          const query = `q ${rawQuery}`;
          trackChatMessageSent.mockClear();
          await submitQuery(query);

          for (const call of trackChatMessageSent.mock.calls) {
            const props = (call[0] ?? {}) as Record<string, unknown>;
            // Coarse keys only — no PII keys ever appear.
            for (const key of Object.keys(props)) {
              expect(isPiiKey(key)).toBe(false);
            }
            // The payload is the SAME coarse object regardless of the query
            // content — i.e. it is provably independent of (and so cannot
            // carry) any query text or PII.
            expect(props).toEqual({ mode: "fast", transport: "tier1_chat" });
          }
        },
      ),
      { numRuns: 25 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property P8 / Req 8.5 — the analytics channel itself strips PII (defense in depth)
// ---------------------------------------------------------------------------

/** Transport spy: records everything the facade would transmit off-device. */
class RecordingTransport implements AnalyticsTransport {
  initCalls = 0;
  identified: string[] = [];
  captured: AnalyticsEvent[] = [];
  init(): void {
    this.initCalls += 1;
  }
  identify(distinctId: string): void {
    this.identified.push(distinctId);
  }
  capture(event: AnalyticsEvent): void {
    this.captured.push(event);
  }
  get totalTransmissions(): number {
    return this.identified.length + this.captured.length;
  }
}

const CONFIGURED: AnalyticsConfig = { provider: "posthog", key: "phc_test_key" };

describe("chat analytics channel strips PII before transmit (Property P8 / Req 8.5)", () => {
  it("Property: a chat_message_sent payload never transmits a query, even if a buggy caller attaches one", () => {
    const queryKeyArb = fc.constantFrom(
      "query",
      "message",
      "prompt",
      "free_text_query",
      "search_query",
    );
    fc.assert(
      fc.property(
        fc.string({ minLength: 3, maxLength: 80 }),
        fc.constantFrom("fast", "deep", "deep_beta"),
        fc.constantFrom("tier1_chat", "tier2_job"),
        queryKeyArb,
        (query, mode, transport, leakKey) => {
          const transport_ = new RecordingTransport();
          const client = new AnalyticsClient({
            config: CONFIGURED,
            transport: transport_,
            consent: true,
          });
          // The coarse payload the v2 chat sends, plus a hypothetical leak that
          // the guardrail must scrub before anything leaves the device.
          client.track(ANALYTICS_EVENTS.chatMessageSent, {
            surface: "chat",
            mode,
            transport,
            [leakKey]: query,
          });

          expect(transport_.captured).toHaveLength(1);
          const props = transport_.captured[0].props ?? {};
          // No PII-flagged key survives, and the query text is gone.
          for (const key of Object.keys(props)) {
            expect(isPiiKey(key)).toBe(false);
          }
          expect(JSON.stringify(props)).not.toContain(query);
          // Coarse signals are preserved.
          expect(props.surface).toBe("chat");
          expect(props.mode).toBe(mode);
          expect(props.transport).toBe(transport);
        },
      ),
      { numRuns: 200 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property P10 / Req 8.4 — consent gating preserved
// ---------------------------------------------------------------------------

describe("consent gating preserved for chat analytics (Property P10 / Req 8.4)", () => {
  it("suppresses chat_message_sent until consent is granted, then transmits", () => {
    const transport = new RecordingTransport();
    const client = new AnalyticsClient({
      config: CONFIGURED,
      transport,
      consent: false,
    });

    client.track(ANALYTICS_EVENTS.chatMessageSent, {
      surface: "chat",
      mode: "fast",
      transport: "tier1_chat",
    });
    expect(transport.totalTransmissions).toBe(0);

    client.setConsent(true);
    client.track(ANALYTICS_EVENTS.chatMessageSent, {
      surface: "chat",
      mode: "fast",
      transport: "tier1_chat",
    });
    expect(transport.captured).toHaveLength(1);
    expect(transport.captured[0].name).toBe(ANALYTICS_EVENTS.chatMessageSent);
  });

  it("Property: configured-but-no-consent yields zero transmissions for any chat-event stream", () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.record({
            mode: fc.constantFrom("fast", "deep", "deep_beta"),
            transport: fc.constantFrom("tier1_chat", "tier2_job"),
          }),
          { maxLength: 12 },
        ),
        (events) => {
          const transport = new RecordingTransport();
          const client = new AnalyticsClient({
            config: CONFIGURED,
            transport,
            consent: false,
          });
          for (const event of events) {
            client.track(ANALYTICS_EVENTS.chatMessageSent, {
              surface: "chat",
              ...event,
            });
          }
          return transport.totalTransmissions === 0;
        },
      ),
      { numRuns: 200 },
    );
  });
});

// ---------------------------------------------------------------------------
// Property P10 / Req 8.4 — persistent medical disclaimer preserved
// ---------------------------------------------------------------------------

describe("medical disclaimer preserved in v2 (Property P10 / Req 8.4)", () => {
  it("renders the persistent medical disclaimer note", async () => {
    await renderShell();
    const disclaimer = screen.getByText(/not a replacement for a clinician/i);
    expect(disclaimer).toBeInTheDocument();
    // It is exposed as a persistent, non-alert note (always visible).
    expect(disclaimer).toHaveAttribute("role", "note");
  });
});

// ---------------------------------------------------------------------------
// Property P10 / Req 8.4 + 6.6 — RBAC: admin-only detailed telemetry preserved
// ---------------------------------------------------------------------------

function emptyTelemetry(): ResearchTier2Result["telemetry"] {
  return {
    keywords: [],
    scores: [],
    docs: [],
    sourceReasoning: [],
    sourceAttempts: [],
    verificationMatrix: [],
    stageSpans: [],
    errors: [],
    traceMetadata: {},
  } as unknown as ResearchTier2Result["telemetry"];
}

function makeTier2(): Tier2Result {
  return {
    tier: "tier2",
    answer: "An answer",
    citations: [],
    steps: [],
    flowStages: [],
    flowEvents: [],
    telemetry: emptyTelemetry(),
    visualAssets: [],
    chartSpecs: [],
    reasoningDigest: {
      items: [],
    } as unknown as ResearchTier2Result["reasoningDigest"],
    tracedClaims: [],
    citationRegistry: [],
    debug: {
      stageCount: 0,
      flowEventCount: 0,
      telemetryKeywordCount: 0,
      telemetryDocCount: 0,
      telemetrySourceAttemptCount: 0,
      telemetryErrorCount: 0,
      crawlDomainCount: 0,
    } as unknown as ResearchTier2Result["debug"],
  } as Tier2Result;
}

describe("RBAC preserved: detailed telemetry is admin-only (Property P10 / Req 8.4, 6.6)", () => {
  it("renders detailed telemetry for an admin", () => {
    render(<TelemetryPanel role="admin" result={makeTier2()} uiLanguage="en" />);
    expect(
      screen.getByRole("complementary", { name: /telemetry/i }),
    ).toBeInTheDocument();
  });

  it.each(["normal", "researcher", "doctor"] as const)(
    "renders nothing for non-admin role=%s",
    (role: UserRole) => {
      const { container } = render(
        <TelemetryPanel role={role} result={makeTier2()} uiLanguage="en" />,
      );
      expect(container.querySelector("[aria-label]")).toBeNull();
    },
  );
});
