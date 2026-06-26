import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";

/**
 * Feature: clara-chat-redesign, Property P2/P4; Requirement 3.1–3.5.
 *
 * `useChatStream` wraps the EXISTING transport unchanged (Requirement 8.3). It
 * must:
 *  - resolve a normalized result exactly once on the fast (tier1) path,
 *  - fall back to the non-streaming endpoint when the token stream errors so a
 *    turn is never lost (Property P4),
 *  - run the tier2 job path via the existing runner for deep/deep_beta,
 *  - expose `status` and a working `cancel()` (Requirement 3.5).
 */

const sendChatMessage = vi.fn();
const streamChatMessage = vi.fn();
const getChatReply = vi.fn();
const getChatIntentDebug = vi.fn(() => null);
const resolveChatTransport = vi.fn();
const normalizeResearchTier2 = vi.fn();
const normalizeResearchTier2JobProgress = vi.fn(() => ({ statusNote: "" }));
const executeResearchTier2Job = vi.fn();

vi.mock("@/lib/chat", () => ({
  sendChatMessage,
  streamChatMessage,
  getChatReply,
  getChatIntentDebug,
}));

vi.mock("@/lib/user-facing-text", () => ({
  stripTelemetryLabels: (value: string) => value,
}));

vi.mock("@/lib/research", () => ({
  resolveChatTransport,
  normalizeResearchTier2,
  normalizeResearchTier2JobProgress,
}));

vi.mock("@/lib/research-tier2-job-runner", () => ({
  executeResearchTier2Job,
}));

async function loadHook() {
  const mod = await import("@/app/chat/_v2/hooks/useChatStream");
  return mod.useChatStream;
}

const FAST_OPTS = {
  mode: "fast" as const,
  retrievalStackMode: "auto" as const,
  personalMode: false,
  uiLanguage: "vi" as const,
};

const DEEP_OPTS = { ...FAST_OPTS, mode: "deep" as const };

afterEach(() => {
  vi.clearAllMocks();
  vi.resetModules();
});

describe("useChatStream — fast (tier1) path", () => {
  it("resolves the streamed answer exactly once and ends in done", async () => {
    resolveChatTransport.mockReturnValue("tier1_chat");
    streamChatMessage.mockImplementation(async (_msg: string, handlers) => {
      handlers.onToken?.("Xin ");
      handlers.onToken?.("chào");
      handlers.onDone?.({ reply: "Xin chào" });
    });
    getChatReply.mockReturnValue("Xin chào");

    const useChatStream = await loadHook();
    const { result } = renderHook(() => useChatStream());

    let resolved: Awaited<ReturnType<typeof result.current.run>> | null = null;
    await act(async () => {
      resolved = await result.current.run("hello", FAST_OPTS);
    });

    expect(resolved).toEqual({ tier: "tier1", answer: "Xin chào", debug: null });
    expect(sendChatMessage).not.toHaveBeenCalled();
    await waitFor(() => expect(result.current.status).toBe("done"));
  });

  it("falls back to the non-streaming endpoint when the stream errors (no turn loss)", async () => {
    resolveChatTransport.mockReturnValue("tier1_chat");
    streamChatMessage.mockRejectedValue(new Error("stream broke"));
    sendChatMessage.mockResolvedValue({ reply: "fallback answer" });
    getChatReply.mockReturnValue("fallback answer");

    const useChatStream = await loadHook();
    const { result } = renderHook(() => useChatStream());

    let resolved: Awaited<ReturnType<typeof result.current.run>> | null = null;
    await act(async () => {
      resolved = await result.current.run("hello", FAST_OPTS);
    });

    expect(sendChatMessage).toHaveBeenCalledTimes(1);
    expect(resolved).toEqual({
      tier: "tier1",
      answer: "fallback answer",
      debug: null,
    });
    await waitFor(() => expect(result.current.status).toBe("done"));
  });
});

describe("useChatStream — deep (tier2 job) path", () => {
  it("runs the existing job runner and returns the normalized tier2 result", async () => {
    resolveChatTransport.mockReturnValue("tier2_job");
    executeResearchTier2Job.mockResolvedValue({ finalPayload: { answer: "x" } });
    normalizeResearchTier2.mockReturnValue({
      answer: "deep answer",
      citations: [{ title: "c" }],
    });

    const useChatStream = await loadHook();
    const { result } = renderHook(() => useChatStream());

    let resolved: Awaited<ReturnType<typeof result.current.run>> | null = null;
    await act(async () => {
      resolved = await result.current.run("deep q", DEEP_OPTS);
    });

    expect(executeResearchTier2Job).toHaveBeenCalledTimes(1);
    expect(resolved).toMatchObject({ tier: "tier2", answer: "deep answer" });
    await waitFor(() => expect(result.current.status).toBe("done"));
  });
});

describe("useChatStream — cancel", () => {
  it("cancel() moves status to cancelled", async () => {
    const useChatStream = await loadHook();
    const { result } = renderHook(() => useChatStream());

    act(() => {
      result.current.cancel();
    });

    expect(result.current.status).toBe("cancelled");
    expect(result.current.jobId).toBeNull();
  });
});
