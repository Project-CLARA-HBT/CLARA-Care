"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import AuthFormShell from "@/components/auth-form-shell";
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
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError(language === "vi" ? "Vui lòng nhập địa chỉ email." : "Please enter your email address.");
      return;
    }
    setIsSubmitting(true);
    setError("");
    setNotice("");
    setTokenPreview("");
    try {
      const response = await api.post("/auth/forgot-password", { email: cleanEmail });
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
    <AuthFormShell
      title={t(language, "auth.passwordRecovery.title")}
      subtitle={t(language, "auth.passwordRecovery.description")}
      backHref="/login"
      backLabel={t(language, "auth.passwordRecovery.back")}
      maxWidth="md"
      archetype="Recovery Focus"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field
          id="forgot-email"
          label={t(language, "auth.email")}
          type="email"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t(language, "auth.emailPlaceholder")}
          autoComplete="email"
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
          <div className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3 text-xs leading-5 text-[var(--text-secondary)]">
            <p className="font-semibold text-[var(--text-primary)]">
              {t(language, "auth.passwordRecovery.previewToken")}
            </p>
            <p className="mt-1 font-mono break-all text-[var(--text-brand)]">
              {tokenPreview}
            </p>
            <Link
              href={`/reset-password?token=${encodeURIComponent(tokenPreview)}`}
              className="focus-ring mt-2 inline-block font-semibold text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.passwordRecovery.openReset")} &rarr;
            </Link>
          </div>
        ) : null}

        <Button
          type="submit"
          block
          loading={isSubmitting}
          loadingLabel={t(language, "auth.passwordRecovery.submitting")}
        >
          {t(language, "auth.passwordRecovery.submit")}
        </Button>

        <div className="pt-2 text-center text-sm">
          <Link
            href="/login"
            className="focus-ring rounded font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:underline"
          >
            &larr; {t(language, "auth.passwordRecovery.back")}
          </Link>
        </div>
      </form>
    </AuthFormShell>
  );
}
