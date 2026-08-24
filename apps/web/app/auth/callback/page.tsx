"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import api from "@/lib/http-client";
import { markAuthenticatedBrowserSession, setRole as setStoredRole } from "@/lib/auth-store";
import Button from "@/components/ui/button";
import AuthFormShell from "@/components/auth-form-shell";
import { resolvePostLoginPath, type UserRole } from "@/lib/navigation.config";
import { t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

function AuthCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const language = useUILanguage();

  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    let active = true;

    const processAuth = async () => {
      const errorParam = searchParams.get("error") || searchParams.get("error_description");
      if (errorParam) {
        if (active) {
          setStatus("error");
          setErrorMessage(errorParam);
        }
        return;
      }

      const tokenParam = searchParams.get("token") || searchParams.get("access_token");
      const codeParam = searchParams.get("code");
      const roleParam = (searchParams.get("role") as UserRole) || undefined;
      const nextParam = searchParams.get("next");

      // 1. Direct token provided in query/hash
      if (tokenParam) {
        markAuthenticatedBrowserSession();
        if (roleParam) {
          setStoredRole(roleParam);
        }
        const targetPath = resolvePostLoginPath({
          nextPath: nextParam,
          role: roleParam,
        });

        if (active) {
          setStatus("success");
        }

        setTimeout(() => {
          router.replace(targetPath);
          router.refresh();
        }, 400);
        return;
      }

      // 2. Authorization code exchange
      if (codeParam) {
        try {
          const response = await api.post("/auth/callback", { code: codeParam });
          const nextRole = (response.data?.role as UserRole) ?? roleParam ?? "normal";

          markAuthenticatedBrowserSession();
          setStoredRole(nextRole);
          const targetPath = resolvePostLoginPath({
            nextPath: nextParam,
            role: nextRole,
          });

          if (active) {
            setStatus("success");
          }

          setTimeout(() => {
            router.replace(targetPath);
            router.refresh();
          }, 400);
          return;
        } catch (exchangeError) {
          if (active) {
            setStatus("error");
            setErrorMessage(
              exchangeError instanceof Error && exchangeError.message
                ? exchangeError.message
                : t(language, "auth.callback.error"),
            );
          }
          return;
        }
      }

      // 3. Fallback: No credentials present
      if (active) {
        setStatus("error");
        setErrorMessage(t(language, "auth.callback.error"));
      }
    };

    void processAuth();

    return () => {
      active = false;
    };
  }, [language, router, searchParams]);

  return (
    <AuthFormShell
      title={
        status === "error"
          ? t(language, "auth.callback.error")
          : status === "success"
            ? t(language, "auth.callback.success")
            : t(language, "auth.callback.title")
      }
      subtitle={
        status === "error"
          ? errorMessage
          : t(language, "auth.callback.description")
      }
      backHref="/login"
      backLabel={t(language, "auth.callback.backToLogin")}
      maxWidth="md"
    >
      <div className="flex flex-col items-center justify-center space-y-6 py-4 text-center">
        {status === "verifying" && (
          <div className="flex flex-col items-center space-y-4">
            <div
              className="h-10 w-10 animate-spin rounded-full border-4 border-[color:var(--shell-border)] border-t-[color:var(--brand-500)]"
              role="progressbar"
              aria-label={t(language, "auth.callback.verifying")}
            />
            <p className="text-sm font-medium text-[var(--text-secondary)]">
              {t(language, "auth.callback.verifying")}
            </p>
          </div>
        )}

        {status === "success" && (
          <div className="flex flex-col items-center space-y-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--status-ok-bg)] text-[var(--status-ok-text)]">
              <span className="text-xl font-bold" aria-hidden="true">✓</span>
            </div>
            <p className="text-sm font-semibold text-[var(--status-ok-text)]">
              {t(language, "auth.callback.success")}
            </p>
          </div>
        )}

        {status === "error" && (
          <div className="w-full space-y-4">
            <p
              role="alert"
              className="rounded-[var(--radius-lg)] border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-danger-text)]"
            >
              {errorMessage || t(language, "auth.callback.error")}
            </p>

            <Button
              block
              onClick={() => router.push("/login")}
            >
              {t(language, "auth.callback.backToLogin")}
            </Button>

            <Link
              href="/"
              className="focus-ring inline-block text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:underline"
            >
              {t(language, "auth.backToHome")}
            </Link>
          </div>
        )}
      </div>
    </AuthFormShell>
  );
}

export default function AuthCallbackPage() {
  const language = useUILanguage();

  return (
    <Suspense
      fallback={
        <AuthFormShell
          title={t(language, "auth.callback.title")}
          subtitle={t(language, "auth.callback.description")}
          maxWidth="md"
        >
          <div className="flex flex-col items-center justify-center space-y-4 py-8 text-center">
            <div
              className="h-10 w-10 animate-spin rounded-full border-4 border-[color:var(--shell-border)] border-t-[color:var(--brand-500)]"
              role="progressbar"
              aria-label={t(language, "auth.callback.verifying")}
            />
            <p className="text-sm font-medium text-[var(--text-secondary)]">
              {t(language, "auth.callback.verifying")}
            </p>
          </div>
        </AuthFormShell>
      }
    >
      <AuthCallbackContent />
    </Suspense>
  );
}
