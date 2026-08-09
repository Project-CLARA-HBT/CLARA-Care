"use client";

import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { Icon, resolveIconName } from "@/components/ui/icon";

export type TabItem = {
  key: string;
  label: string;
  icon?: string;
};

/**
 * Accessible tablist following the WAI-ARIA tabs pattern: roving arrow-key
 * focus, Home/End, `aria-selected`, and `aria-controls`/`id` wiring. Purely
 * presentational — the parent owns the active key and renders the panel.
 *
 * `idBase` must be a stable string shared with the matching `TabPanel`s so the
 * `aria-controls`/`aria-labelledby` relationship resolves correctly.
 */
export function Tabs({
  idBase,
  items,
  active,
  onChange,
  ariaLabel,
  className = "",
}: {
  idBase: string;
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
  ariaLabel: string;
  className?: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const focusIndex = (index: number) => {
    const clamped = (index + items.length) % items.length;
    const key = items[clamped]?.key;
    if (key) {
      refs.current[key]?.focus();
      onChange(key);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        focusIndex(index + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        focusIndex(index - 1);
        break;
      case "Home":
        event.preventDefault();
        focusIndex(0);
        break;
      case "End":
        event.preventDefault();
        focusIndex(items.length - 1);
        break;
      default:
        break;
    }
  };

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={`hide-scrollbar flex max-w-full items-center gap-1 overflow-x-auto rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-1 sm:inline-flex ${className}`}
    >
      {items.map((item, index) => {
        const selected = item.key === active;
        return (
          <button
            key={item.key}
            ref={(node) => {
              refs.current[item.key] = node;
            }}
            type="button"
            role="tab"
            id={`${idBase}-tab-${item.key}`}
            aria-selected={selected}
            aria-controls={`${idBase}-panel-${item.key}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(item.key)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={`focus-ring inline-flex shrink-0 items-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] px-3.5 py-2 text-sm font-semibold transition ${
              selected
                ? "bg-[var(--surface-panel)] text-[var(--text-primary)] shadow-[var(--shadow-sm)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            {item.icon ? (
              <Icon name={resolveIconName(item.icon)} size="1.15em" />
            ) : null}
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/** Panel wrapper wiring `role="tabpanel"` + `aria-labelledby` for a given key. */
export function TabPanel({
  idBase,
  tabKey,
  active,
  children,
}: {
  idBase: string;
  tabKey: string;
  active: string;
  children: ReactNode;
}) {
  if (tabKey !== active) return null;
  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${tabKey}`}
      aria-labelledby={`${idBase}-tab-${tabKey}`}
      tabIndex={0}
      className="focus-visible:outline-none"
    >
      {children}
    </div>
  );
}
