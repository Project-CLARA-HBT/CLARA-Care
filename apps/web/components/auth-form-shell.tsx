"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export type AuthFormShellProps = {
  title: string;
  subtitle?: string;
  badge?: string;
  backHref?: string;
  backLabel?: string;
  maxWidth?: "md" | "lg";
  hideLegal?: boolean;
  children: ReactNode;
};

export default function AuthFormShell({
  title,
  subtitle,
  badge,
  backHref = "/",
  backLabel,
  maxWidth = "lg",
  hideLegal = false,
  children,
}: AuthFormShellProps) {
  const language = useUILanguage();
  const maxClass = maxWidth === "md" ? "max-w-md" : "max-w-lg";

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full items-center justify-center px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <section
        className={`w-full ${maxClass} rounded-[var(--radius-xl)] border border-t-[color:var(--card-top-border)] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-6 sm:p-9 shadow-sm`}
        aria-labelledby="auth-form-title"
        aria-describedby={subtitle ? "auth-form-subtitle" : undefined}
      >
        {/* Top Header: Brand Badge & Back Link */}
        <div className="flex items-center justify-between gap-3">
          <Badge tone="brand">
            {badge ?? t(language, "auth.brand")}
          </Badge>
          {backHref ? (
            <Link
              href={backHref}
              className="focus-ring inline-flex items-center gap-1 text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:underline"
            >
              <span aria-hidden="true">&larr;</span>
              <span>{backLabel ?? t(language, "auth.backToHome")}</span>
            </Link>
          ) : null}
        </div>

        {/* Heading & Subtitle */}
        <h1
          id="auth-form-title"
          className="mt-4 text-2xl font-bold tracking-tight text-[var(--text-primary)] sm:text-3xl"
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            id="auth-form-subtitle"
            className="mt-2 text-sm leading-6 text-[var(--text-secondary)]"
          >
            {subtitle}
          </p>
        ) : null}

        {/* Main Content / Form */}
        <div className="mt-7">{children}</div>

        {/* Clear Legal Consent Disclaimer Footer */}
        {!hideLegal ? (
          <div className="mt-8 border-t border-[color:var(--shell-border)]/60 pt-5 text-center text-xs leading-5 text-[var(--text-muted)]">
            <p>
              {t(language, "auth.legal.acknowledgement")}{" "}
              <Link
                href="/legal/terms"
                className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
              >
                {t(language, "auth.legal.terms")}
              </Link>
              ,{" "}
              <Link
                href="/legal/privacy"
                className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
              >
                {t(language, "auth.legal.privacy")}
              </Link>{" "}
              {language === "vi" ? "và" : "and"}{" "}
              <Link
                href="/legal/consent"
                className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
              >
                {t(language, "auth.legal.medicalConsent")}
              </Link>
              .
            </p>
          </div>
        ) : null}
      </section>
    </main>
  );
}
