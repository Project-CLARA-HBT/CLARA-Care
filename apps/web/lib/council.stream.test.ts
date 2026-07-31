import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isCouncilStreamingEnabled,
  streamCouncilRun,
  type CouncilStreamStage,
} from "@/lib/council";

vi.mock("@/lib/http-client", () => ({ default: { post: vi.fn(), get: vi.fn(), patch: vi.fn() } }));
vi.mock("@/lib/auth-store", () => ({
  getAccessToken: () => "test-token",
  getCsrfToken: () => "csrf",
}));

function sseStream(frames: string[], status = 200): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(body, { status, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
});

describe("isCouncilStreamingEnabled", () => {
  it("defaults to off and accepts common truthy values", () => {
    vi.stubEnv("NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED", "");
    expect(isCouncilStreamingEnabled()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED", "false");
    expect(isCouncilStreamingEnabled()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED", "true");
    expect(isCouncilStreamingEnabled()).toBe(true);
    vi.stubEnv("NEXT_PUBLIC_COUNCIL_STREAMING_ENABLED", "1");
    expect(isCouncilStreamingEnabled()).toBe(true);
  });
});

describe("streamCouncilRun", () => {
  it("dispatches ordered stage events then the terminal result", async () => {
    const frames = [
      'event: stage\ndata: {"sequence":1,"step":"intake_normalized"}\n\n',
      'event: stage\ndata: {"sequence":2,"step":"specialist_assessment"}\n\n',
      'event: result\ndata: {"final_recommendation":"done","is_emergency":false}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));

    const stages: CouncilStreamStage[] = [];
    let result: Record<string, unknown> | null = null;
    let errorMsg: string | null = null;

    await streamCouncilRun(7, { request: { symptoms: ["x"] } }, {
      onStage: (s) => stages.push(s),
      onResult: (r) => {
        result = r as Record<string, unknown>;
      },
      onError: (m) => {
        errorMsg = m;
      },
    });

    expect(errorMsg).toBeNull();
    expect(stages.map((s) => s.sequence)).toEqual([1, 2]);
    expect(stages[0].step).toBe("intake_normalized");
    expect(stages[1]).toEqual({ sequence: 2, step: "specialist_assessment" });
    expect(result).not.toBeNull();
    expect(
      (result as unknown as Record<string, unknown>).final_recommendation,
    ).toBe("done");
  });

  it("posts to the case stream URL with bearer + CSRF headers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseStream(['event: result\ndata: {"ok":true}\n\n'])
    );
    vi.stubGlobal("fetch", fetchMock);

    await streamCouncilRun(42, {}, { onResult: () => {} });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/council/cases/42/run/stream");
    expect(init.method).toBe("POST");
    const headers = init.headers as Record<string, string>;
    expect(headers.Accept).toBe("text/event-stream");
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(headers["X-CSRF-Token"]).toBe("csrf");
  });

  it("dispatches a terminal error event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseStream(['event: error\ndata: {"message":"upstream_unavailable"}\n\n']))
    );

    let errorMsg: string | null = null;
    await streamCouncilRun(1, {}, { onError: (m) => (errorMsg = m) });
    expect(errorMsg).toBe("upstream_unavailable");
  });

  it("throws on a non-ok response so callers can fall back to blocking run", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream([], 404)));
    await expect(streamCouncilRun(1, {})).rejects.toThrow(/status=404/);
  });

  it("throws when the stream ends without a terminal event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseStream(['event: stage\ndata: {"sequence":1,"step":"intake_normalized"}\n\n']))
    );
    await expect(streamCouncilRun(1, {})).rejects.toThrow(/without a terminal event/);
  });
});
