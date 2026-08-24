"use client";

import React, { useState } from "react";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V6 } from "../landing-copy-v6";
import { LandingScene } from "../primitives/landing-scene";
import { SceneHeader } from "../primitives/scene-header";

export function FaqScene() {
  const { language } = useMotionTier();
  const copy = LANDING_COPY_V6[language].faq;
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggleItem = (index: number) => {
    setOpenIndex((prev) => (prev === index ? null : index));
  };

  return (
    <LandingScene id="faq" scale="standard" tone="canvas">
      <SceneHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        align="center"
        tone="neutral"
      />

      <div className="mx-auto max-w-3xl space-y-3.5">
        {copy.items.map((item, index) => {
          const isOpen = openIndex === index;
          const headerId = `faq-header-${index}`;
          const panelId = `faq-panel-${index}`;

          return (
            <div
              key={item.question}
              className={`rounded-2xl bg-white border transition-colors duration-150 ${
                isOpen
                  ? "border-[#0B6FD8]/40 shadow-xs"
                  : "border-[#E3E8EF] hover:border-[#D5DDE7]"
              }`}
            >
              <h3>
                <button
                  id={headerId}
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  onClick={() => toggleItem(index)}
                  className="w-full flex items-center justify-between gap-4 p-5 sm:p-6 text-left rounded-2xl text-[#162033] font-semibold text-base sm:text-lg transition-colors clara-focus-ring focus-visible:outline-none"
                >
                  <span className="leading-snug">{item.question}</span>
                  <span
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border text-sm font-semibold transition-all duration-200 ${
                      isOpen
                        ? "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/30"
                        : "bg-[#F8FAFD] text-[#6D7A8E] border-[#E3E8EF]"
                    }`}
                    aria-hidden="true"
                  >
                    <svg
                      className={`h-4 w-4 transition-transform duration-200 ${
                        isOpen ? "rotate-180 text-[#0B6FD8]" : "text-[#6D7A8E]"
                      }`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </span>
                </button>
              </h3>

              {isOpen && (
                <div
                  id={panelId}
                  role="region"
                  aria-labelledby={headerId}
                  className="px-5 sm:px-6 pb-5 sm:pb-6 text-sm sm:text-base leading-relaxed text-[#48566A] border-t border-[#E3E8EF]/60 pt-4"
                >
                  <p>{item.answer}</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </LandingScene>
  );
}
