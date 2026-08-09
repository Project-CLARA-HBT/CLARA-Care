"use client";

import { useEffect, useRef } from "react";

import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import type { UseCommandPalette } from "@/app/chat/_v2/hooks/useCommandPalette";
import { useFocusTrap } from "@/app/chat/_v2/lib/useFocusTrap";

/**
 * Keyboard-first command palette for the rebuilt CLARA Chat (CHAT_V2).
 *
 * Parity actions (Requirement 6.3), keyboard-first (Requirement 5.1). Focus
 * moves to the input on open and is restored to the previously-focused element
 * on close (Requirement 5.4). Uses a modal dialog with an owned listbox so the
 * input can drive navigation (ArrowUp/ArrowDown/Home/End wrap-around, Enter
 * executes the highlighted action) while keeping a single, predictable focus
 * point on the search field.
 */

export type CommandPaletteProps = {
  palette: UseCommandPalette;
  uiLanguage: UILanguage;
};

const LISTBOX_ID = "chat-v2-command-listbox";
const optionId = (id: string) => `chat-v2-command-option-${id}`;

export default function CommandPalette({ palette, uiLanguage }: CommandPaletteProps) {
  const {
    isOpen,
    query,
    filtered,
    activeIndex,
    setQuery,
    setActiveIndex,
    moveActive,
    close,
    execute,
    executeActive,
  } = palette;
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const copy = (key: UITranslationKey) => t(uiLanguage, key);

  // Keep Tab focus inside the palette dialog while open (Req 5.1, 5.4).
  useFocusTrap(isOpen, dialogRef);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current = (document.activeElement as HTMLElement) ?? null;
    const timer = window.setTimeout(() => inputRef.current?.focus(), 10);
    return () => {
      window.clearTimeout(timer);
      restoreFocusRef.current?.focus?.();
    };
  }, [isOpen]);

  // Keep the highlighted option scrolled into view as the user navigates.
  useEffect(() => {
    if (!isOpen) return;
    const current = filtered[activeIndex];
    if (!current) return;
    const el = document.getElementById(optionId(current.id));
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, filtered, isOpen]);

  if (!isOpen) return null;

  const activeOption = filtered[activeIndex];

  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-[rgba(16,20,25,0.72)] px-4 pt-[10vh]">
      <button
        type="button"
        aria-label={copy("chat.commandPalette.closeAria")}
        onClick={close}
        className="absolute inset-0"
      />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={copy("chat.commandPalette.title")}
        className="relative w-full max-w-2xl rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-3 shadow-2xl"
      >
        <label className="sr-only" htmlFor="chat-v2-command-input">
          {copy("chat.commandPalette.searchLabel")}
        </label>
        <input
          id="chat-v2-command-input"
          ref={inputRef}
          value={query}
          role="combobox"
          aria-expanded="true"
          aria-controls={LISTBOX_ID}
          aria-autocomplete="list"
          aria-activedescendant={activeOption ? optionId(activeOption.id) : undefined}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            switch (event.key) {
              case "ArrowDown":
                event.preventDefault();
                moveActive(1);
                break;
              case "ArrowUp":
                event.preventDefault();
                moveActive(-1);
                break;
              case "Home":
                event.preventDefault();
                setActiveIndex(0);
                break;
              case "End":
                event.preventDefault();
                setActiveIndex(Math.max(0, filtered.length - 1));
                break;
              case "Enter":
                event.preventDefault();
                executeActive();
                break;
              default:
                break;
            }
          }}
          placeholder={copy("chat.commandPalette.searchPlaceholder")}
          className="min-h-[42px] w-full rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 text-sm text-[var(--text-primary)] outline-none focus-visible:border-[color:var(--shell-border-strong)] focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)]"
        />
        <ul
          id={LISTBOX_ID}
          role="listbox"
          aria-label={copy("chat.commandPalette.actions")}
          className="mt-2 max-h-[58vh] space-y-1 overflow-y-auto pr-1"
        >
          {filtered.length ? (
            filtered.map((action, index) => {
              const isActive = index === activeIndex;
              return (
                <li key={action.id}>
                  <button
                    id={optionId(action.id)}
                    type="button"
                    role="option"
                    aria-selected={isActive}
                    disabled={action.disabled}
                    onMouseMove={() => setActiveIndex(index)}
                    onClick={() => execute(action)}
                    className={[
                      "flex min-h-[42px] w-full items-center justify-between rounded-xl border px-3 text-left text-sm text-[var(--text-primary)] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-50",
                      isActive
                        ? "border-[color:var(--shell-border-strong)] bg-[var(--surface-brand-soft)]"
                        : "border-[color:var(--shell-border)] bg-[var(--surface-muted)] hover:border-[color:var(--shell-border-strong)]",
                    ].join(" ")}
                  >
                    <span>{action.label}</span>
                    {action.hint ? (
                      <span className="rounded border border-[color:var(--shell-border)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
                        {action.hint}
                      </span>
                    ) : null}
                  </button>
                </li>
              );
            })
          ) : (
            <li
              role="option"
              aria-selected={false}
              aria-disabled="true"
              className="rounded-xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-4 text-sm text-[var(--text-muted)]"
            >
              {copy("chat.commandPalette.noMatches")}
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
