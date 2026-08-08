"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import api from "@/lib/http-client";
import { markAuthenticatedBrowserSession, setRole as setStoredRole } from "@/lib/auth-store";
import Button from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard } from "@/components/ui/surface";
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

  const isOtpStep = Boolean(otpEmail);
  const shouldShowVerifyLink = /xác thực|verify/i.test(error);

  const resetOtpStep = () => {
    setOtpCode("");
    setOtpEmail(null);
    setOtpDeliveryStatus(null);
    setOtpPreviewCode(null);
    setOtpExpiresInSeconds(null);
  };

  const finishLogin = (payload: {
    access_token?: string;
    refresh_token?: string;
    role?: "normal" | "researcher" | "doctor" | "admin";
  }) => {
    const serverRole = payload.role;

    const nextRole = serverRole ?? "normal";
    // The API has already set HttpOnly access/refresh cookies. Its token fields
    // remain for native clients, but a browser must not retain them in
    // script-readable storage.
    markAuthenticatedBrowserSession();
    setStoredRole(nextRole);
    const targetPath = resolvePostLoginPath({
      nextPath:
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("next")
          : null,
      role: nextRole
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
    setError("");
    setIsSubmitting(true);

    try {
      if (isOtpStep) {
        const normalizedEmail = (otpEmail ?? email).trim();
        const normalizedOtpCode = otpCode.trim();
        const response = await api.post("/auth/login-otp/verify", {
          email: normalizedEmail,
          otp_code: normalizedOtpCode,
        });
        finishLogin(response.data ?? {});
      } else {
        const normalizedEmail = email.trim();
        const response = await api.post("/auth/login", { email: normalizedEmail, password });
        const otpRequired = Boolean(response.data?.otp_required);
        if (otpRequired) {
          setOtpEmail(normalizedEmail);
          setOtpCode("");
          setOtpDeliveryStatus(
            typeof response.data?.otp_delivery_status === "string"
              ? response.data.otp_delivery_status
              : null
          );
          setOtpPreviewCode(
            typeof response.data?.otp_code_preview === "string"
              ? response.data.otp_code_preview
              : null
          );
          setOtpExpiresInSeconds(
            typeof response.data?.otp_expires_in_seconds === "number"
              ? response.data.otp_expires_in_seconds
              : null
          );
          return;
        }
        finishLogin(response.data ?? {});
      }
    } catch (submitError) {
      const fallbackMessage = t(language, "auth.login.failure");
      if (submitError instanceof Error && submitError.message) {
        setError(submitError.message);
      } else {
        setError(fallbackMessage);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[100dvh] max-w-lg items-center justify-center px-4 py-12 sm:px-6">
      <SurfaceCard className="w-full p-7 sm:p-9">
        <Badge tone="brand">{t(language, "auth.brand")}</Badge>
        <h1 className="mt-4 text-2xl font-bold tracking-[-0.02em] text-[var(--text-primary)] sm:text-3xl">
          {isOtpStep ? t(language, "auth.otp.title") : t(language, "auth.login.title")}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[var(--text-secondary)]">
          {isOtpStep
            ? t(language, "auth.otp.description")
            : t(language, "auth.login.description")}
        </p>

        <form className="mt-7 space-y-4" onSubmit={onSubmit}>
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
                required
              />
              <Field
                id="login-password"
                label={t(language, "auth.login.password")}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={t(language, "auth.login.passwordPlaceholder")}
                required
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
              />
              <p className="text-xs text-[var(--text-muted)]">
                {t(language, "auth.otp.sentTo")} {" "}
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
            loading={isSubmitting}
            loadingLabel={isOtpStep ? t(language, "auth.otp.verifying") : t(language, "auth.login.submitting")}
          >
            {isOtpStep ? t(language, "auth.otp.verify") : t(language, "auth.login.submit")}
          </Button>

          {!isOtpStep ? (
            <div className="flex justify-between text-sm">
              <Link
                href="/register"
                className="focus-ring rounded text-[var(--text-brand)] hover:underline"
              >
                {t(language, "auth.login.createAccount")}
              </Link>
              <Link
                href="/forgot-password"
                className="focus-ring rounded text-[var(--text-secondary)] hover:underline"
              >
                {t(language, "auth.login.forgotPassword")}
              </Link>
            </div>
          ) : (
            <Button type="button" variant="secondary" block onClick={resetOtpStep}>
              {t(language, "auth.login.backToPassword")}
            </Button>
          )}

          <p className="text-xs leading-6 text-[var(--text-muted)]">
            {t(language, "auth.legal.acknowledgement")} {" "}
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
            và{" "}
            <Link
              href="/legal/consent"
              className="focus-ring rounded font-medium text-[var(--text-brand)] hover:underline"
            >
              {t(language, "auth.legal.medicalConsent")}
            </Link>
            .
          </p>
        </form>
      </SurfaceCard>
    </main>
  );
}
