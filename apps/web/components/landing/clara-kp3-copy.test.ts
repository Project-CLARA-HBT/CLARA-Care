import { describe, expect, it } from "vitest";

import { LANDING_COPY } from "@/components/landing/clara-kp3-copy";

describe("public landing language copy", () => {
  it("provides the same interactive landing structures in Vietnamese and English", () => {
    expect(LANDING_COPY.vi.modules).toHaveLength(LANDING_COPY.en.modules.length);
    expect(LANDING_COPY.vi.useCases).toHaveLength(LANDING_COPY.en.useCases.length);
    expect(LANDING_COPY.vi.faqs).toHaveLength(LANDING_COPY.en.faqs.length);
    expect(LANDING_COPY.vi.nav).toHaveProperty("login");
    expect(LANDING_COPY.en.nav).toHaveProperty("login");
  });

  it("keeps the safety boundary explicit in both public languages", () => {
    expect(LANDING_COPY.vi.hero.descriptionAfter).toContain("không thay thế đánh giá chuyên môn");
    expect(LANDING_COPY.en.hero.descriptionAfter).toContain("does not replace professional judgement");
    expect(LANDING_COPY.vi.faqs[0]?.a).toContain("quyết định điều trị cuối cùng");
    expect(LANDING_COPY.en.faqs[0]?.a).toContain("final treatment decisions");
  });
});
