import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Council heuristic-risk presentation", () => {
  it("does not present an uncalibrated heuristic score as a percentage or neural clinical model", () => {
    const source = readFileSync(resolve(__dirname, "../app/council/result/page.tsx"), "utf8");
    const catalog = readFileSync(resolve(__dirname, "i18n/catalog.ts"), "utf8");

    expect(source).toContain('t(language, "council.result.ruleRisk")');
    expect(source).toContain('t(language, "council.result.ruleRiskHint")');
    expect(catalog).toContain("Tín hiệu nguy cơ theo quy tắc");
    expect(catalog).toContain("heuristic chưa hiệu chuẩn");
    expect(source).not.toContain('label="Neural Risk (Shadow)"');
    expect(source).not.toContain("fmtPercent(view.quality.ruleShadowProbability)");
  });

  it("does not render raw snapshots, free-text reasoning, or confidence scores", () => {
    const workspace = readFileSync(
      resolve(__dirname, "../components/council/council-workspace-screen.tsx"),
      "utf8",
    );
    const councilClient = readFileSync(resolve(__dirname, "council.ts"), "utf8");

    expect(workspace).not.toContain("Raw Preview");
    expect(workspace).not.toContain("item.reasoning");
    expect(councilClient).toContain("Only render stable, structured findings.");
    expect(councilClient).not.toContain("confidenceScore:");
  });
});
