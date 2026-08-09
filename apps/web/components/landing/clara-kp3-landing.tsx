"use client";

import Image from "next/image";
import Link from "next/link";

import {
  LANDING_COPY,
  LANDING_MODULE_HREFS,
  LANDING_MODULE_ICONS,
} from "@/components/landing/clara-kp3-copy";
import { SPONSORS } from "@/components/landing/clara-kp3-data";
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
};

function LandingIcon({ glyph, className = "", size = 20 }: { glyph: string; className?: string; size?: number }) {
  return <Icon name={LANDING_ICONS[glyph] ?? "clinical-notes"} size={size} className={className} aria-hidden="true" />;
}

export default function ClaraKp3Landing() {
  const language = useUILanguage();
  const copy = LANDING_COPY[language];
  const modules = copy.modules.map((module, index) => ({
    ...module,
    icon: LANDING_MODULE_ICONS[index],
    href: LANDING_MODULE_HREFS[index],
  }));
  const useCaseIcons = ["stethoscope", "school", "biotech"] as const;

  return (
    <>
      <style>{`
        .glass-panel {
          background: var(--surface-panel);
          border: 1px solid var(--shell-border);
          border-top-color: var(--card-top-border);
        }

        .cyber-grid {
          background-color: var(--bg-canvas);
        }

        .data-stream {
          display: none;
        }

        .neural-pulse {
          display: none;
        }

        .glow-cyan {
          color: var(--text-brand);
        }

        .module-blade {
          position: relative;
          overflow: hidden;
          transition: background-color 150ms ease, border-color 150ms ease;
        }

        .module-blade::after {
          content: "";
          position: absolute;
          top: 0;
          left: 0;
          width: 2px;
          height: 100%;
          background: var(--brand-500);
          transform: scaleY(0);
          transition: transform 0.3s ease;
        }

        .module-blade:hover::after {
          transform: scaleY(1);
        }
      `}</style>

      <main className="cyber-grid overflow-x-hidden text-[var(--text-primary)]">
        <nav className="glass-panel fixed top-0 z-[100] flex w-full items-center justify-between border-b border-[color:var(--shell-border)] px-4 py-4 min-[1024px]:px-8">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-[var(--brand-600)] text-lg font-bold text-[var(--button-primary-text)]">
              C
            </div>
            <div className="text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
              The <span className="text-[var(--text-brand)]">Clara Care</span>
            </div>
          </div>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="glow-cyan inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-brand)]" href="#engine">
              <LandingIcon glyph="play_circle" className="text-sm" />
              {copy.nav.engine}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#modules">
              <LandingIcon glyph="widgets" className="text-sm" />
              {copy.nav.modules}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#workflow">
              <LandingIcon glyph="account_tree" className="text-sm" />
              {copy.nav.workflow}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#faq">
              <LandingIcon glyph="help" className="text-sm" />
              {copy.nav.faq}
            </a>
          </div>

          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="landing-language">
              {copy.languageLabel}
            </label>
            <select
              id="landing-language"
              value={language}
              onChange={(event) => saveUILanguage(event.target.value as UILanguage)}
              className="focus-ring rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-2 py-2 text-sm font-bold text-[var(--text-primary)]"
            >
              <option value="vi">{copy.languageNames.vi}</option>
              <option value="en">{copy.languageNames.en}</option>
            </select>
            <Link
              href="/login"
              className="focus-ring rounded-lg px-4 py-2 text-sm font-bold text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]"
            >
              {copy.nav.login}
            </Link>
            <Link
              href="/register"
              className="focus-ring rounded-lg border border-[var(--brand-700)] bg-[var(--brand-600)] px-4 py-2 text-sm font-bold text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)]"
            >
              {copy.nav.register}
            </Link>
          </div>
        </nav>

        <section className="relative mx-auto max-w-7xl px-4 pb-14 pt-28 min-[1024px]:px-8 min-[1024px]:pb-20 min-[1024px]:pt-36">
          <div className="pointer-events-none absolute inset-0 overflow-hidden opacity-30">
            <div className="data-stream left-1/4" style={{ animationDelay: "0s" }} />
            <div className="data-stream left-1/3" style={{ animationDelay: "1.5s" }} />
            <div className="data-stream left-2/3" style={{ animationDelay: "0.7s" }} />
            <div className="data-stream left-3/4" style={{ animationDelay: "2.2s" }} />
          </div>

          <div className="relative z-10 flex flex-col gap-10 min-[1120px]:flex-row min-[1120px]:items-center min-[1120px]:gap-12">
            <div className="w-full space-y-6 min-[1120px]:w-[54%] min-[1280px]:w-[56%]">
              <div className="inline-flex items-center gap-2 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-3 py-1 text-[11px] font-black uppercase tracking-[0.2em] text-[var(--text-brand)]">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--brand-500)]" />
                {copy.hero.eyebrow}
              </div>

              <h1
                className="font-black leading-[1.08] tracking-tight text-[var(--text-primary)] [text-wrap:balance] min-[640px]:leading-[0.98]"
                style={{ fontSize: "clamp(1.4rem, 6.4vw, 4.25rem)" }}
              >
                {copy.hero.headingStart}{" "}
                <span className="text-[var(--text-brand)]">{copy.hero.headingAccent}</span>{" "}
                {copy.hero.headingEnd}
              </h1>

              <p className="max-w-[56ch] text-[0.95rem] font-medium leading-relaxed text-[var(--text-secondary)] min-[640px]:text-base min-[1280px]:text-lg">
                {copy.hero.descriptionBefore}<strong className="font-black text-[var(--text-primary)]">{copy.hero.audience}</strong>{copy.hero.descriptionAfter}
              </p>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/chat"
                  className="focus-ring group inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-[var(--brand-600)] px-6 py-4 text-base font-black text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)] min-[480px]:flex-none min-[480px]:px-8"
                >
                  {copy.hero.primaryCta}
                  <LandingIcon glyph="arrow_forward" className="transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#engine"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-6 py-4 text-base font-black text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-muted)] min-[480px]:flex-none min-[480px]:px-8"
                >
                  <LandingIcon glyph="play_circle" className="text-base" />
                  {copy.hero.secondaryCta}
                </a>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t border-[color:var(--shell-border)] pt-8">
                <div className="flex items-start gap-1.5">
                  <LandingIcon glyph="verified" className="mt-0.5 text-base text-[var(--text-brand)]" />
                  <span className="text-xs font-black leading-tight text-[var(--text-secondary)]">{copy.hero.sourceWhenAvailable}</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <LandingIcon glyph="timer" className="mt-0.5 text-base text-[var(--text-brand)]" />
                  <span className="text-xs font-black leading-tight text-[var(--text-secondary)]">{copy.hero.uncertainty}</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <LandingIcon glyph="fact_check" className="mt-0.5 text-base text-[var(--text-brand)]" />
                  <span className="text-xs font-black leading-tight text-[var(--text-secondary)]">{copy.hero.safetyGuard}</span>
                </div>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-xl self-center min-[1120px]:mx-0 min-[1120px]:w-[46%] min-[1280px]:w-[44%]">
              <div className="glass-panel relative overflow-hidden rounded-2xl p-5">
                <div className="mb-4 flex items-center justify-between border-b border-[color:var(--shell-border)] pb-3">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full bg-[var(--status-danger-bg)]" />
                      <div className="h-2.5 w-2.5 rounded-full bg-[var(--status-warn-bg)]" />
                      <div className="h-2.5 w-2.5 rounded-full bg-[var(--surface-brand-soft)]" />
                    </div>
                    <div className="h-4 w-px bg-[var(--surface-muted)]" />
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-[var(--text-muted)]">
                      {copy.hero.preview.systemCore}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-[var(--text-brand)]">{copy.hero.preview.activeSession}</span>
                    <span className="h-2 w-2 rounded-full bg-[var(--surface-brand-soft)]" />
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="flex justify-between">
                    <div>
                      <div className="text-sm font-black text-[var(--text-primary)]">{copy.hero.preview.engineTitle}</div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--text-muted)]">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--surface-brand-soft)]" />
                        {copy.hero.preview.clinicalContext}
                      </div>
                    </div>
                    <div className="flex h-8 items-end gap-1">
                      <div className="h-4 w-1 rounded-full bg-[var(--surface-brand-soft)]" />
                      <div className="h-6 w-1 animate-bounce rounded-full bg-[var(--surface-brand-soft)]" style={{ animationDelay: "0.1s" }} />
                      <div className="h-8 w-1 rounded-full bg-[var(--surface-container-high)]" />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[82%] rounded-xl rounded-tr-none border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-base font-medium text-[var(--text-secondary)]">
                        {copy.hero.preview.question}
                      </div>
                    </div>

                    <div className="flex justify-start gap-3">
                      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--surface-container-high)] text-[var(--text-primary)]">
                        <div className="neural-pulse absolute inset-0 rounded-full bg-[var(--surface-brand-soft)]/20" />
                        <LandingIcon glyph="psychology" className="relative z-10 text-lg" />
                      </div>

                      <div className="max-w-[86%] space-y-3">
                        <div className="relative overflow-hidden rounded-2xl rounded-tl-none bg-[var(--surface-container-high)] p-4 text-[var(--text-primary)]">
                          <div className="absolute right-2 top-1 opacity-20">
                            <LandingIcon glyph="neurology" className="text-4xl" />
                          </div>
                          <p className="relative z-10 text-base leading-relaxed">
                            {copy.hero.preview.answer}
                          </p>
                          <div className="relative z-10 mt-3 flex flex-wrap gap-2 border-t border-[color:var(--shell-border)] pt-3">
                            <span className="rounded border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-2 py-1 text-[10px] font-bold">{copy.hero.preview.sourceWhenAvailable}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-black uppercase tracking-wider text-[var(--text-brand)]">
                            {copy.hero.preview.reviewSource}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <LandingIcon glyph="barcode_scanner" className="text-[var(--text-brand)]" />
                    <div className="flex-1 text-xs font-bold italic text-[var(--text-muted)]">
                      {copy.hero.preview.analysing}
                    </div>
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--surface-brand-soft)]" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--surface-brand-soft)]" style={{ animationDelay: "0.2s" }} />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-[var(--surface-brand-soft)]" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass-panel absolute -right-6 -top-6 hidden w-36 flex-col items-center justify-center rounded-2xl border border-[color:var(--shell-border)] p-4  min-[1200px]:flex">
                <LandingIcon glyph="verified" className="mb-2 text-3xl text-[var(--text-brand)]" />
                <div className="text-center text-xs font-black uppercase text-[var(--text-secondary)]">{copy.hero.preview.sourceWhenAvailable}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-8">
          <div className="mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-2 text-center text-xs font-black uppercase tracking-[0.28em] text-[var(--text-secondary)]">
              <LandingIcon glyph="handshake" className="mr-1 align-[-3px] text-sm" />
              {copy.sponsors.heading}
            </div>
            <div className="mb-8 text-center text-sm font-medium text-[var(--text-secondary)]">
              {copy.sponsors.description}
            </div>
            <div className="flex flex-wrap justify-center gap-4">
              {SPONSORS.map((sponsor) => (
                <a
                  key={sponsor.name}
                  href={sponsor.href}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-h-[120px] w-full max-w-xs items-center justify-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-container-high)] p-6  transition-all hover:-translate-y-0.5"
                >
                  <Image
                    src={sponsor.logo}
                    alt={`${sponsor.name} logo`}
                    width={sponsor.name === "BNIX" ? 260 : 560}
                    height={sponsor.name === "BNIX" ? 78 : 180}
                    className={sponsor.name === "BNIX" ? "h-12 w-auto object-contain" : "h-16 w-auto object-contain"}
                  />
                </a>
              ))}
            </div>
            <p className="mt-6 text-center text-base font-medium text-[var(--text-muted)]">
              {copy.sponsors.network}
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8" id="engine">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 font-black tracking-tight text-[var(--text-primary)]"
              style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
            >
              {copy.engine.title}
            </h2>
            <p className="mx-auto max-w-3xl text-base font-medium text-[var(--text-secondary)]">
              {copy.engine.description}
            </p>
          </div>

          <div className="flex flex-col gap-3 min-[900px]:flex-row min-[900px]:items-stretch">
            {copy.engine.steps.flatMap((step, idx, arr) => [
              <article
                key={step.title}
                className={
                  step.solid
                    ? "relative z-10 flex-1 rounded-2xl border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-container-high)] p-7 text-[var(--text-primary)]"
                    : "glass-panel relative z-10 flex-1 rounded-2xl p-7"
                }
              >
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--surface-muted)]">
                  <LandingIcon glyph={step.icon} size={24} className="text-[var(--text-brand)]" />
                </div>
                <p className="mb-1 text-xs font-black uppercase tracking-[0.15em] text-[var(--text-brand)]">{step.layer}</p>
                <h3 className="mb-3 text-xl font-black">{step.title}</h3>
                <p className={`text-base leading-relaxed ${step.solid ? "text-[var(--text-secondary)]" : "text-[var(--text-secondary)]"}`}>{step.description}</p>
              </article>,
              idx < arr.length - 1 ? (
                <div key={`arrow-${idx}`} className="hidden shrink-0 items-center justify-center text-[var(--text-brand)]/50 min-[900px]:flex">
                  <LandingIcon glyph="arrow_forward" className="text-2xl" />
                </div>
              ) : null,
            ])}
          </div>
        </section>

        <section className="border-y border-[color:var(--shell-border)] bg-[var(--surface-panel)] py-20" id="modules">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 min-[1120px]:grid-cols-12 min-[1024px]:px-8">
            <div className="space-y-8 min-[1120px]:col-span-5">
              <div className="inline-flex rounded-full bg-[var(--surface-container-high)] px-4 py-1.5 text-xs font-black uppercase tracking-[0.16em] text-[var(--text-primary)]">
                {copy.moduleSection.eyebrow}
              </div>
              <h2
                className="font-black leading-tight tracking-tight text-[var(--text-primary)]"
                style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
              >
                {copy.moduleSection.title}
                <br />
                <span className="text-[var(--text-brand)]">{copy.moduleSection.coreEngine}</span>
              </h2>
              <p className="text-lg font-medium leading-relaxed text-[var(--text-secondary)]">
                {copy.moduleSection.description}
              </p>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-5xl font-light tracking-tight text-[var(--text-brand)]">{copy.moduleSection.source}</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                    {copy.moduleSection.sourceDetail}
                  </p>
                </div>
                <div>
                  <p className="text-5xl font-light tracking-tight text-[var(--text-brand)]">{copy.moduleSection.limits}</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                    {copy.moduleSection.limitsDetail}
                  </p>
                </div>
              </div>
              <Link
                href="/chat"
                className="inline-flex rounded-xl bg-[var(--surface-container-high)] px-8 py-4 text-base font-black text-[var(--text-primary)] transition-colors hover:bg-[var(--surface-panel)]"
              >
                {copy.moduleSection.cta}
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-4 min-[760px]:grid-cols-2 min-[1120px]:col-span-7">
              {modules.map((module) => (
                <article
                  key={module.title}
                  className="glass-panel module-blade rounded-2xl p-7 hover:bg-[var(--surface-container-high)]"
                >
                  <div className="mb-6 flex items-center justify-between">
                    <div className="rounded-xl bg-[var(--surface-brand-soft)] p-3">
                      <LandingIcon glyph={module.icon} size={24} className="text-[var(--text-brand)]" />
                    </div>
                    <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-2.5 py-1 text-xs font-bold text-[var(--text-brand)]">
                      {module.audience}
                    </span>
                  </div>
                  <h3 className="mb-2 text-xl font-black text-[var(--text-primary)]">{module.title}</h3>
                  <p className="mb-6 text-base font-medium leading-relaxed text-[var(--text-secondary)]">
                    {module.description}
                  </p>
                  <Link
                    href={module.href}
                    className="inline-flex items-center gap-1 text-xs font-black uppercase tracking-[0.12em] text-[var(--text-brand)]"
                  >
                    {module.cta}
                    <i className="fa fa-chevron-right text-base" aria-hidden="true" />
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8" id="workflow">
          <h2
            className="mb-16 text-center font-black leading-tight tracking-tight text-[var(--text-primary)]"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.workflow.titleStart}
            <br />
            <span className="text-[var(--text-brand)]">{copy.workflow.titleAccent}</span>
          </h2>

          <div className="grid grid-cols-1 gap-12 min-[900px]:grid-cols-3">
            {copy.workflow.steps.map((step) => (
              <article key={step.number} className="space-y-4">
                <div className="text-7xl font-black text-[var(--text-brand)]/60">{step.number}</div>
                <h3 className="flex items-center gap-2 text-2xl font-black text-[var(--text-primary)]">
                  <LandingIcon glyph={step.icon} className="text-[var(--text-brand)]" />
                  {step.title}
                </h3>
                <p className="text-base font-medium leading-relaxed text-[var(--text-secondary)]">{step.description}</p>
                <p className="text-xs font-black uppercase tracking-widest text-[var(--text-brand)]">
                  → {step.outcome}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="relative overflow-hidden bg-[var(--surface-container-high)] py-20 text-[var(--text-primary)]">
          <div className="cyber-grid absolute inset-0 opacity-10" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-14 flex flex-col gap-6 min-[1024px]:flex-row min-[1024px]:items-end min-[1024px]:justify-between">
              <h2
                className="font-black leading-tight tracking-tight"
                style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
              >
                {copy.principles.title}
                <br />
                <span className="text-[var(--text-brand)]">{copy.principles.titleAccent}</span>
              </h2>
              <p className="max-w-sm text-base font-bold text-[var(--text-secondary)]">
                {copy.principles.description}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-3">
            {copy.principles.items.map((item) => (
                <article key={item.title} className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-8">
                  <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)]/15">
                    <LandingIcon glyph={item.icon} size={30} className="text-[var(--text-brand)]" />
                  </div>
                  <h3 className="mb-3 text-2xl font-black text-[var(--text-primary)]">{item.title}</h3>
                  <p className="mb-4 text-base font-medium leading-relaxed text-[var(--text-secondary)]">{item.description}</p>
                  <div className="flex items-start gap-2 border-t border-[color:var(--shell-border)] pt-3">
                    <LandingIcon glyph="check_circle" className="mt-0.5 text-sm text-[var(--text-brand)]" />
                    <p className="text-sm font-bold leading-snug text-[var(--text-secondary)]">{copy.principles.outcomeLabel}: {item.outcome}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8">
          <h2
            className="mb-4 text-center font-black tracking-tight text-[var(--text-primary)]"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.useCaseSection.title}
          </h2>
          <p className="mb-14 text-center text-base font-medium text-[var(--text-secondary)]">
            {copy.useCaseSection.description}
          </p>
          <div className="grid grid-cols-1 gap-6 min-[1000px]:grid-cols-3">
            {copy.useCases.map((item, index) => (
              <article key={item.role} className="glass-panel rounded-2xl border-l-4 border-[color:var(--shell-border)] p-8">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)]">
                    <LandingIcon glyph={useCaseIcons[index]} className="text-[var(--text-brand)]" />
                  </div>
                  <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-brand-soft)] px-2.5 py-0.5 text-xs font-black text-[var(--text-brand)]">
                    {item.tag}
                  </span>
                </div>
                <p className="mb-1 text-xs font-black uppercase tracking-[0.14em] text-[var(--text-secondary)]">{item.role}</p>
                <p className="mb-4 text-base font-medium leading-relaxed text-[var(--text-secondary)]">
                  {item.scenario}
                </p>
                <p className="border-t border-[color:var(--shell-border)] pt-4 text-sm font-bold text-[var(--text-secondary)]">
                  ✓ {item.benefit}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* CTA giữa trang */}
        <section className="relative overflow-hidden bg-[var(--surface-container-high)] py-16">
          <div className="relative z-10 mx-auto max-w-3xl px-4 text-center min-[1024px]:px-8">
            <p className="mb-3 text-xs font-black uppercase tracking-[0.24em] text-[var(--text-brand)]">{copy.primaryCta.eyebrow}</p>
            <h2
              className="mb-4 font-black leading-tight tracking-tight text-[var(--text-primary)]"
              style={{ fontSize: "clamp(1.7rem, 5vw, 2.6rem)" }}
            >
              {copy.primaryCta.title}
            </h2>
            <p className="mb-8 text-base font-medium leading-relaxed text-[var(--text-secondary)]">
              {copy.primaryCta.description}
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link
                href="/chat"
                className="group inline-flex items-center gap-2 rounded-xl bg-[var(--brand-600)] px-8 py-4 text-base font-black text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)]"
              >
                {copy.primaryCta.chat}
                <LandingIcon glyph="arrow_forward" className="transition-transform group-hover:translate-x-1" />
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-8 py-4 text-base font-black text-[var(--text-secondary)] transition-all hover:border-[color:var(--shell-border)] hover:bg-[var(--surface-muted)]"
              >
                <LandingIcon glyph="fact_check" className="text-base" />
                {copy.primaryCta.workflow}
              </a>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-4 py-20 min-[1024px]:px-8" id="faq">
          <h2
            className="mb-10 text-center font-black tracking-tight text-[var(--text-primary)]"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.faqTitle}
          </h2>
          <div className="space-y-4">
            {copy.faqs.map((faq) => (
              <details key={faq.q} className="glass-panel overflow-hidden rounded-2xl border border-[color:var(--shell-border)]">
                <summary className="flex cursor-pointer list-none items-center justify-between p-5 text-left">
                  <span className="font-black text-[var(--text-primary)]">{faq.q}</span>
                  <LandingIcon glyph="expand_more" className="text-[var(--text-muted)]" />
                </summary>
                <div className="px-5 pb-5 text-base font-medium leading-relaxed text-[var(--text-secondary)]">{faq.a}</div>
              </details>
            ))}
          </div>
        </section>

        <footer className="relative overflow-hidden bg-[var(--surface-container-high)] py-14">
          <div className="cyber-grid absolute inset-0 opacity-5" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 text-[var(--text-secondary)] min-[1024px]:px-8">

            {/* CTA đầu footer */}
            <div className="mb-10 flex flex-col items-center justify-between gap-6 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)]/80 px-8 py-8  min-[900px]:flex-row">
              <div>
                <p className="mb-1 text-lg font-black text-[var(--text-primary)]">{copy.footer.ctaTitle}</p>
                <p className="text-sm font-medium text-[var(--text-muted)]">{copy.footer.ctaDetail}</p>
              </div>
              <Link
                href="/register"
                className="shrink-0 inline-flex items-center gap-2 rounded-xl bg-[var(--brand-600)] px-6 py-3 text-sm font-black text-[var(--button-primary-text)] transition-colors hover:bg-[var(--brand-700)]"
              >
                <LandingIcon glyph="person_add" className="text-base" />
                {copy.footer.register}
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-10 border-b border-[color:var(--shell-border)] pb-10 md:grid-cols-12 md:gap-8">
              <div className="space-y-4 md:col-span-5">
                <p className="text-2xl font-black text-[var(--text-primary)]">
                  The <span className="text-[var(--text-brand)]">Clara Care</span>
                </p>
                <p className="max-w-md text-base font-medium leading-relaxed text-[var(--text-secondary)]">
                  {copy.footer.description}
                </p>
                <p className="text-xs font-black uppercase tracking-[0.15em] text-[var(--text-brand)]">© 2026 The Clara Care</p>
              </div>

              <div className="grid grid-cols-1 gap-8 sm:grid-cols-3 md:col-span-7">
                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-[var(--text-primary)]">
                    <LandingIcon glyph="category" className="text-sm" />
                    {copy.footer.product}
                  </p>
                  <a className="block text-sm font-bold hover:text-[var(--text-brand)]" href="#engine">
                    {copy.nav.engine}
                  </a>
                  <a className="block text-sm font-bold hover:text-[var(--text-brand)]" href="#modules">
                    {copy.nav.modules}
                  </a>
                  <a className="block text-sm font-bold hover:text-[var(--text-brand)]" href="#workflow">
                    {copy.nav.workflow}
                  </a>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-[var(--text-primary)]">
                    <LandingIcon glyph="gavel" className="text-sm" />
                    {copy.footer.legal}
                  </p>
                  <Link className="block text-sm font-bold hover:text-[var(--text-brand)]" href="/legal/privacy">
                    {copy.footer.privacy}
                  </Link>
                  <Link className="block text-sm font-bold hover:text-[var(--text-brand)]" href="/legal/terms">
                    {copy.footer.terms}
                  </Link>
                  <Link className="block text-sm font-bold hover:text-[var(--text-brand)]" href="/legal/consent">
                    {copy.footer.consent}
                  </Link>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-[var(--text-primary)]">
                    <LandingIcon glyph="contact_support" className="text-sm" />
                    {copy.footer.contact}
                  </p>
                  <a className="block text-sm font-bold hover:text-[var(--text-brand)]" href="mailto:clara@thiennn.icu">
                    clara@thiennn.icu
                  </a>
                  <a className="block text-sm font-bold hover:text-[var(--text-brand)]" href="tel:0853374247">
                    0853374247
                  </a>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-start justify-between gap-2 pt-4 text-xs text-[var(--text-secondary)] sm:flex-row sm:items-center">
              <p>{copy.footer.madeFor}</p>
              <p className="text-xs uppercase tracking-[0.12em] text-[var(--text-muted)]">{copy.footer.productLine}</p>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
