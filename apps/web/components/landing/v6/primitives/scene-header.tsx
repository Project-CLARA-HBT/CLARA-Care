"use client";

import React from "react";

export interface SceneHeaderProps {
  eyebrow?: string;
  badge?: string;
  title: string;
  accent?: string;
  description?: string;
  align?: "left" | "center" | "split";
  tone?: "azure" | "mint" | "iris" | "neutral";
  asH1?: boolean;
  className?: string;
}

export function SceneHeader({
  eyebrow,
  badge,
  title,
  accent,
  description,
  align = "left",
  tone = "azure",
  asH1 = false,
  className = "",
}: SceneHeaderProps) {
  const tonePillColor = {
    azure: "bg-[#EFF7FF] text-[#0B6FD8] border-[#0B6FD8]/20",
    mint: "bg-[#ECFDF8] text-[#14A88D] border-[#14A88D]/20",
    iris: "bg-[#F5F3FF] text-[#8B7CF6] border-[#8B7CF6]/20",
    neutral: "bg-[#F1F5F9] text-[#48566A] border-[#E3E8EF]",
  }[tone];

  const toneAccentColor = {
    azure: "text-[#0B6FD8]",
    mint: "text-[#14A88D]",
    iris: "text-[#8B7CF6]",
    neutral: "text-[#162033]",
  }[tone];

  const alignClasses = {
    left: "text-left max-w-3xl",
    center: "text-center mx-auto max-w-3xl items-center",
    split: "flex flex-col md:flex-row md:items-end md:justify-between gap-6",
  }[align];

  const HeadingTag = asH1 ? "h1" : "h2";

  return (
    <div className={`mb-12 md:mb-16 ${alignClasses} ${className}`}>
      <div className={align === "split" ? "max-w-2xl" : ""}>
        {(eyebrow || badge) && (
          <div className={`flex items-center gap-3 mb-4 ${align === "center" ? "justify-center" : ""}`}>
            {eyebrow && (
              <span className="text-xs font-bold tracking-widest uppercase text-[#6D7A8E]">
                {eyebrow}
              </span>
            )}
            {badge && (
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${tonePillColor}`}
              >
                {badge}
              </span>
            )}
          </div>
        )}

        <HeadingTag className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-[#162033] leading-[1.12]">
          {title} {accent && <span className={toneAccentColor}>{accent}</span>}
        </HeadingTag>
      </div>

      {description && (
        <p
          className={`text-base sm:text-lg text-[#48566A] leading-relaxed mt-4 ${
            align === "split" ? "md:mt-0 md:max-w-md" : ""
          }`}
        >
          {description}
        </p>
      )}
    </div>
  );
}
