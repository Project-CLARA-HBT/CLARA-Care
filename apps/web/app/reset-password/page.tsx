"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/field";
import AuthFormShell from "@/components/auth-form-shell";
import { t } from "@/lib/i18n/catalog";
import { safeUserFacingError } from "@/lib/user-facing-text";
import { useUILanguage } from "@/lib/use-ui-language";

function getPasswordValidationError(password: string, language: string): string | null {
  if (password.length < 8) {
    return t(language as any, "auth.register.passwordTooShort");
  }
  if (password !== password.trim()) {
    return t(language as any, "auth.register.passwordWhitespace");
  }
  const hasAlpha = /[A-Za-z]/.test(password);
  const hasDigit = /\d/.test(password);
  if (!hasAlpha || !hasDigit) {
    return t(language as any, "auth.register.passwordRequirements");
  }
  return null;
}

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
    setNotice("");
    setError("");

    const cleanToken = token.trim();
    if (!cleanToken) {
      setError(language === "vi" ? "Vui lòng nhập mã đặt lại mật khẩu." : "Please enter the password reset token.");
      return;
    }

    const passwordError = getPasswordValidationError(newPassword, language);
    if (passwordError) {
      setError(passwordError);
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post("/auth/reset-password", { token: cleanToken, new_password: newPassword });
      setNotice(t(language, "auth.passwordReset.success"));
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "auth.passwordReset.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthFormShell
      title={t(language, "auth.passwordReset.title")}
      subtitle={t(language, "auth.passwordReset.description")}
      backHref="/login"
      backLabel={t(language, "auth.passwordRecovery.back")}
      maxWidth="md"
      archetype="Recovery Focus"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Textarea
          id="reset-token"
          label={t(language, "auth.passwordReset.token")}
          rows={3}
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder={t(language, "auth.passwordReset.tokenPlaceholder")}
          required
        />

        <div className="space-y-1.5">
          <Field
            id="reset-new-password"
            label={t(language, "auth.passwordReset.newPassword")}
            type="password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            placeholder={t(language, "auth.register.passwordPlaceholder")}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {t(language, "auth.register.passwordHint")}
          </p>
        </div>

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
            className="focus-ring inline-block rounded text-sm font-semibold text-[var(--text-brand)] hover:underline"
          >
            {t(language, "auth.passwordReset.goToLogin")} &rarr;
          </Link>
        ) : null}

        <Button
          type="submit"
          block
          loading={isSubmitting}
          loadingLabel={t(language, "auth.passwordReset.submitting")}
        >
          {t(language, "auth.passwordReset.submit")}
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
