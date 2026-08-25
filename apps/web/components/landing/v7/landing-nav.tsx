"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { useMotionTier } from "./runtime/motion-provider";
import { LANDING_COPY_V7 } from "./landing-copy-v7";
import type { UILanguage } from "@/lib/ui-language";

export function LandingNav() {
  const { language, setLanguage } = useMotionTier();
  const copy = LANDING_COPY_V7[language]?.nav ?? LANDING_COPY_V7.vi.nav;
  const langLabel = LANDING_COPY_V7[language]?.languageLabel ?? LANDING_COPY_V7.vi.languageLabel;
  const langNames = LANDING_COPY_V7[language]?.languageNames ?? LANDING_COPY_V7.vi.languageNames;

  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const drawerRef = useRef<HTMLDivElement>(null);
  const hamburgerBtnRef = useRef<HTMLButtonElement>(null);

  // Monitor scroll for smooth compact height transition
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const closeMobileMenu = useCallback(() => {
    setIsMobileMenuOpen(false);
    hamburgerBtnRef.current?.focus();
  }, []);

  // Accessible escape key listener and focus trap for mobile modal drawer
  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeMobileMenu();
        return;
      }

      if (e.key === "Tab" && drawerRef.current) {
        const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    window.addEventListener("keydown", handleKeyDown);

    // Initial focus on first interactive element in drawer
    const timer = setTimeout(() => {
      if (drawerRef.current) {
        const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
          focusableElements[0].focus();
        }
      }
    }, 50);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileMenuOpen, closeMobileMenu]);

  const navLinks = [
    { href: "#how-it-works", label: copy.howItWorks },
    { href: "#chat", label: copy.features },
    { href: "#safety", label: copy.safety },
    { href: "#clinical-transition", label: copy.clinical },
  ];

  return (
    <>
      {/* Skip to main content accessibility link */}
      <a
        href="#hero"
        className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[60] focus:px-4 focus:py-2 focus:bg-[#0B6FD8] focus:text-white focus:font-semibold focus:rounded-xl focus:shadow-xl focus:outline-none"
      >
        {copy.skipToContent}
      </a>

      {/* Floating Island Navigation Outer Wrapper */}
      <header
        role="banner"
        className={`fixed top-0 left-0 right-0 z-50 pointer-events-none transition-all duration-300 ease-out px-3 sm:px-6 flex justify-center ${
          isScrolled ? "pt-2 sm:pt-3" : "pt-4 sm:pt-5"
        }`}
      >
        {/* Floating Island Inner Container */}
        <nav
          aria-label="Main Navigation"
          className={`pointer-events-auto w-full max-w-[1200px] clara-floating-chrome rounded-full transition-all duration-300 ease-out flex items-center justify-between gap-3 ${
            isScrolled
              ? "py-2 px-3 sm:px-5 shadow-md"
              : "py-3 px-4 sm:px-6 shadow-xl"
          }`}
        >
          {/* Brand Logo */}
          <Link
            href="/"
            className="flex items-center gap-2.5 group focus:outline-none rounded-full"
            aria-label={copy.brand}
          >
            <div className="flex h-8 w-8 sm:h-9 sm:w-9 items-center justify-center rounded-full bg-[#0B6FD8] text-white font-black text-sm sm:text-base shadow-xs group-hover:bg-[#0855A8] transition-colors">
              ✦
            </div>
            <div className="flex flex-col text-left">
              <span className="font-bold text-sm sm:text-base text-[#162033] tracking-tight group-hover:text-[#0B6FD8] transition-colors leading-tight">
                {copy.brand}
              </span>
              <span className="text-[10px] text-[#6D7A8E] hidden lg:block leading-none">
                {copy.brandTag}
              </span>
            </div>
          </Link>

          {/* Center Navigation Links (Desktop / Tablet) */}
          <div className="hidden md:flex items-center gap-1 lg:gap-2">
            {navLinks.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-xs lg:text-sm font-semibold text-[#48566A] hover:text-[#0B6FD8] px-3 py-1.5 rounded-full hover:bg-[#EFF7FF] transition-colors clara-focus-ring"
              >
                {item.label}
              </a>
            ))}
          </div>

          {/* Right Action Items: Language Switcher, Login, CTA */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Language Switcher (VI / EN) */}
            <div
              role="group"
              aria-label={langLabel}
              className="inline-flex items-center p-0.5 rounded-full bg-[#162033]/5 border border-[#E3E8EF]"
            >
              <button
                type="button"
                onClick={() => setLanguage("vi" as UILanguage)}
                className={`px-2.5 py-1 rounded-full text-xs font-bold transition-all ${
                  language === "vi"
                    ? "bg-white text-[#0B6FD8] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
                aria-pressed={language === "vi"}
                title={langNames.vi}
              >
                VI
              </button>
              <button
                type="button"
                onClick={() => setLanguage("en" as UILanguage)}
                className={`px-2.5 py-1 rounded-full text-xs font-bold transition-all ${
                  language === "en"
                    ? "bg-white text-[#0B6FD8] shadow-xs"
                    : "text-[#6D7A8E] hover:text-[#162033]"
                }`}
                aria-pressed={language === "en"}
                title={langNames.en}
              >
                EN
              </button>
            </div>

            {/* Login Link */}
            <Link
              href="/login"
              className="hidden sm:inline-flex items-center justify-center text-xs lg:text-sm font-semibold text-[#48566A] hover:text-[#162033] px-3 py-1.5 rounded-full hover:bg-black/5 transition-colors clara-focus-ring"
            >
              {copy.login}
            </Link>

            {/* Primary CTA Button */}
            <Link
              href="/chat"
              className="inline-flex items-center justify-center gap-1.5 rounded-full bg-[#0B6FD8] hover:bg-[#0855A8] px-4 sm:px-5 py-2 text-xs sm:text-sm font-bold text-white shadow-sm hover:shadow-md transition-all clara-focus-ring active:scale-95"
            >
              <span>{copy.askClara}</span>
              <svg
                aria-hidden="true"
                className="w-3.5 h-3.5"
                viewBox="0 0 16 16"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M6.22 3.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 0 1 0-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </Link>

            {/* Mobile Hamburger Button */}
            <button
              ref={hamburgerBtnRef}
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              aria-expanded={isMobileMenuOpen}
              aria-label={copy.openMenu}
              aria-controls="mobile-nav-drawer"
              className="md:hidden flex h-9 w-9 items-center justify-center rounded-full text-[#162033] hover:bg-[#EFF7FF] transition-colors clara-focus-ring"
            >
              <svg
                aria-hidden="true"
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
          </div>
        </nav>
      </header>

      {/* Mobile Drawer Modal & Backdrop */}
      {isMobileMenuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-50 bg-[#162033]/40 backdrop-blur-sm md:hidden transition-opacity"
            onClick={closeMobileMenu}
            aria-hidden="true"
          />

          {/* Modal Drawer */}
          <div
            ref={drawerRef}
            id="mobile-nav-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={copy.brand}
            className="fixed top-3 inset-x-3 max-w-lg mx-auto z-50 md:hidden bg-white/95 backdrop-blur-2xl rounded-3xl p-5 border border-[#E3E8EF] shadow-2xl flex flex-col gap-4 text-left animate-in zoom-in-95 duration-200"
          >
            {/* Drawer Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#E3E8EF]">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#0B6FD8] text-white font-black text-sm">
                  ✦
                </div>
                <div>
                  <span className="font-bold text-base text-[#162033]">
                    {copy.brand}
                  </span>
                  <p className="text-[10px] text-[#6D7A8E]">{copy.brandTag}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={closeMobileMenu}
                aria-label={copy.closeMenu}
                className="flex h-9 w-9 items-center justify-center rounded-full text-[#48566A] hover:bg-[#F1F5F9] transition-colors clara-focus-ring"
              >
                <svg
                  aria-hidden="true"
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            {/* Mobile Nav Links */}
            <div className="flex flex-col gap-1 py-1">
              {navLinks.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={closeMobileMenu}
                  className="px-4 py-2.5 rounded-xl text-sm font-semibold text-[#162033] hover:bg-[#EFF7FF] hover:text-[#0B6FD8] transition-colors clara-focus-ring"
                >
                  {item.label}
                </a>
              ))}
            </div>

            {/* Language Switcher Row in Mobile Drawer */}
            <div className="flex items-center justify-between pt-3 border-t border-[#E3E8EF]">
              <span className="text-xs font-semibold text-[#48566A]">
                {langLabel}
              </span>
              <div
                role="group"
                aria-label={langLabel}
                className="inline-flex items-center p-0.5 rounded-full bg-[#162033]/5 border border-[#E3E8EF]"
              >
                <button
                  type="button"
                  onClick={() => setLanguage("vi" as UILanguage)}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
                    language === "vi"
                      ? "bg-white text-[#0B6FD8] shadow-xs"
                      : "text-[#6D7A8E]"
                  }`}
                  aria-pressed={language === "vi"}
                >
                  VI
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage("en" as UILanguage)}
                  className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${
                    language === "en"
                      ? "bg-white text-[#0B6FD8] shadow-xs"
                      : "text-[#6D7A8E]"
                  }`}
                  aria-pressed={language === "en"}
                >
                  EN
                </button>
              </div>
            </div>

            {/* Mobile Drawer Action Buttons */}
            <div className="flex flex-col gap-2 pt-2 border-t border-[#E3E8EF]">
              <Link
                href="/login"
                onClick={closeMobileMenu}
                className="w-full text-center py-2.5 rounded-xl text-sm font-semibold text-[#162033] bg-[#F8FAFD] hover:bg-[#EFF7FF] border border-[#E3E8EF] transition-colors clara-focus-ring"
              >
                {copy.login}
              </Link>
              <Link
                href="/chat"
                onClick={closeMobileMenu}
                className="w-full text-center py-2.5 rounded-xl text-sm font-bold text-white bg-[#0B6FD8] hover:bg-[#0855A8] shadow-sm transition-all clara-focus-ring active:scale-98"
              >
                {copy.askClara} ➔
              </Link>
            </div>
          </div>
        </>
      )}
    </>
  );
}

export default LandingNav;
