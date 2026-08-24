"use client";

import React from "react";

export interface EditorialStatementProps {
  number?: string;
  statement: string;
  subtext?: string;
  tone?: "azure" | "mint" | "iris" | "neutral";
  className?: string;
}

export function EditorialStatement({
  number,
  statement,
  subtext,
  tone = "azure",
  className = "",
}: EditorialStatementProps) {
  const accentColor = {
    azure: "text-[#0B6FD8]",
    mint: "text-[#14A88D]",
    iris: "text-[#8B7CF6]",
    neutral: "text-[#48566A]",
  }[tone];

  return (
    <div className={`flex flex-col gap-3 py-6 ${className}`}>
      {number && (
        <span className={`text-2xl md:text-3xl font-black font-mono tracking-tight ${accentColor}`}>
          {number}
        </span>
      )}
      <p className="text-2xl sm:text-3xl md:text-4xl font-bold tracking-tight text-[#162033] leading-snug">
        {statement}
      </p>
      {subtext && (
        <p className="text-base sm:text-lg text-[#48566A] leading-relaxed max-w-2xl">
          {subtext}
        </p>
      )}
    </div>
  );
}
