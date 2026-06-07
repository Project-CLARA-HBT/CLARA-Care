import { afterEach, describe, expect, it, vi } from "vitest";

import { streamScribe, type ScribeStreamSegment } from "@/lib/scribe";

vi.mock("@/lib/http-client", () => ({ default: { post: vi.fn(), get: vi.fn(), patch: vi.fn() } }));
vi.mock("@/lib/auth-store", () => ({
  getAccessToken: () => "test-token",
  getCsrfToken: () => "csrf",
}));

function sseStream(frames: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.restoreAllMocks());

describe("streamScribe", () => {
  it("dispatches start/segment/token/done and reconstructs transcript", async () => {
    const frames = [
      "event: start\ndata: {}\n\n",
      'event: segment\ndata: {"index":0,"text":"bệnh nhân ho","speaker":"patient","degraded":false}\n\n',
      'event: token\ndata: {"text":"S "}\n\n',
      'event: token\ndata: {"text":"section"}\n\n',
      'event: done\ndata: {"transcript":"bệnh nhân ho","note":{"template_id":"soap"}}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));

    const segments: ScribeStreamSegment[] = [];
    const tokens: string[] = [];
    let done: Record<string, unknown> | null = null;
    let started = false;

    await streamScribe(7, new Blob([new Uint8Array([1, 2, 3])]), {
      onStart: () => (started = true),
      onSegment: (s) => segments.push(s),
      onToken: (t) => tokens.push(t),
      onDone: (r) => (done = r),
    });

    expect(started).toBe(true);
    expect(segments).toHaveLength(1);
    expect(segments[0].speaker).toBe("patient");
    expect(tokens.join("")).toBe("S section");
    expect(done).not.toBeNull();
    expect((done as Record<string, unknown>).transcript).toBe("bệnh nhân ho");
  });

  it("fires onError on a terminal error frame", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseStream(['event: error\ndata: {"message":"boom"}\n\n']))
    );
    let msg = "";
    await streamScribe(7, new Blob([]), { onError: (m) => (msg = m) });
    expect(msg).toBe("boom");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    await expect(streamScribe(7, new Blob([]), {})).rejects.toThrow();
  });
});
