import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import Composer, {
  type ComposerProps,
} from "@/app/chat/_v2/components/Composer";

/**
 * Feature: clara-chat-redesign, Requirement 3.5 (responsive composer during a
 * run — cancel/await), 4.4 (mode + personal affordances), 5.2 (ARIA live region
 * for streaming status).
 */

function setup(overrides: Partial<ComposerProps> = {}) {
  const props: ComposerProps = {
    query: "",
    onChangeQuery: vi.fn(),
    onSubmit: vi.fn((event) => event.preventDefault()),
    isRunning: false,
    onCancel: vi.fn(),
    mode: "fast",
    onChangeMode: vi.fn(),
    retrievalStackMode: "auto",
    onChangeRetrievalStackMode: vi.fn(),
    personalMode: false,
    onTogglePersonalMode: vi.fn(),
    liveStatusNote: "",
    uiLanguage: "en",
    ...overrides,
  };
  const utils = render(<Composer {...props} />);
  return { props, ...utils };
}

describe("Composer", () => {
  it("disables Send when the prompt is empty and enables it with text", () => {
    const { rerender } = render(
      <Composer
        query=""
        onChangeQuery={vi.fn()}
        onSubmit={vi.fn()}
        isRunning={false}
        onCancel={vi.fn()}
        mode="fast"
        onChangeMode={vi.fn()}
        retrievalStackMode="auto"
        onChangeRetrievalStackMode={vi.fn()}
        personalMode={false}
        onTogglePersonalMode={vi.fn()}
        liveStatusNote=""
        uiLanguage="en"
      />,
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();

    rerender(
      <Composer
        query="hello"
        onChangeQuery={vi.fn()}
        onSubmit={vi.fn()}
        isRunning={false}
        onCancel={vi.fn()}
        mode="fast"
        onChangeMode={vi.fn()}
        retrievalStackMode="auto"
        onChangeRetrievalStackMode={vi.fn()}
        personalMode={false}
        onTogglePersonalMode={vi.fn()}
        liveStatusNote=""
        uiLanguage="en"
      />,
    );
    expect(screen.getByRole("button", { name: "Send" })).toBeEnabled();
  });

  it("swaps Send for a Cancel affordance while running (Req 3.5)", () => {
    const { props } = setup({ isRunning: true, query: "hi" });
    expect(
      screen.queryByRole("button", { name: "Send" }),
    ).not.toBeInTheDocument();
    const cancel = screen.getByRole("button", { name: /Cancel run/i });
    fireEvent.click(cancel);
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("changes mode when a mode button is pressed (Req 4.4)", () => {
    const { props } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Pro" }));
    expect(props.onChangeMode).toHaveBeenCalledWith("deep_beta");
  });

  it("disables the personal toggle in fast mode and enables it otherwise", () => {
    const { rerender } = render(
      <Composer
        query=""
        onChangeQuery={vi.fn()}
        onSubmit={vi.fn()}
        isRunning={false}
        onCancel={vi.fn()}
        mode="fast"
        onChangeMode={vi.fn()}
        retrievalStackMode="auto"
        onChangeRetrievalStackMode={vi.fn()}
        personalMode={false}
        onTogglePersonalMode={vi.fn()}
        liveStatusNote=""
        uiLanguage="en"
      />,
    );
    expect(screen.getByRole("button", { name: "Personal" })).toBeDisabled();

    rerender(
      <Composer
        query=""
        onChangeQuery={vi.fn()}
        onSubmit={vi.fn()}
        isRunning={false}
        onCancel={vi.fn()}
        mode="deep"
        onChangeMode={vi.fn()}
        retrievalStackMode="auto"
        onChangeRetrievalStackMode={vi.fn()}
        personalMode={false}
        onTogglePersonalMode={vi.fn()}
        liveStatusNote=""
        uiLanguage="en"
      />,
    );
    expect(screen.getByRole("button", { name: "Personal" })).toBeEnabled();
  });

  it("exposes the live status note through a polite live region (Req 5.2)", () => {
    const { container } = setup({
      liveStatusNote: "Retrieving evidence...",
    });
    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).not.toBeNull();
    expect(liveRegion).toHaveTextContent("Retrieving evidence...");
  });

  it("submits the form on Enter without Shift", () => {
    const onSubmit = vi.fn((event) => event.preventDefault());
    setup({ query: "ask", onSubmit });
    const textarea = screen.getByLabelText(/medical question/i);
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });
    expect(onSubmit).toHaveBeenCalled();
  });
});
