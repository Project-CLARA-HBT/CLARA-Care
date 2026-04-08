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
                ? "border-cyan-300 bg-cyan-50/80 shadow-[0_10px_30px_-25px_rgba(34,211,238,0.9)] dark:border-cyan-700 dark:bg-cyan-950/30"
                : "border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-900",
            ].join(" ")}
          >
            <h3>
              <button
                type="button"
                className="flex min-h-14 w-full items-center justify-between gap-3 px-5 py-3 text-left"
                onClick={() => setOpenIndex(opened ? -1 : index)}
                aria-expanded={opened}
              >
                <span className="text-base font-semibold text-slate-900 dark:text-slate-100">{item.question}</span>
                <span
                  className={[
                    "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-lg font-semibold transition",
                    opened
                      ? "border-cyan-300 bg-cyan-100 text-cyan-700 dark:border-cyan-700 dark:bg-cyan-900/70 dark:text-cyan-200"
                      : "border-slate-300 bg-white text-slate-600 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-300",
                  ].join(" ")}
                  aria-hidden="true"
                >
                  {opened ? "−" : "+"}
                </span>
              </button>
            </h3>
            {opened ? (
              <div className="border-t border-slate-200 px-5 pb-5 pt-4 dark:border-slate-700">
                <p className="text-sm leading-7 text-slate-700 dark:text-slate-300">{item.answer}</p>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
