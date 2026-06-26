import { useRef } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import {
  getFocusableElements,
  useFocusTrap,
} from "@/app/chat/_v2/lib/useFocusTrap";
import CommandPalette from "@/app/chat/_v2/components/CommandPalette";
import WorkspaceDrawer from "@/app/chat/_v2/components/WorkspaceDrawer";
import type { UseCommandPalette, CommandAction } from "@/app/chat/_v2/hooks/useCommandPalette";
import type { UseWorkspace } from "@/app/chat/_v2/hooks/useWorkspace";

/**
 * Feature: clara-chat-redesign, task 7.1 — Keyboard nav + focus management
 * across drawers / modals / palette. Requirement 5.1, 5.4.
 *
 * These cover the shared focus trap: Tab / Shift+Tab cycle within the active
 * surface (wrap-around) and focus that escapes the container is pulled back in.
 */

afterEach(() => {
  vi.clearAllMocks();
});

// jsdom does not implement scrollIntoView; the palette uses it to keep the
// highlighted option in view. Stub it so component mounting does not throw.
beforeAll(() => {
  if (!("scrollIntoView" in Element.prototype)) {
    Object.defineProperty(Element.prototype, "scrollIntoView", {
      value: () => {},
      writable: true,
    });
  }
});

function TrapHarness({ active }: { active: boolean }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useFocusTrap(active, ref);
  return (
    <div>
      <button type="button">outside before</button>
      <div ref={ref} data-testid="trap">
        <button type="button">first</button>
        <button type="button">middle</button>
        <button type="button">last</button>
      </div>
      <button type="button">outside after</button>
    </div>
  );
}

describe("getFocusableElements", () => {
  it("returns tabbable elements in DOM order, skipping disabled/hidden", () => {
    const root = document.createElement("div");
    root.innerHTML = `
      <a href="#a">link</a>
      <button>ok</button>
      <button disabled>no</button>
      <input aria-hidden="true" />
      <div tabindex="-1">skip</div>
      <textarea></textarea>
    `;
    const focusable = getFocusableElements(root);
    expect(focusable.map((el) => el.tagName.toLowerCase())).toEqual([
      "a",
      "button",
      "textarea",
    ]);
  });
});

describe("useFocusTrap", () => {
  it("wraps focus from the last element back to the first on Tab", () => {
    render(<TrapHarness active />);
    const last = screen.getByRole("button", { name: "last" });
    const first = screen.getByRole("button", { name: "first" });
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });

  it("wraps focus from the first element to the last on Shift+Tab", () => {
    render(<TrapHarness active />);
    const first = screen.getByRole("button", { name: "first" });
    const last = screen.getByRole("button", { name: "last" });
    first.focus();
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("does not intercept Tab between interior elements", () => {
    render(<TrapHarness active />);
    const first = screen.getByRole("button", { name: "first" });
    first.focus();
    const event = fireEvent.keyDown(first, { key: "Tab" });
    // Interior navigation is left to the browser (not prevented).
    expect(event).toBe(true);
  });

  it("is inert when inactive", () => {
    render(<TrapHarness active={false} />);
    const last = screen.getByRole("button", { name: "last" });
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(last);
  });
});

function makePalette(overrides: Partial<UseCommandPalette> = {}): UseCommandPalette {
  const actions: CommandAction[] = [
    { id: "a", label: "New chat", keywords: ["new"], run: vi.fn() },
    { id: "b", label: "Open workspace", keywords: ["workspace"], run: vi.fn() },
  ];
  return {
    isOpen: true,
    query: "",
    filtered: actions,
    activeIndex: 0,
    open: vi.fn(),
    close: vi.fn(),
    toggle: vi.fn(),
    setQuery: vi.fn(),
    setActiveIndex: vi.fn(),
    moveActive: vi.fn(),
    execute: vi.fn(),
    executeActive: vi.fn(),
    executeFirst: vi.fn(),
    ...overrides,
  };
}

describe("CommandPalette focus trap", () => {
  it("keeps Tab focus within the dialog (last wraps to input)", () => {
    render(<CommandPalette palette={makePalette()} uiLanguage="en" />);
    const dialog = screen.getByRole("dialog", { name: "Command palette" });
    const focusable = getFocusableElements(dialog);
    const last = focusable[focusable.length - 1];
    const first = focusable[0];
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });
});

function makeWorkspace(): UseWorkspace {
  return {
    notes: [],
    shares: [],
    searchResults: null,
    loadNotes: vi.fn(async () => {}),
    loadShares: vi.fn(async () => {}),
    saveNote: vi.fn(async () => {}),
    removeNote: vi.fn(async () => {}),
    share: vi.fn(async () => null),
    revokeShare: vi.fn(async () => {}),
    exportConversation: vi.fn(async () => {}),
    search: vi.fn(async () => null),
    clearSearch: vi.fn(),
  };
}

describe("WorkspaceDrawer focus trap", () => {
  it("keeps Tab focus within the drawer dialog (last wraps to first)", () => {
    render(
      <WorkspaceDrawer
        open
        onClose={vi.fn()}
        uiLanguage="en"
        onCopyShareUrl={vi.fn()}
        activeConversationId={7}
        activeTitle="Aspirin chat"
        activeTurns={[]}
        apiUnavailable={false}
        onNotice={vi.fn()}
        workspace={makeWorkspace()}
      />,
    );
    const dialog = screen.getByRole("dialog", { name: "Workspace" });
    const focusable = getFocusableElements(dialog);
    expect(focusable.length).toBeGreaterThan(1);
    const last = focusable[focusable.length - 1];
    const first = focusable[0];
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
  });
});
