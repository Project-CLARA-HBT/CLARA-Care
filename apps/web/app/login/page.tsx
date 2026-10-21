"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { markAuthenticatedBrowserSession, setAuthoritativeServerRole } from "@/lib/auth-store";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import AuthFormShell from "@/components/auth-form-shell";
import AuthRateLimitBanner from "@/components/auth/auth-rate-limit-banner";
import AuthSecurityChallenge from "@/components/auth/auth-security-challenge";
import {
  getAuthCooldownRemaining,
  getAuthRateLimitRecord,
  isRateLimitOrLockoutError,
  recordAuthFailure,
  recordAuthSuccess,
  setAuthCaptchaSolved,
} from "@/lib/auth-rate-limit";
import { resolvePostLoginPath } from "@/lib/navigation.config";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

export default function LoginPage() {
  const router = useRouter();
  const language = useUILanguage();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpEmail, setOtpEmail] = useState<string | null>(null);
  const [otpDeliveryStatus, setOtpDeliveryStatus] = useState<string | null>(null);
  const [otpPreviewCode, setOtpPreviewCode] = useState<string | null>(null);
  const [otpExpiresInSeconds, setOtpExpiresInSeconds] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Rate-limiting, brute-force mitigation & progressive delay state
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const [captchaRequired, setCaptchaRequired] = useState(false);
  const [isCaptchaSolved, setIsCaptchaSolved] = useState(false);
  const [failedAttempts, setFailedAttempts] = useState(0);
  const [isLockedOut, setIsLockedOut] = useState(false);

  const isOtpStep = Boolean(otpEmail);
  const shouldShowVerifyLink = /xác thực|verify/i.test(error);

  const syncRateLimitState = useCallback((targetContext: "login" | "otp", targetEmail?: string | null) => {
    const record = getAuthRateLimitRecord(targetContext, targetEmail);
    const remaining = getAuthCooldownRemaining(targetContext, targetEmail);
    setCooldownSeconds(remaining);
    setCaptchaRequired(record.captchaRequired);
    setIsCaptchaSolved(record.captchaSolved);
    setFailedAttempts(record.failedCount);
    setIsLockedOut(remaining > 0 && record.failedCount >= 5);
  }, []);

  // Sync state whenever switching between password and OTP steps, or when target email changes
  useEffect(() => {
    syncRateLimitState(isOtpStep ? "otp" : "login", isOtpStep ? otpEmail : email);
  }, [isOtpStep, otpEmail, email, syncRateLimitState]);

  // Live countdown timer for active cooldowns
  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const interval = setInterval(() => {
      setCooldownSeconds((prev) => {
        if (prev <= 1) {
          setIsLockedOut(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [cooldownSeconds]);

  const resetOtpStep = () => {
    setOtpCode("");
    setOtpEmail(null);
    setOtpDeliveryStatus(null);
    setOtpPreviewCode(null);
    setOtpExpiresInSeconds(null);
    syncRateLimitState("login", email);
  };

  const handleCaptchaSolved = (solved: boolean) => {
    setIsCaptchaSolved(solved);
    const activeEmail = isOtpStep ? (otpEmail ?? email) : email;
    setAuthCaptchaSolved(isOtpStep ? "otp" : "login", activeEmail, solved);
    if (solved) {
      setError("");
    }
  };

  const finishLogin = (payload: {
    access_token?: string;
    refresh_token?: string;
    role?: "normal" | "researcher" | "doctor" | "admin";
  }) => {
    const activeEmail = isOtpStep ? (otpEmail ?? email) : email;
    recordAuthSuccess("login", activeEmail);
    recordAuthSuccess("otp", activeEmail);

    const serverRole = payload.role;
    const nextRole = serverRole ?? "normal";

    markAuthenticatedBrowserSession();
    setAuthoritativeServerRole(nextRole);
    const targetPath = resolvePostLoginPath({
      nextPath:
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("next")
          : null,
      role: nextRole,
    });
    router.replace(targetPath);
    router.refresh();
    if (typeof window !== "undefined") {
      window.setTimeout(() => {
        if (window.location.pathname === "/login") {
          window.location.assign(targetPath);
        }
      }, 350);
    }
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (cooldownSeconds > 0) {
      setError(
        isLockedOut
          ? t(language, "auth.rateLimit.lockedOut", { seconds: cooldownSeconds })
          : t(language, "auth.rateLimit.cooldown", { seconds: cooldownSeconds }),
      );
      return;
    }

    if (captchaRequired && !isCaptchaSolved) {
      setError(t(language, "auth.rateLimit.challengeRequired"));
      return;
    }

    setError("");
    setIsSubmitting(true);

    const activeContext: "login" | "otp" = isOtpStep ? "otp" : "login";
    const activeEmail = isOtpStep ? (otpEmail ?? email).trim() : email.trim();

    try {
      if (isOtpStep) {
        const normalizedOtpCode = otpCode.trim();
        const response = await api.post("/auth/login-otp/verify", {
          email: activeEmail,
          otp_code: normalizedOtpCode,
        });
        finishLogin(response.data ?? {});
      } else {
        const response = await api.post("/auth/login", { email: activeEmail, password });
        const otpRequired = Boolean(response.data?.otp_required);
        if (otpRequired) {
          // Password step succeeded; clear login attempt failures and transition to OTP
          recordAuthSuccess("login", activeEmail);
          setOtpEmail(activeEmail);
          setOtpCode("");
          setOtpDeliveryStatus(
            typeof response.data?.otp_delivery_status === "string"
              ? response.data.otp_delivery_status
              : null,
          );
          setOtpPreviewCode(
            typeof response.data?.otp_code_preview === "string"
              ? response.data.otp_code_preview
              : null,
          );
          setOtpExpiresInSeconds(
            typeof response.data?.otp_expires_in_seconds === "number"
              ? response.data.otp_expires_in_seconds
              : null,
          );
          syncRateLimitState("otp", activeEmail);
          return;
        }
        finishLogin(response.data ?? {});
      }
    } catch (submitError) {
      const { isRateLimited, isLockedOut: serverLocked, retryAfter } =
        isRateLimitOrLockoutError(submitError);

      const failure = recordAuthFailure(activeContext, activeEmail, retryAfter);
      setCooldownSeconds(failure.cooldownSeconds);
      setCaptchaRequired(failure.captchaRequired);
      setIsCaptchaSolved(false);
      setFailedAttempts(failure.failedCount);
      setIsLockedOut(failure.isLockedOut || isRateLimited || serverLocked);

      const fallbackMessage = t(language, "auth.login.failure");
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else if (failure.isLockedOut) {
        setError(t(language, "auth.rateLimit.lockedOut", { seconds: failure.cooldownSeconds }));
      } else if (failure.cooldownSeconds > 0) {
        setError(t(language, "auth.rateLimit.cooldown", { seconds: failure.cooldownSeconds }));
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormLocked = cooldownSeconds > 0;
  const isSubmitDisabled = isSubmitting || isFormLocked || (captchaRequired && !isCaptchaSolved);

  return (
    <AuthFormShell
      title={isOtpStep ? t(language, "auth.otp.title") : t(language, "auth.login.title")}
      subtitle={
        isOtpStep
          ? t(language, "auth.otp.description")
          : t(language, "auth.login.description")
      }
      backHref="/"
      backLabel={t(language, "auth.backToHome")}
      maxWidth="lg"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {!isOtpStep ? (
          <>
            <Field
              id="login-email"
              label={t(language, "auth.email")}
              type="email"
              inputMode="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder={t(language, "auth.emailPlaceholder")}
              autoComplete="username"
              required
              disabled={isLockedOut}
            />
            <Field
              id="login-password"
              label={t(language, "auth.login.password")}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={t(language, "auth.login.passwordPlaceholder")}
              autoComplete="current-password"
              required
              disabled={isLockedOut}
            />
          </>
        ) : (
          <>
            <Field
              id="login-otp"
              label={t(language, "auth.otp.code")}
              type="text"
              value={otpCode}
              onChange={(event) => setOtpCode(event.target.value)}
              placeholder={t(language, "auth.otp.placeholder")}
              required
              minLength={6}
              maxLength={6}
              autoComplete="one-time-code"
              disabled={isLockedOut}
            />
            <p className="text-xs text-[var(--text-muted)]">
              {t(language, "auth.otp.sentTo")}{" "}
              <span className="font-semibold text-[var(--text-primary)]">{otpEmail}</span>
            </p>
            {otpDeliveryStatus ? (
              <p className="text-xs text-[var(--text-muted)]">
                {t(language, "auth.otp.deliveryStatus", { status: otpDeliveryStatus })}
              </p>
            ) : null}
            {otpExpiresInSeconds ? (
              <p className="text-xs text-[var(--text-muted)]">
                {t(language, "auth.otp.expiresIn", {
                  minutes: Math.max(1, Math.round(otpExpiresInSeconds / 60)),
                })}
              </p>
            ) : null}
            {otpPreviewCode ? (
              <p className="rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2 text-xs text-[var(--status-warn-text)]">
                {t(language, "auth.otp.preview")} <span className="font-bold">{otpPreviewCode}</span>
              </p>
            ) : null}
          </>
        )}

        {/* Rate limit cooldown & lockout banner */}
        <AuthRateLimitBanner
          cooldownSeconds={cooldownSeconds}
          failedAttempts={failedAttempts}
          isLockout={isLockedOut}
          context={isOtpStep ? "otp" : "login"}
          language={language}
        />

        {/* Security Challenge / Captcha required upon reaching failure threshold */}
        {captchaRequired ? (
          <AuthSecurityChallenge
            onSolvedChange={handleCaptchaSolved}
            isSolved={isCaptchaSolved}
            disabled={isSubmitting || cooldownSeconds > 0}
            language={language}
          />
        ) : null}

        {error ? (
          <p
            role="alert"
            className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]"
          >
            {error}
          </p>
        ) : null}

        {!isOtpStep && shouldShowVerifyLink ? (
          <Link
            href={`/verify-email?email=${encodeURIComponent(email)}`}
            className="focus-ring inline-block rounded text-sm font-medium text-[var(--text-brand)] hover:underline"
          >
            {t(language, "auth.login.unverified")}
          </Link>
        ) : null}

        <Button
          type="submit"
          block
          disabled={isSubmitDisabled}
          loading={isSubmitting}
          loadingLabel={
            isOtpStep
              ? t(language, "auth.otp.verifying")
              : t(language, "auth.login.submitting")
          }
        >
          {cooldownSeconds > 0
            ? t(language, "auth.rateLimit.cooldownButton", { seconds: cooldownSeconds })
            : isOtpStep
              ? t(language, "auth.otp.verify")
              : t(language, "auth.login.submit")}
        </Button>

        {!isOtpStep ? (
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-sm">
            <Link
              href="/register"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.login.createAccount")}
            </Link>
            <Link
              href="/forgot-password"
              className="focus-ring rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:underline"
            >
              {t(language, "auth.login.forgotPassword")}
            </Link>
          </div>
        ) : (
          <Button type="button" variant="secondary" block onClick={resetOtpStep}>
            {t(language, "auth.login.backToPassword")}
          </Button>
        )}
      </form>
    </AuthFormShell>
  );
}
