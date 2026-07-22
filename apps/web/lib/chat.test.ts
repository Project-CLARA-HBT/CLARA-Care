import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getChatReply,
  getClinicalAnswerPackage,
  streamChatMessage,
  type ChatStreamStep,
} from "@/lib/chat";

vi.mock("@/lib/http-client", () => ({ default: { post: vi.fn() } }));
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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("getChatReply", () => {
  it("prefers reply then answer", () => {
    expect(getChatReply({ reply: "a", answer: "b" })).toBe("a");
    expect(getChatReply({ answer: "b" })).toBe("b");
    expect(getChatReply({})).toBeNull();
  });
});

describe("getClinicalAnswerPackage", () => {
  const clinicalPackage = {
    schema_version: "1.0",
    protocol: "clinical_answer",
    triage: { level: "routine", emergency: false, policy_action: "allow" },
    claim_support: { status: "supported", evidence_ids: ["E1"] },
    evidence_ledger: [],
    uncertainty: { level: "low", reasons: [] },
    missing_information: [],
    next_actions: [],
    provenance: { evidence_count: 0, fallback_used: false },
  };

  it("reads both direct streaming and nested API envelopes", () => {
    expect(getClinicalAnswerPackage({ clinical_answer_package: clinicalPackage })).toBe(
      clinicalPackage
    );
    expect(getClinicalAnswerPackage({ ml: { clinical_answer_package: clinicalPackage } })).toBe(
      clinicalPackage
    );
    expect(getClinicalAnswerPackage({})).toBeNull();
  });
});

describe("streamChatMessage", () => {
  it("dispatches start/step/token/done and reconstructs the answer", async () => {
    const frames = [
      "event: start\ndata: {}\n\n",
      'event: step\ndata: {"stage":"route","status":"completed"}\n\n',
      'event: token\ndata: {"text":"Hello "}\n\n',
      'event: token\ndata: {"text":"world"}\n\n',
      'event: done\ndata: {"answer":"Hello world","model_used":"m"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));

    const steps: ChatStreamStep[] = [];
    const tokens: string[] = [];
    let started = false;
    let done: Record<string, unknown> | null = null;

    await streamChatMessage("hi", {
      onStart: () => {
        started = true;
      },
      onStep: (s) => steps.push(s),
      onToken: (t) => tokens.push(t),
      onDone: (r) => {
        done = r;
      },
    });

    expect(started).toBe(true);
    expect(steps).toHaveLength(1);
    expect(steps[0].stage).toBe("route");
    expect(tokens.join("")).toBe("Hello world");
    expect(done).not.toBeNull();
    expect((done as Record<string, unknown>).model_used).toBe("m");
  });

  it("handles frames split across chunk boundaries", async () => {
    const frames = [
      "event: token\nda",
      'ta: {"text":"AB"}\n\nevent: ',
      'done\ndata: {"answer":"AB"}\n\n',
    ];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));
    const tokens: string[] = [];
    let done = false;
    await streamChatMessage("hi", {
      onToken: (t) => tokens.push(t),
      onDone: () => {
        done = true;
      },
    });
    expect(tokens.join("")).toBe("AB");
    expect(done).toBe(true);
  });

  it("fires onError on a terminal error frame", async () => {
    const frames = ['event: error\ndata: {"message":"boom"}\n\n'];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseStream(frames)));
    let errMsg = "";
    await streamChatMessage("hi", { onError: (m) => (errMsg = m) });
    expect(errMsg).toBe("boom");
  });

  it("throws when the HTTP response is not ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));
    await expect(streamChatMessage("hi", {})).rejects.toThrow();
  });
});
