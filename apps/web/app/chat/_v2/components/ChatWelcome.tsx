"use client";

import type { UserRole } from "@/lib/auth-store";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

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
        icon: "manage_search",
        label: "chat.welcome.researcher.overview.label",
        prompt: "chat.welcome.researcher.overview.prompt",
      },
      {
        icon: "difference",
        label: "chat.welcome.researcher.compare.label",
        prompt: "chat.welcome.researcher.compare.prompt",
      },
      {
        icon: "fact_check",
        label: "chat.welcome.researcher.claim.label",
        prompt: "chat.welcome.researcher.claim.prompt",
      },
      {
        icon: "biotech",
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
        icon: "clinical_notes",
        label: "chat.welcome.doctor.summary.label",
        prompt: "chat.welcome.doctor.summary.prompt",
      },
      {
        icon: "account_tree",
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
        icon: "symptoms",
        label: t(locale, "chat.welcome.normal.symptoms.label"),
        prompt: t(locale, "chat.welcome.normal.symptoms.prompt"),
      },
      {
        icon: "pill",
        label: t(locale, "chat.welcome.normal.medicine.label"),
        prompt: t(locale, "chat.welcome.normal.medicine.prompt"),
      },
      {
        icon: "experiment",
        label: t(locale, "chat.welcome.normal.lab.label"),
        prompt: t(locale, "chat.welcome.normal.lab.prompt"),
      },
      {
        icon: "health_and_safety",
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
    <div className="clara-scrollbar flex min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-7 sm:py-12">
      <section className="mx-auto flex w-full max-w-3xl flex-col justify-center">
        <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--brand-600)] text-white shadow-[0_14px_30px_-18px_rgba(37,99,235,.85)]">
          <span
            className="material-symbols-outlined text-[25px]"
            style={{ fontVariationSettings: "'FILL' 1" }}
            aria-hidden="true"
          >
            medical_services
          </span>
        </div>
        <p className="text-xs font-semibold text-[var(--text-brand)]">
          {content.eyebrow}
        </p>
        <h2 className="mt-2 max-w-2xl text-[clamp(1.8rem,4vw,2.65rem)] font-semibold leading-[1.08] tracking-[-0.045em] text-[var(--text-primary)]">
          {content.title}
        </h2>
        <p className="mt-3 max-w-2xl text-[15px] leading-6 text-[var(--text-secondary)]">
          {content.description}
        </p>

        <div className="mt-8 grid gap-2.5 sm:grid-cols-2">
          {content.prompts.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => onChoosePrompt(item.prompt)}
              className="group flex min-h-[64px] items-center gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-left shadow-[0_8px_24px_-24px_rgba(15,23,42,.55)] transition hover:-translate-y-0.5 hover:border-[color:var(--shell-border-strong)] hover:shadow-[0_14px_30px_-24px_rgba(37,99,235,.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-500)] motion-reduce:transform-none"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[var(--surface-brand-soft)] text-[var(--text-brand)]">
                <span
                  className="material-symbols-outlined text-[19px]"
                  aria-hidden="true"
                >
                  {item.icon}
                </span>
              </span>
              <span className="min-w-0 flex-1 text-[13px] font-semibold text-[var(--text-primary)]">
                {item.label}
              </span>
              <span
                className="material-symbols-outlined text-[18px] text-[var(--text-muted)] transition group-hover:translate-x-0.5"
                aria-hidden="true"
              >
                arrow_forward
              </span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
