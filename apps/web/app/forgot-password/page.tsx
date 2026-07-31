"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";

export default function ForgotPasswordPage() {
  const language = useUILanguage();
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tokenPreview, setTokenPreview] = useState("");

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    setNotice("");
    setTokenPreview("");
    try {
      const response = await api.post("/auth/forgot-password", { email });
      const token = response.data?.reset_token_preview as string | undefined;
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";
      if (token) {
        setTokenPreview(token);
        setNotice(t(language, "auth.passwordRecovery.previewNotice"));
      } else if (deliveryStatus === "sent") {
        setNotice(t(language, "auth.passwordRecovery.sentNotice"));
      } else {
        setNotice(t(language, "auth.passwordRecovery.genericNotice"));
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "auth.passwordRecovery.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">{t(language, "auth.brand")}</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          {t(language, "auth.passwordRecovery.title")}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "auth.passwordRecovery.description")}
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Field
            id="forgot-email"
            label={t(language, "auth.email")}
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder={t(language, "auth.emailPlaceholder")}
            required
          />

          {notice ? (
            <p
              role="status"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-ok-text)]"
            >
              {notice}
            </p>
          ) : null}
          {error ? (
            <p
              role="alert"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]"
            >
              {error}
            </p>
          ) : null}

          {tokenPreview ? (
            <p className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-2 text-sm text-[var(--text-secondary)]">
              {t(language, "auth.passwordRecovery.previewToken")} <code className="font-mono text-xs">{tokenPreview}</code>{" "}
              <Link
                href={`/reset-password?token=${encodeURIComponent(tokenPreview)}`}
                className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
              >
                {t(language, "auth.passwordRecovery.openReset")}
              </Link>
            </p>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel={t(language, "auth.passwordRecovery.submitting")}>
            {t(language, "auth.passwordRecovery.submit")}
          </Button>

          <Link
            href="/login"
            className="focus-ring inline-block rounded text-sm text-[var(--text-secondary)] hover:underline"
          >
            {t(language, "auth.passwordRecovery.back")}
          </Link>
        </form>
      </SurfaceCard>
    </main>
  );
}
