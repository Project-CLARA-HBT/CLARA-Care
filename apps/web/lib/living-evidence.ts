import api from "@/lib/http-client";

export type EvidenceQuestionInput = {
  question: string;
  population_context?: string;
  outcomes?: string[];
  time_horizon?: string;
};

export type EvidenceQuestion = {
  id: string;
  episode_id: string;
  question: string;
  confirmed: boolean;
  requires_confirmation: boolean;
  compiled: {
    population_context?: string;
    outcomes?: string[];
    time_horizon?: string;
    missing_dimensions?: string[];
  };
};

export type EvidenceRun = {
  id: string;
  evidence_question_id: string;
  status: string;
  release_status: "evidence_available" | "evidence_unavailable" | string;
  evidence_count: number;
  source_class_counts: Record<string, number>;
  uncertainty: Array<{ dimension: string; status: string; reason: string }>;
  safe_message: string;
  completed_at: string | null;
};

export type EvidenceMatrix = {
  run_id: string;
  release_status: string;
  source_classes: Record<
    string,
    Array<{
      evidence_id: string;
      title: string;
      source_class: string;
      study_design: string | null;
      identifiers: Record<string, string>;
      provider: string | null;
      url: string | null;
      published_at: string | null;
      excerpt: string;
    }>
  >;
  unavailable_reason: string | null;
};

export type EvidenceApplicability = {
  status: string;
  matches: string[];
  unknowns: string[];
  mismatches: string[];
  critical_exclusions: string[];
  safe_message: string;
};

export type EvidenceContradictions = {
  status: string;
  items: Array<{ claim: string; citation_ids: string[]; classification: string }>;
  safe_message: string;
};

export type EvidenceSubscription = {
  id: string;
  evidence_run_id: string;
  status: string;
  delivery_channel: string;
};

export type EvidenceRunPollingOptions = {
  intervalMs?: number;
  maxAttempts?: number;
  signal?: AbortSignal;
  onUpdate?: (run: EvidenceRun, attempt: number) => void;
};

const TERMINAL_EVIDENCE_RUN_STATUSES = new Set(["completed", "failed", "cancelled", "canceled"]);

function idempotencyKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `evidence-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function createEvidenceQuestion(
  episodeId: string,
  input: EvidenceQuestionInput,
): Promise<EvidenceQuestion> {
  return (
    await api.post<EvidenceQuestion>(
      `/episodes/${encodeURIComponent(episodeId)}/evidence-questions`,
      { ...input, confirmed: false },
    )
  ).data;
}

export async function confirmEvidenceQuestion(questionId: string): Promise<EvidenceQuestion> {
  return (
    await api.patch<EvidenceQuestion>(
      `/evidence-questions/${encodeURIComponent(questionId)}`,
      { confirmed: true },
    )
  ).data;
}

export async function runEvidenceQuestion(questionId: string): Promise<EvidenceRun> {
  return (
    await api.post<EvidenceRun>(
      `/evidence-questions/${encodeURIComponent(questionId)}/run`,
      {},
      { headers: { "Idempotency-Key": idempotencyKey() } },
    )
  ).data;
}

export async function getEvidenceRun(runId: string): Promise<EvidenceRun> {
  return (await api.get<EvidenceRun>(`/evidence-runs/${encodeURIComponent(runId)}`)).data;
}

export function isEvidenceRunTerminal(run: EvidenceRun): boolean {
  return TERMINAL_EVIDENCE_RUN_STATUSES.has(run.status.toLowerCase());
}

function abortError(): Error {
  const error = new Error("Đã dừng theo dõi tiến trình truy xuất bằng chứng.");
  error.name = "AbortError";
  return error;
}

function waitForNextPoll(milliseconds: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(abortError());
  if (milliseconds <= 0) return Promise.resolve();

  return new Promise((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      signal?.removeEventListener("abort", handleAbort);
      resolve();
    }, milliseconds);
    const handleAbort = () => {
      window.clearTimeout(timeoutId);
      signal?.removeEventListener("abort", handleAbort);
      reject(abortError());
    };
    signal?.addEventListener("abort", handleAbort, { once: true });
  });
}

export async function pollEvidenceRun(
  runId: string,
  {
    intervalMs = 2_000,
    maxAttempts = 180,
    signal,
    onUpdate,
  }: EvidenceRunPollingOptions = {},
): Promise<EvidenceRun> {
  if (maxAttempts < 1) {
    throw new Error("Số lần kiểm tra tiến trình phải lớn hơn 0.");
  }

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    if (signal?.aborted) throw abortError();
    await waitForNextPoll(attempt === 1 ? 0 : intervalMs, signal);
    const run = await getEvidenceRun(runId);
    onUpdate?.(run, attempt);
    if (isEvidenceRunTerminal(run)) return run;
  }

  throw new Error(
    "Quá trình tổng hợp đang mất nhiều thời gian hơn dự kiến. Run vẫn được lưu; bạn có thể thử lại sau.",
  );
}

export async function getEvidenceDetails(runId: string): Promise<{
  matrix: EvidenceMatrix;
  applicability: EvidenceApplicability;
  contradictions: EvidenceContradictions;
}> {
  const safeId = encodeURIComponent(runId);
  const [matrix, applicability, contradictions] = await Promise.all([
    api.get<EvidenceMatrix>(`/evidence-runs/${safeId}/matrix`),
    api.get<EvidenceApplicability>(`/evidence-runs/${safeId}/applicability`),
    api.get<EvidenceContradictions>(`/evidence-runs/${safeId}/contradictions`),
  ]);
  return {
    matrix: matrix.data,
    applicability: applicability.data,
    contradictions: contradictions.data,
  };
}

export async function subscribeToEvidenceRun(runId: string): Promise<EvidenceSubscription> {
  return (await api.post<EvidenceSubscription>(`/evidence-runs/${encodeURIComponent(runId)}/subscribe`, {})).data;
}

export async function deleteEvidenceSubscription(subscriptionId: string): Promise<void> {
  await api.delete(`/evidence-subscriptions/${encodeURIComponent(subscriptionId)}`);
}
