"use client";

import React from "react";

export interface EditorialStatementProps {
  eyebrow?: string;
  statement: string;
  subtext?: string;
  align?: "left" | "center";
  className?: string;
}

export function EditorialStatement({
  eyebrow,
  statement,
  subtext,
  align = "center",
  className = "",
}: EditorialStatementProps) {
  const alignClass = align === "center" ? "text-center mx-auto" : "text-left";

  return (
    <div className={`max-w-4xl py-12 md:py-20 ${alignClass} ${className}`}>
      {eyebrow && (
        <span className="text-xs font-bold uppercase tracking-widest text-[#0B6FD8] mb-4 block">
          {eyebrow}
        </span>
      )}
      <blockquote className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold tracking-tight text-[#162033] leading-tight">
        “{statement}”
      </blockquote>
      {subtext && (
        <p className="text-base sm:text-lg text-[#48566A] mt-6 max-w-2xl mx-auto leading-relaxed">
          {subtext}
        </p>
      )}
    </div>
  );
}
