"use client";

import { useState } from "react";
import type { FaqItem } from "@/components/landing/clara-kp3-data";

type Props = {
  items: readonly FaqItem[];
};

export default function LandingFaqAccordion({ items }: Props) {
  const [openIndex, setOpenIndex] = useState(0);

  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const opened = openIndex === index;
        return (
          <div
            key={item.question}
            className={[
              "overflow-hidden rounded-2xl border transition-all duration-200",
              opened
                ? "border-[color:var(--brand-400)] bg-[var(--surface-brand-soft)] shadow-[var(--shadow-soft)]"
                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
            ].join(" ")}
          >
            <h3>
              <button
                type="button"
                className="flex min-h-14 w-full items-center justify-between gap-3 px-5 py-3 text-left"
                onClick={() => setOpenIndex(opened ? -1 : index)}
                aria-expanded={opened}
              >
                <span className="text-base font-semibold text-[var(--text-primary)]">{item.question}</span>
                <span
                  className={[
                    "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-lg font-semibold transition",
                    opened
                      ? "border-[color:var(--brand-400)] bg-[var(--surface-panel)] text-[var(--text-brand)]"
                      : "border-[color:var(--shell-border-strong)] bg-[var(--surface-panel)] text-[var(--text-secondary)]",
                  ].join(" ")}
                  aria-hidden="true"
                >
                  {opened ? "−" : "+"}
                </span>
              </button>
            </h3>
            {opened ? (
              <div className="border-t border-[color:var(--shell-border)] px-5 pb-5 pt-4">
                <p className="text-sm leading-7 text-[var(--text-secondary)]">{item.answer}</p>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
