"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";

import {
  LANDING_COPY,
  LANDING_MODULE_HREFS,
  LANDING_MODULE_ICONS,
  type InteractivePreviewTab,
} from "@/components/landing/clara-kp3-copy";
import { SPONSORS } from "@/components/landing/clara-kp3-data";
import { Badge } from "@/components/ui/badge";
import Icon, { type IconName } from "@/components/ui/icon";
import { saveUILanguage, type UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

const LANDING_ICONS: Record<string, IconName> = {
  account_tree: "progress",
  arrow_forward: "arrow-right",
  barcode_scanner: "scan",
  category: "more",
  check_circle: "check",
  clinical_notes: "clinical-notes",
  contact_support: "contact",
  edit_note: "clinical-notes",
  expand_more: "chevron-down",
  fact_check: "check",
  flight_takeoff: "progress",
  gavel: "warning",
  groups: "contact",
  handshake: "contact",
  health_and_safety: "warning",
  help: "help",
  medication: "medication",
  menu_book: "clinical-notes",
  monitoring: "progress",
  neurology: "body",
  person_add: "user-card",
  play_circle: "progress",
  psychology: "clinical-notes",
  school: "clinical-notes",
  security: "warning",
  shield: "warning",
  stethoscope: "clinical-notes",
  task_alt: "check",
  timer: "progress",
  verified: "check",
  widgets: "more",
  biotech: "search",
  search: "search",
  emergency: "emergency",
  "user-card": "user-card",
  chat: "chat",
};

function LandingIcon({
  glyph,
  className = "",
  size = 20,
}: {
  glyph: string;
  className?: string;
  size?: number;
}) {
  return (
    <Icon
      name={LANDING_ICONS[glyph] ?? "clinical-notes"}
      size={size}
      className={className}
      aria-hidden="true"
    />
  );
}

export default function ClaraKp3Landing() {
  const language = useUILanguage();
  const copy = LANDING_COPY[language] ?? LANDING_COPY.vi;
  const [activePreviewTab, setActivePreviewTab] = useState<InteractivePreviewTab["id"]>("ddi");
  const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

  const modules = copy.modules.map((module, index) => ({
    ...module,
    icon: LANDING_MODULE_ICONS[index] ?? "clinical-notes",
    href: LANDING_MODULE_HREFS[index] ?? "/chat",
  }));

  const currentTab =
    copy.interactivePreview.tabs.find((t) => t.id === activePreviewTab) ??
    copy.interactivePreview.tabs[0];

  return (
    <div
      className="min-h-screen bg-[var(--bg-canvas)] text-[var(--text-primary)]"
      data-shell-mode="PUBLIC_MARKETING"
      data-layout-archetype="Marketing Landing"
    >
      {/* 1. Quiet Public Navigation Header */}
      <header className="sticky top-0 z-50 w-full border-b border-[color:var(--shell-border)] bg-[var(--surface-panel)]/95 backdrop-blur-md">
        <nav
          className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3.5 sm:px-6 lg:px-8"
          aria-label="Public Navigation"
        >
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2.5 focus-ring rounded-lg">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--brand-600)] text-base font-black text-[var(--button-primary-text)] shadow-sm">
                C
              </div>
              <div className="flex flex-col">
                <span className="text-base font-extrabold tracking-tight text-[var(--text-primary)]">
                  The <span className="text-[var(--text-brand)]">Clara Care</span>
                </span>
                <span className="text-[10px] font-bold tracking-widest text-[var(--text-muted)] uppercase">
                  Clinical AI Assistant
                </span>
              </div>
            </Link>
          </div>

          <div className="hidden items-center gap-6 lg:flex">
            <a
              href="#hero"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.engine}
            </a>
            <a
              href="#preview"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.modules}
            </a>
            <a
              href="#pathways"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.pathways}
            </a>
            <a
              href="#safety"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.safety}
            </a>
            <a
              href="#workflow"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.workflow}
            </a>
            <Link
              href="/huong-dan"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-brand)]"
            >
              {copy.nav.guide}
            </Link>
            <a
              href="#faq"
              className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.faq}
            </a>
          </div>

          <div className="flex items-center gap-2.5">
            <label htmlFor="landing-lang-select" className="sr-only">
              {copy.languageLabel}
            </label>
            <select
              id="landing-lang-select"
              value={language}
              onChange={(e) => saveUILanguage(e.target.value as UILanguage)}
              className="focus-ring rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2.5 py-1.5 text-xs font-bold text-[var(--text-primary)] transition-colors"
            >
              <option value="vi">{copy.languageNames.vi}</option>
              <option value="en">{copy.languageNames.en}</option>
            </select>

            <Link
              href="/login"
              className="focus-ring rounded-lg px-3.5 py-1.5 text-xs font-bold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.login}
            </Link>

            <Link
              href="/register"
              className="focus-ring rounded-lg border border-[var(--brand-700)] bg-[var(--brand-600)] px-4 py-1.5 text-xs font-bold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] shadow-sm"
            >
              {copy.nav.register}
            </Link>
          </div>
        </nav>
      </header>

      <main className="overflow-x-hidden">
        {/* 2. Spatial Editorial Hero Section */}
        <section
          id="hero"
          className="relative mx-auto max-w-7xl px-4 pb-16 pt-12 sm:px-6 sm:pb-24 sm:pt-16 lg:px-8 lg:pb-28 lg:pt-20"
        >
          <div className="flex flex-col gap-12 lg:flex-row lg:items-center lg:gap-14">
            {/* Left Hero Content */}
            <div className="w-full space-y-7 lg:w-[54%]">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="brand" icon="check">
                  {copy.hero.safetyBadgeFides}
                </Badge>
                <Badge tone="ok" icon="warning">
                  {copy.hero.safetyBadgeZeroCot}
                </Badge>
              </div>

              <h1
                className="font-black leading-[1.08] tracking-tight text-[var(--text-primary)] [text-wrap:balance]"
                style={{ fontSize: "clamp(2rem, 5.2vw, 3.8rem)" }}
              >
                {copy.hero.headingStart}{" "}
                <span className="text-[var(--text-brand)]">{copy.hero.headingAccent}</span>{" "}
                {copy.hero.headingEnd}
              </h1>

              <p className="max-w-[58ch] text-base font-medium leading-relaxed text-[var(--text-secondary)] sm:text-lg">
                {copy.hero.descriptionBefore}
                <strong className="font-bold text-[var(--text-primary)]">
                  {copy.hero.audience}
                </strong>
                {copy.hero.descriptionAfter}
              </p>

              {/* Primary Action Buttons */}
              <div className="flex flex-wrap items-center gap-3.5 pt-2">
                <Link
                  href="/chat"
                  className="focus-ring group inline-flex items-center justify-center gap-2.5 rounded-xl bg-[var(--brand-600)] px-7 py-3.5 text-base font-bold text-[var(--button-primary-text)] shadow-sm transition-all hover:bg-[var(--brand-700)] hover:shadow"
                >
                  {copy.hero.primaryCta}
                  <Icon
                    name="arrow-right"
                    size={18}
                    className="transition-transform group-hover:translate-x-1"
                  />
                </Link>
                <a
                  href="#pathways"
                  className="focus-ring inline-flex items-center justify-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-6 py-3.5 text-base font-bold text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-muted)]"
                >
                  <Icon name="chevron-down" size={18} className="text-[var(--text-secondary)]" />
                  {copy.hero.secondaryCta}
                </a>
              </div>

              {/* Safety & Evidence Invariant Highlights */}
              <div className="grid grid-cols-1 gap-3 border-t border-[color:var(--shell-border)] pt-7 sm:grid-cols-3 sm:gap-4">
                <div className="flex items-start gap-2.5">
                  <Icon name="check" size={18} className="mt-0.5 text-[var(--text-brand)]" />
                  <span className="text-xs font-semibold leading-snug text-[var(--text-secondary)]">
                    {copy.hero.sourceWhenAvailable}
                  </span>
                </div>
                <div className="flex items-start gap-2.5">
                  <Icon name="warning" size={18} className="mt-0.5 text-[var(--text-brand)]" />
                  <span className="text-xs font-semibold leading-snug text-[var(--text-secondary)]">
                    {copy.hero.uncertainty}
                  </span>
                </div>
                <div className="flex items-start gap-2.5">
                  <Icon name="emergency" size={18} className="mt-0.5 text-[var(--text-brand)]" />
                  <span className="text-xs font-semibold leading-snug text-[var(--text-secondary)]">
                    {copy.hero.safetyGuard}
                  </span>
                </div>
              </div>
            </div>

            {/* Right Hero Visual Card */}
            <div className="w-full lg:w-[46%]">
              <div className="relative rounded-2xl border border-[color:var(--shell-border)] border-t-[color:var(--card-top-border)] bg-[var(--surface-panel)] p-5 shadow-lg sm:p-6">
                {/* Visual Header */}
                <div className="mb-4 flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                  <div className="flex items-center gap-2.5">
                    <div className="flex gap-1.5">
                      <span className="h-2.5 w-2.5 rounded-full bg-[var(--brand-500)]" />
                      <span className="h-2.5 w-2.5 rounded-full bg-[var(--status-ok-border)]" />
                      <span className="h-2.5 w-2.5 rounded-full bg-[var(--status-warn-border)]" />
                    </div>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      {copy.hero.preview.systemCore}
                    </span>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-[10px] font-bold text-[var(--text-brand)]">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--brand-500)]" />
                    {copy.hero.preview.activeSession}
                  </span>
                </div>

                {/* Simulated Conversation */}
                <div className="space-y-4">
                  {/* User Query */}
                  <div className="flex justify-end">
                    <div className="max-w-[88%] rounded-2xl rounded-tr-sm border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-sm font-medium text-[var(--text-primary)]">
                      {copy.hero.preview.question}
                    </div>
                  </div>

                  {/* AI Response */}
                  <div className="flex items-start gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[var(--brand-600)] text-xs font-bold text-[var(--button-primary-text)]">
                      C
                    </div>
                    <div className="space-y-2.5 rounded-2xl rounded-tl-sm border border-[color:var(--shell-border)] bg-[var(--surface-container-high)] p-4 text-[var(--text-primary)]">
                      <div className="flex items-center gap-2">
                        <Badge tone="warn" icon="warning">
                          FIDES CẢNH BÁO LIỀU
                        </Badge>
                        <span className="text-[10px] font-bold text-[var(--text-muted)]">
                          CYP3A4 Inhibition
                        </span>
                      </div>
                      <p className="text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                        {copy.hero.preview.answer}
                      </p>
                      <div className="flex flex-wrap items-center gap-2 border-t border-[color:var(--shell-border)] pt-2.5 text-[11px]">
                        <span className="rounded bg-[var(--surface-muted)] px-2 py-0.5 font-semibold text-[var(--text-brand)]">
                          {copy.hero.preview.sourceWhenAvailable}
                        </span>
                        <span className="font-medium text-[var(--text-muted)]">
                          {copy.hero.preview.reviewSource}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Status Bar */}
                  <div className="flex items-center justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3.5 py-2.5 text-xs">
                    <div className="flex items-center gap-2 text-[var(--text-brand)]">
                      <Icon name="check" size={16} />
                      <span className="font-semibold">{copy.hero.preview.analysing}</span>
                    </div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                      Zero-CoT Active
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 3. Interactive Feature Preview Showcase */}
        <section
          id="preview"
          className="border-y border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-16 sm:py-20 lg:py-24"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <Badge tone="brand" className="mb-3">
                {copy.interactivePreview.eyebrow}
              </Badge>
              <h2
                className="font-black tracking-tight text-[var(--text-primary)] [text-wrap:balance]"
                style={{ fontSize: "clamp(1.75rem, 4vw, 2.75rem)" }}
              >
                {copy.interactivePreview.title}
              </h2>
              <p className="mt-3 text-base font-medium text-[var(--text-secondary)] sm:text-lg">
                {copy.interactivePreview.subtitle}
              </p>
            </div>

            {/* Tab Selector Buttons */}
            <div className="mt-10 flex flex-wrap items-center justify-center gap-2 sm:gap-3">
              {copy.interactivePreview.tabs.map((tab) => {
                const isActive = tab.id === activePreviewTab;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setActivePreviewTab(tab.id)}
                    className={`focus-ring rounded-xl px-4 py-2.5 text-xs font-bold transition-all sm:text-sm ${
                      isActive
                        ? "border border-[var(--brand-500)] bg-[var(--surface-brand-soft)] text-[var(--text-brand)] shadow-sm"
                        : "border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-secondary)] hover:bg-[var(--surface-container-high)] hover:text-[var(--text-primary)]"
                    }`}
                  >
                    {tab.tabLabel}
                  </button>
                );
              })}
            </div>

            {/* Active Tab Preview Card */}
            {currentTab ? (
              <div className="mt-8 rounded-2xl border border-[color:var(--shell-border)] border-t-[color:var(--card-top-border)] bg-[var(--surface-container-high)] p-6 sm:p-8 lg:p-10 shadow-md">
                <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-10">
                  {/* Left Column: Simulated Clinical Query & AI Result */}
                  <div className="space-y-6 lg:col-span-7">
                    <div className="flex flex-wrap items-center gap-2.5">
                      <Badge tone="brand" icon="clinical-notes">
                        {currentTab.badge}
                      </Badge>
                      <span className="text-xs font-bold text-[var(--text-muted)]">
                        {currentTab.safetyTag}
                      </span>
                    </div>

                    <div className="space-y-2">
                      <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                        Câu hỏi / Tình huống đầu vào:
                      </span>
                      <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-sm font-medium text-[var(--text-primary)]">
                        &ldquo;{currentTab.query}&rdquo;
                      </div>
                    </div>

                    <div className="space-y-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5">
                      <div className="flex items-center gap-2 text-xs font-bold text-[var(--text-brand)]">
                        <Icon name="check" size={16} />
                        {currentTab.responseHeadline}
                      </div>
                      <p className="text-sm font-normal leading-relaxed text-[var(--text-secondary)] whitespace-pre-line">
                        {currentTab.responseBody}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--shell-border)] pt-4">
                      <div className="space-y-1">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                          Nguồn trích dẫn:
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {currentTab.citations.map((c) => (
                            <span
                              key={c}
                              className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-0.5 text-[11px] font-semibold text-[var(--text-secondary)]"
                            >
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Parameters, Assurance & Feature CTA */}
                  <div className="flex flex-col justify-between space-y-6 border-t border-[color:var(--shell-border)] pt-6 lg:col-span-5 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
                    <div className="space-y-5">
                      <h3 className="text-lg font-bold text-[var(--text-primary)]">
                        {currentTab.title}
                      </h3>

                      {currentTab.detailPoints ? (
                        <div className="space-y-2.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                          {currentTab.detailPoints.map((pt) => (
                            <div
                              key={pt.label}
                              className="flex items-center justify-between text-xs"
                            >
                              <span className="font-semibold text-[var(--text-muted)]">
                                {pt.label}:
                              </span>
                              <span className="font-bold text-[var(--text-primary)]">
                                {pt.value}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : null}

                      <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)]/40 p-4 text-xs">
                        <div className="flex items-center gap-2 font-bold text-[var(--text-brand)]">
                          <Icon name="warning" size={16} />
                          Bảo vệ dữ liệu Zero-CoT
                        </div>
                        <p className="mt-1 text-[var(--text-secondary)]">
                          {currentTab.zeroCotAssurance}
                        </p>
                      </div>
                    </div>

                    <Link
                      href={currentTab.ctaHref}
                      className="focus-ring group inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--brand-600)] px-6 py-3 text-sm font-bold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] shadow-sm"
                    >
                      {currentTab.ctaText}
                      <Icon
                        name="arrow-right"
                        size={16}
                        className="transition-transform group-hover:translate-x-1"
                      />
                    </Link>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        {/* 4. Clinician & Personal Pathways */}
        <section id="pathways" className="py-20 sm:py-24 lg:py-28">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <Badge tone="brand" className="mb-3">
                {copy.pathways.eyebrow}
              </Badge>
              <h2
                className="font-black tracking-tight text-[var(--text-primary)] [text-wrap:balance]"
                style={{ fontSize: "clamp(1.85rem, 4.5vw, 3rem)" }}
              >
                {copy.pathways.title}
              </h2>
              <p className="mt-3 text-base font-medium text-[var(--text-secondary)] sm:text-lg">
                {copy.pathways.subtitle}
              </p>
            </div>

            <div className="mt-14 space-y-12">
              {copy.pathways.sections.map((pathway) => (
                <div
                  key={pathway.id}
                  className="rounded-2xl border border-[color:var(--shell-border)] border-t-[color:var(--card-top-border)] bg-[var(--surface-panel)] p-6 sm:p-8 lg:p-10"
                >
                  <div className="flex flex-col justify-between gap-4 border-b border-[color:var(--shell-border)] pb-6 sm:flex-row sm:items-center">
                    <div>
                      <Badge tone="brand" className="mb-2">
                        {pathway.tag}
                      </Badge>
                      <h3 className="text-xl font-bold tracking-tight text-[var(--text-primary)] sm:text-2xl">
                        {pathway.title}
                      </h3>
                      <p className="mt-1 text-sm font-medium text-[var(--text-secondary)]">
                        {pathway.subtitle}
                      </p>
                    </div>

                    <Link
                      href={pathway.primaryCta.href}
                      className="focus-ring group inline-flex shrink-0 items-center gap-2 rounded-xl bg-[var(--brand-600)] px-5 py-2.5 text-xs font-bold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] shadow-sm"
                    >
                      {pathway.primaryCta.label}
                      <Icon
                        name="arrow-right"
                        size={14}
                        className="transition-transform group-hover:translate-x-1"
                      />
                    </Link>
                  </div>

                  <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {pathway.features.map((feature) => (
                      <Link
                        key={feature.title}
                        href={feature.href}
                        className="focus-ring group flex flex-col justify-between rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5 transition-all hover:-translate-y-0.5 hover:bg-[var(--surface-container-high)]"
                      >
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                              <LandingIcon glyph={feature.icon} size={20} />
                            </div>
                            {feature.badge ? (
                              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-0.5 text-[10px] font-bold text-[var(--text-muted)]">
                                {feature.badge}
                              </span>
                            ) : null}
                          </div>
                          <h4 className="text-sm font-bold text-[var(--text-primary)] group-hover:text-[var(--text-brand)] transition-colors">
                            {feature.title}
                          </h4>
                          <p className="text-xs leading-relaxed text-[var(--text-secondary)]">
                            {feature.desc}
                          </p>
                        </div>

                        <div className="mt-4 flex items-center gap-1 text-[11px] font-bold text-[var(--text-brand)]">
                          <span>Chi tiết</span>
                          <Icon
                            name="arrow-right"
                            size={12}
                            className="transition-transform group-hover:translate-x-1"
                          />
                        </div>
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 5. Trust & Safety Invariants Strip */}
        <section
          id="safety"
          className="border-y border-[color:var(--shell-border)] bg-[var(--surface-container-high)] py-16 sm:py-20 lg:py-24"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <Badge tone="warn" icon="warning" className="mb-3">
                {copy.safetyStrip.eyebrow}
              </Badge>
              <h2
                className="font-black tracking-tight text-[var(--text-primary)] [text-wrap:balance]"
                style={{ fontSize: "clamp(1.75rem, 4vw, 2.75rem)" }}
              >
                {copy.safetyStrip.title}
              </h2>
              <p className="mt-3 text-base font-medium text-[var(--text-secondary)] sm:text-lg">
                {copy.safetyStrip.subtitle}
              </p>
            </div>

            <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {copy.safetyStrip.invariants.map((item) => (
                <div
                  key={item.title}
                  className="flex flex-col justify-between rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 shadow-sm"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                        <LandingIcon glyph={item.icon} size={22} />
                      </div>
                      <Badge tone="neutral">{item.badge}</Badge>
                    </div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">{item.title}</h3>
                    <p className="text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                      {item.desc}
                    </p>
                  </div>
                  <div className="mt-5 border-t border-[color:var(--shell-border)] pt-3 text-[11px] font-bold text-[var(--text-brand)]">
                    ✓ Bất biến & Khóa hồi quy
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 6. Real Product Workflow */}
        <section id="workflow" className="py-20 sm:py-24">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <h2
                className="font-black tracking-tight text-[var(--text-primary)]"
                style={{ fontSize: "clamp(1.75rem, 4.5vw, 2.85rem)" }}
              >
                {copy.workflow.titleStart}{" "}
                <span className="text-[var(--text-brand)]">{copy.workflow.titleAccent}</span>
              </h2>
            </div>

            <div className="mt-14 grid grid-cols-1 gap-8 md:grid-cols-3">
              {copy.workflow.steps.map((step) => (
                <div
                  key={step.number}
                  className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-7 space-y-4"
                >
                  <div className="text-4xl font-black text-[var(--text-brand)]">{step.number}</div>
                  <h3 className="flex items-center gap-2 text-lg font-bold text-[var(--text-primary)]">
                    <LandingIcon glyph={step.icon} size={20} className="text-[var(--text-brand)]" />
                    {step.title}
                  </h3>
                  <p className="text-sm font-medium leading-relaxed text-[var(--text-secondary)]">
                    {step.description}
                  </p>
                  <div className="border-t border-[color:var(--shell-border)] pt-3 text-xs font-bold text-[var(--text-brand)]">
                    → {step.outcome}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 7. Sponsors & Ecosystem Strip */}
        <section className="border-y border-[color:var(--shell-border)] bg-[var(--surface-muted)] py-10">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mb-2 text-center text-xs font-black uppercase tracking-[0.2em] text-[var(--text-muted)]">
              {copy.sponsors.heading}
            </div>
            <div className="mb-6 text-center text-xs font-medium text-[var(--text-secondary)]">
              {copy.sponsors.description}
            </div>
            <div className="flex flex-wrap justify-center gap-4">
              {SPONSORS.map((sponsor) => (
                <a
                  key={sponsor.name}
                  href={sponsor.href}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-h-[90px] w-full max-w-xs items-center justify-center rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 transition-transform hover:-translate-y-0.5"
                >
                  <Image
                    src={sponsor.logo}
                    alt={`${sponsor.name} logo`}
                    width={sponsor.name === "BNIX" ? 220 : 400}
                    height={sponsor.name === "BNIX" ? 60 : 120}
                    className={
                      sponsor.name === "BNIX"
                        ? "h-9 w-auto object-contain"
                        : "h-11 w-auto object-contain"
                    }
                  />
                </a>
              ))}
            </div>
          </div>
        </section>

        {/* 8. FAQ Section */}
        <section id="faq" className="py-20 sm:py-24">
          <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
            <h2
              className="mb-10 text-center font-black tracking-tight text-[var(--text-primary)]"
              style={{ fontSize: "clamp(1.75rem, 4vw, 2.5rem)" }}
            >
              {copy.faqTitle}
            </h2>

            <div className="space-y-3">
              {copy.faqs.map((faq, index) => {
                const isOpen = openFaqIndex === index;
                return (
                  <div
                    key={faq.q}
                    className="overflow-hidden rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]"
                  >
                    <button
                      type="button"
                      onClick={() => setOpenFaqIndex(isOpen ? null : index)}
                      className="flex min-h-[56px] w-full items-center justify-between gap-3 p-5 text-left font-bold text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-muted)]"
                      aria-expanded={isOpen}
                    >
                      <span className="text-sm sm:text-base">{faq.q}</span>
                      <Icon
                        name="chevron-down"
                        size={18}
                        className={`text-[var(--text-muted)] transition-transform duration-200 ${
                          isOpen ? "rotate-180 text-[var(--text-brand)]" : ""
                        }`}
                      />
                    </button>
                    {isOpen ? (
                      <div className="border-t border-[color:var(--shell-border)] px-5 pb-5 pt-3 text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                        {faq.a}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 9. Pre-Footer Call-to-Action */}
        <section className="border-t border-[color:var(--shell-border)] bg-[var(--surface-container-high)] py-16 sm:py-20">
          <div className="mx-auto max-w-3xl px-4 text-center sm:px-6 lg:px-8">
            <Badge tone="brand" className="mb-3">
              {copy.primaryCta.eyebrow}
            </Badge>
            <h2
              className="font-black leading-tight tracking-tight text-[var(--text-primary)]"
              style={{ fontSize: "clamp(1.75rem, 4.5vw, 2.5rem)" }}
            >
              {copy.primaryCta.title}
            </h2>
            <p className="mt-3 text-sm font-medium text-[var(--text-secondary)] sm:text-base">
              {copy.primaryCta.description}
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3.5">
              <Link
                href="/chat"
                className="focus-ring group inline-flex items-center gap-2 rounded-xl bg-[var(--brand-600)] px-7 py-3.5 text-sm font-bold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] shadow-sm"
              >
                {copy.primaryCta.chat}
                <Icon
                  name="arrow-right"
                  size={16}
                  className="transition-transform group-hover:translate-x-1"
                />
              </Link>
              <Link
                href="/register"
                className="focus-ring inline-flex items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-6 py-3.5 text-sm font-bold text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-muted)]"
              >
                <Icon name="user-card" size={16} className="text-[var(--text-secondary)]" />
                {copy.footer.register}
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* 10. Footer with Explicit Links to /legal and /huong-dan */}
      <footer className="border-t border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-14">
        <div className="mx-auto max-w-7xl px-4 text-[var(--text-secondary)] sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 gap-10 border-b border-[color:var(--shell-border)] pb-12 sm:grid-cols-2 lg:grid-cols-12">
            {/* Brand Column */}
            <div className="space-y-4 lg:col-span-4">
              <Link href="/" className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand-600)] text-sm font-black text-[var(--button-primary-text)]">
                  C
                </div>
                <span className="text-lg font-black text-[var(--text-primary)]">
                  The <span className="text-[var(--text-brand)]">Clara Care</span>
                </span>
              </Link>
              <p className="max-w-sm text-xs leading-relaxed text-[var(--text-secondary)] sm:text-sm">
                {copy.footer.description}
              </p>
              <div className="flex items-center gap-2 pt-2">
                <Badge tone="ok">Zero-CoT Privacy Safe</Badge>
                <Badge tone="brand">FIDES 2026</Badge>
              </div>
            </div>

            {/* Link Columns */}
            <div className="grid grid-cols-2 gap-8 sm:col-span-2 sm:grid-cols-3 lg:col-span-8">
              {/* Column 1: Products */}
              <div className="space-y-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-[var(--text-primary)]">
                  {copy.footer.product}
                </h4>
                <ul className="space-y-2 text-xs font-semibold">
                  <li>
                    <Link href="/chat" className="hover:text-[var(--text-brand)] transition-colors">
                      CLARA Chat
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/council"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Council AI
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/scribe"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Scribe Y khoa
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/careguard"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      CareGuard
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/medicines?tab=cabinet"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Self-Med & Thuốc
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/lifemap"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      LifeMap
                    </Link>
                  </li>
                </ul>
              </div>

              {/* Column 2: Guides & Support */}
              <div className="space-y-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-[var(--text-primary)]">
                  {copy.footer.guide}
                </h4>
                <ul className="space-y-2 text-xs font-semibold">
                  <li>
                    <Link
                      href="/huong-dan"
                      className="text-[var(--text-brand)] font-bold hover:underline"
                    >
                      Trung tâm hướng dẫn (/huong-dan)
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/huong-dan"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Hướng dẫn Bác sĩ
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/huong-dan"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Hướng dẫn Người dùng
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/huong-dan"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      Quy trình kiểm chứng FIDES
                    </Link>
                  </li>
                </ul>
              </div>

              {/* Column 3: Legal & Privacy */}
              <div className="space-y-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-[var(--text-primary)]">
                  {copy.footer.legal}
                </h4>
                <ul className="space-y-2 text-xs font-semibold">
                  <li>
                    <Link
                      href="/legal"
                      className="text-[var(--text-brand)] font-bold hover:underline"
                    >
                      Trung tâm pháp lý (/legal)
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/legal/privacy"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      {copy.footer.privacy}
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/legal/terms"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      {copy.footer.terms}
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/legal/consent"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      {copy.footer.consent}
                    </Link>
                  </li>
                  <li>
                    <Link
                      href="/legal/cookies"
                      className="hover:text-[var(--text-brand)] transition-colors"
                    >
                      {copy.footer.cookies}
                    </Link>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          {/* Contact & Disclaimer Bar */}
          <div className="mt-8 space-y-4">
            <div className="flex flex-col items-start justify-between gap-3 text-xs sm:flex-row sm:items-center">
              <div className="flex flex-wrap items-center gap-4 text-[var(--text-muted)]">
                <span>{copy.footer.contact}:</span>
                <a
                  href="mailto:clara@thiennn.icu"
                  className="font-bold text-[var(--text-secondary)] hover:text-[var(--text-brand)]"
                >
                  clara@thiennn.icu
                </a>
                <a
                  href="tel:0853374247"
                  className="font-bold text-[var(--text-secondary)] hover:text-[var(--text-brand)]"
                >
                  0853374247
                </a>
              </div>
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--text-muted)]">
                © 2026 The Clara Care · {copy.footer.madeFor}
              </span>
            </div>

            {/* Prominent Medical Disclaimer */}
            <div className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4 text-[11px] leading-relaxed text-[var(--text-muted)]">
              {copy.footer.disclaimer}
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
