import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { EmptyState, InlineError, StatCard } from "@/components/ui/surface";

afterEach(cleanup);

describe("Surface primitives", () => {
  it("renders semantic SVG icons instead of raw Material Symbol glyph text", () => {
    const { container } = render(
      <>
        <StatCard label="Hồ sơ" value="3" icon="assignment" />
        <EmptyState icon="family_restroom" title="Chưa có thành viên" description="Mời người thân để bắt đầu." />
      </>,
    );

    expect(container.querySelectorAll(".material-symbols-outlined")).toHaveLength(0);
    expect(container.querySelector('[data-icon="clinical-notes"]')).toBeTruthy();
    expect(container.querySelector('[data-icon="contact"]')).toBeTruthy();
  });

  it("exposes an error as an alert and retains a keyboard-accessibile retry action", () => {
    const retry = () => undefined;
    render(<InlineError message="Không thể tải dữ liệu." onRetry={retry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Không thể tải dữ liệu.");
    expect(screen.getByRole("button")).toBeEnabled();
  });
});
