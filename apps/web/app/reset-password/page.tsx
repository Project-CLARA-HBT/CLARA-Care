"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function ResetPasswordPage() {
  const language = useUILanguage();
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token") ?? "";
    if (tokenFromUrl) setToken(tokenFromUrl);
  }, []);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setNotice("");
    setError("");
    try {
      await api.post("/auth/reset-password", { token, new_password: newPassword });
      setNotice(t(language, "auth.passwordReset.success"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t(language, "auth.passwordReset.error"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">{t(language, "auth.brand")}</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          {t(language, "auth.passwordReset.title")}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {t(language, "auth.passwordReset.description")}
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
          <Textarea
            id="reset-token"
            label={t(language, "auth.passwordReset.token")}
            rows={3}
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder={t(language, "auth.passwordReset.tokenPlaceholder")}
            required
          />

          <Field
            id="reset-new-password"
            label={t(language, "auth.passwordReset.newPassword")}
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder={t(language, "auth.register.passwordPlaceholder")}
            minLength={8}
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
              {t(language, "auth.passwordReset.goToLogin")}
            </Link>
          ) : null}

          <Button type="submit" block loading={isSubmitting} loadingLabel={t(language, "auth.passwordReset.submitting")}>
            {t(language, "auth.passwordReset.submit")}
          </Button>
        </form>
      </SurfaceCard>
    </main>
  );
}
