"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Button from "@/components/ui/button";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { SurfaceCard, EmptyState, InlineError } from "@/components/ui/surface";
import Icon from "@/components/ui/icon";
import MedicalConsentGate from "@/components/medicines/medical-consent-gate";
import { CabinetItem, deleteCabinetItem, getCabinet } from "@/lib/selfmed";
import { trackCareguardViewed } from "@/lib/analytics/events";
import { formatLocaleDate, formatLocaleNumber, t } from "@/lib/i18n/catalog";
import { useUILanguage } from "@/lib/use-ui-language";
import { safeUserFacingError } from "@/lib/user-facing-text";

type TimelineEntry = {
  id: number;
  time: string;
  title: string;
  note: string;
};

function sourceLabel(language: "vi" | "en", source: string): string {
  if (source === "ocr") return t(language, "medicines.cabinet.source.ocr");
  if (source === "manual") return t(language, "medicines.cabinet.source.manual");
  if (source === "barcode") return t(language, "medicines.cabinet.source.barcode");
  if (source === "imported") return t(language, "medicines.cabinet.source.imported");
  return source;
}

function sourceTone(source: string): BadgeTone {
  if (source === "ocr") return "brand";
  if (source === "manual") return "neutral";
  if (source === "barcode") return "brand";
  if (source === "imported") return "brand";
  return "neutral";
}

function normalizationLabel(language: "vi" | "en", source: string | null | undefined): string {
  if (source === "db" || source === "matched") return t(language, "medicines.cabinet.normalization.matched");
  if (source === "candidate") return t(language, "medicines.cabinet.normalization.candidate");
  if (source === "needs_review") return t(language, "medicines.cabinet.normalization.review");
  if (source === "fallback") return t(language, "medicines.cabinet.normalization.manual");
  return t(language, "medicines.cabinet.normalization.unknown");
}

function normalizationTone(source: string | null | undefined): BadgeTone {
  if (source === "db" || source === "matched") return "ok";
  if (source === "candidate") return "warn";
  if (source === "needs_review") return "danger";
  if (source === "fallback") return "danger";
  return "neutral";
}

function formatDate(language: "vi" | "en", value: string | null): string {
  if (!value) return t(language, "medicines.cabinet.notAvailable");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t(language, "medicines.cabinet.notAvailable");
  return formatLocaleDate(language, date);
}

function normalizeText(value: string | null | undefined): string {
  return String(value ?? "").trim().toLowerCase();
}

function includesAny(text: string, tokens: string[]): boolean {
  return tokens.some((token) => text.includes(token));
}

function timelineLabelForItem(language: "vi" | "en", item: CabinetItem): string {
  const dosageText = normalizeText(item.dosage);
  const noteText = normalizeText(item.note);
  const fullText = `${dosageText} ${noteText}`;

  if (includesAny(fullText, ["sáng", "morning", "breakfast"])) return t(language, "medicines.cabinet.morning");
  if (includesAny(fullText, ["trưa", "noon", "lunch"])) return t(language, "medicines.cabinet.noon");
  if (includesAny(fullText, ["chiều", "afternoon"])) return t(language, "medicines.cabinet.afternoon");
  if (includesAny(fullText, ["tối", "đêm", "night", "evening", "bedtime"])) return t(language, "medicines.cabinet.evening");
  return t(language, "medicines.cabinet.following");
}

export default function MedicinesCabinetTab() {
  const language = useUILanguage();
  const [cabinetLabel, setCabinetLabel] = useState("");
  const [items, setItems] = useState<CabinetItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const stats = useMemo(() => {
    const fromOcr = items.filter((item) => item.source === "ocr").length;
    const manual = items.filter((item) => item.source === "manual").length;

    const now = Date.now();
    const in30Days = now + 30 * 24 * 60 * 60 * 1000;

    let expiringSoon = 0;
    let expired = 0;
    let missingDosage = 0;

    items.forEach((item) => {
      if (!String(item.dosage ?? "").trim()) {
        missingDosage += 1;
      }
      if (!item.expires_on) return;
      const expiresAt = Date.parse(item.expires_on);
      if (!Number.isFinite(expiresAt)) return;
      if (expiresAt < now) {
        expired += 1;
      } else if (expiresAt <= in30Days) {
        expiringSoon += 1;
      }
    });

    return {
      total: items.length,
      fromOcr,
      manual,
      expiringSoon,
      expired,
      missingDosage,
    };
  }, [items]);

  const canCheckInteractions = stats.total >= 2;

  const topItems = useMemo(
    () =>
      [...items]
        .sort((a, b) => Date.parse(b.updated_at || b.created_at) - Date.parse(a.updated_at || a.created_at))
        .slice(0, 6),
    [items]
  );

  const timelineItems = useMemo(
    (): TimelineEntry[] =>
      topItems.slice(0, 3).map((item, idx) => ({
        id: item.id,
        time: idx === 0 ? t(language, "medicines.cabinet.next") : timelineLabelForItem(language, item),
        title: item.drug_name,
        note: item.dosage || t(language, "medicines.cabinet.addDose"),
      })),
    [language, topItems]
  );

  const refreshCabinet = useCallback(async () => {
    setError("");
    setIsLoading(true);
    try {
      const response = await getCabinet();
      // Keep an absent API label empty so the render-time fallback responds to
      // a locale change without requiring another network request.
      setCabinetLabel(response.label || "");
      setItems(response.items ?? []);
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.cabinet.loadError")));
    } finally {
      setIsLoading(false);
    }
  }, [language]);

  useEffect(() => {
    // Emit a named SelfMed/CareGuard product event (Req 9.1). The facade
    // suppresses transmission without consent/credentials and strips PII; only
    // the coarse surface label is sent.
    trackCareguardViewed({ surface: "selfmed" });
    void refreshCabinet();
  }, [refreshCabinet]);

  const onDelete = async (itemId: number) => {
    setNotice("");
    setError("");
    try {
      await deleteCabinetItem(itemId);
      setNotice(t(language, "medicines.cabinet.deleted"));
      await refreshCabinet();
    } catch (cause) {
      setError(safeUserFacingError(cause, t(language, "medicines.cabinet.deleteError")));
    }
  };

  return (
    <MedicalConsentGate>
      <div className="space-y-6">
        <SurfaceCard className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-2xl font-extrabold tracking-tight text-[var(--text-primary)]">{cabinetLabel || t(language, "medicines.cabinet.defaultLabel")}</h2>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">
                {t(language, "medicines.cabinet.description")}
              </p>
            </div>
            <div className="flex flex-col items-start gap-2">
              <div className="flex flex-wrap gap-2">
                <Button as="link" href="/medicines/cabinet/add" icon="add">
                  {t(language, "medicines.cabinet.add")}
                </Button>
                {canCheckInteractions ? (
                  <Button as="link" href="/medicines?tab=safety" variant="secondary">
                    {t(language, "medicines.cabinet.checkInteractions")}
                  </Button>
                ) : (
                  <Button
                    variant="secondary"
                    disabled
                    title={t(language, "medicines.cabinet.needsTwo")}
                  >
                    {t(language, "medicines.cabinet.checkInteractions")}
                  </Button>
                )}
                <Button variant="ghost" icon="refresh" onClick={() => void refreshCabinet()}>
                  {t(language, "medicines.cabinet.refresh")}
                </Button>
              </div>
              {!canCheckInteractions ? (
                <p className="text-xs text-[var(--text-muted)]">{t(language, "medicines.cabinet.needsTwo")}</p>
              ) : null}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-4 text-xs uppercase tracking-wider text-[var(--text-muted)]">
            <span className="inline-flex items-center gap-1"><Icon name="warning" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.verifiedSource")}</span>
            <span className="inline-flex items-center gap-1"><Icon name="folder" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.accountData")}</span>
            <span className="inline-flex items-center gap-1"><Icon name="progress" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.updateAnytime")}</span>
          </div>
        </SurfaceCard>

        <section className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-8 space-y-6">
            <SurfaceCard className="p-6">
              <div className="mb-6 flex items-center justify-between">
                <h3 className="text-sm uppercase tracking-widest text-[var(--text-secondary)]">{t(language, "medicines.cabinet.readiness")}</h3>
                <Badge tone={stats.total === 0 || stats.missingDosage > 0 ? "warn" : "ok"}>
                  {stats.total === 0 ? t(language, "medicines.cabinet.noMedicines") : stats.missingDosage > 0 ? t(language, "medicines.cabinet.needsMore") : t(language, "medicines.cabinet.ready")}
                </Badge>
              </div>

              <p className="mb-5 text-xs leading-5 text-[var(--text-secondary)]">
                {t(language, "medicines.cabinet.readinessDescription")}
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{t(language, "medicines.cabinet.interactionData")}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {(stats.total ?? 0) < 2 ? t(language, "medicines.cabinet.atLeastTwo") : t(language, "medicines.cabinet.medicinesInCabinet", { count: formatLocaleNumber(language, stats.total) })}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{t(language, "medicines.cabinet.completeness")}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stats.missingDosage > 0 ? t(language, "medicines.cabinet.missingDose", { count: formatLocaleNumber(language, stats.missingDosage) }) : t(language, "medicines.cabinet.basicDataReady")}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{t(language, "medicines.cabinet.expiry")}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {stats.expired > 0 ? t(language, "medicines.cabinet.expiredCount", { count: formatLocaleNumber(language, stats.expired) }) : stats.expiringSoon > 0 ? t(language, "medicines.cabinet.expiringCount", { count: formatLocaleNumber(language, stats.expiringSoon) }) : t(language, "medicines.cabinet.noneExpired")}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3">
                    <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{t(language, "medicines.cabinet.entrySources")}</p>
                    <p className="text-sm font-medium text-[var(--text-primary)]">
                      {t(language, "medicines.cabinet.sourceCounts", { ocr: formatLocaleNumber(language, stats.fromOcr), manual: formatLocaleNumber(language, stats.manual) })}
                    </p>
                  </div>
              </div>
            </SurfaceCard>

            <article className="space-y-4">
              <div className="flex items-center justify-between px-1">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">{t(language, "medicines.cabinet.currentList")}</h3>
                <span className="text-xs text-[var(--text-muted)]">{t(language, "medicines.cabinet.currentCount", { count: formatLocaleNumber(language, stats.total) })}</span>
              </div>

              {isLoading ? <p className="text-sm text-[var(--text-secondary)]">{t(language, "medicines.cabinet.loading")}</p> : null}
              {error ? <InlineError message={error} onRetry={() => void refreshCabinet()} /> : null}
              {notice ? <p className="text-sm font-medium text-[var(--status-ok-text)]">{notice}</p> : null}

              {!isLoading && topItems.length === 0 ? (
                <EmptyState
                  icon="medication"
                  title={t(language, "medicines.cabinet.emptyTitle")}
                  description={t(language, "medicines.cabinet.emptyDescription")}
                />
              ) : null}

              {topItems.map((item) => (
                <SurfaceCard key={item.id} className="group overflow-hidden" interactive>
                  <div className="flex flex-col gap-4 p-5 md:flex-row md:items-center md:gap-6">
                    <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-[var(--surface-brand-soft)]">
                      <Icon name="medication" size={30} className="text-[var(--text-brand)]" aria-hidden="true" />
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <h4 className="truncate text-lg font-bold text-[var(--text-primary)]">{item.drug_name}</h4>
                        <Badge tone={sourceTone(item.source)}>{sourceLabel(language, item.source)}</Badge>
                        {(item.normalization_status ?? item.normalization_source) ? (
                          <Badge tone={normalizationTone(item.normalization_status ?? item.normalization_source)}>
                            {normalizationLabel(language, item.normalization_status ?? item.normalization_source)}
                          </Badge>
                        ) : null}
                      </div>

                      <p className="text-sm text-[var(--text-secondary)]">
                        {t(language, "medicines.cabinet.doseValue", { dose: item.dosage || t(language, "medicines.cabinet.notAvailable"), quantity: formatLocaleNumber(language, item.quantity) })}
                      </p>
                      <p className="mt-1 text-xs text-[var(--text-muted)]">
                        {t(language, "medicines.cabinet.brandValue", { brand: item.brand_name || t(language, "medicines.cabinet.notAvailable"), manufacturer: item.manufacturer || t(language, "medicines.cabinet.notAvailable") })}
                      </p>

                      <div className="mt-2 flex flex-wrap items-center gap-3 text-[10px] text-[var(--text-muted)]">
                        <span className="inline-flex items-center gap-1">
                          <Icon name="calendar" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.expiryValue", { date: formatDate(language, item.expires_on) })}
                        </span>
                        {item.ocr_confidence !== null ? (
                          <span className="inline-flex items-center gap-1 font-semibold text-[var(--status-ok-text)]">
                            <Icon name="check" size={14} aria-hidden="true" /> OCR {Math.round(item.ocr_confidence * 100)}%
                          </span>
                        ) : null}
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--text-muted)]">{t(language, "medicines.cabinet.quantity")}</p>
                      <p className="text-xl font-extrabold text-[var(--text-primary)]">{formatLocaleNumber(language, item.quantity)}</p>
                      <Button
                        variant="danger"
                        size="sm"
                        className="mt-3"
                        onClick={() => void onDelete(item.id)}
                      >
                        {t(language, "medicines.cabinet.delete")}
                      </Button>
                    </div>
                  </div>

                  <div className="border-t border-[color:var(--shell-border)] bg-[var(--surface-muted)] px-5 py-3">
                    <div className="flex flex-wrap items-center gap-4 text-[10px] text-[var(--text-muted)]">
                      <span className="inline-flex items-center gap-1"><Icon name="warning" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.saved")}</span>
                      <span className="inline-flex items-center gap-1"><Icon name="progress" size={14} aria-hidden="true" /> {t(language, "medicines.cabinet.updated", { date: formatDate(language, item.updated_at) })}</span>
                    </div>
                  </div>
                </SurfaceCard>
              ))}
            </article>
          </div>

          <div className="col-span-12 lg:col-span-4 space-y-6">
            <SurfaceCard className="p-6">
              <h3 className="mb-6 text-sm uppercase tracking-widest text-[var(--text-secondary)]">{t(language, "medicines.cabinet.timeline")}</h3>
              {timelineItems.length > 0 ? (
                <div className="relative space-y-6 before:absolute before:left-[11px] before:top-2 before:bottom-2 before:w-[1px] before:bg-[color:var(--shell-border)]">
                  {timelineItems.map((entry, idx) => (
                    <div className="relative pl-8" key={entry.id}>
                      <div
                        className={[
                          "absolute top-1 z-10 rounded-full border-2 border-[var(--bg-canvas)]",
                          idx === 0 ? "left-0 w-6 h-6 bg-[var(--brand-500)]" : "left-[5px] w-[14px] h-[14px] bg-[var(--surface-muted)]",
                        ].join(" ")}
                      />
                      <p className={`mb-1 text-[10px] font-bold uppercase ${idx === 0 ? "text-[var(--text-brand)]" : "text-[var(--text-muted)]"}`}>{entry.time}</p>
                      <p className="text-sm font-bold text-[var(--text-primary)]">{entry.title}</p>
                      <p className="text-xs text-[var(--text-secondary)]">{entry.note}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-[var(--text-secondary)]">
                  {t(language, "medicines.cabinet.timelineEmpty")}
                </p>
              )}
            </SurfaceCard>

            <section className="rounded-[var(--radius-xl)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-6">
              <div className="mb-4 flex items-center gap-3">
                <Icon name="warning" className="text-[var(--text-brand)]" aria-hidden="true" />
                <h3 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]">{t(language, "medicines.cabinet.verifiedTitle")}</h3>
              </div>
              <p className="text-xs leading-5 text-[var(--text-secondary)]">
                {t(language, "medicines.cabinet.verifiedDescription")}
              </p>
              {stats.expired > 0 || stats.expiringSoon > 0 || stats.missingDosage > 0 ? (
                <ul className="mt-4 space-y-2 text-xs text-[var(--text-secondary)]">
                  {stats.expired > 0 ? <li>• {t(language, "medicines.cabinet.expiredCount", { count: formatLocaleNumber(language, stats.expired) })}</li> : null}
                  {stats.expiringSoon > 0 ? <li>• {t(language, "medicines.cabinet.expiringCount", { count: formatLocaleNumber(language, stats.expiringSoon) })}</li> : null}
                  {stats.missingDosage > 0 ? <li>• {t(language, "medicines.cabinet.missingDose", { count: formatLocaleNumber(language, stats.missingDosage) })}</li> : null}
                </ul>
              ) : null}
              <Button as="link" href="/medicines?tab=safety" variant="secondary" block className="mt-4 text-[10px] uppercase tracking-widest">
                {t(language, "medicines.cabinet.openSafety")}
              </Button>
            </section>

          </div>
        </section>
      </div>
    </MedicalConsentGate>
  );
}
