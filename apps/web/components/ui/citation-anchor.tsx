"use client";

import React, { useState } from "react";

interface CitationSource {
  id: string;
  title: string;
  authors?: string;
  publication?: string;
  year?: number | string;
  pmid?: string;
  doi?: string;
  url?: string;
  confidenceScore?: number;
}

interface CitationAnchorProps {
  index: number;
  source: CitationSource;
  className?: string;
}

export function CitationAnchor({ index, source, className = "" }: CitationAnchorProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span className={`inline-relative inline-block ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-label={`Trích dẫn ${index}: ${source.title}`}
        className="inline-flex items-center justify-center h-4 min-w-4 px-1 -translate-y-1 mx-0.5 text-[10px] font-bold text-[var(--action-primary)] bg-[var(--clara-brand-50)] dark:bg-[var(--clara-brand-900)]/40 border border-[var(--clara-brand-200)] dark:border-[var(--clara-brand-800)] rounded hover:bg-[var(--clara-brand-100)] transition-colors focus-ring"
      >
        {index}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute left-0 bottom-full mb-2 z-50 w-72 sm:w-80 p-3.5 bg-[var(--surface-0)] border border-[var(--border-default)] rounded-xl shadow-lg text-left animate-fade-in text-xs leading-normal">
            <div className="flex items-start justify-between gap-2">
              <span className="font-semibold text-[var(--text-primary)] line-clamp-2">
                [{index}] {source.title}
              </span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] p-0.5"
              >
                ✕
              </button>
            </div>
            {(source.authors || source.publication) && (
              <div className="mt-1 text-[var(--text-secondary)]">
                {source.authors && <span>{source.authors}. </span>}
                {source.publication && <span className="italic">{source.publication} </span>}
                {source.year && <span>({source.year}).</span>}
              </div>
            )}
            <div className="mt-2.5 pt-2 border-t border-[var(--border-subtle)] flex items-center justify-between text-[11px]">
              {source.pmid && (
                <span className="text-[var(--text-tertiary)]">PMID: {source.pmid}</span>
              )}
              {source.url ? (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-[var(--action-primary)] hover:underline ml-auto"
                >
                  Xem tài liệu gốc ↗
                </a>
              ) : null}
            </div>
          </div>
        </>
      )}
    </span>
  );
}

export default CitationAnchor;
