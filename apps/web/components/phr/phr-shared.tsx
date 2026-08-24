"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import AsyncSection, { type AsyncState } from "@/components/ui/async-section";
import type {
  PhrAllergyItem,
  PhrBodyMeasurement,
  PhrCompleteness,
  PhrCompletenessClass,
  PhrConditionItem,
  PhrInformationSource,
  PhrMedicationItem,
  PhrRecord,
  PhrVerificationStatus,
} from "@/lib/phr";
import { t, type UITranslationKey } from "@/lib/i18n/catalog";
import type { UILanguage } from "@/lib/ui-language";

export const COMPLETENESS_CLASS_LABEL_KEYS: Record<
  PhrCompletenessClass,
  UITranslationKey
> = {
  patient_demographics: "phr.completeness.class.patientDemographics",
  allergies: "phr.completeness.class.allergies",
  medications: "phr.completeness.class.medications",
  problems: "phr.completeness.class.problems",
  immunizations: "phr.completeness.class.immunizations",
  procedures: "phr.completeness.class.procedures",
  labs: "phr.completeness.class.labs",
};

export const SOURCE_LABEL_KEYS: Record<
  PhrInformationSource,
  UITranslationKey
> = {
  "self-declared": "phr.source.selfDeclared",
  ocr: "phr.source.ocr",
  imported: "phr.source.imported",
};

export const VERIFICATION_LABEL_KEYS: Record<
  PhrVerificationStatus,
  UITranslationKey
> = {
  unconfirmed: "phr.verification.unconfirmed",
  confirmed: "phr.verification.confirmed",
  provisional: "phr.verification.provisional",
  refuted: "phr.verification.refuted",
  "entered-in-error": "phr.verification.enteredInError",
};

export const PHR_TEXT_KEYS = {
  title: "phr.title",
  description: "phr.description",
  save: "phr.action.save",
  saving: "phr.action.saving",
  cancel: "phr.action.cancel",
  loading: "phr.loading",
  loadError: "phr.error.load",
  saveOk: "phr.notice.saved",
  saveError: "phr.error.save",
  profile: "phr.profile",
  allergies: "phr.allergies",
  conditions: "phr.conditions",
  medications: "phr.medications",
  add: "phr.action.add",
  remove: "phr.action.remove",
  fullName: "phr.field.fullName",
  dob: "phr.field.dob",
  gender: "phr.field.gender",
  bloodType: "phr.field.bloodType",
  height: "phr.field.height",
  weight: "phr.field.weight",
  phone: "phr.field.phone",
  address: "phr.field.address",
  emergencyName: "phr.field.emergencyName",
  emergencyPhone: "phr.field.emergencyPhone",
  insurance: "phr.field.insurance",
  notes: "phr.field.notes",
  allergyName: "phr.field.allergyName",
  reaction: "phr.field.reaction",
  severity: "phr.field.severity",
  conditionName: "phr.field.conditionName",
  status: "phr.field.status",
  diagnosedOn: "phr.field.diagnosedOn",
  medicationName: "phr.field.medicationName",
  dose: "phr.field.dose",
  frequency: "phr.field.frequency",
  startedOn: "phr.field.startedOn",
  current: "phr.field.current",
  itemNote: "phr.field.itemNote",
  updatedAt: "phr.updatedAt",
  unknown: "phr.unknown",
  disclaimer: "phr.disclaimer",
  source: "phr.source.label",
  verification: "phr.verification.label",
  consentTitle: "phr.consent.title",
  consentBody: "phr.consent.body",
  consentLink: "phr.consent.link",
  completenessTitle: "phr.completeness.title",
  completenessDescription: "phr.completeness.description",
  completenessLoading: "phr.completeness.loading",
  completenessError: "phr.completeness.error",
  completenessComplete: "phr.completeness.complete",
  completenessPresent: "phr.completeness.present",
  completenessMissing: "phr.completeness.missing",
  bodyBmi: "phr.body.bmi",
  bodyHistory: "phr.body.history",
  bodyHistoryEmpty: "phr.body.historyEmpty",
  bodyHistorySave: "phr.body.historySave",
  bodyHistorySaving: "phr.body.historySaving",
  noAllergies: "phr.empty.allergies",
  noConditions: "phr.empty.conditions",
  noMedications: "phr.empty.medications",
  allergyEmptyUnknown: "phr.allergy.empty.unknown",
  allergyEmptyNoneKnown: "phr.allergy.empty.noneKnown",
  allergyNoneKnownAction: "phr.allergy.action.noneKnown",
  pastMedications: "phr.medication.past",
  resumeMedication: "phr.medication.action.resume",
  mobileHistory: "phr.mobile.history",
  mobileProgress: "phr.mobile.progress",
  bodyTrend: "phr.body.trend",
  bodyTrendNeedMore: "phr.body.trendNeedMore",
  sectionNotFoundTitle: "phr.error.sectionNotFound.title",
  sectionNotFoundDesc: "phr.error.sectionNotFound.description",
  backToRecord: "phr.action.backToRecord",
  recordHome: "phr.action.recordHome",
} as const satisfies Record<string, UITranslationKey>;

export type PhrText = { [Key in keyof typeof PHR_TEXT_KEYS]: string };

export function getPhrText(language: UILanguage): PhrText {
  return Object.fromEntries(
    Object.entries(PHR_TEXT_KEYS).map(([name, key]) => [
      name,
      t(language, key as UITranslationKey),
    ]),
  ) as PhrText;
}

export const EMPTY_RECORD: PhrRecord = {
  full_name: "",
  date_of_birth: null,
  gender: "",
  blood_type: "",
  height_cm: null,
  weight_kg: null,
  phone: "",
  contact_email: "",
  address: "",
  emergency_contact_name: "",
  emergency_contact_phone: "",
  emergency_contact_relationship: "",
  emergency_contact_note: "",
  insurance_provider: "",
  insurance_id: "",
  insurance_expiry: null,
  allergy_status: "unknown",
  notes: "",
  allergies: [],
  conditions: [],
  medications: [],
  created_at: null,
  updated_at: null,
};

export function makeId() {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `phr_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function toInputDate(value?: string | null): string {
  if (!value) return "";
  return String(value).slice(0, 10);
}

export function parseInputNumber(value: string): number | null {
  const normalized = value.trim();
  if (!normalized) return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function normalizeRecord(record: PhrRecord): PhrRecord {
  const normalizedAllergies = (record.allergies ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    reaction: item.reaction ?? "",
    severity: item.severity ?? "unknown",
    note: item.note ?? "",
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  const normalizedConditions = (record.conditions ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    status: item.status ?? "unknown",
    diagnosed_on: item.diagnosed_on ?? null,
    note: item.note ?? "",
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  const normalizedMeds = (record.medications ?? []).map((item) => ({
    id: item.id || makeId(),
    name: item.name ?? "",
    dose: item.dose ?? "",
    frequency: item.frequency ?? "",
    started_on: item.started_on ?? null,
    is_current: item.is_current ?? true,
    note: item.note ?? "",
    information_source: item.information_source ?? null,
    verification_status: item.verification_status ?? null,
  }));
  return {
    ...EMPTY_RECORD,
    ...record,
    allergy_status:
      normalizedAllergies.length > 0
        ? "recorded"
        : record.allergy_status === "none_known"
          ? "none_known"
          : "unknown",
    allergies: normalizedAllergies,
    conditions: normalizedConditions,
    medications: normalizedMeds,
  };
}

export function ProvenanceBadges({
  source,
  verification,
  uiLanguage,
  sourceLabel,
  verificationLabel,
}: {
  source?: PhrInformationSource | null;
  verification?: PhrVerificationStatus | null;
  uiLanguage: UILanguage;
  sourceLabel: string;
  verificationLabel: string;
}) {
  if (!source && !verification) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {source ? (
        <Badge tone="brand">
          {sourceLabel}: {t(uiLanguage, SOURCE_LABEL_KEYS[source])}
        </Badge>
      ) : null}
      {verification ? (
        <Badge tone="neutral">
          {verificationLabel}:{" "}
          {t(uiLanguage, VERIFICATION_LABEL_KEYS[verification])}
        </Badge>
      ) : null}
    </div>
  );
}

export function BodyMassIndexTrend({
  measurements,
  title,
  needMore,
}: {
  measurements: PhrBodyMeasurement[];
  title: string;
  needMore: string;
}) {
  if (measurements.length < 2) {
    return (
      <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
        {needMore}
      </p>
    );
  }
  const chronological = [...measurements].reverse();
  const values = chronological.map((item) => item.bmi);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const points = chronological
    .map((item, index) => {
      const x = 18 + (index / (chronological.length - 1)) * 264;
      const y = 18 + ((max - item.bmi) / span) * 104;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const latest = chronological.at(-1)!;

  return (
    <figure className="mt-4 rounded-[var(--radius-lg)] border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-4">
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-sm font-semibold text-[var(--text-primary)]">
        <span>{title}</span>
        <Badge tone="brand">BMI {latest.bmi}</Badge>
      </figcaption>
      <svg
        className="mt-3 h-36 w-full"
        viewBox="0 0 300 140"
        role="img"
        aria-label={title}
      >
        <line
          x1="18"
          x2="282"
          y1="122"
          y2="122"
          stroke="var(--shell-border)"
          strokeWidth="1"
        />
        <polyline
          points={points}
          fill="none"
          stroke="var(--brand-500)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {chronological.map((item, index) => {
          const [x, y] = points.split(" ")[index].split(",");
          return (
            <circle
              key={item.observed_on}
              cx={x}
              cy={y}
              r="4"
              fill="var(--brand-500)"
            >
              <title>{`${item.observed_on}: BMI ${item.bmi}`}</title>
            </circle>
          );
        })}
      </svg>
      <div className="flex justify-between text-xs text-[var(--text-secondary)]">
        <span>{chronological[0].observed_on}</span>
        <span>{latest.observed_on}</span>
      </div>
    </figure>
  );
}

export function CompletenessMeter({
  state,
  text,
  uiLanguage,
}: {
  state: AsyncState<PhrCompleteness>;
  text: PhrText;
  uiLanguage: UILanguage;
}) {
  return (
    <section className={phrPanelClass}>
      <p className="text-sm font-semibold text-[var(--text-primary)]">
        {text.completenessTitle}
      </p>
      <p className="mt-1 text-[13px] leading-6 text-[var(--text-secondary)]">
        {text.completenessDescription}
      </p>
      <div className="mt-4">
        <AsyncSection<PhrCompleteness>
          state={state}
          loadingLabel={text.completenessLoading}
        >
          {(data) => {
            const percent = Math.round(data.score * 100);
            return (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div
                    className="h-2.5 flex-1 overflow-hidden rounded-full bg-[var(--surface-muted)]"
                    role="progressbar"
                    aria-valuenow={percent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={text.completenessTitle}
                  >
                    <div
                      className="h-full rounded-full bg-[var(--brand-500)] transition-[width]"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                  <span className="text-sm font-bold tabular-nums text-[var(--text-primary)]">
                    {percent}%
                  </span>
                </div>
                {data.present.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {text.completenessPresent}:
                    </span>
                    {data.present.map((cls) => (
                      <Badge key={cls} tone="ok">
                        {t(uiLanguage, COMPLETENESS_CLASS_LABEL_KEYS[cls])}
                      </Badge>
                    ))}
                  </div>
                ) : null}
                {data.missing.length > 0 ? (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">
                      {text.completenessMissing}:
                    </span>
                    {data.missing.map((cls) => (
                      <Badge key={cls} tone="warn">
                        {t(uiLanguage, COMPLETENESS_CLASS_LABEL_KEYS[cls])}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-[var(--status-ok-text)]">
                    {text.completenessComplete}
                  </p>
                )}
              </div>
            );
          }}
        </AsyncSection>
      </div>
    </section>
  );
}

export const phrPanelClass =
  "rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-5 sm:p-6";
export const phrColumnClass =
  "rounded-[14px] border border-t-[#2A3950] border-[color:var(--shell-border)] bg-[var(--surface-panel)] p-4";
export const phrItemClass =
  "rounded-lg border border-[color:var(--shell-border)] bg-[var(--surface-muted)] p-3";

export type PhrCanonicalSection =
  | "demographics"
  | "identity"
  | "body"
  | "measurements"
  | "contact"
  | "allergies"
  | "conditions"
  | "medications"
  | "documents"
  | "ocr"
  | "status"
  | "export"
  | "sharing"
  | "emergency-card"
  | "reminders";

export const PHR_CANONICAL_SECTIONS = new Set<PhrCanonicalSection>([
  "demographics",
  "identity",
  "body",
  "measurements",
  "contact",
  "allergies",
  "conditions",
  "medications",
  "documents",
  "ocr",
  "status",
  "export",
  "sharing",
  "emergency-card",
  "reminders",
]);

export function normalizeSectionSlug(
  slug: string | null | undefined,
): PhrCanonicalSection | null {
  if (!slug) return null;
  const candidate = slug.toLowerCase().trim();
  if (PHR_CANONICAL_SECTIONS.has(candidate as PhrCanonicalSection)) {
    return candidate as PhrCanonicalSection;
  }
  return null;
}
