"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { acceptConsent, getConsentStatus } from "@/lib/consent";
import { formatLocaleDate, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";
import Icon from "@/components/ui/icon";

type MedicalConsentGateProps = {
  children: ReactNode;
};

/**
 * Shared medical-consent boundary for every Medicines task.
 *
 * It deliberately owns no route-specific state: the cabinet, scan and
 * interaction views all call the same consent API and get the same safe
 * failure behaviour.
 */
export default function MedicalConsentGate({ children }: MedicalConsentGateProps) {
  const language = useUILanguage();
  const [isLoading, setIsLoading] = useState(true);
  const [accepted, setAccepted] = useState(false);
  const [requiredVersion, setRequiredVersion] = useState("");
  const [acceptedAt, setAcceptedAt] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const acceptedAtDisplay = acceptedAt
    ? formatLocaleDate(language, acceptedAt, { dateStyle: "medium", timeStyle: "short" })
    : null;

  const refreshConsent = async (): Promise<boolean> => {
    setError("");
    try {
      const status = await getConsentStatus();
      setRequiredVersion(status.required_version);
      setAccepted(status.accepted);
      setAcceptedAt(status.accepted_at ?? null);
      return status.accepted;
    } catch (cause) {
      setAccepted(false);
      setError(safeUserFacingError(cause, t(language, "medicines.consent.checkError")));
      return false;
    }
  };

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await refreshConsent();
      setIsLoading(false);
    };
    void init();
  }, []);

  const onAccept = async () => {
    if (!requiredVersion) return;
    if (!checked) {
      setError(t(language, "medicines.consent.acknowledgementRequired"));
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await acceptConsent({ consent_version: requiredVersion, accepted: true });
      const unlocked = await refreshConsent();
      if (!unlocked) {
        setError(t(language, "medicines.consent.saveIncomplete"));
      }
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.consent.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  const onRetryStatus = async () => {
    setIsLoading(true);
    await refreshConsent();
    setIsLoading(false);
  };

  if (isLoading) {
    return (
      <section className="chrome-panel rounded-[1.5rem] p-6">
        <p className="text-base font-semibold text-[var(--text-primary)]">{t(language, "medicines.consent.loading")}</p>
      </section>
    );
  }

  if (!accepted) {
    return (
      <section className="chrome-panel rounded-[14px] border border-[color:var(--status-warn-border)] border-t-[#2A3950] p-6">
        <p className="inline-flex rounded-full border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--status-warn-text)]">
          {t(language, "medicines.consent.requiredStep")}
        </p>
        <h2 className="mt-3 text-2xl font-semibold text-[var(--text-primary)]">{t(language, "medicines.consent.title")}</h2>
        <p className="mt-3 max-w-4xl text-base leading-7 text-[var(--text-secondary)]">
          {t(language, "medicines.consent.description")}
        </p>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {t(language, "medicines.consent.readFull")} {" "}
          <Link href="/legal/consent" className="font-semibold text-[var(--text-brand)] hover:underline">
            {t(language, "medicines.consent.consentLink")}
          </Link>
          {" "}{t(language, "medicines.consent.and")} {" "}
          <Link href="/legal/privacy" className="font-semibold text-[var(--text-brand)] hover:underline">
            {t(language, "medicines.consent.privacyLink")}
          </Link>
          .
        </p>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          {t(language, "medicines.consent.version")}: <span className="font-semibold">{requiredVersion || "-"}</span>
        </p>

        <label className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
          <input
            type="checkbox"
            checked={checked}
            onChange={(event) => setChecked(event.target.checked)}
            className="mt-1 h-6 w-6 rounded border-[color:var(--shell-border)]"
          />
          <span className="text-sm font-medium leading-6 text-[var(--text-primary)]">
            {t(language, "medicines.consent.acknowledgement")}
          </span>
        </label>

        <button
          type="button"
          onClick={onAccept}
          disabled={isSaving || !checked}
          className="mt-4 min-h-12 rounded-lg bg-[#60a5fa] px-5 py-2 text-sm font-bold text-[#003a6b] transition hover:bg-[#a4c9ff] disabled:cursor-not-allowed disabled:bg-[var(--surface-muted)] disabled:text-[var(--text-muted)]"
        >
          {isSaving ? t(language, "medicines.consent.saving") : t(language, "medicines.consent.accept")}
        </button>

        {error ? (
          <div className="mt-3 space-y-2 rounded-xl border border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)] p-3">
            <p className="text-sm text-[var(--status-danger-text)]">{error}</p>
            <p className="text-xs text-[var(--status-danger-text)]">{t(language, "medicines.consent.retryNotice")}</p>
            <button
              type="button"
              onClick={() => void onRetryStatus()}
              className="inline-flex min-h-11 items-center rounded-lg border border-[color:var(--status-danger-border)] bg-[#93000a]/30 px-4 py-2 text-sm font-semibold text-[var(--status-danger-text)] transition hover:bg-[#93000a]/45"
            >
              {t(language, "medicines.consent.retry")}
            </button>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <section className="chrome-panel rounded-2xl border border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)] p-4">
        <div className="flex flex-wrap items-center gap-3">
          <Icon name="check" className="text-[var(--status-ok-text)]" aria-hidden="true" />
          <div>
            <p className="text-sm font-semibold text-[var(--status-ok-text)]">
              {t(language, "medicines.consent.acceptedTitle")}
            </p>
            <p className="text-xs text-[var(--status-ok-text)]">
              {acceptedAtDisplay
                ? t(language, "medicines.consent.acceptedAt", { date: acceptedAtDisplay })
                : t(language, "medicines.consent.acceptedReady")}
            </p>
          </div>
        </div>
      </section>
      {children}
    </div>
  );
}
