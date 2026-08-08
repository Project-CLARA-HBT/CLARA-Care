import { describe, expect, it } from "vitest";
import { sanitizeAssistantAnswer } from "./user-facing-text";

describe("assistant answer safety boundary", () => {
  it("removes common English and Vietnamese hidden-reasoning markers", () => {
    const answer = sanitizeAssistantAnswer(
      "Thought: hidden chain\nAnalysis: private scratchpad\nPhân tích: nội bộ\n<analysis>secret</analysis>\nĐiều quan trọng: hãy liên hệ bác sĩ.",
    );
    expect(answer).toBe("Điều quan trọng: hãy liên hệ bác sĩ.");
  });

  it("removes step-by-step prompts without removing patient-facing prose", () => {
    expect(sanitizeAssistantAnswer("Let's think step by step.\nUống thuốc theo hướng dẫn trên nhãn.")).toBe(
      "Uống thuốc theo hướng dẫn trên nhãn.",
    );
  });
});
