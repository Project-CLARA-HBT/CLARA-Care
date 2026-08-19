import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ContextDisclosureBadge } from "./context-disclosure-badge";

afterEach(cleanup);

describe("ContextDisclosureBadge", () => {
  it("renders nothing when disclosure is absent or used_personal_context is false", () => {
    const { container: c1 } = render(<ContextDisclosureBadge disclosure={null} />);
    expect(c1.firstChild).toBeNull();

    const { container: c2 } = render(
      <ContextDisclosureBadge
        disclosure={{ used_personal_context: false, data_classes: [] }}
      />
    );
    expect(c2.firstChild).toBeNull();
  });

  it("renders translated data classes and trigger button", () => {
    const onOpen = vi.fn();
    render(
      <ContextDisclosureBadge
        disclosure={{
          used_personal_context: true,
          data_classes: ["medications", "allergies", "conditions"],
        }}
        personalEvidenceCount={3}
        onOpenEvidenceDrawer={onOpen}
      />
    );

    const badge = screen.getByTestId("context-disclosure-badge");
    expect(badge).toBeInTheDocument();
    expect(screen.getByText("Đã dùng thông tin:")).toBeInTheDocument();
    expect(
      screen.getByText("[Thuốc đang dùng, Dị ứng, Tiền sử bệnh]")
    ).toBeInTheDocument();

    const trigger = screen.getByTestId("context-disclosure-drawer-trigger");
    expect(trigger).toHaveTextContent("Xem chi tiết (3)");
    fireEvent.click(trigger);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
