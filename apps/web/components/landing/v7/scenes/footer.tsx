"use client";

import React from "react";
import Link from "next/link";
import { useMotionTier } from "../runtime/motion-provider";
import { LANDING_COPY_V7 } from "../landing-copy-v7";
import type { UILanguage } from "@/lib/ui-language";

export function FooterScene() {
  const { language, setLanguage } = useMotionTier();
  const lang = language === "en" ? "en" : "vi";
  const copy = LANDING_COPY_V7[lang] ?? LANDING_COPY_V7.vi;
  const footerCopy = copy.footer;

  return (
    <footer
      id="footer"
      className="relative w-full border-t border-[#E3E8EF] bg-white text-[#162033] transition-colors"
      aria-label="Site footer"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-16 pb-12">
        {/* Main Columns Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-8 pb-12 border-b border-[#E3E8EF]">
          {/* Brand & Medical Disclaimer Column (Desktop: 4 columns) */}
          <div className="lg:col-span-4 space-y-4 text-left">
            <Link
              href="/"
              className="inline-flex items-center gap-2.5 clara-focus-ring rounded-xl group"
              aria-label="CLARA Care homepage"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#0B6FD8] text-white font-black text-base shadow-xs group-hover:bg-[#0855A8] transition-colors">
                ✦
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-lg leading-tight text-[#162033]">
                  {copy.nav.brand}
                </span>
                <span className="text-[11px] font-medium text-[#6D7A8E]">
                  {copy.nav.brandTag}
                </span>
              </div>
            </Link>

            <p className="text-sm text-[#48566A] leading-relaxed max-w-sm">
              {footerCopy.tagline}
            </p>

            {/* Medical Disclaimer Callout */}
            <div className="rounded-2xl bg-[#F8FAFD] p-4 border border-[#E3E8EF] text-xs text-[#6D7A8E] leading-relaxed">
              <div className="flex items-start gap-2.5">
                <svg
                  className="w-4 h-4 text-[#0B6FD8] shrink-0 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p>{footerCopy.disclaimer}</p>
              </div>
            </div>
          </div>

          {/* 4 Navigation Link Columns (Desktop: 8 columns) */}
          <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-8">
            {/* Column 1: Sản phẩm */}
            <div className="space-y-3.5 text-left">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                {footerCopy.columns.product.title}
              </h3>
              <ul className="space-y-2.5 text-sm">
                {footerCopy.columns.product.links.map((link) => (
                  <li key={link.href + link.label}>
                    <Link
                      href={link.href}
                      className="text-[#48566A] hover:text-[#0B6FD8] transition-colors duration-150 inline-block clara-focus-ring rounded-sm"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Column 2: Chuyên gia & Lâm sàng */}
            <div className="space-y-3.5 text-left">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                {footerCopy.columns.clinical.title}
              </h3>
              <ul className="space-y-2.5 text-sm">
                {footerCopy.columns.clinical.links.map((link) => (
                  <li key={link.href + link.label}>
                    <Link
                      href={link.href}
                      className="text-[#48566A] hover:text-[#0B6FD8] transition-colors duration-150 inline-block clara-focus-ring rounded-sm"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Column 3: Tin cậy & An toàn */}
            <div className="space-y-3.5 text-left">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                {footerCopy.columns.trust.title}
              </h3>
              <ul className="space-y-2.5 text-sm">
                {footerCopy.columns.trust.links.map((link) => (
                  <li key={link.href + link.label}>
                    <Link
                      href={link.href}
                      className="text-[#48566A] hover:text-[#0B6FD8] transition-colors duration-150 inline-block clara-focus-ring rounded-sm"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Column 4: Hỗ trợ & Pháp lý */}
            <div className="space-y-3.5 text-left">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#162033]">
                {footerCopy.columns.company.title}
              </h3>
              <ul className="space-y-2.5 text-sm">
                {footerCopy.columns.company.links.map((link) => (
                  <li key={link.href + link.label}>
                    <Link
                      href={link.href}
                      className="text-[#48566A] hover:text-[#0B6FD8] transition-colors duration-150 inline-block clara-focus-ring rounded-sm"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* Sub-footer / Legal / Language Bar */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#6D7A8E]">
          <p>{footerCopy.copyright}</p>

          <div className="flex flex-wrap items-center gap-6">
            <Link
              href="/terms"
              className="hover:text-[#162033] transition-colors clara-focus-ring"
            >
              {footerCopy.terms}
            </Link>
            <Link
              href="/privacy"
              className="hover:text-[#162033] transition-colors clara-focus-ring"
            >
              {footerCopy.privacy}
            </Link>
            <Link
              href="/consent"
              className="hover:text-[#162033] transition-colors clara-focus-ring"
            >
              {footerCopy.consent}
            </Link>

            {/* Language Switcher in Footer */}
            <div
              role="group"
              aria-label={copy.languageLabel}
              className="inline-flex items-center p-0.5 rounded-full bg-[#162033]/5 border border-[#E3E8EF]"
            >
              <button
                type="button"
                onClick={() => setLanguage("vi" as UILanguage)}
                aria-label={copy.languageNames.vi}
                className={`px-2 py-0.5 rounded-full text-[11px] font-bold transition-all ${
                  language === "vi"
                    ? "bg-white text-[#0B6FD8] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
                aria-pressed={language === "vi"}
              >
                VI
              </button>
              <button
                type="button"
                onClick={() => setLanguage("en" as UILanguage)}
                aria-label={copy.languageNames.en}
                className={`px-2 py-0.5 rounded-full text-[11px] font-bold transition-all ${
                  language === "en"
                    ? "bg-white text-[#0B6FD8] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
                aria-pressed={language === "en"}
              >
                EN
              </button>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default FooterScene;
