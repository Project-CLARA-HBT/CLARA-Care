import {
  RESEARCH_TIER2_JOB_POLL_MS,
  ResearchTier2JobCreateOptions,
  ResearchTier2JobResponse,
  createResearchTier2Job,
  getResearchTier2Job,
  normalizeResearchTier2JobProgress,
  streamResearchTier2Job,
} from "@/lib/research";

const JOB_FETCH_RETRY_ATTEMPTS = 3;
const JOB_FETCH_RETRY_BACKOFF_MS = 600;
const JOB_COMPLETED_RESULT_REFETCH_ATTEMPTS = 5;
const JOB_COMPLETED_RESULT_REFETCH_MS = 900;
const JOB_MAX_POLL_ROUNDS = 1200;

type ResearchTier2JobRunnerCallbacks = {
  onJobCreated?: (job: ResearchTier2JobResponse) => void;
  onSnapshot?: (snapshot: ResearchTier2JobResponse) => void;
  onStreamingFallback?: (message: string) => void;
};

export type ExecuteResearchTier2JobOptions = ResearchTier2JobCreateOptions &
  ResearchTier2JobRunnerCallbacks & {
    pollMs?: number;
    maxPollRounds?: number;
  };

type ExecuteResearchTier2JobResult = {
  finalJob: ResearchTier2JobResponse;
  finalPayload: Record<string, unknown>;
};

function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed";
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function asResultPayload(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, unknown>;
}

async function fetchResearchTier2JobWithRetry(jobId: string): Promise<ResearchTier2JobResponse> {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= JOB_FETCH_RETRY_ATTEMPTS; attempt += 1) {
    try {
      return await getResearchTier2Job(jobId);
    } catch (error) {
      lastError = error;
      if (attempt < JOB_FETCH_RETRY_ATTEMPTS) {
        await sleep(JOB_FETCH_RETRY_BACKOFF_MS * attempt);
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Không thể tải trạng thái research job.");
}

export async function executeResearchTier2Job(
  query: string,
  options?: ExecuteResearchTier2JobOptions
): Promise<ExecuteResearchTier2JobResult> {
  const createOptions: ResearchTier2JobCreateOptions = {
    uploadedFileIds: options?.uploadedFileIds,
    sourceIds: options?.sourceIds,
    sourceHubSources: options?.sourceHubSources,
    researchMode: options?.researchMode,
    retrievalStackMode: options?.retrievalStackMode,
    personalMode: options?.personalMode,
    uiLanguage: options?.uiLanguage,
    deepPassCount: options?.deepPassCount,
    outputMode: options?.outputMode,
    clarifyingAnswers: options?.clarifyingAnswers,
  };

  const job = await createResearchTier2Job(query, createOptions);
  options?.onJobCreated?.(job);

  let currentJob = job;
  options?.onSnapshot?.(currentJob);

  let streamError: string | null = null;
  try {
    await streamResearchTier2Job(job.job_id, {
      onEvent: (eventPayload) => {
        const payload = eventPayload.payload;
        if (payload && typeof payload === "object" && "status" in payload) {
          currentJob = payload as ResearchTier2JobResponse;
          options?.onSnapshot?.(currentJob);
        }
        if (
          eventPayload.event === "error" &&
          payload &&
          typeof payload === "object" &&
          "message" in payload
        ) {
          const text =
            typeof (payload as { message?: unknown }).message === "string"
              ? (payload as { message: string }).message
              : "";
          streamError = text || "Streaming research gặp lỗi.";
        }
      },
    });
  } catch (streamCause) {
    streamError =
      streamCause instanceof Error ? streamCause.message : "Streaming research tạm gián đoạn.";
  }

  if (streamError && !isTerminalStatus(currentJob.status)) {
    options?.onStreamingFallback?.(streamError);
  }

  const pollMs = Math.max(250, Math.trunc(options?.pollMs ?? RESEARCH_TIER2_JOB_POLL_MS));
  const maxPollRounds = Math.max(1, Math.trunc(options?.maxPollRounds ?? JOB_MAX_POLL_ROUNDS));
  let pollingRounds = 0;
  while (!isTerminalStatus(currentJob.status) && pollingRounds < maxPollRounds) {
    pollingRounds += 1;
    await sleep(pollMs);
    currentJob = await fetchResearchTier2JobWithRetry(job.job_id);
    options?.onSnapshot?.(currentJob);
  }

  if (currentJob.status === "failed") {
    throw new Error(currentJob.error ?? "Research job thất bại ở backend.");
  }
  if (currentJob.status !== "completed") {
    throw new Error("Research job quá thời gian chờ. Vui lòng thử lại.");
  }

  let finalPayload = asResultPayload(currentJob.result);
  if (!finalPayload) {
    for (let attempt = 1; attempt <= JOB_COMPLETED_RESULT_REFETCH_ATTEMPTS; attempt += 1) {
      await sleep(JOB_COMPLETED_RESULT_REFETCH_MS);
      currentJob = await fetchResearchTier2JobWithRetry(job.job_id);
      options?.onSnapshot?.(currentJob);
      finalPayload = asResultPayload(currentJob.result);
      if (finalPayload) {
        break;
      }
    }
  }

  if (!finalPayload) {
    const progress = normalizeResearchTier2JobProgress(currentJob.progress);
    throw new Error(progress.statusNote || "Không nhận được kết quả cuối từ research job.");
  }

  return {
    finalJob: currentJob,
    finalPayload,
  };
}
