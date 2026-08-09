import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { Field, Select, Textarea } from "@/components/ui/field";

afterEach(cleanup);

describe("Field primitives", () => {
  it("connects label, hint and validation error without relying on colour", () => {
    render(<Field label="Email" hint="Dùng email bạn thường kiểm tra" error="Email không hợp lệ" />);

    const input = screen.getByRole("textbox", { name: "Email" });
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toMatch(/-hint .*?-error/);
    expect(screen.getByRole("alert")).toHaveTextContent("Email không hợp lệ");
  });

  it("keeps multiline and select controls labelled and touch-target sized", () => {
    render(
      <>
        <Textarea label="Ghi chú" hint="Không bắt buộc" />
        <Select label="Loại hồ sơ"><option>Khác</option></Select>
      </>,
    );

    expect(screen.getByRole("textbox", { name: "Ghi chú" })).toHaveAttribute("aria-describedby");
    expect(screen.getByRole("combobox", { name: "Loại hồ sơ" }).className).toContain("min-h-[var(--touch-target-min)]");
  });
});
