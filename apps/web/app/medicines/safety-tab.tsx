"use client";

import { useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/field";
import { InlineError } from "@/components/ui/surface";
import SelfMedConsentGate from "@/components/selfmed/selfmed-consent-gate";
import {
  DdiUserView,
  MINIMUM_DDI_MEDICINES,
  requiresTwoMedicines,
  toCareguardUserMessage,
  toDdiUserView
} from "@/lib/careguard";
import {
  cacheDdiUserView,
  isCareguardOfflineFallbackEnabled,
  isLikelyOfflineError,
  readCachedDdiView
} from "@/lib/careguard-offline";
import { CabinetItem, getCabinet, runCabinetAutoDdi } from "@/lib/selfmed";
import { trackCareguardDdiChecked, trackCareguardViewed } from "@/lib/analytics/events";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";

function formatOfflineCachedAt(language: "vi" | "en", cachedAt: string): string | null {
  const parsed = new Date(cachedAt);
  if (Number.isNaN(parsed.getTime())) return null;
  try {
    return formatLocaleDate(language, parsed, { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return parsed.toISOString();
  }
}

function parseLineList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function riskLevel(value: string | null | undefined): "high" | "medium" | "low" | "unknown" {
  const normalized = (value ?? "").toLowerCase();
  if (/critical|severe|contra|major|high|red|danger/.test(normalized)) return "high";
  if (/moderate|medium|amber|intermediate/.test(normalized)) return "medium";
  if (/minor|low|green|safe|none/.test(normalized)) return "low";
  return "unknown";
}

function riskTone(value: string | null | undefined): BadgeTone {
  const level = riskLevel(value);
  if (level === "high") return "danger";
  if (level === "medium") return "warn";
  if (level === "low") return "ok";
  return "neutral";
}

function riskPanelClass(value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return "border-[color:var(--status-danger-border)] bg-[var(--status-danger-bg)]";
  if (level === "medium") return "border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)]";
  if (level === "low") return "border-[color:var(--status-ok-border)] bg-[var(--status-ok-bg)]";
  return "border-[color:var(--shell-border)] bg-[var(--surface-muted)]";
}

function riskLabel(language: "vi" | "en", value: string | null | undefined): string {
  const level = riskLevel(value);
  if (level === "high") return t(language, "medicines.safety.risk.high");
  if (level === "medium") return t(language, "medicines.safety.risk.medium");
  if (level === "low") return t(language, "medicines.safety.risk.low");
  return t(language, "medicines.safety.risk.unknown");
}

export default function MedicinesSafetyTab() {
  const language = useUILanguage();
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoadingCabinet, setIsLoadingCabinet] = useState(true);
  const [cabinetError, setCabinetError] = useState("");

  const [allergiesInput, setAllergiesInput] = useState("");
  const [result, setResult] = useState<DdiUserView | null>(null);
  const [error, setError] = useState("");
  const [isChecking, setIsChecking] = useState(false);
  // Offline / last-known fallback state (Req 6.3). When the result on screen was
  // served from the client cache because the API was unreachable, we flag it as
  // stale and show when it was captured.
  const [offlineCachedAt, setOfflineCachedAt] = useState<string | null>(null);

  // Distinct medicine names drive the two-medicine guard (Requirement 3.5).
  // A drug-drug interaction needs two *different* medicines, so the canonical
  // requiresTwoMedicines helper collapses case-insensitive duplicates.
  const medicineNames = useMemo(() => items.map((item) => item.drug_name), [items]);
  const needsMoreMedicines = useMemo(() => requiresTwoMedicines(medicineNames), [medicineNames]);

  const refreshCabinet = async () => {
    setCabinetError("");
    setIsLoadingCabinet(true);
    try {
      const response = await getCabinet();
      setItems(response.items ?? []);
    } catch (cause) {
      setCabinetError(toCareguardUserMessage(cause, t(language, "medicines.safety.loadError")));
    } finally {
      setIsLoadingCabinet(false);
    }
  };

  useEffect(() => {
    // Named SelfMed/CareGuard product event (Req 9.1); consent/PII guarded.
    trackCareguardViewed({ surface: "selfmed" });
    void refreshCabinet();
  }, []);

  const onRunDdi = async () => {
    setError("");
    setResult(null);
    setOfflineCachedAt(null);
    // Guard the analysis call: with fewer than two distinct medicines, prompt
    // the End_User to add at least two and do NOT call the DDI analysis
    // (Requirement 3.5).
    if (needsMoreMedicines) {
      setError(t(language, "medicines.safety.needsTwo", { count: MINIMUM_DDI_MEDICINES }));
      return;
    }
    setIsChecking(true);
    try {
      const next = await runCabinetAutoDdi({ allergies: parseLineList(allergiesInput) });
      // Render ONLY the End_User projection: risk level, alerts,
      // recommendations, and reference sources. Runtime mode, fallback flags,
      // and source_errors are dropped by toDdiUserView (Req 3.1, 3.6, 4.1).
      const view = toDdiUserView(next);
      setResult(view);
      // Cache the last-known *projection* for offline fallback (Req 6.3). No-op
      // when CAREGUARD_OFFLINE_FALLBACK_ENABLED is off.
      cacheDdiUserView(view);
      // Coarse, non-PII aggregate signals only — no drug names (Req 9.1, 9.4).
      trackCareguardDdiChecked({
        riskLevel: view.riskLevel,
        alertCount: view.alerts.length,
        medicineCount: items.length,
        source: "selfmed"
      });
    } catch (cause) {
      // Offline / degraded fallback (Req 6.3): when the flag is on and the API
      // is unreachable, show the last-known cached projection labeled stale.
      // We never fabricate an all-clear — only a genuine cached result is shown.
      if (isCareguardOfflineFallbackEnabled() && isLikelyOfflineError(cause)) {
        const cached = readCachedDdiView();
        if (cached) {
          setResult(cached.view);
          setOfflineCachedAt(cached.cachedAt);
          return;
        }
      }
      setError(
        toCareguardUserMessage(cause, t(language, "medicines.list.checkError"))
      );
    } finally {
      setIsChecking(false);
    }
  };

  return (
    <SelfMedConsentGate>
      <div className="space-y-5">
        <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--text-muted)]">{t(language, "medicines.safety.module")}</p>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.title")}</h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button as="link" href="/medicines?tab=cabinet" variant="secondary">
                {t(language, "medicines.safety.back")}
              </Button>
              <Button as="link" href="/medicines/cabinet/add">
                {t(language, "medicines.cabinet.add")}
              </Button>
            </div>
          </div>
        </section>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xl font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.inCabinet")}</h3>
              <span className="rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-1 text-xs text-[var(--text-secondary)]">
                {t(language, "medicines.safety.count", { count: formatLocaleNumber(language, items.length) })}
              </span>
            </div>

            {isLoadingCabinet ? <p className="mt-3 text-sm text-[var(--text-secondary)]">{t(language, "medicines.safety.loading")}</p> : null}
            {cabinetError ? <div className="mt-3"><InlineError message={cabinetError} onRetry={() => void refreshCabinet()} /></div> : null}

            {!isLoadingCabinet && !items.length ? (
              <div className="mt-3 rounded-2xl border border-dashed border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-5">
                <p className="text-sm text-[var(--text-secondary)]">{t(language, "medicines.safety.empty")}</p>
              </div>
            ) : null}

            {items.length ? (
              <ul className="mt-3 grid gap-2 md:grid-cols-2">
                {items.map((item) => (
                  <li
                    key={item.id}
                    className="rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-3 py-3"
                  >
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{item.drug_name}</p>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.dosage || t(language, "medicines.safety.noDose")}</p>
                  </li>
                ))}
              </ul>
            ) : null}
          </section>

          <section className="chrome-panel rounded-[1.35rem] p-5 sm:p-6">
            <h3 className="text-xl font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.setup")}</h3>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">{t(language, "medicines.safety.setupDescription")}</p>

            <Textarea
              label={t(language, "medicines.safety.allergies")}
              optional
              wrapperClassName="mt-3"
              value={allergiesInput}
              onChange={(event) => setAllergiesInput(event.target.value)}
              placeholder={t(language, "medicines.safety.allergyPlaceholder")}
              className="min-h-[140px]"
            />

            <Button
              className="mt-3"
              onClick={() => void onRunDdi()}
              disabled={isChecking || needsMoreMedicines}
              loading={isChecking}
              loadingLabel={t(language, "medicines.safety.checking")}
            >
              {t(language, "medicines.cabinet.checkInteractions")}
            </Button>

            {needsMoreMedicines ? <p className="mt-2 text-xs text-[var(--status-warn-text)]">{t(language, "medicines.safety.needsTwo", { count: MINIMUM_DDI_MEDICINES })}</p> : null}
            {error ? <div className="mt-2"><InlineError message={error} onRetry={() => void onRunDdi()} /></div> : null}
          </section>
        </div>

        {result ? (
          <section className={`chrome-panel rounded-[1.35rem] border p-5 sm:p-6 ${riskPanelClass(result.riskLevel)}`}>
            {offlineCachedAt ? (
              <div className="mb-3 flex flex-wrap items-center gap-2 rounded-2xl border border-[color:var(--status-warn-border)] bg-[var(--status-warn-bg)] px-3 py-2">
                <Badge tone="warn">{t(language, "medicines.safety.offline")}</Badge>
                <span className="text-xs text-[var(--status-warn-text)]">
                  {(() => {
                    const at = formatOfflineCachedAt(language, offlineCachedAt);
                    return at
                      ? t(language, "medicines.safety.cachedResult", { date: at })
                      : t(language, "medicines.safety.cachedResultNoDate");
                  })()}
                </span>
              </div>
            ) : null}
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.overview")}</p>
              <Badge tone={riskTone(result.riskLevel)}>
                {t(language, "medicines.safety.risk", { risk: riskLabel(language, result.riskLevel) })}
              </Badge>
            </div>

            {result.alerts.length ? (
              <ul className="mt-3 space-y-2">
                {result.alerts.map((alert, index) => (
                  <li key={`${alert.message}-${index}`} className={`rounded-2xl border p-3 ${riskPanelClass(alert.severity)}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--text-primary)]">{alert.message}</p>
                      <Badge tone={riskTone(alert.severity)}>
                        {riskLabel(language, alert.severity)}
                      </Badge>
                    </div>
                    {alert.details ? <p className="mt-1 text-xs text-[var(--text-secondary)]">{alert.details}</p> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm text-[var(--text-secondary)]">{t(language, "medicines.safety.noAlerts")}</p>
            )}

            {result.recommendations.length ? (
              <article className="mt-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
                <p className="text-sm font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.recommendations")}</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--text-secondary)]">
                  {result.recommendations.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              </article>
            ) : null}

            <article className="mt-3 rounded-2xl border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
              <p className="text-sm font-semibold text-[var(--text-primary)]">{t(language, "medicines.safety.sources")}</p>
              {result.sources.length ? (
                <ul className="mt-1 flex flex-wrap gap-2">
                  {result.sources.map((source, index) => (
                    <li key={`${source.label}-${index}`}>
                      {source.url ? (
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-brand)] underline"
                        >
                          {source.label}
                        </a>
                      ) : (
                        <span className="inline-flex items-center rounded-full border border-[color:var(--shell-border)] bg-[var(--surface-panel)] px-3 py-1 text-xs font-semibold text-[var(--text-secondary)]">
                          {source.label}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{t(language, "medicines.safety.noSources")}</p>
              )}
            </article>
          </section>
        ) : null}
      </div>
    </SelfMedConsentGate>
  );
}
