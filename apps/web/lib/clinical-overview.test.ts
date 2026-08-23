import { describe, expect, it } from "vitest";
import { CLINICAL_TOOLS } from "@/components/clinical/clinical-overview-launchpad";
import { t } from "@/lib/i18n/catalog";

describe("Clinical Overview Launchpad configuration and contracts", () => {
  it("contains all 4 core clinical tools with canonical routes", () => {
    expect(CLINICAL_TOOLS).toHaveLength(4);

    const hrefs = CLINICAL_TOOLS.map((tool) => tool.href);
    expect(hrefs).toContain("/council");
    expect(hrefs).toContain("/scribe");
    expect(hrefs).toContain("/evidence");
    expect(hrefs).toContain("/chat");
  });

  it("assigns appropriate badges and icon tokens to each clinical tool", () => {
    const council = CLINICAL_TOOLS.find((t) => t.id === "council");
    const scribe = CLINICAL_TOOLS.find((t) => t.id === "scribe");
    const evidence = CLINICAL_TOOLS.find((t) => t.id === "evidence");
    const chat = CLINICAL_TOOLS.find((t) => t.id === "chat");

    expect(council?.badge).toBe("AI Council");
    expect(scribe?.badge).toBe("SOAP Notes");
    expect(evidence?.badge).toBe("Living Evidence");
    expect(chat?.badge).toBe("Decision Support");

    expect(council?.titleKey).toBe("clinical.overview.tools.council");
    expect(scribe?.titleKey).toBe("clinical.overview.tools.scribe");
    expect(evidence?.titleKey).toBe("clinical.overview.tools.evidence");
    expect(chat?.titleKey).toBe("clinical.overview.tools.chat");
  });

  it("provides rich clinical highlight bullets for each core tool", () => {
    CLINICAL_TOOLS.forEach((tool) => {
      expect(tool.highlights).toBeDefined();
      expect(tool.highlights?.length).toBeGreaterThanOrEqual(3);
      tool.highlights?.forEach((h) => {
        expect(h.vi).toBeTruthy();
        expect(h.en).toBeTruthy();
      });
    });
  });

  it("has Vietnamese and English translations for Clinician Command Center", () => {
    expect(t("vi", "clinical.overview.title")).toBe("Trung tâm Lâm sàng & Hội chẩn");
    expect(t("en", "clinical.overview.title")).toBe("Clinical & Consultation Command Center");

    expect(t("vi", "clinical.overview.tools.council")).toBe("Hội chẩn AI");
    expect(t("vi", "clinical.overview.tools.scribe")).toBe("Ghi chép SOAP");
    expect(t("vi", "clinical.overview.tools.evidence")).toBe("Bằng chứng");
    expect(t("vi", "clinical.overview.tools.chat")).toBe("Tra cứu lâm sàng");
  });
});
