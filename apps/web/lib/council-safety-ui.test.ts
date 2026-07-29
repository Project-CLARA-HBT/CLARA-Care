import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Council heuristic-risk presentation", () => {
  it("does not present an uncalibrated heuristic score as a percentage or neural clinical model", () => {
    const source = readFileSync(resolve(__dirname, "../app/council/result/page.tsx"), "utf8");

    expect(source).toContain("Tín hiệu nguy cơ theo quy tắc");
    expect(source).toContain("heuristic chưa hiệu chuẩn");
    expect(source).not.toContain('label="Neural Risk (Shadow)"');
    expect(source).not.toContain("fmtPercent(view.quality.neuralProbability)");
  });
});
