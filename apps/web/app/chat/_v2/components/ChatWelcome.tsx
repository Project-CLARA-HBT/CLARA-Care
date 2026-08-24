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

  return (
    <div className="clara-scrollbar flex min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-6 sm:py-12">
      {/* Centered reading column (760-900px) */}
      <section
        data-testid="chat-welcome"
        className="mx-auto flex w-full max-w-[860px] flex-col items-center justify-center text-center my-auto"
      >
        {/* Subtle Icon Glow */}
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] text-[var(--text-brand)] shadow-xs">
          <Icon name="clinical-notes" size={24} />
        </div>

        <p className="text-xs font-semibold uppercase tracking-wider text-[var(--text-brand)]">
          {content.eyebrow}
        </p>
        <h2 className="mt-2 text-2xl sm:text-3xl font-bold leading-tight tracking-tight text-[var(--text-primary)]">
          {content.title}
        </h2>
        <p className="mt-2.5 max-w-lg text-xs sm:text-sm leading-relaxed text-[var(--text-secondary)]">
          {content.description}
        </p>

        {/* Evidence Promise Line */}
        <div className="mt-3 flex items-center justify-center gap-1.5 text-[11px] text-[var(--text-muted)]">
          <Icon name="check" size={13} className="text-[var(--text-brand)]" />
          <span>{t(uiLanguage, "chat.welcome.promise")}</span>
        </div>

        {/* 3–4 Starter Chips (Spec v8 §7.2: Calm starter chips, no 4 large shortcut cards) */}
        <div className="mt-6 flex flex-wrap justify-center gap-2 max-w-2xl">
          {content.prompts.slice(0, 4).map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => onChoosePrompt(item.prompt)}
              className="inline-flex items-center gap-2 rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] shadow-xs transition hover:border-[color:var(--brand-500)] hover:bg-[var(--surface-muted)] hover:text-[var(--text-primary)] active:scale-95"
            >
              <Icon name={item.icon as any} size={14} className="text-[var(--text-brand)] shrink-0" />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
