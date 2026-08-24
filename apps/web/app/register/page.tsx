"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import Button from "@/components/ui/button";
import { Field, Select } from "@/components/ui/field";
import AuthFormShell from "@/components/auth-form-shell";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";
import { useUILanguage } from "@/lib/use-ui-language";

type UserRole = "normal" | "researcher" | "doctor";

function normalizeRegisterErrorMessage(message: string, language: UILanguage): string {
  const normalized = message.trim();
  const lowered = normalized.toLowerCase();
  if (!normalized) {
    return t(language, "auth.register.failure");
  }
  if (
    lowered.includes("internal server error") ||
    lowered.includes("request failed with status code 500") ||
    lowered.includes("status code: 500") ||
    lowered.includes("gateway") ||
    lowered.includes("timeout")
  ) {
    return t(language, "auth.register.failureConnection");
  }
  return normalized;
}

function getPasswordValidationError(password: string, language: UILanguage): string | null {
  if (password.length < 8) {
    return t(language, "auth.register.passwordTooShort");
  }
  if (password !== password.trim()) {
    return t(language, "auth.register.passwordWhitespace");
  }
  const hasAlpha = /[A-Za-z]/.test(password);
  const hasDigit = /\d/.test(password);
  if (!hasAlpha || !hasDigit) {
    return t(language, "auth.register.passwordRequirements");
  }
  return null;
}

export default function RegisterPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>("normal");
  const [acceptedLegal, setAcceptedLegal] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [needsVerificationLink, setNeedsVerificationLink] = useState(false);

  const passwordValidationError = getPasswordValidationError(password, language);
  const confirmPasswordError =
    confirmPassword && password !== confirmPassword
      ? t(language, "auth.register.passwordMismatch")
      : "";

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setNeedsVerificationLink(false);

    if (!acceptedLegal) {
      setError(t(language, "auth.register.acceptRequired"));
      return;
    }
    if (passwordValidationError) {
      setError(passwordValidationError);
      return;
    }
    if (password !== confirmPassword) {
      setError(t(language, "auth.register.passwordMismatch"));
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await api.post("/auth/register", {
        full_name: fullName,
        email,
        password,
        role,
        accepted_terms: true,
        accepted_privacy: true,
        accepted_medical_consent: true,
      });
      const tokenPreview = response.data?.verification_token_preview as string | undefined;
      const isVerified = Boolean(response.data?.is_email_verified);
      const deliveryStatus = (response.data?.email_delivery_status as string | undefined) ?? "";

      if (isVerified) {
        setNotice(t(language, "auth.register.success"));
        setTimeout(() => router.push("/login"), 1000);
      } else if (tokenPreview) {
        setNotice(t(language, "auth.register.successPreview", { token: tokenPreview }));
        setNeedsVerificationLink(true);
      } else if (deliveryStatus === "sent") {
        setNotice(t(language, "auth.register.successSent"));
        setNeedsVerificationLink(true);
      } else {
        setNotice(t(language, "auth.register.successVerify"));
        setNeedsVerificationLink(true);
      }
    } catch (cause) {
      setError(
        cause instanceof Error
          ? normalizeRegisterErrorMessage(cause.message, language)
          : t(language, "auth.register.failure"),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthFormShell
      title={t(language, "auth.register.title")}
      subtitle={t(language, "auth.register.description")}
      backHref="/"
      backLabel={t(language, "auth.backToHome")}
      maxWidth="lg"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field
          id="register-full-name"
          label={t(language, "auth.register.fullName")}
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder={t(language, "auth.register.fullNamePlaceholder")}
          autoComplete="name"
          required
        />

        <Field
          id="register-email"
          label={t(language, "auth.email")}
          type="email"
          inputMode="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={t(language, "auth.emailPlaceholder")}
          autoComplete="email"
          required
        />

        <div className="space-y-1.5">
          <Field
            id="register-password"
            label={t(language, "auth.register.password")}
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder={t(language, "auth.register.passwordPlaceholder")}
            autoComplete="new-password"
            minLength={8}
            required
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {t(language, "auth.register.passwordHint")}
          </p>
        </div>

        <div className="space-y-1.5">
          <Field
            id="register-confirm-password"
            label={t(language, "auth.register.confirmPassword")}
            type="password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            placeholder={t(language, "auth.register.confirmPasswordPlaceholder")}
            autoComplete="new-password"
            minLength={8}
            required
            aria-invalid={confirmPasswordError ? true : undefined}
          />
          {confirmPasswordError ? (
            <p role="alert" className="text-xs font-medium text-[var(--status-danger-text)]">
              {confirmPasswordError}
            </p>
          ) : (
            <p className="text-xs text-[var(--text-secondary)]">
              {t(language, "auth.register.confirmPasswordHint")}
            </p>
          )}
        </div>

        <Select
          id="register-role"
          label={t(language, "auth.register.role")}
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
        >
          <option value="normal">{t(language, "auth.register.role.normal")}</option>
          <option value="researcher">{t(language, "auth.register.role.researcher")}</option>
          <option value="doctor">{t(language, "auth.register.role.doctor")}</option>
        </Select>

        <label className="flex cursor-pointer items-start gap-3 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
          <input
            type="checkbox"
            checked={acceptedLegal}
            onChange={(event) => setAcceptedLegal(event.target.checked)}
            className="focus-ring mt-1 h-4 w-4 rounded border-[color:var(--shell-border-strong)] text-[var(--brand-500)]"
          />
          <span className="text-xs leading-5 text-[var(--text-secondary)]">
            {t(language, "auth.register.acceptLegal")}{" "}
            <Link
              href="/legal/terms"
              className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.register.terms")}
            </Link>
            ,{" "}
            <Link
              href="/legal/privacy"
              className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.register.privacy")}
            </Link>{" "}
            và{" "}
            <Link
              href="/legal/consent"
              className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.register.medicalConsent")}
            </Link>
            .
          </span>
        </label>

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

        {needsVerificationLink ? (
          <Link
            href={`/verify-email?email=${encodeURIComponent(email)}`}
            className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
          >
            {t(language, "auth.register.goToVerify")}
          </Link>
        ) : null}

        <Button
          type="submit"
          block
          loading={isSubmitting}
          loadingLabel={t(language, "auth.register.submitting")}
        >
          {t(language, "auth.register.submit")}
        </Button>

        <div className="pt-2 text-center text-sm text-[var(--text-secondary)]">
          <span>{t(language, "auth.register.hasAccount")} </span>
          <Link
            href="/login"
            className="focus-ring rounded font-semibold text-[var(--text-brand)] hover:underline"
          >
            {t(language, "auth.login.submit")}
          </Link>
        </div>
      </form>
    </AuthFormShell>
  );
}
