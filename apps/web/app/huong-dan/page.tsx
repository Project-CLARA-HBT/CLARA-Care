"use client";

import { useEffect, useState } from "react";

import Button from "@/components/ui/button";
import { Icon, resolveIconName } from "@/components/ui/icon";
import { SurfaceCard } from "@/components/ui/surface";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import { PRIMARY_ACTIONS, type PrimarySurface } from "@/lib/primary-actions";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";

type GuideTask = {
  title: UITranslationKey;
  detail: UITranslationKey;
  surface: PrimarySurface;
  icon: string;
  steps: [UITranslationKey, UITranslationKey, UITranslationKey];
  action: UITranslationKey;
};

const TASKS: GuideTask[] = [
  {
    title: "guide.tasks.chat.title",
    detail: "guide.tasks.chat.detail",
    surface: "chat",
    icon: "chat",
    steps: ["guide.tasks.chat.step1", "guide.tasks.chat.step2", "guide.tasks.chat.step3"],
    action: "guide.tasks.chat.action",
  },
  {
    title: "guide.tasks.thinking.title",
    detail: "guide.tasks.thinking.detail",
    surface: "chat_thinking",
    icon: "psychology",
    steps: [
      "guide.tasks.thinking.step1",
      "guide.tasks.thinking.step2",
      "guide.tasks.thinking.step3",
    ],
    action: "guide.tasks.thinking.action",
  },
  {
    title: "guide.tasks.cabinet.title",
    detail: "guide.tasks.cabinet.detail",
    surface: "selfmed",
    icon: "medication",
    steps: [
      "guide.tasks.cabinet.step1",
      "guide.tasks.cabinet.step2",
      "guide.tasks.cabinet.step3",
    ],
    action: "guide.tasks.cabinet.action",
  },
  {
    title: "guide.tasks.interactions.title",
    detail: "guide.tasks.interactions.detail",
    surface: "ddi",
    icon: "health_and_safety",
    steps: [
      "guide.tasks.interactions.step1",
      "guide.tasks.interactions.step2",
      "guide.tasks.interactions.step3",
    ],
    action: "guide.tasks.interactions.action",
  },
  {
    title: "guide.tasks.council.title",
    detail: "guide.tasks.council.detail",
    surface: "council",
    icon: "groups",
    steps: [
      "guide.tasks.council.step1",
      "guide.tasks.council.step2",
      "guide.tasks.council.step3",
    ],
    action: "guide.tasks.council.action",
  },
  {
    title: "guide.tasks.scribe.title",
    detail: "guide.tasks.scribe.detail",
    surface: "scribe",
    icon: "edit_note",
    steps: [
      "guide.tasks.scribe.step1",
      "guide.tasks.scribe.step2",
      "guide.tasks.scribe.step3",
    ],
    action: "guide.tasks.scribe.action",
  },
];

const LABELS = [
  { term: "guide.labels.quick.term", meaning: "guide.labels.quick.meaning" },
  { term: "guide.labels.thinking.term", meaning: "guide.labels.thinking.meaning" },
  { term: "guide.labels.pro.term", meaning: "guide.labels.pro.meaning" },
  { term: "guide.labels.autoSources.term", meaning: "guide.labels.autoSources.meaning" },
  { term: "guide.labels.fullSources.term", meaning: "guide.labels.fullSources.meaning" },
] as const satisfies ReadonlyArray<{
  term: UITranslationKey;
  meaning: UITranslationKey;
}>;

export default function GuidePage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-5 py-8 sm:px-6 lg:px-8">
      <SurfaceCard className="p-5 sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">
          {t(uiLanguage, "guide.eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)]">
          {t(uiLanguage, "guide.title")}
        </h1>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">
          {t(uiLanguage, "guide.description")}
        </p>
      </SurfaceCard>

      <section className="grid gap-3 md:grid-cols-2">
        {TASKS.map((task) => {
          const action = PRIMARY_ACTIONS[task.surface];
          return (
            <SurfaceCard key={task.title} className="p-4">
              <div className="flex items-start gap-3">
                <Icon name={resolveIconName(task.icon)} size="22px" className="mt-0.5 text-[var(--brand-600)]" />
                <div className="min-w-0 flex-1">
                  <h2 className="text-base font-semibold text-[var(--text-primary)]">
                    {t(uiLanguage, task.title)}
                  </h2>
                  <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                    {t(uiLanguage, task.detail)}
                  </p>
                </div>
              </div>
              <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm leading-6 text-[var(--text-secondary)]">
                {task.steps.map((step) => (
                  <li key={step}>{t(uiLanguage, step)}</li>
                ))}
              </ol>
              <div className="mt-4">
                <Button as="link" href={action.href} variant="secondary" size="sm">
                  {t(uiLanguage, task.action)}
                </Button>
              </div>
            </SurfaceCard>
          );
        })}
      </section>

      <SurfaceCard className="p-5">
        <h2 className="text-base font-semibold text-[var(--text-primary)]">
          {t(uiLanguage, "guide.labels.title")}
        </h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {LABELS.map((item) => (
            <div
              key={item.term}
              className="rounded-[var(--radius-md)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3"
            >
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                {t(uiLanguage, item.term)}
              </p>
              <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                {t(uiLanguage, item.meaning)}
              </p>
            </div>
          ))}
        </div>
      </SurfaceCard>
    </main>
  );
}
