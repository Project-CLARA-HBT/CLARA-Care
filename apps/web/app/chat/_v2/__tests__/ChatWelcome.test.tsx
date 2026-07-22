import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ChatWelcome from "@/app/chat/_v2/components/ChatWelcome";

describe("ChatWelcome", () => {
  it.each([
    ["normal", "What would you like to understand?", "Understand symptoms"],
    ["researcher", "Start with a research question", "Evidence overview"],
    ["doctor", "What do you need to clarify?", "Summarize a case"],
  ] as const)("shows a focused %s experience", (role, heading, action) => {
    render(
      <ChatWelcome role={role} uiLanguage="en" onChoosePrompt={vi.fn()} />,
    );
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: action })).toBeInTheDocument();
  });

  it("sends the selected starter prompt back to the composer", () => {
    const onChoosePrompt = vi.fn();
    render(
      <ChatWelcome
        role="researcher"
        uiLanguage="en"
        onChoosePrompt={onChoosePrompt}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Check a claim" }));
    expect(onChoosePrompt).toHaveBeenCalledWith(
      expect.stringContaining("supporting and conflicting"),
    );
  });
});
