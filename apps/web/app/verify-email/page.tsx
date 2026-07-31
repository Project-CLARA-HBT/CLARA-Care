"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";

export default function VerifyEmailPage() {
  const language = useUILanguage();
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isResending, setIsResending] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token") ?? "";
    const emailFromUrl = params.get("email") ?? "";
    if (tokenFromUrl) setToken(tokenFromUrl);
    if (emailFromUrl) setEmail(emailFromUrl);
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setNotice("");
    setError("");
    setIsSubmitting(true);
    try {
      await api.post("/auth/verify-email", { token });
      setNotice(t(language, "auth.verify.success"));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "auth.verify.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const onResend = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice("");
    setError("");
    setIsResending(true);
    try {
      const response = await api.post("/auth/resend-verification", { email });
      const tokenPreview = response.data?.verification_token_preview as string | undefined;
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";
      if (tokenPreview) {
        setToken(tokenPreview);
        setNotice(t(language, "auth.verify.resendPreview"));
      } else if (deliveryStatus === "sent") {
        setNotice(t(language, "auth.verify.resendSent"));
      } else {
        setNotice(t(language, "auth.verify.resendGeneric"));
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "auth.verify.resendError")));
    } finally {
      setIsResending(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">{t(language, "auth.brand")}</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          {t(language, "auth.verify.title")}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "auth.verify.description")}
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Textarea
            id="verify-token"
            label={t(language, "auth.verify.token")}
            rows={3}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={t(language, "auth.verify.tokenPlaceholder")}
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

          {notice ? (
            <Link
              href="/login"
              className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.verify.goToLogin")}
            </Link>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel={t(language, "auth.verify.submitting")}>
            {t(language, "auth.verify.submit")}
          </Button>
        </form>

        <div className="my-6 border-t border-[color:var(--shell-border)]" />

        <form className="space-y-4" onSubmit={onResend}>
          <Field
            id="verify-email"
            label={t(language, "auth.verify.resendEmail")}
            type="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder={t(language, "auth.emailPlaceholder")}
            required
          />
          <Button
            type="submit"
            variant="secondary"
            block
            loading={isResending}
            loadingLabel={t(language, "auth.verify.resending")}
          >
            {t(language, "auth.verify.resend")}
          </Button>
        </form>
      </SurfaceCard>
    </main>
  );
}
