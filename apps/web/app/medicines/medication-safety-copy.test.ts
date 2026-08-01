import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const cabinet = readFileSync(resolve(process.cwd(), "app/medicines/cabinet-tab.tsx"), "utf8");
const list = readFileSync(resolve(process.cwd(), "app/medicines/list-tab.tsx"), "utf8");
const catalog = readFileSync(resolve(process.cwd(), "lib/i18n/catalog.ts"), "utf8");

describe("Medication Guardian client safety contract", () => {
  it("does not infer clinical alerts or a risk score from cabinet names", () => {
    expect(cabinet).not.toContain("riskScore");
    expect(cabinet).not.toContain("medicationAlerts");
    expect(cabinet).not.toContain("Chưa phát hiện cảnh báo tự động");
    expect(cabinet).toContain('t(language, "medicines.cabinet.verifiedDescription")');
    expect(catalog).toContain("không suy luận cảnh báo từ tên thuốc");
    expect(catalog).toContain("DrugBank/FIDES");
  });

  it("describes course ending as record-keeping, never advice to stop", () => {
    expect(list).toContain('t(language, "medicines.list.endConfirm")');
    expect(catalog).toContain("chỉ là cập nhật hồ sơ");
    expect(catalog).toContain("không phải lời khuyên ngừng thuốc");
    expect(catalog).toContain("Đừng dùng danh sách này thay cho đơn");
  });
});
