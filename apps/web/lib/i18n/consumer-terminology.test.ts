import { describe, expect, it } from "vitest";

import { consumerTerm, CONSUMER_TERMINOLOGY_VERSION } from "./consumer-terminology";
import { t } from "./catalog";

describe("consumer terminology contract v1", () => {
  it("keeps the Vietnamese-first shared labels aligned with the typed catalog", () => {
    expect(CONSUMER_TERMINOLOGY_VERSION).toBe("2026-07-30.v1");
    expect(consumerTerm("vi", "today.emptyDescription")).toContain(
      "CLARA không tự thêm việc thay bạn",
    );
    expect(t("vi", "today.openLifeMap")).toBe(
      consumerTerm("vi", "today.openLifeMap"),
    );
  });

  it("contains English labels without treating runtime health data as a term", () => {
    expect(consumerTerm("en", "navigation.lifeMap")).toBe("Health journey");
    expect(consumerTerm("en", "action.askClara")).toBe("Ask CLARA");
  });
});
