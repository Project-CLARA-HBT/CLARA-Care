import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/use-ui-language", () => ({
  useUILanguage: () => "vi",
}));

import ClaraKp3Landing from "@/components/landing/clara-kp3-landing";

describe("ClaraKp3Landing", () => {
  it("keeps every public section available while using bundled semantic icons", () => {
    const { container } = render(<ClaraKp3Landing />);

    expect(screen.getAllByRole("link", { name: /dùng thử clara chat/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /hỏi đáp/i })).toBeInTheDocument();
    expect(container.querySelectorAll(".material-symbols-outlined")).toHaveLength(0);
    expect(container.querySelectorAll("[data-icon]").length).toBeGreaterThan(12);
    expect(container).not.toHaveTextContent("arrow_forward");
  });
});
