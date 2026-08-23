import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ClaraOrb } from "./clara-orb";
import type { ClaraOrbState } from "./shell-mode-provider";

describe("ClaraOrb", () => {
  const ALL_ORB_STATES: ClaraOrbState[] = [
    "idle",
    "hover",
    "listening",
    "processing",
    "ready",
    "attention",
    "error",
  ];

  it.each(ALL_ORB_STATES)(
    "renders properly across all 7 interaction states: %s",
    (state) => {
      render(<ClaraOrb state={state} />);

      const button = screen.getByRole("button");
      expect(button).toBeInTheDocument();
      expect(button).toHaveAttribute("aria-label");
      expect(button.getAttribute("aria-label")).toBeTruthy();
    },
  );

  it("handles user click and keyboard interactions when interactive", () => {
    const handleClick = vi.fn();
    render(<ClaraOrb state="idle" onClick={handleClick} />);

    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);

    // Keyboard Enter trigger
    fireEvent.keyDown(button, { key: "Enter" });
    expect(handleClick).toHaveBeenCalledTimes(2);

    // Keyboard Space trigger
    fireEvent.keyDown(button, { key: " " });
    expect(handleClick).toHaveBeenCalledTimes(3);
  });

  it("renders non-interactive variant with role status", () => {
    render(<ClaraOrb state="ready" interactive={false} label="CLARA System Status" />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    const statusEl = screen.getByRole("status");
    expect(statusEl).toBeInTheDocument();
    expect(statusEl).toHaveAttribute("aria-label", "CLARA System Status");
  });

  it("supports size variants sm, md, lg, xl", () => {
    const { rerender } = render(<ClaraOrb size="sm" />);
    expect(screen.getByRole("button")).toHaveClass("min-w-[32px]");

    rerender(<ClaraOrb size="lg" />);
    expect(screen.getByRole("button")).toHaveClass("min-w-[56px]");

    rerender(<ClaraOrb size="xl" />);
    expect(screen.getByRole("button")).toHaveClass("min-w-[72px]");
  });
});
