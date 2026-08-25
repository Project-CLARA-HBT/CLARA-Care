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
    fireEvent.click(screen.getByRole("button", { name: "Research" }));
    expect(props.onChangeMode).toHaveBeenCalledWith("deep_beta");
  });

  it("progressively reveals the personal-context toggle outside quick mode", () => {
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
    expect(
      screen.queryByRole("button", { name: "Use my health profile" }),
    ).not.toBeInTheDocument();

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
    expect(
      screen.getByRole("button", { name: "Use my health profile" }),
    ).toBeEnabled();
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

  it("toggles 1-click quick context pills and mic voice recording", () => {
    const onTogglePersonalMode = vi.fn();
    setup({ onTogglePersonalMode, uiLanguage: "vi" });

    // 1-Click Quick Context Pills
    const healthProfilePill = screen.getByTitle("+ Hồ sơ sức khỏe");
    expect(healthProfilePill).toBeInTheDocument();
    fireEvent.click(healthProfilePill);
    expect(onTogglePersonalMode).toHaveBeenCalledTimes(1);

    const cabinetPill = screen.getByTitle("+ Tủ thuốc cá nhân");
    expect(cabinetPill).toBeInTheDocument();
    fireEvent.click(cabinetPill);
    expect(screen.getByText("✓ Tủ thuốc cá nhân")).toBeInTheDocument();

    // 1-Click Mic Voice Button
    const micButton = screen.getByRole("button", { name: /Nói bằng giọng nói/i });
    expect(micButton).toBeInTheDocument();
    fireEvent.click(micButton);
    expect(screen.getByText(/Đang lắng nghe giọng nói/i)).toBeInTheDocument();

    // 1-Click Attachment Button
    const attachButton = screen.getByRole("button", { name: /Đính kèm ảnh đơn thuốc/i });
    expect(attachButton).toBeInTheDocument();
  });
});
