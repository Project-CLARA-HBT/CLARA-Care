"use client";

import Icon from "@/components/ui/icon";
import { t } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

export interface AuthRateLimitBannerProps {
  cooldownSeconds: number;
  failedAttempts: number;
  isLockout: boolean;
  context: "login" | "otp";
  language: UILanguage;
}

export default function AuthRateLimitBanner({
  cooldownSeconds,
  failedAttempts,
  isLockout,
  context,
  language,
}: AuthRateLimitBannerProps) {
  if (cooldownSeconds > 0) {
    const isDanger = isLockout || cooldownSeconds > 10;
    const toneClass = isDanger
      ? "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger-text)]"
      : "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn-text)]";

    const message = isLockout
      ? t(language, "auth.rateLimit.lockedOut", { seconds: cooldownSeconds })
      : t(language, "auth.rateLimit.cooldown", { seconds: cooldownSeconds });

    return (
      <div
        role="alert"
        aria-live="assertive"
        className={`flex items-start gap-3 rounded-[var(--radius-lg)] border px-4 py-3 text-sm leading-6 ${toneClass}`}
        data-testid="auth-rate-limit-banner"
      >
        <Icon name="warning" size={18} className="mt-1 shrink-0" aria-hidden="true" />
        <div className="flex-1 font-medium">{message}</div>
      </div>
    );
  }

  if (context === "otp" && failedAttempts > 0) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex items-start gap-3 rounded-[var(--radius-lg)] border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-4 py-3 text-sm leading-6 text-[var(--status-warn-text)]"
        data-testid="auth-otp-attempt-warning"
      >
        <Icon name="warning" size={18} className="mt-1 shrink-0" aria-hidden="true" />
        <div className="flex-1 font-medium">
          {t(language, "auth.rateLimit.otpAttemptsWarning", { attempts: failedAttempts })}
        </div>
      </div>
    );
  }

  return null;
}
