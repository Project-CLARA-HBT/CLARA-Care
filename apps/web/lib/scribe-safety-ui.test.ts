import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("Scribe end-user safety presentation", () => {
  it("requires explicit consent before microphone access and labels completion as a draft", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");
    expect(source).toContain("recordingConsentCaptured");
    expect(source).toContain('copy("scribe.error.consentRequired")');
    expect(source).toContain('status: "finalized"');
    expect(source).toContain('copy("scribe.notice.draftCompleted")');
    expect(source.indexOf("recordingConsentCaptured")).toBeLessThan(source.indexOf("getUserMedia"));
  });

  it("uses the shared calm workflow instead of the legacy neon sub-brand", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");

    expect(source).toContain('copy("scribe.workflow.capture")');
    expect(source).toContain('copy("scribe.workflow.transcript")');
    expect(source).toContain('copy("scribe.workflow.soap")');
    expect(source).toContain('copy("scribe.workflow.complete")');
    expect(source).not.toContain("ScribeOS v2.4");
    expect(source).not.toContain("neon");
  });

  it("does not auto-assign R69, diagnosis/procedure codes, or fabricated confidence", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");
    const catalog = readFileSync(resolve(__dirname, "i18n/catalog.ts"), "utf8");

    expect(source).not.toContain('add("R69"');
    expect(source).not.toContain("function deriveClinicalCodes");
    expect(source).not.toContain("function confidenceFromSoap");
    expect(source).toContain('copy("scribe.review.statusDescription")');
    expect(source).toContain('copy("scribe.review.codingDescription")');
    expect(catalog).toContain("không hiển thị phần trăm tin cậy chưa được hiệu chuẩn");
    expect(catalog).toContain("không tự gán mã chẩn đoán hoặc thủ thuật");
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

  it("makes recording-derived deletion explicit and preserves signed/audit records", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");
    const client = readFileSync(resolve(__dirname, "scribe.ts"), "utf8");

    expect(source).toContain("canDeleteSelectedRecordingData");
    expect(source).toContain("scribe.recordingData.confirmTitle");
    expect(source).toContain("setTranscriptDraft(\"\")");
    expect(source).toContain("raw transport error");
    expect(client).toContain("raw_audio_persisted: false");
    expect(client).toContain("signed_note_preserved");
  });
});
