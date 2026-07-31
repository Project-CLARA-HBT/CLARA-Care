import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Scribe end-user safety presentation", () => {
  it("does not auto-assign R69, diagnosis/procedure codes, or fabricated confidence", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");

    expect(source).not.toContain('add("R69"');
    expect(source).not.toContain("function deriveClinicalCodes");
    expect(source).not.toContain("function confidenceFromSoap");
    expect(source).toContain("không hiển thị phần trăm tin cậy chưa được hiệu chuẩn");
    expect(source).toContain("không tự gán mã chẩn đoán hoặc thủ thuật");
  });

  it("keeps medical-ASR corrections review-only and never applies a replacement to the transcript", () => {
    const source = readFileSync(resolve(__dirname, "../components/scribe/enterprise-review.tsx"), "utf8");
    const catalog = readFileSync(resolve(__dirname, "i18n/catalog.ts"), "utf8");

    expect(source).not.toContain("onApplyMedicalCorrection");
    expect(source).not.toContain("applyMedicalCorrection");
    expect(source).not.toContain("scribe.enterprise.corrections.apply");
    expect(source).toContain("result.medical_correction");
    expect(catalog).toContain("Hãy đối chiếu với âm thanh hoặc nguồn gốc");
  });
});
