"use client";

import Image from "next/image";
import Link from "next/link";

import {
  LANDING_COPY,
  LANDING_MODULE_HREFS,
  LANDING_MODULE_ICONS,
} from "@/components/landing/clara-kp3-copy";
import { SPONSORS } from "@/components/landing/clara-kp3-data";
import { saveUILanguage, type UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

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
        .material-symbols-outlined {
          font-variation-settings: 'FILL' 0, 'wght' 500, 'GRAD' 0, 'opsz' 24;
        }

        .glass-panel {
          backdrop-filter: blur(24px);
          -webkit-backdrop-filter: blur(24px);
          background: color-mix(in srgb, var(--surface-panel) 84%, transparent);
          border: 1px solid color-mix(in srgb, var(--shell-border) 82%, transparent);
          box-shadow: var(--shadow-soft);
        }

        .dark .glass-panel {
          background: color-mix(in srgb, var(--surface-panel) 88%, transparent);
          border-color: color-mix(in srgb, var(--shell-border-strong) 48%, transparent);
        }

        .cyber-grid {
          background-color: var(--bg-canvas);
          background-image: linear-gradient(color-mix(in srgb, var(--brand-500) 7%, transparent) 1px, transparent 1px),
            linear-gradient(90deg, color-mix(in srgb, var(--brand-500) 7%, transparent) 1px, transparent 1px);
          background-size: 40px 40px;
        }

        .data-stream {
          position: absolute;
          background: linear-gradient(to bottom, transparent, var(--brand-400), transparent);
          width: 1px;
          height: 100px;
          animation: flow 3s linear infinite;
        }

        @keyframes flow {
          from {
            top: -100px;
            opacity: 0;
          }
          50% {
            opacity: 1;
          }
          to {
            top: 100%;
            opacity: 0;
          }
        }

        .neural-pulse {
          animation: pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }

        .glow-cyan {
          filter: drop-shadow(0 0 8px color-mix(in srgb, var(--brand-500) 38%, transparent));
        }

        .module-blade {
          position: relative;
          overflow: hidden;
          transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
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

        @keyframes pulse {
          0%,
          100% {
            opacity: 0.3;
            transform: scale(1);
          }
          50% {
            opacity: 0.7;
            transform: scale(1.05);
          }
        }
      `}</style>

      <main className="cyber-grid overflow-x-hidden text-[var(--text-primary)]">
        <nav className="glass-panel fixed top-0 z-[100] flex w-full items-center justify-between border-b border-[color:var(--shell-border)] px-4 py-4 min-[1024px]:px-8">
          <div className="flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg bg-[var(--brand-600)] text-lg font-bold text-white">
              C
            </div>
            <div className="text-xl font-extrabold tracking-tight text-[var(--text-primary)]">
              The <span className="text-[var(--text-brand)]">Clara Care</span>
            </div>
          </div>

          <div className="hidden items-center gap-8 min-[900px]:flex">
            <a className="glow-cyan inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-brand)]" href="#engine">
              <span className="material-symbols-outlined text-sm">play_circle</span>
              {copy.nav.engine}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#modules">
              <span className="material-symbols-outlined text-sm">widgets</span>
              {copy.nav.modules}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#workflow">
              <span className="material-symbols-outlined text-sm">account_tree</span>
              {copy.nav.workflow}
            </a>
            <a className="inline-flex items-center gap-1.5 text-sm font-bold uppercase tracking-[0.2em] text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)]" href="#faq">
              <span className="material-symbols-outlined text-sm">help</span>
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
              className="focus-ring rounded-lg border border-[var(--brand-700)] bg-[var(--brand-600)] px-4 py-2 text-sm font-bold text-white transition-all hover:bg-[var(--brand-700)]"
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
                  className="focus-ring group inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-[var(--brand-600)] px-6 py-4 text-base font-black text-white transition-all hover:bg-[var(--brand-700)] min-[480px]:flex-none min-[480px]:px-8"
                >
                  {copy.hero.primaryCta}
                  <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">arrow_forward</span>
                </Link>
                <a
                  href="#engine"
                  className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-4 text-base font-black text-slate-900 transition-colors hover:bg-slate-100 min-[480px]:flex-none min-[480px]:px-8 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="material-symbols-outlined text-base">play_circle</span>
                  {copy.hero.secondaryCta}
                </a>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t border-slate-300/45 pt-8 dark:border-slate-700/45">
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">verified</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">{copy.hero.sourceWhenAvailable}</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">timer</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">{copy.hero.uncertainty}</span>
                </div>
                <div className="flex items-start gap-1.5">
                  <span className="material-symbols-outlined mt-0.5 text-base text-cyan-600 dark:text-cyan-400">fact_check</span>
                  <span className="text-xs font-black leading-tight text-slate-700 dark:text-slate-200">{copy.hero.safetyGuard}</span>
                </div>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-xl self-center min-[1120px]:mx-0 min-[1120px]:w-[46%] min-[1280px]:w-[44%]">
              <div className="absolute -inset-10 rounded-full bg-cyan-300/15 blur-[100px] dark:bg-cyan-700/20" />

              <div className="glass-panel relative overflow-hidden rounded-2xl border border-white/40 p-5 shadow-[0_32px_64px_-12px_rgba(0,218,243,0.15)] dark:border-cyan-500/30">
                <div className="mb-4 flex items-center justify-between border-b border-slate-300/35 pb-3 dark:border-slate-700/45">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                      <div className="h-2.5 w-2.5 rounded-full bg-red-300/70" />
                      <div className="h-2.5 w-2.5 rounded-full bg-amber-300/70" />
                      <div className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" />
                    </div>
                    <div className="h-4 w-px bg-slate-300 dark:bg-slate-700" />
                    <div className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">
                      {copy.hero.preview.systemCore}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-cyan-700 dark:text-cyan-300">{copy.hero.preview.activeSession}</span>
                    <span className="h-2 w-2 rounded-full bg-cyan-500 dark:bg-cyan-300" />
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="flex justify-between">
                    <div>
                      <div className="text-sm font-black text-slate-900 dark:text-slate-100">{copy.hero.preview.engineTitle}</div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-500 dark:bg-cyan-300" />
                        {copy.hero.preview.clinicalContext}
                      </div>
                    </div>
                    <div className="flex h-8 items-end gap-1">
                      <div className="h-4 w-1 rounded-full bg-cyan-300" />
                      <div className="h-6 w-1 animate-bounce rounded-full bg-cyan-500" style={{ animationDelay: "0.1s" }} />
                      <div className="h-8 w-1 rounded-full bg-slate-900 dark:bg-cyan-200" />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex justify-end">
                      <div className="max-w-[82%] rounded-xl rounded-tr-none border border-slate-300/45 bg-slate-100 px-4 py-3 text-base font-medium text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                        {copy.hero.preview.question}
                      </div>
                    </div>

                    <div className="flex justify-start gap-3">
                      <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white dark:bg-cyan-400 dark:text-slate-950">
                        <div className="neural-pulse absolute inset-0 rounded-full bg-cyan-300/20 dark:bg-cyan-700/30" />
                        <span className="material-symbols-outlined relative z-10 text-lg">psychology</span>
                      </div>

                      <div className="max-w-[86%] space-y-3">
                        <div className="relative overflow-hidden rounded-2xl rounded-tl-none bg-slate-900 p-4 text-white dark:bg-cyan-700">
                          <div className="absolute right-2 top-1 opacity-20">
                            <span className="material-symbols-outlined text-4xl">neurology</span>
                          </div>
                          <p className="relative z-10 text-base leading-relaxed">
                            {copy.hero.preview.answer}
                          </p>
                          <div className="relative z-10 mt-3 flex flex-wrap gap-2 border-t border-white/15 pt-3">
                            <span className="rounded border border-white/20 bg-white/10 px-2 py-1 text-[10px] font-bold">{copy.hero.preview.sourceWhenAvailable}</span>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-black uppercase tracking-wider text-cyan-700 dark:text-cyan-300">
                            {copy.hero.preview.reviewSource}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 rounded-xl border border-slate-300/45 bg-slate-100 p-3 dark:border-slate-700 dark:bg-slate-900">
                    <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">barcode_scanner</span>
                    <div className="flex-1 text-xs font-bold italic text-slate-500 dark:text-slate-400">
                      {copy.hero.preview.analysing}
                    </div>
                    <div className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" style={{ animationDelay: "0.2s" }} />
                      <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-500 dark:bg-cyan-300" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass-panel absolute -right-6 -top-6 hidden w-36 flex-col items-center justify-center rounded-2xl border border-cyan-300/35 p-4 shadow-2xl shadow-cyan-900/20 min-[1200px]:flex">
                <span className="material-symbols-outlined mb-2 text-3xl text-cyan-600 dark:text-cyan-400">verified</span>
                <div className="text-center text-xs font-black uppercase text-slate-800 dark:text-slate-200">{copy.hero.preview.sourceWhenAvailable}</div>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white/75 py-8 dark:border-slate-800/50 dark:bg-slate-900/55">
          <div className="mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-2 text-center text-xs font-black uppercase tracking-[0.28em] text-slate-600 dark:text-slate-400">
              <span className="material-symbols-outlined mr-1 align-[-3px] text-sm">handshake</span>
              {copy.sponsors.heading}
            </div>
            <div className="mb-8 text-center text-sm font-medium text-slate-600 dark:text-slate-300">
              {copy.sponsors.description}
            </div>
            <div className="flex flex-wrap justify-center gap-4">
              {SPONSORS.map((sponsor) => (
                <a
                  key={sponsor.name}
                  href={sponsor.href}
                  target="_blank"
                  rel="noreferrer"
                  className="flex min-h-[120px] w-full max-w-xs items-center justify-center rounded-2xl border border-slate-700/50 bg-slate-900 p-6 shadow-lg shadow-slate-900/10 transition-all hover:-translate-y-0.5 dark:bg-slate-950"
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
            <p className="mt-6 text-center text-base font-medium text-slate-500 dark:text-slate-400">
              {copy.sponsors.network}
            </p>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8" id="engine">
          <div className="mb-16 text-center">
            <h2
              className="mb-4 font-black tracking-tight text-slate-900 dark:text-slate-100"
              style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
            >
              {copy.engine.title}
            </h2>
            <p className="mx-auto max-w-3xl text-base font-medium text-slate-600 dark:text-slate-300">
              {copy.engine.description}
            </p>
          </div>

          <div className="flex flex-col gap-3 min-[900px]:flex-row min-[900px]:items-stretch">
            {copy.engine.steps.flatMap((step, idx, arr) => [
              <article
                key={step.title}
                className={
                  step.solid
                    ? "relative z-10 flex-1 rounded-2xl bg-slate-900 p-7 text-white shadow-2xl dark:bg-cyan-800"
                    : "glass-panel relative z-10 flex-1 rounded-2xl p-7"
                }
              >
                <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 dark:bg-slate-800/60">
                  <span className={`material-symbols-outlined text-2xl ${step.tone}`}>{step.icon}</span>
                </div>
                <p className={`mb-1 text-xs font-black uppercase tracking-[0.15em] ${step.tone}`}>{step.layer}</p>
                <h3 className="mb-3 text-xl font-black">{step.title}</h3>
                <p className={`text-base leading-relaxed ${step.solid ? "text-slate-200" : "text-slate-600 dark:text-slate-300"}`}>{step.description}</p>
              </article>,
              idx < arr.length - 1 ? (
                <div key={`arrow-${idx}`} className="hidden shrink-0 items-center justify-center text-cyan-400/50 min-[900px]:flex">
                  <span className="material-symbols-outlined text-2xl">arrow_forward</span>
                </div>
              ) : null,
            ])}
          </div>
        </section>

        <section className="border-y border-slate-200/50 bg-white py-20 dark:border-slate-800/50 dark:bg-slate-900/55" id="modules">
          <div className="mx-auto grid max-w-7xl gap-12 px-4 min-[1120px]:grid-cols-12 min-[1024px]:px-8">
            <div className="space-y-8 min-[1120px]:col-span-5">
              <div className="inline-flex rounded-full bg-slate-900 px-4 py-1.5 text-xs font-black uppercase tracking-[0.16em] text-white dark:bg-cyan-400 dark:text-slate-950">
                {copy.moduleSection.eyebrow}
              </div>
              <h2
                className="font-black leading-tight tracking-tight text-slate-900 dark:text-slate-100"
                style={{ fontSize: "clamp(1.75rem, 5vw, 3rem)" }}
              >
                {copy.moduleSection.title}
                <br />
                <span className="text-cyan-600 dark:text-cyan-300">{copy.moduleSection.coreEngine}</span>
              </h2>
              <p className="text-lg font-medium leading-relaxed text-slate-600 dark:text-slate-300">
                {copy.moduleSection.description}
              </p>
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">{copy.moduleSection.source}</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
                    {copy.moduleSection.sourceDetail}
                  </p>
                </div>
                <div>
                  <p className="text-5xl font-light tracking-tight text-cyan-600 dark:text-cyan-300">{copy.moduleSection.limits}</p>
                  <p className="mt-2 text-xs font-black uppercase tracking-[0.12em] text-slate-600 dark:text-slate-300">
                    {copy.moduleSection.limitsDetail}
                  </p>
                </div>
              </div>
              <Link
                href="/chat"
                className="inline-flex rounded-xl bg-slate-900 px-8 py-4 text-base font-black text-white transition-colors hover:bg-slate-800 dark:bg-cyan-400 dark:text-slate-950 dark:hover:bg-cyan-300"
              >
                {copy.moduleSection.cta}
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-4 min-[760px]:grid-cols-2 min-[1120px]:col-span-7">
              {modules.map((module) => (
                <article
                  key={module.title}
                  className="glass-panel module-blade rounded-2xl p-7 transition-all hover:-translate-y-1 hover:shadow-2xl"
                >
                  <div className="mb-6 flex items-center justify-between">
                    <div className="rounded-xl bg-cyan-100/60 p-3 dark:bg-cyan-900/35">
                      {module.icon.startsWith("fa ") ? (
                        <i className={`${module.icon} text-2xl text-cyan-700 dark:text-cyan-300`} aria-hidden="true" />
                      ) : (
                        <span className="material-symbols-outlined text-2xl text-cyan-700 dark:text-cyan-300">{module.icon}</span>
                      )}
                    </div>
                    <span className="rounded-full border border-cyan-300/40 bg-cyan-100/50 px-2.5 py-1 text-xs font-bold text-cyan-800 dark:border-cyan-700/40 dark:bg-cyan-900/30 dark:text-cyan-300">
                      {module.audience}
                    </span>
                  </div>
                  <h3 className="mb-2 text-xl font-black text-slate-900 dark:text-slate-100">{module.title}</h3>
                  <p className="mb-6 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-300">
                    {module.description}
                  </p>
                  <Link
                    href={module.href}
                    className="inline-flex items-center gap-1 text-xs font-black uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300"
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
            className="mb-16 text-center font-black leading-tight tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.workflow.titleStart}
            <br />
            <span className="text-cyan-600 dark:text-cyan-300">{copy.workflow.titleAccent}</span>
          </h2>

          <div className="grid grid-cols-1 gap-12 min-[900px]:grid-cols-3">
            {copy.workflow.steps.map((step) => (
              <article key={step.number} className="space-y-4">
                <div className="text-7xl font-black text-cyan-600/60 dark:text-cyan-400/50">{step.number}</div>
                <h3 className="flex items-center gap-2 text-2xl font-black text-slate-900 dark:text-slate-100">
                  <span className="material-symbols-outlined text-cyan-700 dark:text-cyan-300">{step.icon}</span>
                  {step.title}
                </h3>
                <p className="text-base font-medium leading-relaxed text-slate-600 dark:text-slate-300">{step.description}</p>
                <p className="text-xs font-black uppercase tracking-widest text-cyan-700 dark:text-cyan-400">
                  → {step.outcome}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section className="relative overflow-hidden bg-slate-900 py-20 text-white dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-10" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 min-[1024px]:px-8">
            <div className="mb-14 flex flex-col gap-6 min-[1024px]:flex-row min-[1024px]:items-end min-[1024px]:justify-between">
              <h2
                className="font-black leading-tight tracking-tight"
                style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
              >
                {copy.principles.title}
                <br />
                <span className="text-cyan-300">{copy.principles.titleAccent}</span>
              </h2>
              <p className="max-w-sm text-base font-bold text-slate-200">
                {copy.principles.description}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-5 min-[900px]:grid-cols-3">
            {copy.principles.items.map((item) => (
                <article key={item.title} className="rounded-2xl border border-white/25 bg-white/10 p-8">
                  <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-xl bg-cyan-400/15">
                    <span className="material-symbols-outlined text-3xl text-cyan-300">{item.icon}</span>
                  </div>
                  <h3 className="mb-3 text-2xl font-black text-white">{item.title}</h3>
                  <p className="mb-4 text-base font-medium leading-relaxed text-slate-200">{item.description}</p>
                  <div className="flex items-start gap-2 border-t border-white/15 pt-3">
                    <span className="material-symbols-outlined mt-0.5 text-sm text-cyan-400">check_circle</span>
                    <p className="text-sm font-bold leading-snug text-slate-300">{copy.principles.outcomeLabel}: {item.outcome}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-4 py-20 min-[1024px]:px-8">
          <h2
            className="mb-4 text-center font-black tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.useCaseSection.title}
          </h2>
          <p className="mb-14 text-center text-base font-medium text-slate-600 dark:text-slate-300">
            {copy.useCaseSection.description}
          </p>
          <div className="grid grid-cols-1 gap-6 min-[1000px]:grid-cols-3">
            {copy.useCases.map((item, index) => (
              <article key={item.role} className="glass-panel rounded-2xl border-l-4 border-cyan-500 p-8">
                <div className="mb-4 flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-100/60 dark:bg-cyan-900/35">
                    <span className="material-symbols-outlined text-xl text-cyan-700 dark:text-cyan-300">{useCaseIcons[index]}</span>
                  </div>
                  <span className="rounded-full border border-cyan-300/40 bg-cyan-100/50 px-2.5 py-0.5 text-xs font-black text-cyan-800 dark:border-cyan-700/50 dark:bg-cyan-900/35 dark:text-cyan-200">
                    {item.tag}
                  </span>
                </div>
                <p className="mb-1 text-xs font-black uppercase tracking-[0.14em] text-slate-600 dark:text-slate-400">{item.role}</p>
                <p className="mb-4 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-200">
                  {item.scenario}
                </p>
                <p className="border-t border-slate-300/35 pt-4 text-sm font-bold text-slate-600 dark:border-slate-700/45 dark:text-slate-300">
                  ✓ {item.benefit}
                </p>
              </article>
            ))}
          </div>
        </section>

        {/* CTA giữa trang */}
        <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 py-16">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-1/4 top-0 h-64 w-64 -translate-y-1/2 rounded-full bg-cyan-500/10 blur-3xl" />
            <div className="absolute right-1/4 bottom-0 h-64 w-64 translate-y-1/2 rounded-full bg-cyan-400/8 blur-3xl" />
          </div>
          <div className="relative z-10 mx-auto max-w-3xl px-4 text-center min-[1024px]:px-8">
            <p className="mb-3 text-xs font-black uppercase tracking-[0.24em] text-cyan-400">{copy.primaryCta.eyebrow}</p>
            <h2
              className="mb-4 font-black leading-tight tracking-tight text-white"
              style={{ fontSize: "clamp(1.7rem, 5vw, 2.6rem)" }}
            >
              {copy.primaryCta.title}
            </h2>
            <p className="mb-8 text-base font-medium leading-relaxed text-slate-300">
              {copy.primaryCta.description}
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link
                href="/chat"
                className="group inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-8 py-4 text-base font-black text-slate-950 transition-all hover:bg-cyan-300"
              >
                {copy.primaryCta.chat}
                <span className="material-symbols-outlined transition-transform group-hover:translate-x-1">arrow_forward</span>
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-600 bg-white/5 px-8 py-4 text-base font-black text-slate-200 transition-all hover:border-slate-400 hover:bg-white/10"
              >
                <span className="material-symbols-outlined text-base">fact_check</span>
                {copy.primaryCta.workflow}
              </a>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-4 py-20 min-[1024px]:px-8" id="faq">
          <h2
            className="mb-10 text-center font-black tracking-tight text-slate-900 dark:text-slate-100"
            style={{ fontSize: "clamp(1.9rem, 5vw, 3rem)" }}
          >
            {copy.faqTitle}
          </h2>
          <div className="space-y-4">
            {copy.faqs.map((faq) => (
              <details key={faq.q} className="glass-panel overflow-hidden rounded-2xl border border-slate-300/35 dark:border-slate-700/45">
                <summary className="flex cursor-pointer list-none items-center justify-between p-5 text-left">
                  <span className="font-black text-slate-900 dark:text-slate-100">{faq.q}</span>
                  <span className="material-symbols-outlined text-slate-400">expand_more</span>
                </summary>
                <div className="px-5 pb-5 text-base font-medium leading-relaxed text-slate-700 dark:text-slate-300">{faq.a}</div>
              </details>
            ))}
          </div>
        </section>

        <footer className="relative overflow-hidden bg-slate-900 py-14 dark:bg-slate-950">
          <div className="cyber-grid absolute inset-0 opacity-5" />
          <div className="relative z-10 mx-auto max-w-7xl px-4 text-slate-300 min-[1024px]:px-8">

            {/* CTA đầu footer */}
            <div className="mb-10 flex flex-col items-center justify-between gap-6 rounded-2xl border border-cyan-500/20 bg-slate-800/80 px-8 py-8 shadow-2xl shadow-cyan-900/20 min-[900px]:flex-row">
              <div>
                <p className="mb-1 text-lg font-black text-white">{copy.footer.ctaTitle}</p>
                <p className="text-sm font-medium text-slate-400">{copy.footer.ctaDetail}</p>
              </div>
              <Link
                href="/register"
                className="shrink-0 inline-flex items-center gap-2 rounded-xl bg-cyan-400 px-6 py-3 text-sm font-black text-slate-950 transition-all hover:bg-cyan-300"
              >
                <span className="material-symbols-outlined text-base">person_add</span>
                {copy.footer.register}
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-10 border-b border-slate-800/80 pb-10 md:grid-cols-12 md:gap-8">
              <div className="space-y-4 md:col-span-5">
                <p className="text-2xl font-black text-white">
                  The <span className="text-cyan-300">Clara Care</span>
                </p>
                <p className="max-w-md text-base font-medium leading-relaxed text-slate-300">
                  {copy.footer.description}
                </p>
                <p className="text-xs font-black uppercase tracking-[0.15em] text-cyan-300">© 2026 The Clara Care</p>
              </div>

              <div className="grid grid-cols-1 gap-8 sm:grid-cols-3 md:col-span-7">
                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">category</span>
                    {copy.footer.product}
                  </p>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#engine">
                    {copy.nav.engine}
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#modules">
                    {copy.nav.modules}
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="#workflow">
                    {copy.nav.workflow}
                  </a>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">gavel</span>
                    {copy.footer.legal}
                  </p>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/privacy">
                    {copy.footer.privacy}
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/terms">
                    {copy.footer.terms}
                  </Link>
                  <Link className="block text-sm font-bold hover:text-cyan-300" href="/legal/consent">
                    {copy.footer.consent}
                  </Link>
                </div>

                <div className="space-y-3">
                  <p className="inline-flex items-center gap-1.5 text-xs font-black uppercase tracking-[0.16em] text-white">
                    <span className="material-symbols-outlined text-sm">contact_support</span>
                    {copy.footer.contact}
                  </p>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="mailto:clara@thiennn.icu">
                    clara@thiennn.icu
                  </a>
                  <a className="block text-sm font-bold hover:text-cyan-300" href="tel:0853374247">
                    0853374247
                  </a>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-start justify-between gap-2 pt-4 text-xs text-slate-300 sm:flex-row sm:items-center">
              <p>{copy.footer.madeFor}</p>
              <p className="text-xs uppercase tracking-[0.12em] text-slate-400">{copy.footer.productLine}</p>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
