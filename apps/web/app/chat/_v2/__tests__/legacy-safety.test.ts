import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("legacy chat rollback safety", () => {
  it("does not restore an invented telemetry confidence display when Chat V2 is off", () => {
    const source = readFileSync(resolve(__dirname, "../../_legacy/page-legacy.tsx"), "utf8");

    expect(source).not.toContain("resolveTelemetryConfidence");
    expect(source).not.toContain("confidenceHighReliability");
    expect(source).not.toContain("confidenceNeedsReview");
    expect(source).not.toContain('telemetryCopy.confidence');
  });
});
