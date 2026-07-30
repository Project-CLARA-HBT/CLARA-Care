"use client";

import { useId, type MouseEventHandler, type ReactNode } from "react";

import Button from "@/components/ui/button";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type ReviewItem = {
  label: string;
  value: ReactNode;
};

export function ReviewSection({
  title,
  description,
  items = [],
  children,
  edit,
}: {
  title: string;
  description?: string;
  items?: ReviewItem[];
  children?: ReactNode;
  edit?: {
    label?: string;
    href?: string;
    onClick?: MouseEventHandler<HTMLButtonElement>;
  };
}) {
  const language = useUILanguage();
  const headingId = useId();

  return (
    <section
      aria-labelledby={headingId}
      className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4 shadow-[var(--shadow-sm)] sm:p-5"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 id={headingId} className="font-semibold text-[var(--text-primary)]">
            {title}
          </h2>
          {description ? (
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">{description}</p>
          ) : null}
        </div>
        {edit?.href ? (
          <Button as="link" href={edit.href} variant="ghost" size="sm">
            {edit.label ?? t(language, "action.edit")}
          </Button>
        ) : edit ? (
          <Button type="button" variant="ghost" size="sm" onClick={edit.onClick}>
            {edit.label ?? t(language, "action.edit")}
          </Button>
        ) : null}
      </div>

      {items.length ? (
        <dl className="mt-4 divide-y divide-[color:var(--shell-border)]">
          {items.map((item) => (
            <div key={item.label} className="grid gap-1 py-3 first:pt-0 last:pb-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)] sm:gap-4">
              <dt className="text-sm text-[var(--text-secondary)]">{item.label}</dt>
              <dd className="min-w-0 text-sm font-medium text-[var(--text-primary)]">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}

      {children ? <div className="mt-4">{children}</div> : null}
    </section>
  );
}

export default ReviewSection;
