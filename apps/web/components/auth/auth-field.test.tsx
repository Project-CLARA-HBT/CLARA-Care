import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AuthField from "@/components/auth/auth-field";

afterEach(cleanup);

describe("AuthField", () => {
  it("keeps validation semantic and uses the bundled visibility icon", () => {
    const onChange = vi.fn();
    const { container } = render(
      <AuthField
        id="password"
        label="Mật khẩu"
        type="password"
        value=""
        onChange={onChange}
        error="Mật khẩu chưa đủ mạnh"
      />,
    );

    const input = screen.getByLabelText("Mật khẩu");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Mật khẩu chưa đủ mạnh");
    expect(container.querySelector('[data-icon="eye"]')).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Hien mat khau" }));
    expect(input).toHaveAttribute("type", "text");
    expect(container.querySelector('[data-icon="eye-off"]')).toBeTruthy();
  });
});
