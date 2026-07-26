"use client";

import { useId } from "react";

/**
 * Accessible switch built on a real `role="switch"` button with `aria-checked`.
 * Token-driven; transition is suppressed under reduced motion by globals.css.
 */
export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  const descId = useId();
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-describedby={description ? descId : undefined}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="focus-ring flex w-full items-center gap-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-left transition hover:border-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span
        className={`relative h-6 w-11 shrink-0 rounded-full transition ${
          checked ? "bg-[var(--brand-600)]" : "bg-[var(--surface-muted)]"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
            checked ? "left-[1.375rem]" : "left-0.5"
          }`}
        />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-[var(--text-primary)]">{label}</span>
        {description ? (
          <span id={descId} className="mt-0.5 block text-xs leading-5 text-[var(--text-secondary)]">
            {description}
          </span>
        ) : null}
      </span>
    </button>
  );
}

export default Toggle;
