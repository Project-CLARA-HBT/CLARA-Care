"use client";

import { useEffect, type ReactNode } from "react";

/**
 * Lightweight, dependency-free modal used by the enhanced PHR surfaces
 * (personal-health-record Component O). Renders a centered dialog over a dimmed
 * backdrop, traps `Escape` to close, and restores body scroll on unmount. It is
 * intentionally minimal — the project has no shared dialog primitive — and is
 * only mounted when its parent surface's capability flag is effective.
 */
export default function PhrModal({
  open,
  title,
  onClose,
  children,
  closeLabel,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  closeLabel: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/45 p-4 sm:items-center"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl rounded-[14px] border border-[color:var(--shell-border)] border-t-[#2A3950] bg-[var(--surface-panel)] shadow-none">
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--shell-border)] px-5 py-3.5">
          <p className="text-sm font-bold text-[var(--text-primary)]">{title}</p>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            className="rounded-full px-2 py-1 text-lg leading-none text-[var(--text-secondary)] transition hover:bg-[var(--surface-muted)]"
          >
            ×
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  );
}
