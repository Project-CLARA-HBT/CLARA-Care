import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Icon, { resolveIconName, type IconName } from "@/components/ui/icon";

afterEach(cleanup);

describe("Icon", () => {
  it("renders decorative icons as bundled SVG without visible glyph text", () => {
    const { container } = render(<Icon name="medication" />);

    const icon = container.querySelector("svg");
    expect(icon).toHaveAttribute("data-icon", "medication");
    expect(icon).toHaveAttribute("aria-hidden", "true");
    expect(container).not.toHaveTextContent("medication");
  });

  it("gives a meaningful standalone icon an accessible name", () => {
    render(<Icon name="warning" label="Cảnh báo" />);

    expect(screen.getByRole("img", { name: "Cảnh báo" })).toBeInTheDocument();
  });

  it("resolves an unexpected runtime name to a bundled semantic icon", () => {
    const { container } = render(<Icon name={"unknown-provider-glyph" as IconName} />);

    expect(container.querySelector("svg")).toHaveAttribute("data-icon", "clinical-notes");
    expect(container).not.toHaveTextContent("unknown-provider-glyph");
  });

  it("maps persisted Material Symbols identifiers to the matching bundled icon", () => {
    expect(resolveIconName("check_circle")).toBe("check");
    expect(resolveIconName("folder_open")).toBe("folder");
    expect(resolveIconName("diversity_1")).toBe("contact");
  });
});
