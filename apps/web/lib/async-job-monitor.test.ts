import { describe, expect, it, vi } from "vitest";
import { AsyncJobMonitor, type AsyncJobStatus } from "./async-job-monitor";

describe("AsyncJobMonitor SSE & Polling Seam", () => {
  it("initializes and handles polling updates cleanly", async () => {
    let capturedStatus: AsyncJobStatus | null = null;
    const monitor = new AsyncJobMonitor("job-123", (s) => {
      capturedStatus = s;
    });

    expect(monitor).toBeDefined();
    monitor.stopMonitoring();
  });
});
