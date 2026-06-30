import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import fc from "fast-check";

import {
  filterCommands,
  useCommandPalette,
  wrapIndex,
  type CommandAction,
} from "@/app/chat/_v2/hooks/useCommandPalette";

/**
 * Feature: clara-chat-redesign; Requirement 5.1, 6.3.
 *
 * The command palette filters parity actions by free text (case-insensitive
 * across label/hint/keywords), opens/closes, and executes enabled actions while
 * skipping disabled ones. `filterCommands` is a pure exported helper so the
 * matching logic is property-testable without React.
 */

function action(
  id: string,
  label: string,
  extra: Partial<CommandAction> = {},
): CommandAction {
  return { id, label, keywords: [], run: () => {}, ...extra };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("filterCommands", () => {
  const actions = [
    action("new", "New chat", { keywords: ["create", "start"] }),
    action("export", "Export conversation", { hint: "markdown/docx" }),
    action("share", "Share", { keywords: ["link"] }),
  ];

  it("returns everything for an empty query", () => {
    expect(filterCommands(actions, "  ").map((a) => a.id)).toEqual([
      "new",
      "export",
      "share",
    ]);
  });

  it("matches across label, hint, and keywords case-insensitively", () => {
    expect(filterCommands(actions, "CREATE").map((a) => a.id)).toEqual(["new"]);
    expect(filterCommands(actions, "docx").map((a) => a.id)).toEqual(["export"]);
    expect(filterCommands(actions, "link").map((a) => a.id)).toEqual(["share"]);
  });

  it("Property: a filtered result is always a subset of the input", () => {
    fc.assert(
      fc.property(fc.string(), (query) => {
        const filtered = filterCommands(actions, query);
        return filtered.every((item) => actions.includes(item));
      }),
      { numRuns: 200 },
    );
  });
});

describe("useCommandPalette", () => {
  it("opens, filters by query, and closes (resetting query)", () => {
    const actions = [action("new", "New chat"), action("share", "Share")];
    const { result } = renderHook(() => useCommandPalette(actions));

    act(() => result.current.open());
    expect(result.current.isOpen).toBe(true);

    act(() => result.current.setQuery("share"));
    expect(result.current.filtered.map((a) => a.id)).toEqual(["share"]);

    act(() => result.current.close());
    expect(result.current.isOpen).toBe(false);
    expect(result.current.query).toBe("");
  });

  it("executes an enabled action and closes; skips disabled actions", () => {
    const enabled = vi.fn();
    const disabled = vi.fn();
    const actions = [
      action("a", "Alpha", { run: enabled }),
      action("b", "Beta", { run: disabled, disabled: true }),
    ];
    const { result } = renderHook(() => useCommandPalette(actions));

    act(() => result.current.open());
    act(() => result.current.execute(actions[1]));
    expect(disabled).not.toHaveBeenCalled();
    expect(result.current.isOpen).toBe(true);

    act(() => result.current.execute(actions[0]));
    expect(enabled).toHaveBeenCalledTimes(1);
    expect(result.current.isOpen).toBe(false);
  });

  it("executeFirst runs the first enabled match", () => {
    const first = vi.fn();
    const second = vi.fn();
    const actions = [
      action("a", "Alpha", { run: first, disabled: true }),
      action("b", "Beta", { run: second }),
    ];
    const { result } = renderHook(() => useCommandPalette(actions));

    act(() => result.current.open());
    act(() => result.current.executeFirst());
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });

  it("navigates the highlight with wrap-around and executes the active action", () => {
    const alpha = vi.fn();
    const beta = vi.fn();
    const gamma = vi.fn();
    const actions = [
      action("a", "Alpha", { run: alpha }),
      action("b", "Beta", { run: beta }),
      action("c", "Gamma", { run: gamma }),
    ];
    const { result } = renderHook(() => useCommandPalette(actions));

    act(() => result.current.open());
    expect(result.current.activeIndex).toBe(0);

    act(() => result.current.moveActive(1));
    expect(result.current.activeIndex).toBe(1);

    // Wrap past the end back to the top.
    act(() => result.current.moveActive(2));
    expect(result.current.activeIndex).toBe(0);

    // Wrap before the start to the last item.
    act(() => result.current.moveActive(-1));
    expect(result.current.activeIndex).toBe(2);

    act(() => result.current.executeActive());
    expect(gamma).toHaveBeenCalledTimes(1);
    expect(result.current.isOpen).toBe(false);
  });

  it("resets the highlight to the top when the query changes", () => {
    const actions = [action("a", "Alpha"), action("b", "Beta")];
    const { result } = renderHook(() => useCommandPalette(actions));

    act(() => result.current.open());
    act(() => result.current.moveActive(1));
    expect(result.current.activeIndex).toBe(1);

    act(() => result.current.setQuery("be"));
    expect(result.current.activeIndex).toBe(0);
  });
});

describe("wrapIndex", () => {
  it("wraps indices within bounds in both directions", () => {
    expect(wrapIndex(0, 3)).toBe(0);
    expect(wrapIndex(3, 3)).toBe(0);
    expect(wrapIndex(-1, 3)).toBe(2);
    expect(wrapIndex(4, 3)).toBe(1);
  });

  it("returns 0 for an empty list", () => {
    expect(wrapIndex(5, 0)).toBe(0);
    expect(wrapIndex(-2, 0)).toBe(0);
  });

  it("Property: result is always a valid index for a non-empty list", () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer({ min: 1, max: 50 }), (index, length) => {
        const wrapped = wrapIndex(index, length);
        return wrapped >= 0 && wrapped < length;
      }),
      { numRuns: 200 },
    );
  });
});
