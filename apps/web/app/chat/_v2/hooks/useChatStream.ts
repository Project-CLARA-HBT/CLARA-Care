"use client";

import { useCallback, useRef, useState } from "react";

import { getChatIntentDebug, getChatReply, sendChatMessage, streamChatMessage } from "@/lib/chat";
import { stripTelemetryLabels } from "@/lib/user-facing-text";
import {
  ResearchExecutionMode,
  ResearchRetrievalStackMode,
  normalizeResearchTier2,
  normalizeResearchTier2JobProgress,
  resolveChatTransport,
} from "@/lib/research";
import { executeResearchTier2Job } from "@/lib/research-tier2-job-runner";
import type { UILanguage } from "@/lib/ui-language";
import type { ResearchResult } from "@/components/research/lib/research-page-types";

/**
 * Chat streaming/transport hook for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Wraps the EXISTING transport (`lib/chat` fast stream + `research-tier2-job-runner`
 * job poll/SSE) unchanged (design Property P2, Requirement 8.3). It exposes a
 * single `run(...)` that resolves to a normalized `ResearchResult` exactly once
 * (no turn loss — Property P4), plus `status`, a live `statusNote`, the active
 * `jobId`, and `cancel()` (Requirement 3.1–3.5).
 *
 * It performs NO persistence and NO state mutation beyond its own status — the
 * caller owns turn persistence so the "persist final turn exactly once"
 * invariant stays in one place.
 */

export type ChatStreamStatus = "idle" | "streaming" | "done" | "error" | "cancelled";

export type ChatRunOptions = {
  mode: ResearchExecutionMode;
  retrievalStackMode: ResearchRetrievalStackMode;
  personalMode: boolean;
  uiLanguage: UILanguage;
};

export type UseChatStream = {
  status: ChatStreamStatus;
  statusNote: string;
  jobId: string | null;
  isRunning: boolean;
  run: (message: string, options: ChatRunOptions) => Promise<ResearchResult>;
  cancel: () => void;
};

export function useChatStream(): UseChatStream {
  const [status, setStatus] = useState<ChatStreamStatus>("idle");
  const [statusNote, setStatusNote] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const cancelledRef = useRef(false);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    abortRef.current?.abort();
    setStatus("cancelled");
    setStatusNote("");
    setJobId(null);
  }, []);

  const run = useCallback(
    async (message: string, options: ChatRunOptions): Promise<ResearchResult> => {
      cancelledRef.current = false;
      setStatus("streaming");
      setStatusNote("");
      const transport = resolveChatTransport(options.mode);

      try {
        if (transport === "tier1_chat") {
          // Fast path: stream tokens with a non-streaming fallback. The terminal
          // `done` frame yields the structured result; otherwise we retry once
          // via the non-streaming endpoint so a turn is never lost.
          const controller = new AbortController();
          abortRef.current = controller;
          let streamedAnswer = "";
          let donePayload:
            | (Awaited<ReturnType<typeof sendChatMessage>> & Record<string, unknown>)
            | null = null;

          try {
            setJobId("chat-stream");
            await streamChatMessage(message, {
              signal: controller.signal,
              onStart: () => setStatusNote(""),
              onStep: (step) => {
                const label = String(step.stage ?? "").trim();
                const statusText = String(step.status ?? "").trim();
                if (label) {
                  setStatusNote(stripTelemetryLabels(statusText ? `${label} · ${statusText}` : label));
                }
              },
              onToken: (text) => {
                streamedAnswer += text;
                setStatusNote(streamedAnswer);
              },
              onDone: (result) => {
                donePayload = result;
              },
              onError: (msg) => {
                throw new Error(msg || "chat stream error");
              },
            });
          } catch {
            donePayload = null; // force non-streaming fallback
          }

          if (cancelledRef.current) {
            throw new DOMException("cancelled", "AbortError");
          }

          const chatPayload = donePayload ?? (await sendChatMessage(message));
          const reply = getChatReply(chatPayload) ?? (streamedAnswer.trim() || null);
          if (!reply) {
            throw new Error("Chưa có phản hồi chat hợp lệ.");
          }
          setStatus("done");
          setJobId(null);
          setStatusNote("");
          return { tier: "tier1", answer: reply, debug: getChatIntentDebug(chatPayload) };
        }

        // Deep / deep_beta: tier2 job create + poll/SSE via the existing runner.
        const { finalPayload } = await executeResearchTier2Job(message, {
          researchMode: options.mode,
          retrievalStackMode: options.retrievalStackMode,
          personalMode: options.personalMode,
          uiLanguage: options.uiLanguage,
          onJobCreated: (job) => setJobId(job.job_id),
          onSnapshot: (snapshot) => {
            const progress = normalizeResearchTier2JobProgress(snapshot.progress);
            setStatusNote(stripTelemetryLabels(progress.statusNote ?? ""));
          },
          onStreamingFallback: (streamMessage) => {
            setStatusNote(stripTelemetryLabels(`${streamMessage} Đang fallback sang polling.`));
          },
        });

        if (cancelledRef.current) {
          throw new DOMException("cancelled", "AbortError");
        }

        const normalized = normalizeResearchTier2(finalPayload);
        if (!normalized.answer && !normalized.citations.length) {
          throw new Error("Chưa có phản hồi research hợp lệ.");
        }
        setStatus("done");
        setJobId(null);
        setStatusNote("");
        return { tier: "tier2", ...normalized };
      } catch (cause) {
        if (cancelledRef.current || (cause instanceof DOMException && cause.name === "AbortError")) {
          setStatus("cancelled");
          throw cause;
        }
        setStatus("error");
        setJobId(null);
        throw cause;
      }
    },
    []
  );

  return {
    status,
    statusNote,
    jobId,
    isRunning: status === "streaming",
    run,
    cancel,
  };
}
