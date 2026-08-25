import { describe, expect, it } from "vitest";
import {
  checkInstantDrugInteractions,
  removeVietnameseAccents,
  searchVietnameseDrugs,
  VIETNAMESE_DRUGS_CATALOG,
} from "./vietnamese-drugs";

describe("Vietnamese Drugs Catalog & Instant Interaction Checker", () => {
  describe("1. Catalog data integrity & search", () => {
    it("contains essential Vietnamese trade names (Panadol, Glucophage, Coversyl, Augmentin, Lipitor, etc.)", () => {
      const names = VIETNAMESE_DRUGS_CATALOG.map((d) => d.tradeName);
      expect(names.some((n) => n.includes("Panadol"))).toBe(true);
      expect(names.some((n) => n.includes("Glucophage"))).toBe(true);
      expect(names.some((n) => n.includes("Coversyl"))).toBe(true);
      expect(names.some((n) => n.includes("Augmentin"))).toBe(true);
      expect(names.some((n) => n.includes("Lipitor"))).toBe(true);
      expect(names.some((n) => n.includes("Crestor"))).toBe(true);
      expect(names.some((n) => n.includes("Nexium"))).toBe(true);
      expect(names.some((n) => n.includes("Plavix"))).toBe(true);
      expect(names.some((n) => n.includes("Voltaren"))).toBe(true);
    });

    it("searches with or without Vietnamese diacritics", () => {
      const resWithAccents = searchVietnameseDrugs("Hạ sốt");
      expect(resWithAccents.length).toBeGreaterThan(0);
      expect(resWithAccents.some((d) => d.tradeName.includes("Panadol") || d.tradeName.includes("Hapacol"))).toBe(true);

      const resNoAccents = searchVietnameseDrugs("ha sot");
      expect(resNoAccents.length).toBeGreaterThan(0);
    });

    it("autocompletes trade name queries accurately", () => {
      const panadolResults = searchVietnameseDrugs("panadol");
      expect(panadolResults.length).toBeGreaterThan(0);
      expect(panadolResults[0].tradeName).toContain("Panadol");

      const glucoResults = searchVietnameseDrugs("glucophage");
      expect(glucoResults.length).toBeGreaterThan(0);
      expect(glucoResults[0].tradeName).toContain("Glucophage");

      const coversylResults = searchVietnameseDrugs("coversyl");
      expect(coversylResults.length).toBeGreaterThan(0);
      expect(coversylResults[0].tradeName).toContain("Coversyl");

      const augmentinResults = searchVietnameseDrugs("augmentin");
      expect(augmentinResults.length).toBeGreaterThan(0);
      expect(augmentinResults[0].tradeName).toContain("Augmentin");

      const lipitorResults = searchVietnameseDrugs("lipitor");
      expect(lipitorResults.length).toBeGreaterThan(0);
      expect(lipitorResults[0].tradeName).toContain("Lipitor");
    });

    it("normalizes Vietnamese text correctly", () => {
      expect(removeVietnameseAccents("Thuốc hạ đường huyết Đái Tháo Đường")).toBe(
        "thuoc ha duong huyet dai thao duong",
      );
    });
  });

  describe("2. Traffic-Light Interaction Safety Matrix", () => {
    it("returns 'danger' (Đỏ: Tương tác nguy hiểm) for Plavix + Aspirin / NSAID bleeding risk", () => {
      const result = checkInstantDrugInteractions(["Plavix", "Aspirin Protect"]);
      expect(result.level).toBe("danger");
      expect(result.alerts.length).toBeGreaterThan(0);
      expect(result.alerts[0].title).toContain("xuất huyết");
      expect(result.alerts[0].symptomsToWatch.length).toBeGreaterThan(0);
    });

    it("returns 'danger' (Đỏ: Tương tác nguy hiểm) for Plavix + Nexium (CYP2C19 inhibition)", () => {
      const result = checkInstantDrugInteractions(["Plavix", "Nexium Mups"]);
      expect(result.level).toBe("danger");
      expect(result.alerts[0].title).toContain("giảm hiệu quả chống huyết khối");
    });

    it("returns 'danger' (Đỏ: Tương tác nguy hiểm) for Statin (Lipitor) + Clarithromycin (Klacid)", () => {
      const result = checkInstantDrugInteractions(["Lipitor", "Klacid MR"]);
      expect(result.level).toBe("danger");
      expect(result.alerts[0].title).toContain("tiêu cơ vân");
    });

    it("returns 'danger' (Đỏ: Tương tác nguy hiểm) for duplicate Paracetamol overdose", () => {
      const result = checkInstantDrugInteractions(["Panadol Extra", "Hapacol 650"]);
      expect(result.level).toBe("danger");
      expect(result.alerts[0].title).toContain("Trùng lặp hoạt chất Paracetamol");
    });

    it("returns 'caution' (Vàng: Cần lưu ý) for Coversyl + Voltaren (ACEi + NSAID)", () => {
      const result = checkInstantDrugInteractions(["Coversyl", "Voltaren"]);
      expect(result.level).toBe("caution");
      expect(result.alerts[0].title).toContain("chức năng thận");
    });

    it("returns 'safe' (Xanh: An toàn) for compatible combinations like Augmentin + Panadol", () => {
      const result = checkInstantDrugInteractions(["Augmentin", "Panadol"]);
      expect(result.level).toBe("safe");
      expect(result.alerts.some((a) => a.level === "safe")).toBe(true);
    });

    it("returns 'safe' (Xanh: An toàn) for Glucophage + Coversyl", () => {
      const result = checkInstantDrugInteractions(["Glucophage XR", "Coversyl"]);
      expect(result.level).toBe("safe");
      expect(result.alerts.some((a) => a.level === "safe")).toBe(true);
    });

    it("handles fewer than 2 medicines gracefully", () => {
      const single = checkInstantDrugInteractions(["Panadol Extra"]);
      expect(single.checkedCount).toBe(1);
      expect(single.alerts.length).toBe(0);
    });
  });
});
