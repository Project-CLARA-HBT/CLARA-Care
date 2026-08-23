import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  ShellModeProvider,
  useShellMode,
  SHELL_DISPLAY_MODES,
  DOCK_MORPH_STATES,
} from "./shell-mode-provider";

function TestConsumer() {
  const {
    mode,
    setMode,
    cycleMode,
    isExplore,
    isFocus,
    isImmersive,
    isRead,
    isDense,
    dockMorphState,
    setDockMorphState,
    cycleDockMorphState,
    isDockVisible,
    toggleDockVisibility,
    orbState,
    setOrbState,
    activeEntity,
    setActiveEntity,
    clearActiveEntity,
    isCommandPaletteOpen,
    openCommandPalette,
    closeCommandPalette,
    toggleCommandPalette,
  } = useShellMode();

  return (
    <div>
      <span data-testid="mode">{mode}</span>
      <span data-testid="isExplore">{String(isExplore)}</span>
      <span data-testid="isFocus">{String(isFocus)}</span>
      <span data-testid="isImmersive">{String(isImmersive)}</span>
      <span data-testid="isRead">{String(isRead)}</span>
      <span data-testid="isDense">{String(isDense)}</span>

      <span data-testid="dockState">{dockMorphState}</span>
      <span data-testid="isDockVisible">{String(isDockVisible)}</span>
      <span data-testid="orbState">{orbState}</span>

      <span data-testid="entityLabel">{activeEntity?.label ?? "none"}</span>
      <span data-testid="paletteOpen">{String(isCommandPaletteOpen)}</span>

      <button onClick={() => setMode("focus")}>Set Focus</button>
      <button onClick={() => setMode("immersive")}>Set Immersive</button>
      <button onClick={() => setMode("read")}>Set Read</button>
      <button onClick={() => setMode("dense")}>Set Dense</button>
      <button onClick={() => setMode("explore")}>Set Explore</button>
      <button onClick={cycleMode}>Cycle Mode</button>

      <button onClick={() => setDockMorphState("COMPACT")}>Set Compact</button>
      <button onClick={() => setDockMorphState("ORB_ONLY")}>Set Orb Only</button>
      <button onClick={() => setDockMorphState("CONTEXTUAL")}>Set Contextual</button>
      <button onClick={() => setDockMorphState("HIDDEN_WITH_ESCAPE")}>Set Hidden</button>
      <button onClick={cycleDockMorphState}>Cycle Dock</button>
      <button onClick={toggleDockVisibility}>Toggle Dock Visibility</button>

      <button onClick={() => setOrbState("listening")}>Set Listening</button>
      <button onClick={() => setOrbState("processing")}>Set Processing</button>
      <button onClick={() => setOrbState("ready")}>Set Ready</button>
      <button onClick={() => setOrbState("attention")}>Set Attention</button>
      <button onClick={() => setOrbState("error")}>Set Error</button>

      <button
        onClick={() =>
          setActiveEntity({
            id: "ent-1",
            type: "patient",
            label: "Nguyen Van A",
            badge: "VIP",
          })
        }
      >
        Set Patient Entity
      </button>
      <button onClick={clearActiveEntity}>Clear Entity</button>

      <button onClick={openCommandPalette}>Open Palette</button>
      <button onClick={closeCommandPalette}>Close Palette</button>
      <button onClick={toggleCommandPalette}>Toggle Palette</button>
    </div>
  );
}

describe("ShellModeProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    delete document.documentElement.dataset.shellMode;
  });

  it("provides default explore mode and expanded dock state", () => {
    render(
      <ShellModeProvider>
        <TestConsumer />
      </ShellModeProvider>,
    );

    expect(screen.getByTestId("mode")).toHaveTextContent("explore");
    expect(screen.getByTestId("isExplore")).toHaveTextContent("true");
    expect(screen.getByTestId("isFocus")).toHaveTextContent("false");
    expect(screen.getByTestId("dockState")).toHaveTextContent("EXPANDED");
    expect(screen.getByTestId("isDockVisible")).toHaveTextContent("true");
    expect(screen.getByTestId("orbState")).toHaveTextContent("idle");
    expect(screen.getByTestId("paletteOpen")).toHaveTextContent("false");
    expect(document.documentElement.dataset.shellMode).toBe("explore");
  });

  it("allows switching between all 5 shell modes and syncs document attribute", () => {
    render(
      <ShellModeProvider>
        <TestConsumer />
      </ShellModeProvider>,
    );

    // Switch to focus
    fireEvent.click(screen.getByRole("button", { name: "Set Focus" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("focus");
    expect(screen.getByTestId("isFocus")).toHaveTextContent("true");
    expect(document.documentElement.dataset.shellMode).toBe("focus");

    // Switch to immersive
    fireEvent.click(screen.getByRole("button", { name: "Set Immersive" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("immersive");
    expect(screen.getByTestId("isImmersive")).toHaveTextContent("true");
    expect(document.documentElement.dataset.shellMode).toBe("immersive");

    // Switch to read
    fireEvent.click(screen.getByRole("button", { name: "Set Read" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("read");
    expect(screen.getByTestId("isRead")).toHaveTextContent("true");
    expect(document.documentElement.dataset.shellMode).toBe("read");

    // Switch to dense
    fireEvent.click(screen.getByRole("button", { name: "Set Dense" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("dense");
    expect(screen.getByTestId("isDense")).toHaveTextContent("true");
    expect(document.documentElement.dataset.shellMode).toBe("dense");

    // Cycle modes
    fireEvent.click(screen.getByRole("button", { name: "Cycle Mode" }));
    expect(screen.getByTestId("mode")).toHaveTextContent("explore");
  });

  it("manages all 5 dock morph states and visibility toggling", () => {
    render(
      <ShellModeProvider>
        <TestConsumer />
      </ShellModeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Set Compact" }));
    expect(screen.getByTestId("dockState")).toHaveTextContent("COMPACT");

    fireEvent.click(screen.getByRole("button", { name: "Set Orb Only" }));
    expect(screen.getByTestId("dockState")).toHaveTextContent("ORB_ONLY");

    fireEvent.click(screen.getByRole("button", { name: "Set Contextual" }));
    expect(screen.getByTestId("dockState")).toHaveTextContent("CONTEXTUAL");

    fireEvent.click(screen.getByRole("button", { name: "Set Hidden" }));
    expect(screen.getByTestId("dockState")).toHaveTextContent("HIDDEN_WITH_ESCAPE");
    expect(screen.getByTestId("isDockVisible")).toHaveTextContent("false");

    fireEvent.click(screen.getByRole("button", { name: "Toggle Dock Visibility" }));
    expect(screen.getByTestId("dockState")).toHaveTextContent("EXPANDED");
    expect(screen.getByTestId("isDockVisible")).toHaveTextContent("true");
  });

  it("manages orb states and active entity context", () => {
    render(
      <ShellModeProvider>
        <TestConsumer />
      </ShellModeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Set Listening" }));
    expect(screen.getByTestId("orbState")).toHaveTextContent("listening");

    fireEvent.click(screen.getByRole("button", { name: "Set Attention" }));
    expect(screen.getByTestId("orbState")).toHaveTextContent("attention");

    fireEvent.click(screen.getByRole("button", { name: "Set Patient Entity" }));
    expect(screen.getByTestId("entityLabel")).toHaveTextContent("Nguyen Van A");

    fireEvent.click(screen.getByRole("button", { name: "Clear Entity" }));
    expect(screen.getByTestId("entityLabel")).toHaveTextContent("none");
  });

  it("handles keyboard shortcut Ctrl+K to toggle command palette", () => {
    render(
      <ShellModeProvider>
        <TestConsumer />
      </ShellModeProvider>,
    );

    expect(screen.getByTestId("paletteOpen")).toHaveTextContent("false");

    // Press Ctrl+K
    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }),
      );
    });
    expect(screen.getByTestId("paletteOpen")).toHaveTextContent("true");

    // Press Escape to close
    act(() => {
      window.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    });
    expect(screen.getByTestId("paletteOpen")).toHaveTextContent("false");
  });
});
