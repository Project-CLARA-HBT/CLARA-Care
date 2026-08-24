"use client";

import React from "react";

export interface FloatingMetadataProps {
  label: string;
  value: string;
  tag?: string;
  tone?: "azure" | "mint" | "iris" | "neutral";
  className?: string;
}

export function FloatingMetadata({
  label,
  value,
  tag,
  tone = "azure",
  className = "",
}: FloatingMetadataProps) {
  const toneDot = {
    azure: "bg-[#0B6FD8]",
    mint: "bg-[#14A88D]",
    iris: "bg-[#8B7CF6]",
    neutral: "bg-[#6D7A8E]",
  }[tone];

  return (
    <div
      className={`clara-floating-chrome z-30 inline-flex items-center gap-3 rounded-2xl px-4 py-2.5 shadow-lg ${className}`}
    >
      <span className={`h-2 w-2 rounded-full shrink-0 ${toneDot}`} aria-hidden="true" />
      <div className="flex flex-col text-left">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D7A8E]">
            {label}
          </span>
          {tag && (
            <span className="rounded bg-[#F1F5F9] px-1.5 py-0.5 text-[10px] font-semibold text-[#48566A]">
              {tag}
            </span>
          )}
        </div>
        <span className="text-xs font-semibold text-[#162033] line-clamp-1">{value}</span>
      </div>
    </div>
  );
}
