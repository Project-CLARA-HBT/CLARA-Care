import { afterEach, describe, expect, it, vi } from "vitest";

import {
  streamScribe,
  type ScribeStreamDone,
  type ScribeStreamPartial,
  type ScribeStreamSegment,
} from "@/lib/scribe";

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
  it("dispatches start/partial/segment/token/done and reconstructs transcript", async () => {
    const frames = [
      "event: start\ndata: {}\n\n",
      'event: partial\ndata: {"index":0,"text":"bệnh"}\n\n',
      'event: segment\ndata: {"index":0,"text":"bệnh nhân ho","speaker":"patient","degraded":false}\n\n',
      'event: token\ndata: {"text":"S "}\n\n',
      'event: token\ndata: {"text":"section"}\n\n',
      'event: done\ndata: {"transcript":"bệnh nhân ho","segments":[{"index":0,"text":"bệnh nhân ho","speaker":"patient","start_ms":0,"end_ms":0,"degraded":false}],"note":{"template_id":"soap","sections":{"subjective":"S section"}},"asr_meta":{"provider":"fake","language":"vi","degraded_count":0}}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));

    const partials: ScribeStreamPartial[] = [];
    const segments: ScribeStreamSegment[] = [];
    const tokens: string[] = [];
    let done: ScribeStreamDone | null = null;
    let started = false;

    await streamScribe(7, new Blob([new Uint8Array([1, 2, 3])]), {
      language: "vi",
      templateId: "soap",
      onStart: () => (started = true),
      onPartial: (p) => partials.push(p),
      onSegment: (s) => segments.push(s),
      onToken: (t) => tokens.push(t),
      onDone: (r) => (done = r),
    });

    expect(started).toBe(true);
    expect(partials).toHaveLength(1);
    expect(partials[0].text).toBe("bệnh");
    expect(segments).toHaveLength(1);
    expect(segments[0].speaker).toBe("patient");
    expect(tokens.join("")).toBe("S section");
    expect(done).not.toBeNull();
    const result = done as unknown as ScribeStreamDone;
    expect(result.transcript).toBe("bệnh nhân ho");
    expect(result.asr_meta?.provider).toBe("fake");
    expect(result.note?.template_id).toBe("soap");
  });

  it("POSTs multipart audio with language + template_id to the session stream URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseStream(["event: done\ndata: {}\n\n"]));
    vi.stubGlobal("fetch", fetchMock);

    await streamScribe(42, new Blob([new Uint8Array([9])]), {
      filename: "enc.webm",
      language: "vi",
      templateId: "hpi",
      onDone: () => undefined,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/scribe/sessions/42/stream");
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("include");
    const headers = init.headers as Record<string, string>;
    expect(headers.Accept).toBe("text/event-stream");
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(headers["X-CSRF-Token"]).toBe("csrf");
    const form = init.body as FormData;
    expect(form).toBeInstanceOf(FormData);
    expect(form.get("language")).toBe("vi");
    expect(form.get("template_id")).toBe("hpi");
    expect(form.get("audio_file")).toBeInstanceOf(Blob);
  });

  it("passes degraded segments through verbatim without fabricating text", async () => {
    const frames = [
      "event: start\ndata: {}\n\n",
      'event: partial\ndata: {"index":0,"text":"","degraded":true}\n\n',
      'event: segment\ndata: {"index":0,"text":"","speaker":"unknown","start_ms":0,"end_ms":0,"degraded":true}\n\n',
      'event: done\ndata: {"transcript":"","segments":[],"asr_meta":{"degraded_count":1}}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));

    const partials: ScribeStreamPartial[] = [];
    const segments: ScribeStreamSegment[] = [];

    await streamScribe(7, new Blob([]), {
      onPartial: (p) => partials.push(p),
      onSegment: (s) => segments.push(s),
      onDone: () => undefined,
    });

    expect(partials[0].degraded).toBe(true);
    expect(partials[0].text).toBe("");
    expect(segments).toHaveLength(1);
    expect(segments[0].degraded).toBe(true);
    expect(segments[0].text).toBe("");
  });

  it("fires onError on a terminal error frame naming the failure class", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseStream(['event: error\ndata: {"message":"scribe streaming unavailable","error":"TimeoutError"}\n\n'])
      )
    );
    let msg = "";
    await streamScribe(7, new Blob([]), { onError: (m) => (msg = m) });
    expect(msg).toBe("scribe streaming unavailable");
  });

  it("throws when the stream ends without a terminal event", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseStream(["event: start\ndata: {}\n\n"]))
    );
    await expect(streamScribe(7, new Blob([]), {})).rejects.toThrow(/terminal/);
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 404 })));
    await expect(streamScribe(7, new Blob([]), {})).rejects.toThrow();
  });
});
