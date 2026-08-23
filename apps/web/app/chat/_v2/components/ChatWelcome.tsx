"use client";

import type { UserRole } from "@/lib/auth-store";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { Icon } from "@/components/ui/icon";

type WelcomeContent = {
  eyebrow: string;
  title: string;
  description: string;
  prompts: Array<{ icon: string; label: string; prompt: string }>;
};

type SpecialistWelcomeContent = {
  eyebrow: UITranslationKey;
  title: UITranslationKey;
  description: UITranslationKey;
  prompts: Array<{
    icon: string;
    label: UITranslationKey;
    prompt: UITranslationKey;
  }>;
};

const SPECIALIST_CONTENT: Record<
  "researcher" | "doctor",
  SpecialistWelcomeContent
> = {
  researcher: {
    eyebrow: "chat.welcome.researcher.eyebrow",
    title: "chat.welcome.researcher.title",
    description: "chat.welcome.researcher.description",
    prompts: [
      {
        icon: "scan",
        label: "chat.welcome.researcher.overview.label",
        prompt: "chat.welcome.researcher.overview.prompt",
      },
      {
        icon: "clinical-notes",
        label: "chat.welcome.researcher.compare.label",
        prompt: "chat.welcome.researcher.compare.prompt",
      },
      {
        icon: "check",
        label: "chat.welcome.researcher.claim.label",
        prompt: "chat.welcome.researcher.claim.prompt",
      },
      {
        icon: "progress",
        label: "chat.welcome.researcher.gaps.label",
        prompt: "chat.welcome.researcher.gaps.prompt",
      },
    ],
  },
  doctor: {
    eyebrow: "chat.welcome.doctor.eyebrow",
    title: "chat.welcome.doctor.title",
    description: "chat.welcome.doctor.description",
    prompts: [
      {
        icon: "clinical-notes",
        label: "chat.welcome.doctor.summary.label",
        prompt: "chat.welcome.doctor.summary.prompt",
      },
      {
        icon: "progress",
        label: "chat.welcome.doctor.differential.label",
        prompt: "chat.welcome.doctor.differential.prompt",
      },
      {
        icon: "medication",
        label: "chat.welcome.doctor.medicines.label",
        prompt: "chat.welcome.doctor.medicines.prompt",
      },
      {
        icon: "emergency",
        label: "chat.welcome.doctor.risk.label",
        prompt: "chat.welcome.doctor.risk.prompt",
      },
    ],
  },
};

function specialistWelcomeContent(
  role: "researcher" | "doctor",
  locale: UILanguage,
): WelcomeContent {
  const content = SPECIALIST_CONTENT[role];
  return {
    eyebrow: t(locale, content.eyebrow),
    title: t(locale, content.title),
    description: t(locale, content.description),
    prompts: content.prompts.map((item) => ({
      icon: item.icon,
      label: t(locale, item.label),
      prompt: t(locale, item.prompt),
    })),
  };
}

function normalWelcomeContent(locale: UILanguage): WelcomeContent {
  return {
    eyebrow: t(locale, "chat.welcome.normal.eyebrow"),
    title: t(locale, "chat.welcome.normal.title"),
    description: t(locale, "chat.welcome.normal.description"),
    prompts: [
      {
        icon: "body",
        label: t(locale, "chat.welcome.normal.symptoms.label"),
        prompt: t(locale, "chat.welcome.normal.symptoms.prompt"),
      },
      {
        icon: "medication",
        label: t(locale, "chat.welcome.normal.medicine.label"),
        prompt: t(locale, "chat.welcome.normal.medicine.prompt"),
      },
      {
        icon: "scan",
        label: t(locale, "chat.welcome.normal.lab.label"),
        prompt: t(locale, "chat.welcome.normal.lab.prompt"),
      },
      {
        icon: "warning",
        label: t(locale, "chat.welcome.normal.safety.label"),
        prompt: t(locale, "chat.welcome.normal.safety.prompt"),
      },
    ],
  };
}

export default function ChatWelcome({
  role,
  uiLanguage,
  onChoosePrompt,
}: {
  role: UserRole;
  uiLanguage: UILanguage;
  onChoosePrompt: (prompt: string) => void;
}) {
  const experience =
    role === "researcher"
      ? "researcher"
      : role === "doctor" || role === "admin"
        ? "doctor"
        : "normal";
  const content =
    experience === "normal"
      ? normalWelcomeContent(uiLanguage)
      : specialistWelcomeContent(experience, uiLanguage);

  const contextualStarters = [
    {
      id: "meds",
      icon: "medication" as const,
      label: t(uiLanguage, "chat.welcome.chip.medicines"),
      prompt: t(uiLanguage, "chat.welcome.normal.medicine.prompt"),
    },
    {
      id: "labs",
      icon: "scan" as const,
      label: t(uiLanguage, "chat.welcome.chip.labs"),
      prompt: t(uiLanguage, "chat.welcome.normal.lab.prompt"),
    },
    {
      id: "symptoms",
      icon: "body" as const,
      label: t(uiLanguage, "chat.welcome.chip.symptoms"),
      prompt: t(uiLanguage, "chat.welcome.normal.symptoms.prompt"),
    },
    {
      id: "visitPrep",
      icon: "clinical-notes" as const,
      label: t(uiLanguage, "chat.welcome.chip.visitPrep"),
      prompt: t(uiLanguage, "chat.welcome.normal.safety.prompt"),
    },
  ];

  return (
    <div className="clara-scrollbar flex min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8 sm:py-12">
      <section className="mx-auto flex w-full max-w-3xl flex-col items-center justify-center text-center">
        {/* Glowing Hero Icon */}
        <div className="mb-5 flex h-16 w-16 items-center justify-center rounded-2xl border border-[color:var(--card-top-border)] bg-[var(--brand-600)]/15 text-[var(--text-brand)] shadow-[0_0_35px_rgba(164,201,255,0.15)]">
          <Icon name="clinical-notes" size={32} />
        </div>

        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-brand)]">
          {content.eyebrow}
        </p>
        <h2 className="mt-2.5 max-w-2xl text-[clamp(1.75rem,3.5vw,2.5rem)] font-bold leading-[1.15] tracking-tight text-[var(--text-primary)]">
          {content.title}
        </h2>
        <p className="mt-3 max-w-xl text-sm sm:text-base leading-relaxed text-[var(--text-secondary)]">
          {content.description}
        </p>

        {/* Evidence Promise Badge Line */}
        <div className="mt-4 flex items-center justify-center gap-1.5 text-xs text-[var(--text-muted)]">
          <Icon name="check" size={14} className="text-[var(--text-brand)]" />
          <span>{t(uiLanguage, "chat.welcome.promise")}</span>
        </div>

        {/* Contextual Quick Chips */}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {contextualStarters.map((starter) => (
            <button
              key={starter.id}
              type="button"
              onClick={() => onChoosePrompt(starter.prompt)}
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--shell-border)]/70 bg-[var(--surface-panel)] px-4 py-2 text-xs font-semibold text-[var(--text-secondary)] shadow-xs transition hover:border-[color:var(--brand-500)]/50 hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] active:scale-95"
            >
              <Icon name={starter.icon} size={15} className="text-[var(--text-brand)]" />
              <span>{starter.label}</span>
            </button>
          ))}
        </div>

        {/* Starter Prompts 2x2 Grid */}
        <div className="mt-8 grid w-full gap-3 sm:grid-cols-2 text-left">
          {content.prompts.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => onChoosePrompt(item.prompt)}
              className="group flex min-h-[64px] items-center justify-between gap-3.5 rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 text-left shadow-xs transition hover:-translate-y-0.5 hover:border-[color:var(--brand-500)]/50 hover:bg-[var(--surface-muted)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] motion-reduce:transform-none"
            >
              <div className="flex items-center gap-3.5 min-w-0">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[color:var(--shell-border)]/60 bg-[var(--surface-muted)] text-[var(--text-brand)] transition-colors group-hover:bg-[var(--surface-brand-soft)]">
                  <Icon name={item.icon as any} size={18} />
                </span>
                <span className="truncate text-xs sm:text-[13px] font-semibold text-[var(--text-primary)]">
                  {item.label}
                </span>
              </div>
              <Icon
                name="arrow-right"
                size={16}
                className="shrink-0 text-[var(--text-muted)] transition group-hover:translate-x-1 group-hover:text-[var(--text-brand)]"
              />
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
