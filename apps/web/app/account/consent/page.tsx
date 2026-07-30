"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import PageShell from "@/components/ui/page-shell";
import { Badge } from "@/components/ui/badge";
import { SurfaceCard, InlineError } from "@/components/ui/surface";
import {
  grantConsent,
  isGranularConsentEnabled,
  listConsents,
  withdrawConsent,
  type ConsentPurpose,
  type ConsentRecord,
} from "@/lib/compliance";
import {
  getStoredUILanguage,
  onUILanguageChange,
  type UILanguage,
} from "@/lib/ui-language";
import {
  formatLocaleDate,
  t,
  type UITranslationKey,
} from "@/lib/i18n/catalog";

/**
 * Consent Center (regulatory-compliance Requirement 2.6, Property P10; PHR
 * Requirement 19.5).
 *
 * Self-service per-purpose consent toggles backed by the append-only consent
 * ledger. Withdrawal is exactly as easy as granting (a single toggle). All
 * mutations go through the shared `http-client`, which attaches the CSRF header
 * for cookie-authenticated requests.
 *
 * PHR sharing and personalization consents are surfaced HERE through the unified
 * purpose ledger rather than as a PHR-only toggle (PHR Req 19.5).
 *
 * The surface activates only when `NEXT_PUBLIC_COMPLIANCE_GRANULAR_CONSENT_ENABLED`
 * is on; otherwise it shows a "feature unavailable" notice and current behavior
 * is preserved (Requirement 8.1, 8.2).
 */

type PurposeCopy = {
  label: UITranslationKey;
  description: UITranslationKey;
  /** Core service consent is the lawful basis for the product and is locked on. */
  locked?: boolean;
};

const PURPOSE_ORDER: ConsentPurpose[] = [
  "core_service",
  "personalization",
  "research",
  "cross_border_processing",
  "sharing",
];

const PURPOSE_COPY: Record<ConsentPurpose, PurposeCopy> = {
  core_service: {
    label: "consent.purpose.coreService.label",
    description: "consent.purpose.coreService.description",
    locked: true,
  },
  personalization: {
    label: "consent.purpose.personalization.label",
    description: "consent.purpose.personalization.description",
  },
  research: {
    label: "consent.purpose.research.label",
    description: "consent.purpose.research.description",
  },
  cross_border_processing: {
    label: "consent.purpose.crossBorder.label",
    description: "consent.purpose.crossBorder.description",
  },
  sharing: {
    label: "consent.purpose.sharing.label",
    description: "consent.purpose.sharing.description",
  },
  ai_transparency: {
    label: "consent.purpose.aiTransparency.label",
    description: "consent.purpose.aiTransparency.description",
  },
};

export default function ConsentCenterPage() {
  const [uiLanguage, setUiLanguage] = useState<UILanguage>("vi");
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState<ConsentPurpose | null>(null);
  const [consentMap, setConsentMap] = useState<Record<string, ConsentRecord>>({});

  const text = useMemo(
    () => ({
      title: t(uiLanguage, "consent.title"),
      description: t(uiLanguage, "consent.description"),
      loading: t(uiLanguage, "consent.loading"),
      loadError: t(uiLanguage, "consent.loadError"),
      disabled: t(uiLanguage, "consent.disabled"),
      granted: t(uiLanguage, "consent.granted"),
      notGranted: t(uiLanguage, "consent.notGranted"),
      locked: t(uiLanguage, "consent.locked"),
      saving: t(uiLanguage, "consent.saving"),
      sensitiveNote: t(uiLanguage, "consent.sensitiveNote"),
      updatedAt: t(uiLanguage, "consent.updatedAt"),
    }),
    [uiLanguage],
  );
  const flagOn = isGranularConsentEnabled();

  useEffect(() => {
    setUiLanguage(getStoredUILanguage());
    return onUILanguageChange(setUiLanguage);
  }, []);

  const refresh = useCallback(async () => {
    if (!flagOn) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const data = await listConsents();
      setEnabled(Boolean(data.enabled));
      const map: Record<string, ConsentRecord> = {};
      for (const record of data.consents ?? []) {
        map[record.purpose] = record;
      }
      setConsentMap(map);
    } catch {
      setError(text.loadError);
    } finally {
      setLoading(false);
    }
  }, [flagOn, text.loadError]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onToggle = useCallback(
    async (purpose: ConsentPurpose, nextGranted: boolean) => {
      setPending(purpose);
      setError("");
      // Optimistic update; reconciled by the refresh below.
      setConsentMap((prev) => ({
        ...prev,
        [purpose]: { ...prev[purpose], purpose, granted: nextGranted },
      }));
      try {
        if (nextGranted) {
          await grantConsent(purpose);
        } else {
          await withdrawConsent(purpose);
        }
        await refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : text.loadError);
        await refresh();
      } finally {
        setPending(null);
      }
    },
    [refresh, text.loadError],
  );

  const showDisabled = !flagOn || (!loading && !enabled);

  return (
    <PageShell variant="plain" title={text.title} description={text.description}>
      <div className="space-y-4">
        <p className="rounded-xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-4 py-3 text-[13px] leading-6 text-[var(--text-secondary)]">
          {text.sensitiveNote}
        </p>

        {showDisabled ? (
          <p
            role="status"
            className="rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-4 py-3 text-sm text-[var(--text-secondary)]"
          >
            {text.disabled}
          </p>
        ) : loading ? (
          <p className="text-sm text-[var(--text-secondary)]">{text.loading}</p>
        ) : (
          <>
            {error ? <InlineError message={error} /> : null}

            <ul className="space-y-3">
              {PURPOSE_ORDER.map((purpose) => {
                const copy = PURPOSE_COPY[purpose];
                const record = consentMap[purpose];
                const granted = copy.locked ? true : Boolean(record?.granted);
                const isPending = pending === purpose;
                return (
                  <SurfaceCard key={purpose} className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-[var(--text-primary)]">
                          {t(uiLanguage, copy.label)}
                        </p>
                        <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
                          {t(uiLanguage, copy.description)}
                        </p>
                        {record?.updated_at ? (
                          <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                            {text.updatedAt}:{" "}
                            {formatLocaleDate(uiLanguage, record.updated_at, {
                              dateStyle: "medium",
                              timeStyle: "short",
                            })}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-1.5">
                        <Badge tone={granted ? "ok" : "neutral"}>
                          {copy.locked
                            ? text.locked
                            : granted
                              ? text.granted
                              : text.notGranted}
                        </Badge>
                        {copy.locked ? null : (
                          <button
                            type="button"
                            role="switch"
                            aria-checked={granted}
                            aria-label={t(uiLanguage, copy.label)}
                            disabled={isPending}
                            onClick={() => void onToggle(purpose, !granted)}
                            className={[
                              "inline-flex h-6 w-11 items-center rounded-full border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--shell-border-strong)] disabled:cursor-not-allowed disabled:opacity-60",
                              granted
                                ? "border-[color:var(--brand-600)] bg-[var(--brand-600)]"
                                : "border-[color:var(--shell-border)] bg-[var(--surface-muted)]",
                            ].join(" ")}
                          >
                            <span
                              aria-hidden="true"
                              className={[
                                "ml-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform motion-reduce:transition-none",
                                granted ? "translate-x-5" : "translate-x-0",
                              ].join(" ")}
                            />
                          </button>
                        )}
                        {isPending ? (
                          <span className="text-[10px] text-[var(--text-muted)]">
                            {text.saving}
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </SurfaceCard>
                );
              })}
            </ul>
          </>
        )}
      </div>
    </PageShell>
  );
}
