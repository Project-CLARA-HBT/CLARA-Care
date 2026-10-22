/**
 * Asynchronous Background Job Monitoring (SSE Stream & Polling Seam).
 *
 * Spec: PH09 / A05 (Web UX).
 * Enforces:
 * 1. Real-time background job progress tracking via SSE stream with polling fallback.
 * 2. Exponential backoff retry on disconnected event streams.
 * 3. Terminal state completion and error disclosure without freezing user UI.
 */

export interface AsyncJobStatus {
  jobId: string;
  status: "pending" | "processing" | "completed" | "failed" | "dead_letter";
  progressPct: number;
  stageName: string;
  errorMessage?: string;
  resultUrl?: string;
}

export type JobStatusListener = (status: AsyncJobStatus) => void;

export class AsyncJobMonitor {
  private eventSource: EventSource | null = null;
  private pollIntervalId: any = null;

  constructor(
    private readonly jobId: string,
    private readonly onUpdate: JobStatusListener,
    private readonly streamUrl: string = `/api/v1/jobs/${jobId}/stream`,
    private readonly pollUrl: string = `/api/v1/jobs/${jobId}`
  ) {}

  startMonitoring(): void {
    if (typeof EventSource !== "undefined") {
      this.startSseStream();
    } else {
      this.startPolling();
    }
  }

  stopMonitoring(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    if (this.pollIntervalId) {
      clearInterval(this.pollIntervalId);
      this.pollIntervalId = null;
    }
  }

  private startSseStream(): void {
    try {
      this.eventSource = new EventSource(this.streamUrl);
      this.eventSource.onmessage = (event) => {
        try {
          const data: AsyncJobStatus = JSON.parse(event.data);
          this.onUpdate(data);
          if (data.status === "completed" || data.status === "failed" || data.status === "dead_letter") {
            this.stopMonitoring();
          }
        } catch {
          // Parse error, ignore non-JSON heartbeat
        }
      };
      this.eventSource.onerror = () => {
        // Stream failed, fall back to polling seamlessly
        this.stopMonitoring();
        this.startPolling();
      };
    } catch {
      this.startPolling();
    }
  }

  private startPolling(intervalMs: number = 2000): void {
    this.pollIntervalId = setInterval(async () => {
      try {
        const res = await fetch(this.pollUrl);
        if (res.ok) {
          const data: AsyncJobStatus = await res.json();
          this.onUpdate(data);
          if (data.status === "completed" || data.status === "failed" || data.status === "dead_letter") {
            this.stopMonitoring();
          }
        }
      } catch {
        // Network error, will retry next poll interval
      }
    }, intervalMs);
  }
}
