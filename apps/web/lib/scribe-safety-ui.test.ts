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

  it("implements the canonical 6-stage Scribe state model: Consent -> Capture -> Transcript Review -> SOAP Review -> Draft Complete -> Export/Sign", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");

    expect(source).toContain('copy("scribe.workflow.consent")');
    expect(source).toContain('copy("scribe.workflow.capture")');
    expect(source).toContain('copy("scribe.workflow.transcript")');
    expect(source).toContain('copy("scribe.workflow.soap")');
    expect(source).toContain('copy("scribe.workflow.complete")');
    expect(source).toContain('copy("scribe.workflow.exportSign")');
    expect(source).not.toContain("ScribeOS v2.4");
    expect(source).not.toContain("neon");
  });

  it("clearly distinguishes Scribe states: Recording, Transcript ready, Draft, Reviewed, Signed, Exported, Amended", () => {
    const source = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");
    const catalog = readFileSync(resolve(__dirname, "i18n/catalog.ts"), "utf8");

    // Status label function handles all distinct states
    expect(source).toContain('normalized === "recording"');
    expect(source).toContain('normalized === "ready" || normalized === "transcript_ready"');
    expect(source).toContain('normalized === "signed"');
    expect(source).toContain('normalized === "exported"');
    expect(source).toContain('normalized === "amended"');
    expect(source).toContain('normalized === "in_review" || normalized === "reviewed"');

    // Catalog provides localized strings for each distinct status
    expect(catalog).toContain('"scribe.status.recording"');
    expect(catalog).toContain('"scribe.status.transcriptReady"');
    expect(catalog).toContain('"scribe.status.draft"');
    expect(catalog).toContain('"scribe.status.reviewed"');
    expect(catalog).toContain('"scribe.status.signed"');
    expect(catalog).toContain('"scribe.status.exported"');
    expect(catalog).toContain('"scribe.status.amended"');
  });

  it("ensures opaque high-contrast reading surfaces for transcripts and SOAP notes without transparent glass", () => {
    const pageSource = readFileSync(resolve(__dirname, "../app/scribe/page.tsx"), "utf8");
    const reviewSource = readFileSync(resolve(__dirname, "../components/scribe/enterprise-review.tsx"), "utf8");

    // No glass effects or backdrop-blur on Scribe clinical document reading surfaces
    expect(pageSource).not.toContain("backdrop-blur");
    expect(pageSource).not.toContain("bg-opacity");
    expect(pageSource).toContain("bg-[var(--surface-panel)]");
    expect(reviewSource).not.toContain("backdrop-blur");
    expect(reviewSource).toContain("bg-[var(--surface-panel)]");
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
